from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import Book
from .models import Supplier, SupplierOrder, SupplierOrderItem


class SupplierPurchaseOrderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="employee",
            password="test-password",
        )
        self.client.login(username="employee", password="test-password")
        self.supplier = Supplier.objects.create(name="Test Book Vendor")
        self.book = Book.objects.create(
            title="Existing Book",
            author="Existing Author",
            isbn="1111111111",
            price=Decimal("15.99"),
            quantity=4,
        )

    def test_receive_order_updates_inventory_only_once(self):
        order = SupplierOrder.objects.create(
            supplier=self.supplier,
            user=self.user,
            total_cost=Decimal("24.00"),
        )
        SupplierOrderItem.objects.create(
            supplier_order=order,
            book=self.book,
            quantity_ordered=3,
            cost_each=Decimal("8.00"),
        )

        self.assertTrue(order.mark_received())
        self.book.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(self.book.quantity, 7)
        self.assertEqual(order.status, SupplierOrder.Status.RECEIVED)
        self.assertTrue(order.inventory_updated)

        # A second receive must not add inventory again.
        self.assertFalse(order.mark_received())
        self.book.refresh_from_db()
        self.assertEqual(self.book.quantity, 7)

    def test_cancelled_order_cannot_be_received(self):
        order = SupplierOrder.objects.create(
            supplier=self.supplier,
            user=self.user,
        )
        SupplierOrderItem.objects.create(
            supplier_order=order,
            book=self.book,
            quantity_ordered=2,
            cost_each=Decimal("8.00"),
        )

        order.cancel()
        with self.assertRaises(ValueError):
            order.mark_received()

        self.book.refresh_from_db()
        self.assertEqual(self.book.quantity, 4)

    def test_employee_can_create_multi_item_purchase_order(self):
        second_book = Book.objects.create(
            title="Second Book",
            author="Another Author",
            quantity=10,
        )

        response = self.client.post(
            reverse("orders:create_supplier_order"),
            {
                "supplier": self.supplier.id,
                "items-TOTAL_FORMS": "2",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-book": self.book.id,
                "items-0-quantity_ordered": "2",
                "items-0-cost_each": "5.50",
                "items-0-new_title": "",
                "items-0-new_author": "",
                "items-0-new_isbn": "",
                "items-0-new_price": "",
                "items-0-new_shelf_location": "",
                "items-1-book": second_book.id,
                "items-1-quantity_ordered": "3",
                "items-1-cost_each": "4.00",
                "items-1-new_title": "",
                "items-1-new_author": "",
                "items-1-new_isbn": "",
                "items-1-new_price": "",
                "items-1-new_shelf_location": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        order = SupplierOrder.objects.latest("id")
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.total_cost, Decimal("23.00"))
        self.assertEqual(order.status, SupplierOrder.Status.ORDERED)

    def test_new_book_line_creates_zero_stock_then_receive_adds_stock(self):
        response = self.client.post(
            reverse("orders:create_supplier_order"),
            {
                "supplier": self.supplier.id,
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-book": "",
                "items-0-quantity_ordered": "6",
                "items-0-cost_each": "7.25",
                "items-0-new_title": "Brand New Book",
                "items-0-new_author": "New Author",
                "items-0-new_isbn": "2222222222",
                "items-0-new_price": "14.99",
                "items-0-new_shelf_location": "A-12",
            },
        )

        self.assertEqual(response.status_code, 302)
        new_book = Book.objects.get(isbn="2222222222")
        self.assertEqual(new_book.quantity, 0)

        order = SupplierOrder.objects.latest("id")
        order.mark_received()
        new_book.refresh_from_db()
        self.assertEqual(new_book.quantity, 6)

    def test_typed_new_book_reuses_matching_isbn(self):
        response = self.client.post(
            reverse("orders:create_supplier_order"),
            {
                "supplier": self.supplier.id,
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-book": "",
                "items-0-quantity_ordered": "2",
                "items-0-cost_each": "6.00",
                "items-0-new_title": "Existing Book Entered Again",
                "items-0-new_author": "Someone Else",
                "items-0-new_isbn": "1111111111",
                "items-0-new_price": "",
                "items-0-new_shelf_location": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Book.objects.filter(isbn="1111111111").count(), 1)
        order = SupplierOrder.objects.latest("id")
        self.assertEqual(order.items.get().book_id, self.book.id)
