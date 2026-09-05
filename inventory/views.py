from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Book
from .forms import BookForm



def books(request):
    books = Book.objects.all()

    return render(request,"inventory/books.html",{"books": books})

@login_required
def manage_inventory(request):
    books = Book.objects.all()
    return render(
        request,
        "inventory/manage_inventory.html",
        {"books": books}
    )

@login_required
def add_book(request):
    if request.method == "POST":
        form = BookForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("manage_inventory")
    else:
        form = BookForm()

    return render(request, "inventory/book_form.html", {"form": form})


@login_required
def edit_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)

    if request.method == "POST":
        form = BookForm(request.POST, instance=book)

        if form.is_valid():
            form.save()
            return redirect("manage_inventory")
    else:
        form = BookForm(instance=book)

    return render(request, "inventory/book_form.html", {"form": form})


@login_required
def delete_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)

    if request.method == "POST":
        book.delete()

    return redirect("inventory/manage_inventory")