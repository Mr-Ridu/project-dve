"""Staff dashboard views (Phase 7).

Rules enforced here (approved plan, Phase 1 §5/§6/§11):
- Staff gate on every view: authenticated + active + is_staff. Everyone
  else is denied — anonymous users get a login redirect, non-staff users a
  hard 403 (PermissionDenied), never a soft "please log in" leak.
- No self-approval paths: any mutating action targeting the signed-in staff
  member themselves is refused.
- All mutations are POST-only and CSRF-protected; every one is audited with
  actor + direct-socket IP.
"""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from accounts.models import AuditEvent
from tutorials.models import Category, Tutorial, TutorialAccess, TutorialProgress

from core.throttle import rate_limit
from .forms import CategoryForm, TutorialForm
from tutorials.providers import bunny_upload

User = get_user_model()


def _client_ip(request):
    return request.META.get("REMOTE_ADDR") or None


def staff_required(view):
    @login_required
    def wrapped(request, *args, **kwargs):
        user = request.user
        if not (user.is_active and user.is_staff):
            raise PermissionDenied("Staff access required.")
        return view(request, *args, **kwargs)

    return wrapped


def _audit(request, action, target_user=None, detail=""):
    AuditEvent.objects.create(
        actor=request.user, target_user=target_user, action=action,
        detail=detail[:255], ip_address=_client_ip(request),
    )


def _back(request, fallback_name, **kwargs):
    """Return to the page the action was submitted from (validated), else the fallback.

    The same grant/revoke endpoints are used from the account page and from the
    tutorial access page; `next` keeps the operator where they were working.
    """
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(nxt)
    return redirect(fallback_name, **kwargs)


def _block_self(request, target_user):
    """No self-approval paths: refuse acting on your own account."""
    if target_user.pk == request.user.pk:
        messages.error(request, "You cannot perform approval actions on your own account.")
        return redirect("dashboard:user_detail", pk=target_user.pk)
    return None


# --- Overview ---------------------------------------------------------------

@staff_required
def overview(request):
    counts = {
        "pending": User.objects.filter(approval_status=User.ApprovalStatus.PENDING).count(),
        "approved": User.objects.filter(approval_status=User.ApprovalStatus.APPROVED).count(),
        "rejected": User.objects.filter(approval_status=User.ApprovalStatus.REJECTED).count(),
        "tutorials_published": Tutorial.objects.filter(is_published=True).count(),
        "tutorials_draft": Tutorial.objects.filter(is_published=False).count(),
    }
    pending_queue = User.objects.filter(
        approval_status=User.ApprovalStatus.PENDING
    ).order_by("-date_joined")
    recent_audit = AuditEvent.objects.select_related("actor", "target_user")[:15]
    return render(request, "dashboard/overview.html", {
        "counts": counts,
        "pending_queue": pending_queue,
        "recent_audit": recent_audit,
    })


# --- User management --------------------------------------------------------

@staff_required
def user_list(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    qs = User.objects.order_by("-date_joined")
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))
    if status in {v for v, _ in User.ApprovalStatus.choices}:
        qs = qs.filter(approval_status=status)
    return render(request, "dashboard/user_list.html", {
        "users": qs[:200], "q": q, "status": status,
        "status_choices": User.ApprovalStatus.choices,
    })


@staff_required
def user_detail(request, pk):
    user = get_object_or_404(User, pk=pk)
    grants = TutorialAccess.objects.filter(user=user).select_related("tutorial")
    progress = TutorialProgress.objects.filter(user=user).select_related("tutorial")
    tutorials = Tutorial.objects.filter(is_published=True)
    return render(request, "dashboard/user_detail.html", {
        "target_user": user,
        "grants": {g.tutorial_id: g for g in grants},
        "tutorials": tutorials,
        "progress": progress,
    })


@require_http_methods(["POST"])
@staff_required
def user_approval(request, pk, action):
    target_user = get_object_or_404(User, pk=pk)
    blocked = _block_self(request, target_user)
    if blocked:
        return blocked

    if action == "approve":
        target_user.approval_status = User.ApprovalStatus.APPROVED
        if not target_user.approved_at:
            target_user.approved_at = timezone.now()
        target_user.approved_by = request.user
        audit_action = AuditEvent.Action.USER_APPROVED
    elif action == "reject":
        target_user.approval_status = User.ApprovalStatus.REJECTED
        audit_action = AuditEvent.Action.USER_REJECTED
    elif action == "reset_pending":
        target_user.approval_status = User.ApprovalStatus.PENDING
        audit_action = AuditEvent.Action.USER_RESET_PENDING
    else:
        raise PermissionDenied("Unknown approval action.")

    target_user.save(update_fields=["approval_status", "approved_at", "approved_by"])
    _audit(request, audit_action, target_user=target_user)
    messages.success(request, f"{target_user.username}: {target_user.get_approval_status_display()}.")
    return redirect("dashboard:user_detail", pk=pk)


@require_http_methods(["POST"])
@staff_required
def user_access_flag(request, pk):
    """Toggles the admin-granted access_all_tutorials bypass (audited)."""
    target_user = get_object_or_404(User, pk=pk)
    blocked = _block_self(request, target_user)
    if blocked:
        return blocked
    target_user.access_all_tutorials = not target_user.access_all_tutorials
    target_user.save(update_fields=["access_all_tutorials"])
    _audit(
        request, AuditEvent.Action.ACCESS_FLAG_SET, target_user=target_user,
        detail=f"access_all_tutorials={target_user.access_all_tutorials}",
    )
    messages.success(
        request,
        f"{target_user.username}: access_all_tutorials={target_user.access_all_tutorials}.",
    )
    return redirect("dashboard:user_detail", pk=pk)


