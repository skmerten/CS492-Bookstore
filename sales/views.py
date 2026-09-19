from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render

from inventory.models import Book
from .forms import CustomerCheckoutForm
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

def checkout(request):
    # Get the current shopping cart.
    cart = request.session.get("cart", {})

    # Do not allow checkout with an empty cart.
    if not cart:
        messages.warning(request, "Your cart is empty.")
        return redirect("cart:detail")

    # Build information needed to display the checkout page.
    books = Book.objects.filter(id__in=cart.keys())
    books_by_id = {
        str(book.id): book
        for book in books
    }

    items = []
    display_subtotal = Decimal("0.00")

    # Make sure every book in the cart still exists.
    for book_id, quantity in cart.items():

        book = books_by_id.get(str(book_id))

        if book is None:
            messages.error(
                request,
                "One of the books in your cart is no longer available."
            )
            return redirect("cart:detail")

        quantity = int(quantity)
        price = book.price or Decimal("0.00")
        line_total = price * quantity

        items.append({
            "book": book,
            "quantity": quantity,
            "line_total": line_total,
        })

        display_subtotal += line_total

    # GET = display empty form.
    # POST = populate form with submitted customer information.
    form = CustomerCheckoutForm(request.POST or None)

    if request.method == "POST" and form.is_valid():

        try:
            # Customer, sale, sale items, and inventory changes
            # must either ALL succeed or ALL fail.
            with transaction.atomic():

                # Save customer information.
                customer = form.save()

                # Create sale header.
                sale = Sale.objects.create(
                    customer=customer,
                    user=request.user
                    if request.user.is_authenticated
                    else None,
                    payment_method="Mock Checkout",
                )

                subtotal = Decimal("0.00")

                for book_id, quantity in cart.items():

                    quantity = int(quantity)

                    # Get current book information.
                    book = Book.objects.get(id=book_id)

                    # Atomically subtract inventory ONLY if enough
                    # inventory still exists.
                    updated_rows = Book.objects.filter(
                        id=book_id,
                        quantity__gte=quantity,
                    ).update(
                        quantity=F("quantity") - quantity
                    )

                    # Zero updated rows means someone else purchased
                    # the remaining inventory first.
                    if updated_rows == 0:

                        current_quantity = (
                            Book.objects
                            .filter(id=book_id)
                            .values_list("quantity", flat=True)
                            .first()
                        )

                        if current_quantity is None:
                            raise ValueError(
                                f"{book.title} is no longer available."
                            )

                        raise ValueError(
                            f"Only {current_quantity} copies of "
                            f"{book.title} are currently available."
                        )

                    price = book.price or Decimal("0.00")
                    line_total = price * quantity

                    SaleItem.objects.create(
                        sale=sale,
                        book=book,
                        quantity=quantity,
                        price_each=price,
                        line_total=line_total,
                    )

                    subtotal += line_total

                # Finish calculating sale totals.
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

            messages.error(
                request,
                str(error)
            )

            return redirect("cart:detail")

        # Only clear the cart AFTER everything succeeds.
        request.session["cart"] = {}
        request.session.modified = True

        return redirect(
            "sales:confirmation",
            sale_id=sale.id
        )

    return render(
        request,
        "sales/checkout.html",
        {
            "form": form,
            "items": items,
            "subtotal": display_subtotal,
        },
    )

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