from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import Book
from sales.models import Customer
from .models import CustomerRequest, Supplier, SupplierOrder, SupplierOrderItem


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

    def test_existing_book_cannot_include_new_book_details(self):
        response = self.client.post(reverse("orders:create_supplier_order"), {
            "supplier": self.supplier.pk,
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-book": self.book.pk,
            "items-0-quantity_ordered": "2",
            "items-0-cost_each": "5.00",
            "items-0-new_author": "Wrong author",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SupplierOrder.objects.exists())


class CustomerRequestWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="employee", password="test-password"
        )
        self.client.login(username="employee", password="test-password")
        self.customer = Customer.objects.create(
            full_name="Request Customer", email="customer@example.com"
        )
        self.supplier = Supplier.objects.create(name="Vendor")
        self.request_record = CustomerRequest.objects.create(
            customer=self.customer,
            requested_title="Requested Novel",
            requested_author="Test Author",
        )

    def po_data(self):
        return {
            "supplier": self.supplier.pk,
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-book": "",
            "items-0-new_title": "Requested Novel",
            "items-0-new_author": "Test Author",
            "items-0-quantity_ordered": "3",
            "items-0-cost_each": "8.50",
        }

    def test_new_request_defaults_to_pending_and_employee_can_edit_or_reject(self):
        response = self.client.post(
            reverse("orders:create_customer_request"),
            {
                "full_name": "Another Customer",
                "email": "another@example.com",
                "phone": "",
                "requested_title": "Another Book",
                "requested_author": "Another Author",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CustomerRequest.objects.get(requested_title="Another Book").status, "Pending")

        edit_url = reverse("orders:customer_request_detail", args=[self.request_record.pk])
        response = self.client.post(edit_url, {
            "requested_title": "Corrected Title",
            "requested_author": "Corrected Author",
            "status": "Rejected",
        })
        self.assertEqual(response.status_code, 302)
        self.request_record.refresh_from_db()
        self.assertEqual(self.request_record.requested_title, "Corrected Title")
        self.assertEqual(self.request_record.status, "Rejected")
        self.assertNotContains(self.client.get(edit_url), "Create PO")

        response = self.client.post(edit_url, {
            "requested_title": "Requested Novel",
            "requested_author": "Test Author",
            "status": "Pending",
        })
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(edit_url), "Create PO")

    def test_po_from_request_prefills_book_and_completes_on_receipt_once(self):
        po_url = reverse("orders:create_supplier_order_for_request", args=[self.request_record.pk])
        page = self.client.get(po_url)
        self.assertContains(page, 'value="Requested Novel"')
        self.assertContains(page, 'value="Test Author"')

        response = self.client.post(po_url, self.po_data())
        self.assertEqual(response.status_code, 302)
        self.request_record.refresh_from_db()
        self.assertEqual(self.request_record.status, CustomerRequest.Status.APPROVED)
        order = self.request_record.purchase_order
        self.assertEqual(order.items.get().book.quantity, 0)

        # An old form submission must not create another PO for this request.
        self.assertEqual(self.client.post(po_url, self.po_data()).status_code, 302)
        self.assertEqual(SupplierOrder.objects.count(), 1)

        self.assertTrue(order.mark_received())
        self.request_record.refresh_from_db()
        self.assertEqual(self.request_record.status, CustomerRequest.Status.COMPLETED)
        book = order.items.get().book
        book.refresh_from_db()
        self.assertEqual(book.quantity, 3)
        self.assertFalse(order.mark_received())
        book.refresh_from_db()
        self.assertEqual(book.quantity, 3)

        # The manually editable status cannot override a received PO.
        response = self.client.post(reverse("orders:customer_request_detail", args=[self.request_record.pk]), {
            "requested_title": "Changed", "requested_author": "", "status": "Pending",
        })
        self.assertEqual(response.status_code, 302)
        self.request_record.refresh_from_db()
        self.assertEqual(self.request_record.status, CustomerRequest.Status.COMPLETED)

    def test_invalid_po_does_not_approve_request(self):
        po_url = reverse("orders:create_supplier_order_for_request", args=[self.request_record.pk])
        data = self.po_data()
        data["items-0-cost_each"] = ""
        response = self.client.post(po_url, data)
        self.assertEqual(response.status_code, 200)
        self.request_record.refresh_from_db()
        self.assertEqual(self.request_record.status, CustomerRequest.Status.PENDING)
        self.assertIsNone(self.request_record.purchase_order_id)

    def test_linked_po_cannot_replace_requested_book_with_another_title(self):
        po_url = reverse("orders:create_supplier_order_for_request", args=[self.request_record.pk])
        data = self.po_data()
        data["items-0-new_title"] = "Unrelated Book"
        response = self.client.post(po_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Include the requested title and author")
        self.assertFalse(SupplierOrder.objects.exists())

    def test_rejected_request_cannot_create_po_directly(self):
        self.request_record.status = CustomerRequest.Status.REJECTED
        self.request_record.save(update_fields=["status"])
        url = reverse("orders:create_supplier_order_for_request", args=[self.request_record.pk])
        self.assertEqual(self.client.post(url, self.po_data()).status_code, 302)
        self.assertFalse(SupplierOrder.objects.exists())

    def test_cancelling_linked_po_cancels_request(self):
        po_url = reverse("orders:create_supplier_order_for_request", args=[self.request_record.pk])
        self.client.post(po_url, self.po_data())
        self.request_record.refresh_from_db()
        self.request_record.purchase_order.cancel()
        self.request_record.refresh_from_db()
        self.assertEqual(self.request_record.status, CustomerRequest.Status.CANCELLED)

    def test_add_vendor_returns_to_request_po(self):
        url = reverse("orders:create_supplier",) + f"?request={self.request_record.pk}"
        response = self.client.post(url, {"name": "New Vendor", "save_and_order": "1"})
        self.assertRedirects(
            response,
            reverse("orders:create_supplier_order_for_request", args=[self.request_record.pk])
            + f"?supplier={Supplier.objects.get(name='New Vendor').pk}",
        )
