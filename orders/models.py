from django.conf import settings
from django.db import models, transaction
from django.db.models import F

from inventory.models import Book
from sales.models import Customer


# Book supplier / vendor
class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name


# An order for books from a supplier.
class SupplierOrder(models.Model):
    class Status(models.TextChoices):
        ORDERED = "Ordered", "Ordered"
        CANCELLED = "Cancelled", "Cancelled"
        RECEIVED = "Received", "Received"

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    order_date = models.DateTimeField(auto_now_add=True)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ORDERED,
    )

    # Prevents a received PO from adding the same inventory more than once.
    inventory_updated = models.BooleanField(default=False, editable=False)

    def __str__(self):
        return f"Supplier Order #{self.id}"

    def mark_received(self):
        """Receive this PO and add every line item to inventory exactly once."""
        with transaction.atomic():
            # Lock the order row so two receive requests cannot process together.
            order = SupplierOrder.objects.select_for_update().get(pk=self.pk)

            if order.status == self.Status.CANCELLED:
                raise ValueError("A cancelled purchase order cannot be received.")

            if order.inventory_updated:
                # It was already received. Return without touching inventory again.
                self.refresh_from_db()
                return False

            for item in order.items.select_related("book"):
                Book.objects.filter(pk=item.book_id).update(
                    quantity=F("quantity") + item.quantity_ordered
                )

            order.status = self.Status.RECEIVED
            order.inventory_updated = True
            order.save(update_fields=["status", "inventory_updated"])

        self.refresh_from_db()
        return True

    def cancel(self):
        """Cancel an order that has not already been received."""
        if self.status == self.Status.RECEIVED or self.inventory_updated:
            raise ValueError("A received purchase order cannot be cancelled.")

        self.status = self.Status.CANCELLED
        self.save(update_fields=["status"])


# A line item on the supply order (for example, 10 copies of one book).
class SupplierOrderItem(models.Model):
    supplier_order = models.ForeignKey(
        SupplierOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )
    book = models.ForeignKey(Book, on_delete=models.PROTECT)
    quantity_ordered = models.PositiveIntegerField(default=1)
    cost_each = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity_ordered} x {self.book.title}"

    @property
    def line_total(self):
        return self.quantity_ordered * self.cost_each


# Customer request for a new book which could turn into a supply order.
class CustomerRequest(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.SET_NULL, null=True, blank=True)
    requested_title = models.CharField(max_length=200)
    requested_author = models.CharField(max_length=200, blank=True)
    request_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.requested_title} - {self.customer.full_name}"
