from django.db import models
from django.conf import settings
from inventory.models import Book
from sales.models import Customer

# Book supplier
class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name

# an order for books from a supplier
class SupplierOrder(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    order_date = models.DateTimeField(auto_now_add=True)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"Supplier Order #{self.id}"

# a line item on the supply order (1 of X book or 10 of Y book)
class SupplierOrderItem(models.Model):
    supplier_order = models.ForeignKey(SupplierOrder, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.PROTECT)
    quantity_ordered = models.PositiveIntegerField(default=1)
    cost_each = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity_ordered} x {self.book.title}"

# customer request for a new book which could turn into a supply order
class CustomerRequest(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.SET_NULL, null=True, blank=True)
    requested_title = models.CharField(max_length=200)
    requested_author = models.CharField(max_length=200, blank=True)
    request_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.requested_title} - {self.customer.full_name}"