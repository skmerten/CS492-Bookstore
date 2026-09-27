from decimal import Decimal, InvalidOperation
from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render

from inventory.models import Book
from .forms import CustomerCheckoutForm
from .models import Sale, SaleItem
from .services import calculate_daily_sales_total, calculate_sales_tax

# Only logged-in employees may access the cashier payment page
@login_required
def cash_payment(request, sale_id=None):
    #Load a completed sale when cashier page was opened from confirmation.
    sale = get_object_or_404(Sale, id=sale_id) if sale_id is not None else None
    #This dictionary holds information sent to the HTML page.
    context = {
        "sale": sale,
        "sale_total":sale.total if sale is not None else "",
        "amount_paid":"",
        "result_ready": False,
    }

    #Only calculate after the cashier submits the form.
    if request.method == "POST":
        try:
            #Use the stored total when this cashieer page is tied to a saved sale.
            if sale is not None:
                sale_total = sale.total
            else:
                sale_total = Decimal(request.POST.get("sale_total", "0"))
            amount_paid = Decimal(request.POST.get("amount_paid", "o"))

            #Prevent negative dollar amounts.
            if sale_total < 0 or amount_paid < 0:
                raise InvalidOperation

            #Keep validated payment values and mark the calculation result.
            context["sale_total"] = sale_total
            context["amount_paid"] = amount_paid
            context["result_ready"] = True

            if amount_paid >= sale_total:
                #Customer paid more than sales total; calculate change.
                context["change_due"] = amount_paid - sale_total
                #Store completed cash payment details on the linked sale.
                if sale is not None:
                    sale.payment_method = "Cash"
                    sale.amount_paid = amount_paid
                    sale.change_due = context["change_due"]
                    sale.save(
                        update_fields=["payment_method", "amount_paid", "change_due"]
                    )
                    messages.success(
                        request, f"Cash payment for sale #{sale.id} was recorded."
                    )
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

        #Calculate all amount before confirmation page so customer can review full cost.
        display_tax = calculate_sales_tax(display_subtotal)
        display_total = display_subtotal + display_tax

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
                sale.tax = calculate_sales_tax(subtotal)
                sale.total = subtotal + sale.tax
                sale.amount_paid = sale.total
                sale.save(
                    update_fields=["subtotal", "tax", "total", "amount_paid"]
                )

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
            "tax": display_tax,
            "total": display_total,
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

@login_required
def daily_sales_log(request):
    #Use today's date when the employee has not selected another date.
    selected_date = date.today()

    #Read the date chosen in log page's date field.
    selected_date_value = request.GET.get("date")

    #Convert a valid YYYY-MM-DD value into a python date.
    if selected_date_value:
        try:
            selected_date = date.fromisoformat(selected_date_value)
        except ValueError:

            #Keep today's date and explain an invalid date is submitted.
            messages.error(
                request, "Please select a valid sales date."
            )

    #Retrieve all sales for specificed date, newest first.
    sales = (
        Sale.objects.filter(sale_date__date=selected_date)
        .select_related("customer", "user").order_by("-sale_date")
    )

    #Calculate the combined total for all selected date sales.
    daily_total = calculate_daily_sales_total(selected_date)

    #Display the daily sales log and provide its required information.
    return render(
        request, "sales/daily_sales_log.html",
        {"sales":sales, "selected_date": selected_date, "daily_total": daily_total,},
    )