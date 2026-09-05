from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Book
from .forms import BookForm
from django.db.models import Q


def books(request):
    query = request.GET.get("search", "")
    books = Book.objects.all()
    if query:
        books = books.filter(Q(title__icontains=query) | Q(author__icontains=query) | Q(isbn__icontains=query))
    return render(request, "inventory/books.html", {"books": books,"query": query})


@login_required
def add_book(request):
    if request.method == "POST":
        form = BookForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("books")
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
            return redirect("books")
    else:
        form = BookForm(instance=book)

    return render(request, "inventory/book_form.html", {"form": form})


@login_required
def delete_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)

    if request.method == "POST":
        book.delete()

    return redirect("books")
