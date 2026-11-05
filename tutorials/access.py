"""The one access predicate.

Every protected request — catalog page, tutorial page, playback token — is
authorized here and nowhere else (Phase 1 §6 rule):

    authenticated AND is_active AND approval_status == approved
    AND tutorial.is_published
    AND (whole library open to approved accounts OR
         user.access_all_tutorials OR a grant row exists)

The library defaults to *open to approved accounts*: approving a person is the
only manual step. The stricter per-tutorial model is still fully implemented
and can be switched back on with `TUTORIALS_REQUIRE_GRANTS=1`; the dashboard
grant tools and the `access_all_tutorials` flag keep working in either mode.

Templates may *hide* links this rule would deny, but hiding is cosmetic:
the backend re-checks on every request. Revoking a grant row denies the very
next request in grant mode. Progress/watched state is never proof of
authorization.
"""
from django.conf import settings
from django.db.models import BooleanField, Exists, OuterRef, Value

from .models import TutorialAccess


def is_user_approved(user):
    """Approved account = active + approval_status approved."""
    from accounts.models import User

    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and user.approval_status == User.ApprovalStatus.APPROVED
    )


def library_open_to_approved():
    """True by default: approved accounts see the whole published library.

    Set TUTORIALS_REQUIRE_GRANTS=1 to require an explicit grant per tutorial.
    """
    return not getattr(settings, "TUTORIALS_REQUIRE_GRANTS", False)


def has_grant(user, tutorial):
    """Does an explicit TutorialAccess row exist for this (user, tutorial)?"""
    if not (user and user.is_authenticated) or tutorial is None or tutorial.pk is None:
        return False
    return TutorialAccess.objects.filter(user=user, tutorial=tutorial).exists()


def can_access(user, tutorial):
    """The full predicate. Called for page views AND playback authorization."""
    if not is_user_approved(user):
        return False
    if tutorial is None or not tutorial.is_published:
        return False
    if library_open_to_approved():
        return True
    return bool(getattr(user, "access_all_tutorials", False)) or has_grant(user, tutorial)


def annotate_queryset(tutorials_qs, user):
    """Attach a per-row access flag for listing pages (cosmetic only).

    Anonymous users get a constant False annotation — filtering on the FK
    with an AnonymousUser lazy proxy would blow up in get_prep_value.
    """
    if not is_user_approved(user):
        return tutorials_qs.annotate(
            user_has_access=Value(False, output_field=BooleanField())
        )
    if library_open_to_approved() or can_access_all(user):
        return tutorials_qs.annotate(
            user_has_access=Value(True, output_field=BooleanField())
        )
    grants = TutorialAccess.objects.filter(user=user.pk, tutorial=OuterRef("pk"))
    return tutorials_qs.annotate(user_has_access=Exists(grants))


def can_access_all(user):
    """Admin-granted all-library flag (explicit; default off)."""
    return bool(
        is_user_approved(user) and getattr(user, "access_all_tutorials", False)
    )
