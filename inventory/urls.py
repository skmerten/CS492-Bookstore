from django.urls import path
from . import views


urlpatterns = [
    path("", views.books, name="books"),   
    path("manage/add/", views.add_book, name="add_book"),
    path("manage/edit/<int:book_id>/", views.edit_book, name="edit_book"),
    path("manage/delete/<int:book_id>/", views.delete_book, name="delete_book"),
]