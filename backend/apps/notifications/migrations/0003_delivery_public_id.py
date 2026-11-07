"""Give deliveries a public UUID (the admin API addresses them by it).

Three steps because a unique UUID column can't be added to existing rows in one go: Django would
give every row the same default value.
"""

import uuid

from django.db import migrations, models


def fill(apps, schema_editor):
    Delivery = apps.get_model("notifications", "Delivery")
    for delivery in Delivery.objects.filter(public_id__isnull=True).only("pk"):
        delivery.public_id = uuid.uuid4()
        delivery.save(update_fields=["public_id"])


class Migration(migrations.Migration):
    dependencies = [("notifications", "0002_notification_feedback")]

    operations = [
        migrations.AddField("delivery", "public_id", models.UUIDField(null=True, editable=False)),
        migrations.RunPython(fill, migrations.RunPython.noop),
        migrations.AlterField(
            "delivery",
            "public_id",
            models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
