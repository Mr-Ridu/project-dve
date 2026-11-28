"""Open the library: new accounts are approved on creation.

Watching a tutorial no longer needs a staff approval step or a per-tutorial
grant, so the default approval status flips to approved. Accounts that were
already sitting in the pending queue are approved here as well, otherwise they
would keep hitting the "awaiting approval" page for no reason.
"""
from django.db import migrations, models


def approve_pending(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(approval_status="pending").update(approval_status="approved")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_auditevent_action"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="approval_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending approval"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                default="approved",
                help_text="New accounts can watch tutorials right away. Set to Pending to "
                "hold an account for review, or Rejected to close it.",
                max_length=10,
            ),
        ),
        migrations.RunPython(approve_pending, migrations.RunPython.noop),
    ]
