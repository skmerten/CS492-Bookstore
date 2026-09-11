from decimal import Decimal
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.contrib import messages

from inventory.models import Book

# Shows the customer's shopping cart page.
def cart_detail(request):
    #Get the session cart. Cart is empty if the visitor has not added anything.
    cart = request.session.get("cart", {})

    #Get every Book whose ID is stored in the cart.
    books = Book.objects.filter(id__in=cart.keys())

    #Create a list containing each book and the quantity.
    items = []

    #Start subtotal at zero.
    subtotal = Decimal("0.00")

    for book in books:
        #Get how many copies of book are in the cart.
        quantity = cart[str(book.id)]

        #Use zero when a book does not yet have a price.
        price = book.price or Decimal("0.00")

        #Price multiplied by quantity gives this book's total.
        line_total = price * quantity

        #Save the information needed by the HTML page.
        items.append({
            "book": book,
            "quantity": quantity,
            "line_total": line_total,
        })

        #Add book's total to the full cart subtotal.
        subtotal += line_total

    #Send the cart items and subtotal to HTML page.    
    return render (request, 
                   "cart/detail.html",
                     {"items":items, "subtotal": subtotal},
    )

#This function only accepts form submissions, not regular browser visits
@require_POST
def add_to_cart(request, book_id):
    #Find the selected book using the ID in the URL.
    book = get_object_or_404(Book, id=book_id)

    #Get the visitor's current cart or start an empty one.
    cart = request.session.get("cart", {})
    book_key = str(book.id)

    try:
        #Get the quantity entered on the inventory page.
        quantity_to_add = int(request.POST.get("quantity", 1))
    except(TypeError, ValueError):
        #Use zero if an invalid value, such as letters was entered.
        quantity_to_add = 0

    #Find how many copies are already in the cart.
    current_quantity = cart.get(book_key, 0)

    #Warn customer when every available copy is already in their cart.
    if current_quantity >= book.quantity:
        messages.warning(
            request, f"Sorry, no more copies of {book.title} are currently avilable."
        )

    #IF statementto add chosen amount without exceeding available inventory.
    if quantity_to_add > 0:
        cart[book_key] = min(
            current_quantity + quantity_to_add,
            book.quantity,
        )

        request.session["cart"] = cart
        messages.success(request, f"{book.title} was added to your cart.")
    else:
        messages.error(request, "Please enter a quantity greater than zero.")
    return redirect("books")

#This function only accepts form submissions.
@require_POST
def remove_from_cart(request, book_id):
    #Get visitor's current cart.
    cart = request.session.get("cart", {})

    #Remove book if present in cart.
    cart.pop(str(book_id), None)

    #Save the updated cart in the session.
    request.session["cart"] = cart

    #Return the customer to the updated cart page.
    return redirect("cart:detail")

#Function to update book quantity in a cart.
@require_POST
def update_cart(request, book_id):
    #Find the book being updated.
    book = get_object_or_404(Book, id=book_id)

    cart = request.session.get("cart", {})
    book_key = str(book.id)

    try:
        #Get the quantity typed by the customer.
        request_quantity = int(request.POST.get("quantity", 0))

    except (TypeError, ValueError):
        #Treat invalid entries, like letters as zero.
        request_quantity = 0

    if request_quantity <= 0:
        cart.pop(book_key, None)

    else:
        cart[book_key] = min(request_quantity, book.quantity)

    request.session["cart"] = cart
    return redirect("cart:detail")

