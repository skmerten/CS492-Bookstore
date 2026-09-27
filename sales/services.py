from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

from .models import Sale

##Use Texas sales tax rate of 8.25% for project.
TEXAS_COMBINED_SALES_TAX_RATE = Decimal("0.0825")

def calculate_sales_tax(subtotal: Decimal) -> Decimal:
    #Calculate tax and round result to nearest cent.
    return (subtotal * TEXAS_COMBINED_SALES_TAX_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP,)


#Function to return the total dollar amount of all sales recorded on a date.
def calculate_daily_sales_total(sale_date: date)-> Decimal:
    total = (
        Sale.objects.filter(sale_date__date=sale_date).aggregate(total=Sum("total"))
        ["total"]
    )

#Return $0.00 when no sales were recorded on the selected date.
    return (total or Decimal("0.00")).quantize(Decimal("0.01"))