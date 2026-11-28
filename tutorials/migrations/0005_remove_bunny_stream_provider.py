from django.db import migrations, models


def drop_bunny_rows(apps, schema_editor):
    """Bunny playback is gone: keep the tutorial, drop the unusable reference."""
    Tutorial = apps.get_model("tutorials", "Tutorial")
    Tutorial.objects.filter(video_provider="bunny").update(
        video_provider="none", video_ref=""
    )


class Migration(migrations.Migration):

    dependencies = [
        ("tutorials", "0004_alter_tutorial_video_provider_and_more"),
    ]

    operations = [
        migrations.RunPython(drop_bunny_rows, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="tutorial",
            name="video_provider",
            field=models.CharField(
                choices=[
                    ("none", "No video yet"),
                    ("youtube", "YouTube (unlisted, privacy-enhanced embed)"),
                    ("url", "Plain URL (dev/preview only)"),
                ],
                default="none",
                help_text="YouTube plays an unlisted video through the privacy-enhanced embed — the video id is visible, so it suits low-budget content only. Plain URL is for local preview only — it hands the stored URL to the browser unsigned.",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="tutorial",
            name="video_ref",
            field=models.CharField(
                blank=True,
                help_text="YouTube: the 11-character video id or any watch/youtu.be/embed link. Plain URL: the full file or manifest URL.",
                max_length=500,
            ),
        ),
    ]