@require_http_methods(["POST"])
@staff_required
def grant_access(request, pk, tutorial_pk):
    target_user = get_object_or_404(User, pk=pk)
    tutorial = get_object_or_404(Tutorial, pk=tutorial_pk)
    TutorialAccess.objects.get_or_create(
        user=target_user, tutorial=tutorial,
        defaults={"granted_by": request.user},
    )
    _audit(request, AuditEvent.Action.ACCESS_GRANTED, target_user=target_user,
           detail=f"tutorial={tutorial.slug}")
    messages.success(request, f"Granted {tutorial.title} to {target_user.username}.")
    return _back(request, "dashboard:user_detail", pk=pk)


@require_http_methods(["POST"])
@staff_required
def revoke_access(request, pk, tutorial_pk):
    target_user = get_object_or_404(User, pk=pk)
    tutorial = get_object_or_404(Tutorial, pk=tutorial_pk)
    deleted, _ = TutorialAccess.objects.filter(user=target_user, tutorial=tutorial).delete()
    if deleted:
        _audit(request, AuditEvent.Action.ACCESS_REVOKED, target_user=target_user,
               detail=f"tutorial={tutorial.slug}")
        messages.success(request, f"Revoked {tutorial.title} from {target_user.username}.")
    return _back(request, "dashboard:user_detail", pk=pk)


# --- Tutorial CRUD ----------------------------------------------------------

@staff_required
def tutorial_list(request):
    tutorials = Tutorial.objects.annotate(
        grant_count=Count("grants", distinct=True),
        completed_count=Count(
            "progress_records", filter=Q(progress_records__completed=True), distinct=True
        ),
    ).select_related("category")
    return render(request, "dashboard/tutorial_list.html", {"tutorials": tutorials})


@rate_limit("upload")
@staff_required
def tutorial_edit(request, pk=None):
    if pk:
        tutorial = get_object_or_404(Tutorial, pk=pk)
    else:
        tutorial = None
    if request.method == "POST":
        form = TutorialForm(request.POST, request.FILES, instance=tutorial)
        if form.is_valid():
            saved = form.save(commit=False)
            uploaded = form.cleaned_data.get("video_file")
            if uploaded:
                # Upload first, save second: a failed upload leaves the tutorial
                # exactly as it was, with an explanation on the form.
                try:
                    guid = bunny_upload.upload_file(uploaded, title=saved.title)
                except bunny_upload.UploadError as exc:
                    form.add_error("video_file", f"{exc} (Choose the file again to retry.)")
                    return render(request, "dashboard/tutorial_edit.html", {
                        "form": form, "tutorial": tutorial,
                    })
                saved.video_provider = Tutorial.VideoProvider.BUNNY
                saved.video_ref = guid
                messages.success(
                    request,
                    f"Uploaded the video to Bunny Stream and attached it to “{saved.title}”.",
                )
            saved.save()
            _audit(
                request,
                AuditEvent.Action.TUTORIAL_UPDATED,
                detail=f"tutorial={saved.slug} (id={saved.pk})" if pk else f"tutorial={saved.slug} (id={saved.pk}) created",
            )
            messages.success(request, f"Saved “{saved.title}”.")
            return redirect("dashboard:tutorial_list")
    else:
        form = TutorialForm(instance=tutorial)
    return render(request, "dashboard/tutorial_edit.html", {
        "form": form, "tutorial": tutorial,
    })


@staff_required
def tutorial_access(request, pk):
    """Give existing accounts access to ONE tutorial, from the tutorial's side.

    Mirrors the per-tutorial table on the account page: the account page answers
    "what can this person watch", this page answers "who can watch this video".
    Grants are prepared for drafts too, but only published + approved accounts
    can actually play (tutorials/access.py is the only authority).
    """
    tutorial = get_object_or_404(Tutorial, pk=pk)
    accounts = User.objects.order_by("username")
    q = (request.GET.get("q") or "").strip()
    if q:
        accounts = accounts.filter(Q(username__icontains=q) | Q(email__icontains=q))
    grants = set(
        TutorialAccess.objects.filter(tutorial=tutorial).values_list("user_id", flat=True)
    )
    return render(request, "dashboard/tutorial_access.html", {
        "tutorial": tutorial,
        "accounts": accounts[:200],
        "granted": grants,
        "grant_count": len(grants),
        "q": q,
    })


@require_http_methods(["POST"])
@staff_required
def tutorial_delete(request, pk):
    tutorial = get_object_or_404(Tutorial, pk=pk)
    title, slug = tutorial.title, tutorial.slug
    tutorial.delete()
    _audit(request, AuditEvent.Action.TUTORIAL_DELETED, detail=f"tutorial={slug}")
    messages.success(request, f"Deleted “{title}”.")
    return redirect("dashboard:tutorial_list")


# --- Categories -------------------------------------------------------------

@staff_required
def category_list(request):
    categories = Category.objects.annotate(tutorial_count=Count("tutorials"))
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Added category “{form.instance.name}”.")
            return redirect("dashboard:category_list")
    else:
        form = CategoryForm()
    return render(request, "dashboard/category_list.html", {
        "categories": categories, "form": form,
    })


@require_http_methods(["POST"])
@staff_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    name = category.name
    category.delete()
    messages.success(request, f"Deleted category “{name}”.")
    return redirect("dashboard:category_list")
