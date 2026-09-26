from datetime import date
from decimal import Decimal

from django.db.models import Sum

from .models import Sale

#Function to return the total dollar amount of all sales recorded on a date.
def calculate_daily_sales_total(sale_date: date)-> Decimal:
    total = (
        Sale.objects.filter(sale_date__date=sale_date).aggregate(total=Sum("total"))
        ["total"]
    )

#Return $0.00 when no sales were recorded on the selected date.
    return (total or Decimal("0.00")).quantize(Decimal("0.01"))