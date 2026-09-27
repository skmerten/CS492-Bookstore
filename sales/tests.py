"""Checkout, inventory, cash payment, reports, and local backup behavior."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sqlite3

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from inventory.models import Book
from .models import Customer, Sale, SaleItem
from .services import calculate_daily_sales_total, calculate_sales_tax


class CheckoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.first = Book.objects.create(title="First Book", price=Decimal("10.00"), quantity=4)
        cls.second = Book.objects.create(title="Second Book", price=Decimal("5.00"), quantity=3)

    def customer_data(self, **changes):
        return {"full_name": "Jamie Buyer", "email": "buyer@example.com", "phone": "", **changes}

    def set_cart(self, cart):
        session = self.client.session
        session["cart"] = {str(key): quantity for key, quantity in cart.items()}
        session.save()

    def test_checkout_requires_cart_and_missing_book_redirects_without_sale(self):
        self.assertRedirects(self.client.get(reverse("sales:checkout")), reverse("cart:detail"))
        self.set_cart({99999: 1})
        self.assertRedirects(self.client.post(reverse("sales:checkout"), self.customer_data()),
                             reverse("cart:detail"))
        self.assertFalse(Sale.objects.exists())

    def test_get_shows_subtotal_tax_and_total(self):
        self.set_cart({self.first.pk: 2, self.second.pk: 1})
        response = self.client.get(reverse("sales:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["subtotal"], Decimal("25.00"))
        self.assertEqual(response.context["tax"], Decimal("2.06"))
        self.assertEqual(response.context["total"], Decimal("27.06"))

    def test_visitor_purchase_records_sale_and_decrements_stock_once(self):
        self.set_cart({self.first.pk: 2, self.second.pk: 1})
        response = self.client.post(reverse("sales:checkout"), self.customer_data())
        sale = Sale.objects.get()
        self.assertRedirects(response, reverse("sales:confirmation", args=[sale.pk]))
        self.assertEqual((sale.subtotal, sale.tax, sale.total),
                         (Decimal("25.00"), Decimal("2.06"), Decimal("27.06")))
        self.assertIsNone(sale.user)
        self.assertEqual(sale.payment_method, "Mock Checkout")
        self.assertEqual(sale.amount_paid, sale.total)
        self.assertEqual(SaleItem.objects.filter(sale=sale).count(), 2)
        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertEqual((self.first.quantity, self.second.quantity), (2, 2))
        self.assertEqual(self.client.session["cart"], {})
        self.assertContains(self.client.get(response.url), "First Book")

    def test_checkout_rolls_back_customer_sale_and_stock_when_one_item_sells_out(self):
        self.set_cart({self.first.pk: 2, self.second.pk: 2})
        self.second.quantity = 1
        self.second.save(update_fields=["quantity"])
        response = self.client.post(reverse("sales:checkout"), self.customer_data())
        self.assertRedirects(response, reverse("cart:detail"))
        self.assertEqual((Sale.objects.count(), SaleItem.objects.count(), Customer.objects.count()), (0, 0, 0))
        self.first.refresh_from_db()
        self.assertEqual(self.first.quantity, 4)
        self.assertEqual(self.client.session["cart"][str(self.second.pk)], 2)

    def test_invalid_customer_details_do_not_create_sale(self):
        self.set_cart({self.first.pk: 1})
        response = self.client.post(reverse("sales:checkout"), self.customer_data(full_name=""))
        self.assertEqual(response.status_code, 200)
        self.assertIn("full_name", response.context["form"].errors)
        self.assertFalse(Sale.objects.exists())

    def test_authenticated_checkout_attributes_sale_to_employee(self):
        employee = get_user_model().objects.create_user("cashier", password="test-password")
        self.client.force_login(employee)
        self.set_cart({self.first.pk: 1})
        self.client.post(reverse("sales:checkout"), self.customer_data())
        self.assertEqual(Sale.objects.get().user, employee)

    def test_confirmation_is_public_and_unknown_sale_is_404(self):
        customer = Customer.objects.create(full_name="Buyer")
        sale = Sale.objects.create(customer=customer, total=Decimal("10.00"))
        SaleItem.objects.create(sale=sale, book=self.first, quantity=1,
                                price_each=Decimal("10.00"), line_total=Decimal("10.00"))
        self.assertContains(self.client.get(reverse("sales:confirmation", args=[sale.pk])), self.first.title)
        self.assertEqual(self.client.get(reverse("sales:confirmation", args=[99999])).status_code, 404)


class CashPaymentAndReportTests(TestCase):
    def setUp(self):
        self.employee = get_user_model().objects.create_user("cashier", password="test-password")
        self.sale = Sale.objects.create(total=Decimal("13.75"), subtotal=Decimal("12.70"),
                                        tax=Decimal("1.05"))

    def test_cashier_page_requires_login_and_records_change_on_saved_sale(self):
        url = reverse("sales:cash_payment_for_sale", args=[self.sale.pk])
        self.assertRedirects(self.client.get(url), f"/login/?next={url}")
        self.client.force_login(self.employee)
        response = self.client.post(url, {"sale_total": "1.00", "amount_paid": "20.00"})
        self.sale.refresh_from_db()
        self.assertEqual(response.context["change_due"], Decimal("6.25"))
        self.assertEqual((self.sale.payment_method, self.sale.amount_paid, self.sale.change_due),
                         ("Cash", Decimal("20.00"), Decimal("6.25")))

    def test_underpayment_and_invalid_amount_do_not_update_sale(self):
        self.client.force_login(self.employee)
        url = reverse("sales:cash_payment_for_sale", args=[self.sale.pk])
        response = self.client.post(url, {"amount_paid": "10.00"})
        self.assertEqual(response.context["amount_remaining"], Decimal("3.75"))
        response = self.client.post(url, {"amount_paid": "-1.00"})
        self.assertContains(response, "Please enter valid dollar amounts")
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.payment_method, "")

    def test_standalone_cash_calculator_does_not_create_sale(self):
        self.client.force_login(self.employee)
        response = self.client.post(reverse("sales:cash_payment"),
                                    {"sale_total": "8.00", "amount_paid": "10.00"})
        self.assertEqual(response.context["change_due"], Decimal("2.00"))
        self.assertEqual(Sale.objects.count(), 1)

    def test_daily_sales_filters_date_and_aggregates_total(self):
        self.client.force_login(self.employee)
        selected = timezone.localtime(self.sale.sale_date).date()
        older = Sale.objects.create(total=Decimal("99.00"))
        Sale.objects.filter(pk=older.pk).update(sale_date=self.sale.sale_date - timedelta(days=4))
        url = reverse("sales:daily_sales_log")
        response = self.client.get(url, {"date": selected.isoformat()})
        self.assertEqual(response.context["daily_total"], Decimal("13.75"))
        self.assertEqual(list(response.context["sales"]), [self.sale])
        self.assertEqual(calculate_daily_sales_total(selected), Decimal("13.75"))
        self.assertEqual(calculate_daily_sales_total(selected - timedelta(days=100)), Decimal("0.00"))
        self.assertContains(self.client.get(url, {"date": "not-a-date"}), "Please select a valid sales date")

    def test_sales_tax_rounds_to_cent(self):
        self.assertEqual(calculate_sales_tax(Decimal("25.00")), Decimal("2.06"))
        self.assertEqual(calculate_sales_tax(Decimal("0.07")), Decimal("0.01"))


class LocalBackupCommandTests(SimpleTestCase):
    def test_backup_copies_local_sqlite_file(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / "source.sqlite3"
            with sqlite3.connect(source) as db:
                db.execute("CREATE TABLE example (value TEXT)")
                db.execute("INSERT INTO example VALUES ('saved')")
            with patch.object(settings, "BASE_DIR", Path(folder)), patch.object(
                settings, "DATABASES", {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": source}}
            ):
                call_command("backup_local_database", verbosity=0)
            backups = list((Path(folder) / "backups").glob("bookstore_backup_*.sqlite3"))
            self.assertEqual(len(backups), 1)
            with sqlite3.connect(backups[0]) as db:
                self.assertEqual(db.execute("SELECT value FROM example").fetchone(), ("saved",))

    def test_backup_rejects_non_sqlite_and_missing_local_file(self):
        with patch.object(settings, "DATABASES", {"default": {"ENGINE": "django.db.backends.postgresql"}}):
            with self.assertRaisesMessage(CommandError, "only the local SQLite"):
                call_command("backup_local_database", verbosity=0)
        with TemporaryDirectory() as folder:
            with patch.object(settings, "DATABASES", {"default": {
                "ENGINE": "django.db.backends.sqlite3", "NAME": Path(folder) / "missing.sqlite3"
            }}):
                with self.assertRaisesMessage(CommandError, "was not found"):
                    call_command("backup_local_database", verbosity=0)
