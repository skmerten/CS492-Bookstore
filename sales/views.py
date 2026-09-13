from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from inventory.models import Book
from .models import Sale, SaleItem

# Only logged-in employees may access the cashier payment page
@login_required
def cash_payment(request):
    #This dictionary holds information sent to the HTML page.
    context = {
        "sale_total": "",
        "amount_paid":"",
        "result_ready": False,
    }

    #Only calculate after the cashier submits the form.
    if request.method == "POST":
        try:
            #Read the two amounts from the form.
            sale_total = Decimal(request.POST.get("sale_total", "0"))
            amount_paid = Decimal(request.POST.get("amount_paid", "0"))

            #Prevent negative dollar amounts.
            if sale_total < 0 or amount_paid < 0:
                raise InvalidOperation

            #Keep the entered values so the page can display them.
            context["sale_total"] = sale_total
            context["amount_paid"] = amount_paid

            if amount_paid >= sale_total:
                #Customer paid more than sales total; calculate change.
                context["change_due"] = amount_paid - sale_total
            else:
                context["amount_remaining"] = sale_total - amount_paid

        except (InvalidOperation, ValueError):
            #Show error message when invalid data entered.
            context["error"] = "Please enter valid dollar amounts."

    #Display the page with calculation results.
    return render(request, "sales/cash_payment.html", context)

@require_POST
def checkout(request):
    # Get the customer's current shopping cart.
    cart = request.session.get("cart", {})

    # Do not allow an empty cart to be checked out.
    if not cart:
        messages.warning(request, "Your cart is empty.")
        return redirect("cart:detail")

    try:
        # Everything inside this block succeeds together or fails together.
        with transaction.atomic():

            # Create the main sale record.
            sale = Sale.objects.create(
                user=request.user if request.user.is_authenticated else None,
                payment_method="Mock Checkout",
            )

            subtotal = Decimal("0.00")

            # Convert each cart item into a SaleItem.
            for book_id, quantity in cart.items():
                quantity = int(quantity)

                # Get the latest copy of the book from the database.
                book = Book.objects.select_for_update().get(id=book_id)

                # Check inventory again at checkout.
                if quantity > book.quantity:
                    raise ValueError(
                        f"Only {book.quantity} copies of {book.title} are available."
                    )

                price = book.price or Decimal("0.00")
                line_total = price * quantity

                # Save this purchased book as a sale line item.
                SaleItem.objects.create(
                    sale=sale,
                    book=book,
                    quantity=quantity,
                    price_each=price,
                    line_total=line_total,
                )

                # Reduce inventory.
                book.quantity -= quantity
                book.save(update_fields=["quantity"])

                subtotal += line_total

            # For now this is a mock checkout, so no tax calculation.
            sale.subtotal = subtotal
            sale.tax = Decimal("0.00")
            sale.total = subtotal
            sale.amount_paid = subtotal
            sale.save()

    except Book.DoesNotExist:
        messages.error(
            request,
            "One of the books in your cart is no longer available."
        )
        return redirect("cart:detail")

    except ValueError as error:
        messages.error(request, str(error))
        return redirect("cart:detail")

    # Only clear the cart after the database transaction succeeds.
    request.session["cart"] = {}
    request.session.modified = True

    # Redirect instead of directly rendering.
    # This prevents refresh from submitting the order again.
    return redirect("sales:confirmation", sale_id=sale.id)


def confirmation(request, sale_id):
    # Find the completed sale.
    sale = get_object_or_404(Sale, id=sale_id)

    # Get all books associated with the sale.
    items = SaleItem.objects.filter(
        sale=sale
    ).select_related("book")

    return render(
        request,
        "sales/confirmation.html",
        {
            "sale": sale,
            "items": items,
        },
    )