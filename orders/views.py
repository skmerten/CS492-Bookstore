from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from inventory.models import Book
from sales.models import Customer
from .forms import (
    CustomerRequestCustomerForm,
    CustomerRequestEditForm,
    CustomerRequestForm,
    SupplierForm,
    SupplierOrderForm,
    SupplierOrderItemFormSet,
)
from .models import CustomerRequest, Supplier, SupplierOrder


# Only allows logged in employees to record a customer book request.
@login_required
def create_customer_request(request):
    customer_form = CustomerRequestCustomerForm(request.POST or None)
    request_form = CustomerRequestForm(request.POST or None)

    if request.method == "POST":
        if customer_form.is_valid() and request_form.is_valid():
            customer_data = customer_form.cleaned_data

            customer, created = Customer.objects.get_or_create(
                full_name=customer_data["full_name"],
                email=customer_data["email"],
                phone=customer_data["phone"],
            )

            customer_request = request_form.save(commit=False)
            customer_request.customer = customer
            customer_request.save()

            messages.success(request, "The customer request was saved successfully.")
            return redirect("orders:customer_request_log")

    return render(
        request,
        "orders/customer_request_form.html",
        {
            "customer_form": customer_form,
            "request_form": request_form,
        },
    )


# Only logged-in employees can view customer request log.
@login_required
def customer_request_log(request):
    customer_requests = CustomerRequest.objects.select_related(
        "customer", "book", "purchase_order"
    ).order_by("-request_date")

    return render(
        request,
        "orders/customer_request_log.html",
        {"customer_requests": customer_requests},
    )


@login_required
def customer_request_detail(request, request_id):
    customer_request = get_object_or_404(
        CustomerRequest.objects.select_related("customer", "purchase_order"),
        pk=request_id,
    )
    editable = not customer_request.purchase_order_id and customer_request.status in {
        CustomerRequest.Status.PENDING,
        CustomerRequest.Status.REJECTED,
        CustomerRequest.Status.CANCELLED,
    }
    form = CustomerRequestEditForm(request.POST or None, instance=customer_request) if editable else None

    if request.method == "POST":
        if not editable:
            messages.error(request, "This request is linked to a purchase order and cannot be edited.")
            return redirect("orders:customer_request_detail", request_id=request_id)
        if form.is_valid():
            form.save()
            messages.success(request, "Customer request updated.")
            return redirect("orders:customer_request_detail", request_id=request_id)

    return render(
        request,
        "orders/customer_request_detail.html",
        {"customer_request": customer_request, "form": form},
    )


@login_required
def supplier_list(request):
    suppliers = Supplier.objects.all().order_by("name")
    return render(request, "orders/supplier_list.html", {"suppliers": suppliers})


@login_required
def create_supplier(request):
    form = SupplierForm(request.POST or None)
    request_id = request.GET.get("request")
    linked_request = None
    if request_id and request_id.isdecimal():
        linked_request = CustomerRequest.objects.filter(
            pk=request_id,
            status=CustomerRequest.Status.PENDING,
            purchase_order__isnull=True,
        ).first()

    if request.method == "POST" and form.is_valid():
        supplier = form.save()
        messages.success(request, f"Vendor {supplier.name} was added successfully.")

        # If the employee came here from the PO form, return to it afterward.
        if request.POST.get("save_and_order"):
            if linked_request:
                url = reverse(
                    "orders:create_supplier_order_for_request",
                    args=[linked_request.pk],
                )
            else:
                url = reverse("orders:create_supplier_order")
            return redirect(f"{url}?supplier={supplier.id}")

        return redirect("orders:supplier_list")

    return render(request, "orders/supplier_form.html", {"form": form, "linked_request": linked_request})


@login_required
def supplier_order_list(request):
    supplier_orders = (
        SupplierOrder.objects.select_related("supplier", "user")
        .prefetch_related("items__book")
        .order_by("-order_date")
    )

    return render(
        request,
        "orders/supplier_order_list.html",
        {"supplier_orders": supplier_orders},
    )


def _book_for_new_order_line(cleaned_data):
    """Find an existing matching book or create an inventory record at quantity 0."""
    title = (cleaned_data.get("new_title") or "").strip()
    author = (cleaned_data.get("new_author") or "").strip()
    isbn = (cleaned_data.get("new_isbn") or "").strip()

    # ISBN is the strongest match when available.
    book = None
    if isbn:
        book = Book.objects.filter(isbn__iexact=isbn).first()

    # If there is no ISBN match, use title + author.
    if book is None and title:
        book = Book.objects.filter(
            title__iexact=title,
            author__iexact=author,
        ).first()

    if book is None:
        book = Book.objects.create(
            title=title,
            author=author,
            isbn=isbn,
            price=cleaned_data.get("new_price"),
            quantity=0,
            shelf_location=(cleaned_data.get("new_shelf_location") or "").strip(),
        )

    return book


