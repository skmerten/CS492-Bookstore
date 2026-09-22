from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from sales.models import Customer
from .forms import CustomerRequestCustomerForm, CustomerRequestForm 
from .models import CustomerRequest

#Only allows logged in employees to record a customer book request.
@login_required
def create_customer_request(request):
    customer_form = CustomerRequestCustomerForm(request.POST or None)
    request_form = CustomerRequestForm(request.POST or None)

    #Only save information after the employee submits form.
    if request.method == "POST":

        #Both forms must contain valid information in order for anything to be saved.
        if customer_form.is_valid() and request_form.is_valid():
            customer_data = customer_form.cleaned_data

            #Reuse a matching customer information or create a new record.
            customer, created = Customer.objects.get_or_create(
                full_name=customer_data["full_name"],
                email=customer_data["email"],
                phone=customer_data["phone"],
            )

            customer_request = request_form.save(commit=False)

            #Connect the book request to the customer record.
            customer_request.customer = customer

            #Saves the completed request to database.
            customer_request.save()

            #Shows confirmation message.
            messages.success(
                request,
                "The customer request was saved successfully."
            )

            return redirect("orders:customer_request_log")

    return render(
        request,
        "orders/customer_request_form.html",
        {
            "customer_form": customer_form,
            "request_form": request_form,
        },
    )

#Only logged-in employees can view customer request log.
@login_required
def customer_request_log(request):

    #Retrieve customer requests from newest to oldest
    customer_requests = (
        CustomerRequest.objects.select_related("customer", "book").order_by("-request_date")
    )

    #Display the log page 
    return render(
        request,
        "orders/customer_request_log.html",
        {
            "customer_requests": customer_requests,
        },
    )

