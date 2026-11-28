from django.db import migrations

OLD_SLUG = "presentatin"
NEW_SLUG = "presentation"


def fix_presentation_slug(apps, schema_editor):
    """Spell the Presentation category slug correctly, merging if needed.

    The dashboard's Presentation category was saved as "presentatin"; the
    landing page's presentations band filters on this slug, so it has to match.
    """
    Category = apps.get_model("tutorials", "Category")
    target = Category.objects.filter(slug=NEW_SLUG).first()
    for category in Category.objects.filter(slug=OLD_SLUG):
        if target is None:
            category.slug = NEW_SLUG
            category.save(update_fields=["slug"])
            target = category
            continue
        category.tutorials.update(category=target)
        category.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tutorials", "0005_remove_bunny_stream_provider"),
    ]

    operations = [
        migrations.RunPython(fix_presentation_slug, migrations.RunPython.noop),
    ]
