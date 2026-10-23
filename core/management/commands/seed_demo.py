"""Create a visible demo tutorial so the catalog is not empty.

A fresh install has zero tutorials, which reads as "the frontend is broken"
even though the library, the player and the permission flow all work. This
command creates one published tutorial (and optionally grants it) using the
plain-URL provider, which is for development/preview only — real playback is
signed by Bunny once the library id and security key are configured.

Refuses to run with DEBUG=False so demo rows cannot be seeded into production.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from tutorials.models import Category, Tutorial, TutorialAccess

# Public sample clip (Google's sample bucket), used only by this dev helper.
SAMPLE_VIDEO_URL = (
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
)


class Command(BaseCommand):
    help = "Create a published demo tutorial (development only) and optionally grant it."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            help="Grant access to this account; it is approved if it was still pending.",
        )
        parser.add_argument("--video-url", default=SAMPLE_VIDEO_URL, help="URL for the sample video.")
        parser.add_argument(
            "--slug", default="welcome-tour", help="Tutorial slug (default: welcome-tour)."
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo is a development helper and refuses to run with DEBUG=False."
            )

        category, _ = Category.objects.get_or_create(
            slug="getting-started", defaults={"name": "Getting started", "ordering": 0}
        )
        tutorial, created = Tutorial.objects.get_or_create(
            slug=options["slug"],
            defaults={"title": "Welcome tour: how tutorial playback works"},
        )
        tutorial.title = tutorial.title or "Welcome tour: how tutorial playback works"
        tutorial.description = (
            "A short sample used to verify that the catalog, the access check and "
            "the player are wired correctly. Replace it with real content."
        )
        tutorial.category = category
        tutorial.duration_seconds = 15
        tutorial.estimated_minutes = 1
        tutorial.video_provider = Tutorial.VideoProvider.URL
        tutorial.video_ref = options["video_url"]
        tutorial.is_published = True
        tutorial.save()

        self.stdout.write(
            f"{'Created' if created else 'Updated'} tutorial /tutorials/{tutorial.slug}/"
        )

        username = options.get("username")
        if username:
            user = User.objects.filter(username=username).first()
            if user is None:
                raise CommandError(f"No account named {username!r}.")
            if user.approval_status != User.ApprovalStatus.APPROVED:
                user.approval_status = User.ApprovalStatus.APPROVED
                user.approved_at = timezone.now()
                user.save(update_fields=["approval_status", "approved_at"])
                self.stdout.write(f"Approved {username} (it was still pending).")
            _, granted = TutorialAccess.objects.get_or_create(
                user=user, tutorial=tutorial, defaults={"granted_by": None}
            )
            self.stdout.write(
                f"{'Granted' if granted else 'Already granted'} {tutorial.slug} to {username}."
            )
        else:
            self.stdout.write(
                "No --username given: grant it in /dashboard/users/ or add "
                "'access_all_tutorials' to your account."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Open /tutorials/ while signed in. Playback uses the plain-URL "
                "provider; set BUNNY_STREAM_LIBRARY_ID and BUNNY_STREAM_SECURITY_KEY "
                "for real signed playback."
            )
        )
