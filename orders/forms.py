from django import forms

from .models import CustomerRequest
from sales.forms import CustomerCheckoutForm

class CustomerRequestForm(forms.ModelForm):
    #Connects the form with the CustomerRequest database
    class Meta:
        model = CustomerRequest

        #Customeer information is handled by the existing sales/forms.py
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
    #Require at least one way to contact customer.
    def clean(self):
        cleaned_data = super().clean()

        email = cleaned_data.get("email")
        phone = cleaned_data.get("phone")

        #Does not save a request when both contact methods blank.
        if not email and not phone:
            raise forms.ValidationError(
                "Enter an email or phone number."
            )

        return cleaned_data