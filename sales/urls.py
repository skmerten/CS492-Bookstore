from django.urls import path
from . import views

#URL routes for the sales app.
app_name = "sales"

urlpatterns = [
    #Displays the cashier cash-payment page.
    path("cash-payment/", views.cash_payment, name="cash_payment"),
    path("checkout/", views.checkout, name="checkout"),
    path("confirmation/<int:sale_id>/",views.confirmation,name="confirmation"),
]
