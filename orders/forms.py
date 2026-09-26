from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from inventory.models import Book
from sales.forms import CustomerCheckoutForm
from .models import CustomerRequest, Supplier, SupplierOrder, SupplierOrderItem


class CustomerRequestForm(forms.ModelForm):
    # Connects the form with the CustomerRequest database.
    class Meta:
        model = CustomerRequest
        # Customer information is handled by the existing sales/forms.py.
        fields = ["requested_title", "requested_author"]
        widgets = {
            "requested_title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Requested book title",
                }
            ),
            "requested_author": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Requested author (optional)",
                }
            ),
        }


class CustomerRequestCustomerForm(CustomerCheckoutForm):
    # Require at least one way to contact customer.
    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        phone = cleaned_data.get("phone")

        if not email and not phone:
            raise forms.ValidationError("Enter an email or phone number.")

        return cleaned_data


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "contact_name", "email", "phone", "address"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "contact_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class SupplierOrderForm(forms.ModelForm):
    class Meta:
        model = SupplierOrder
        fields = ["supplier"]
        widgets = {
            "supplier": forms.Select(attrs={"class": "form-select"}),
        }


class SupplierOrderItemForm(forms.ModelForm):
    # An employee can either select an existing inventory record or enter a new book.
    book = forms.ModelChoiceField(
        queryset=Book.objects.none(),
        required=False,
        empty_label="-- Select an existing book --",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    new_title = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "New book title"}
        ),
    )
    new_author = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Author (optional)"}
        ),
    )
    new_isbn = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "ISBN (optional)"}
        ),
    )
    new_price = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        label="Retail Price",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.01", "min": "0"}
        ),
    )
    new_shelf_location = forms.CharField(
        required=False,
        label="Shelf Location",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Optional"}
        ),
    )

    class Meta:
        model = SupplierOrderItem
        fields = ["book", "quantity_ordered", "cost_each"]
        widgets = {
            "quantity_ordered": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
            "cost_each": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
        }
        labels = {
            "quantity_ordered": "Quantity",
            "cost_each": "Vendor Cost Each",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["book"].queryset = Book.objects.all().order_by("title", "author")

    def clean(self):
        cleaned_data = super().clean()

        # Ignore forms the employee marked for deletion.
        if cleaned_data.get("DELETE"):
            return cleaned_data

        existing_book = cleaned_data.get("book")
        new_title = (cleaned_data.get("new_title") or "").strip()

        if existing_book and new_title:
            raise forms.ValidationError(
                "Choose an existing book OR enter a new book, not both."
            )

        if not existing_book and not new_title:
            # Empty extra formset rows are allowed. The formset clean method will
            # make sure at least one real line item was entered.
            quantity = cleaned_data.get("quantity_ordered")
            cost_each = cleaned_data.get("cost_each")
            has_any_new_data = any(
                [
                    cleaned_data.get("new_author"),
                    cleaned_data.get("new_isbn"),
                    cleaned_data.get("new_price") is not None,
                    cleaned_data.get("new_shelf_location"),
                ]
            )
            if quantity or cost_each is not None or has_any_new_data:
                raise forms.ValidationError(
                    "Select an existing book or enter a new book title."
                )

        return cleaned_data


class BaseSupplierOrderItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        item_count = 0
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            if form.cleaned_data.get("book") or (
                form.cleaned_data.get("new_title") or ""
            ).strip():
                item_count += 1

        if item_count == 0:
            raise forms.ValidationError("Add at least one book to the purchase order.")


SupplierOrderItemFormSet = inlineformset_factory(
    SupplierOrder,
    SupplierOrderItem,
    form=SupplierOrderItemForm,
    formset=BaseSupplierOrderItemFormSet,
    extra=1,
    can_delete=True,
)
