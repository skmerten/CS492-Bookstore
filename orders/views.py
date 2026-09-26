from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from inventory.models import Book
from sales.models import Customer
from .forms import (
    CustomerRequestCustomerForm,
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
        "customer", "book"
    ).order_by("-request_date")

    return render(
        request,
        "orders/customer_request_log.html",
        {"customer_requests": customer_requests},
    )


@login_required
def supplier_list(request):
    suppliers = Supplier.objects.all().order_by("name")
    return render(request, "orders/supplier_list.html", {"suppliers": suppliers})


@login_required
def create_supplier(request):
    form = SupplierForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        supplier = form.save()
        messages.success(request, f"Vendor {supplier.name} was added successfully.")

        # If the employee came here from the PO form, return to it afterward.
        if request.POST.get("save_and_order"):
            return redirect(f"/orders/purchase-orders/new/?supplier={supplier.id}")

        return redirect("orders:supplier_list")

    return render(request, "orders/supplier_form.html", {"form": form})


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


@login_required
@transaction.atomic
def create_supplier_order(request):
    order = SupplierOrder()

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

        if order_form.is_valid() and item_formset.is_valid():
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
        )

    return render(
        request,
        "orders/supplier_order_form.html",
        {
            "order_form": order_form,
            "item_formset": item_formset,
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
