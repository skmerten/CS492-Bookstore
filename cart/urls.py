from django.urls import path
from . import views

#This lets us refer to cart URLs with names such as "cart:detail".
app_name = "cart"

#URL routes for the cart app.
urlpatterns = [
    path("", views.cart_detail, name="detail"),
    path("add/<int:book_id>/", views.add_to_cart, name="add"),
    path("remove/<int:book_id>/", views.remove_from_cart, name="remove"),
    path("update/<int:book_id>/", views.update_cart, name="update"),
]