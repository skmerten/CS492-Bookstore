from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path(
        "customer-request/",
        views.create_customer_request,
        name="create_customer_request",
    ),
    path(
        "customer-requests/",
        views.customer_request_log,
        name="customer_request_log",
    ),
    path("vendors/", views.supplier_list, name="supplier_list"),
    path("vendors/new/", views.create_supplier, name="create_supplier"),
    path(
        "purchase-orders/",
        views.supplier_order_list,
        name="supplier_order_list",
    ),
    path(
        "purchase-orders/new/",
        views.create_supplier_order,
        name="create_supplier_order",
    ),
    path(
        "purchase-orders/<int:order_id>/",
        views.supplier_order_detail,
        name="supplier_order_detail",
    ),
    path(
        "purchase-orders/<int:order_id>/receive/",
        views.receive_supplier_order,
        name="receive_supplier_order",
    ),
    path(
        "purchase-orders/<int:order_id>/cancel/",
        views.cancel_supplier_order,
        name="cancel_supplier_order",
    ),
]
