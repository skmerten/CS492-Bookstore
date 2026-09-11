from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

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
