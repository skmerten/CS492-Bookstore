from django.contrib import admin
from .models import Supplier, SupplierOrder, SupplierOrderItem, CustomerRequest


class SupplierOrderItemInline(admin.TabularInline):
    model = SupplierOrderItem
    extra = 0


@admin.register(SupplierOrder)
class SupplierOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "supplier", "order_date", "status", "total_cost", "user")
    list_filter = ("status", "supplier")
    readonly_fields = ("inventory_updated",)
    inlines = [SupplierOrderItemInline]


admin.site.register(Supplier)
admin.site.register(CustomerRequest)
