# Adds controlled supplier-order statuses and one-time inventory receipt tracking.

from django.db import migrations, models
import django.db.models.deletion


def set_existing_orders_to_ordered(apps, schema_editor):
    SupplierOrder = apps.get_model("orders", "SupplierOrder")
    SupplierOrder.objects.filter(status="").update(status="Ordered")


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="supplierorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("Ordered", "Ordered"),
                    ("Cancelled", "Cancelled"),
                    ("Received", "Received"),
                ],
                default="Ordered",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="supplierorder",
            name="inventory_updated",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AlterField(
            model_name="supplierorderitem",
            name="supplier_order",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                to="orders.supplierorder",
            ),
        ),
        migrations.RunPython(
            set_existing_orders_to_ordered,
            migrations.RunPython.noop,
        ),
    ]
