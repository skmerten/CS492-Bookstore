from django.contrib import admin
from .models import Supplier, SupplierOrder, SupplierOrderItem, CustomerRequest

admin.site.register(Supplier)
admin.site.register(SupplierOrder)
admin.site.register(SupplierOrderItem)
admin.site.register(CustomerRequest)