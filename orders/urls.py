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
]