def _contains_requested_book(formset, customer_request):
    """A linked PO must still contain the title and author from its request."""
    title = customer_request.requested_title.strip().casefold()
    author = customer_request.requested_author.strip().casefold()
    for form in formset.forms:
        data = form.cleaned_data
        if data.get("DELETE") or not data:
            continue
        book = data.get("book")
        line_title = book.title if book else data.get("new_title", "")
        line_author = book.author if book else data.get("new_author", "")
        if line_title.strip().casefold() == title and (
            not author or line_author.strip().casefold() == author
        ):
            return True
    return False


@login_required
@transaction.atomic
def create_supplier_order(request, request_id=None):
    order = SupplierOrder()
    customer_request = None
    if request_id is not None:
        customer_request = get_object_or_404(
            CustomerRequest.objects.select_for_update(), pk=request_id
        )
        if customer_request.status != CustomerRequest.Status.PENDING or customer_request.purchase_order_id:
            messages.error(request, "Only a pending request without a purchase order can create a PO.")
            return redirect("orders:customer_request_detail", request_id=request_id)

    initial = {}
    supplier_id = request.GET.get("supplier")
    if supplier_id and Supplier.objects.filter(pk=supplier_id).exists():
        initial["supplier"] = supplier_id

    if request.method == "POST":
        order_form = SupplierOrderForm(request.POST, instance=order)
        item_formset = SupplierOrderItemFormSet(
            request.POST,
            instance=order,
            prefix="items",
        )

        order_valid = order_form.is_valid()
        items_valid = item_formset.is_valid()
        if items_valid and customer_request and not _contains_requested_book(item_formset, customer_request):
            item_formset._non_form_errors.append(
                "Include the requested title and author on this purchase order. "
                "Edit the customer request first if those details need correcting."
            )
            items_valid = False

        if order_valid and items_valid:
            order = order_form.save(commit=False)
            order.user = request.user
            order.status = SupplierOrder.Status.ORDERED
            order.total_cost = Decimal("0.00")
            order.save()

            total_cost = Decimal("0.00")

            for form in item_formset.forms:
                if not hasattr(form, "cleaned_data") or not form.cleaned_data:
                    continue
                if form.cleaned_data.get("DELETE"):
                    continue

                existing_book = form.cleaned_data.get("book")
                new_title = (form.cleaned_data.get("new_title") or "").strip()

                # Skip the completely blank extra form.
                if existing_book is None and not new_title:
                    continue

                item = form.save(commit=False)
                item.supplier_order = order

                if existing_book is not None:
                    item.book = existing_book
                else:
                    item.book = _book_for_new_order_line(form.cleaned_data)

                item.save()
                total_cost += item.line_total

            order.total_cost = total_cost
            order.save(update_fields=["total_cost"])

            if customer_request:
                customer_request.purchase_order = order
                customer_request.status = CustomerRequest.Status.APPROVED
                customer_request.save(update_fields=["purchase_order", "status"])

            messages.success(
                request,
                f"Purchase Order #{order.id} was created successfully.",
            )
            return redirect("orders:supplier_order_detail", order_id=order.id)

    else:
        order_form = SupplierOrderForm(instance=order, initial=initial)
        item_formset = SupplierOrderItemFormSet(
            instance=order,
            prefix="items",
            initial=[{
                "new_title": customer_request.requested_title,
                "new_author": customer_request.requested_author,
            }] if customer_request else None,
        )

    return render(
        request,
        "orders/supplier_order_form.html",
        {
            "order_form": order_form,
            "item_formset": item_formset,
            "customer_request": customer_request,
        },
    )


@login_required
def supplier_order_detail(request, order_id):
    supplier_order = get_object_or_404(
        SupplierOrder.objects.select_related("supplier", "user").prefetch_related(
            "items__book"
        ),
        pk=order_id,
    )

    return render(
        request,
        "orders/supplier_order_detail.html",
        {"supplier_order": supplier_order},
    )


@login_required
def receive_supplier_order(request, order_id):
    if request.method != "POST":
        return redirect("orders:supplier_order_detail", order_id=order_id)

    supplier_order = get_object_or_404(SupplierOrder, pk=order_id)

    try:
        updated = supplier_order.mark_received()
        if updated:
            messages.success(
                request,
                f"Purchase Order #{supplier_order.id} was received and inventory was updated.",
            )
        else:
            messages.info(
                request,
                f"Purchase Order #{supplier_order.id} had already been received. No inventory was added again.",
            )
    except ValueError as error:
        messages.error(request, str(error))

    return redirect("orders:supplier_order_detail", order_id=order_id)


@login_required
def cancel_supplier_order(request, order_id):
    if request.method != "POST":
        return redirect("orders:supplier_order_detail", order_id=order_id)

    supplier_order = get_object_or_404(SupplierOrder, pk=order_id)

    try:
        supplier_order.cancel()
        messages.success(request, f"Purchase Order #{supplier_order.id} was cancelled.")
    except ValueError as error:
        messages.error(request, str(error))

    return redirect("orders:supplier_order_detail", order_id=order_id)
