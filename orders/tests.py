from decimal import Decimal
from unittest import expectedFailure

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


class VendorAndOrderBoundaryTests(TestCase):
    def setUp(self):
        self.employee = get_user_model().objects.create_user("buyer", password="test-password")
        self.supplier = Supplier.objects.create(name="Existing Supplier")
        self.book = Book.objects.create(
            title="Matching Title", author="Matching Author", isbn="9780000000100",
            price=Decimal("19.00"), quantity=5,
        )

    def order_data(self, **changes):
        return {
            "supplier": self.supplier.pk,
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
            "items-0-book": self.book.pk,
            "items-0-quantity_ordered": "2", "items-0-cost_each": "4.50",
            **changes,
        }

    def test_all_employee_order_and_vendor_pages_require_login(self):
        customer = Customer.objects.create(full_name="Request Customer")
        customer_request = CustomerRequest.objects.create(customer=customer, requested_title="Book")
        order = SupplierOrder.objects.create(supplier=self.supplier)
        for url in (
            reverse("orders:create_customer_request"),
            reverse("orders:customer_request_log"),
            reverse("orders:customer_request_detail", args=[customer_request.pk]),
            reverse("orders:create_supplier_order_for_request", args=[customer_request.pk]),
            reverse("orders:supplier_list"), reverse("orders:create_supplier"),
            reverse("orders:supplier_order_list"), reverse("orders:create_supplier_order"),
            reverse("orders:supplier_order_detail", args=[order.pk]),
            reverse("orders:receive_supplier_order", args=[order.pk]),
            reverse("orders:cancel_supplier_order", args=[order.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.post(reverse("orders:receive_supplier_order", args=[order.pk])).status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, SupplierOrder.Status.ORDERED)

    def test_create_vendor_validates_name_and_lists_saved_vendor(self):
        self.client.force_login(self.employee)
        self.assertEqual(self.client.post(reverse("orders:create_supplier"), {"name": ""}).status_code, 200)
        self.assertEqual(Supplier.objects.count(), 1)
        response = self.client.post(reverse("orders:create_supplier"), {
            "name": "New Supplier", "contact_name": "Alex", "email": "alex@example.com",
            "phone": "555-0101", "address": "Main Street",
        })
        self.assertRedirects(response, reverse("orders:supplier_list"))
        self.assertContains(self.client.get(reverse("orders:supplier_list")), "New Supplier")

    def test_po_form_requires_supplier_and_a_real_line_item(self):
        self.client.force_login(self.employee)
        url = reverse("orders:create_supplier_order")
        missing_supplier = self.order_data(supplier="")
        self.assertEqual(self.client.post(url, missing_supplier).status_code, 200)
        blank_line = self.order_data(**{
            "items-0-book": "", "items-0-quantity_ordered": "", "items-0-cost_each": ""
        })
        response = self.client.post(url, blank_line)
        self.assertEqual(response.status_code, 200)
        formset = response.context["item_formset"]
        self.assertTrue(formset.non_form_errors() or any(formset.errors))
        self.assertFalse(SupplierOrder.objects.exists())

    def test_po_rejects_book_conflict_for_title_or_isbn(self):
        self.client.force_login(self.employee)
        url = reverse("orders:create_supplier_order")
        for changes in (
            {"items-0-new_title": "Another Book"},
            {"items-0-new_isbn": "9780000000999"},
        ):
            with self.subTest(changes=changes):
                response = self.client.post(url, self.order_data(**changes))
                self.assertEqual(response.status_code, 200)
                self.assertFalse(SupplierOrder.objects.exists())

    @expectedFailure  # Existing form only sets HTML min=1; server accepts quantity 0.
    def test_po_rejects_zero_quantity(self):
        self.client.force_login(self.employee)
        response = self.client.post(reverse("orders:create_supplier_order"),
                                    self.order_data(**{"items-0-quantity_ordered": "0"}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SupplierOrder.objects.exists())

    @expectedFailure  # Existing form only sets HTML min=0; server accepts negative cost.
    def test_po_rejects_negative_vendor_cost(self):
        self.client.force_login(self.employee)
        response = self.client.post(reverse("orders:create_supplier_order"),
                                    self.order_data(**{"items-0-cost_each": "-0.01"}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SupplierOrder.objects.exists())

    def test_new_book_line_reuses_title_and_author_and_stores_book_metadata(self):
        self.client.force_login(self.employee)
        data = self.order_data(**{
            "items-0-book": "", "items-0-new_title": "matching title",
            "items-0-new_author": "matching author", "items-0-quantity_ordered": "1",
        })
        self.assertEqual(self.client.post(reverse("orders:create_supplier_order"), data).status_code, 302)
        self.assertEqual(SupplierOrderItem.objects.get().book_id, self.book.pk)
        self.assertEqual(Book.objects.count(), 1)

        new_data = self.order_data(**{
            "items-0-book": "", "items-0-new_title": "Never Stocked",
            "items-0-new_author": "New Author", "items-0-new_isbn": "9780000000300",
            "items-0-new_price": "24.99", "items-0-new_shelf_location": "D2",
        })
        self.client.post(reverse("orders:create_supplier_order"), new_data)
        new_book = Book.objects.get(isbn="9780000000300")
        self.assertEqual((new_book.quantity, new_book.price, new_book.shelf_location),
                         (0, Decimal("24.99"), "D2"))

    def test_deleted_extra_line_is_not_saved_and_lists_show_created_order(self):
        self.client.force_login(self.employee)
        data = self.order_data(**{
            "items-TOTAL_FORMS": "2",
            "items-1-book": self.book.pk,
            "items-1-quantity_ordered": "12",
            "items-1-cost_each": "6.00",
            "items-1-DELETE": "on",
        })
        self.client.post(reverse("orders:create_supplier_order"), data)
        order = SupplierOrder.objects.get()
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.total_cost, Decimal("9.00"))
        self.assertContains(self.client.get(reverse("orders:supplier_order_list")),
                            "Existing Supplier")
        self.assertContains(self.client.get(reverse("orders:supplier_order_detail", args=[order.pk])),
                            "Matching Title")

    def test_save_vendor_then_create_unlinked_po_preserves_vendor_selection(self):
        self.client.force_login(self.employee)
        response = self.client.post(reverse("orders:create_supplier"), {
            "name": "New Vendor", "save_and_order": "1"
        })
        new_vendor = Supplier.objects.get(name="New Vendor")
        expected = reverse("orders:create_supplier_order") + f"?supplier={new_vendor.pk}"
        self.assertRedirects(response, expected)
        page = self.client.get(expected)
        self.assertEqual(page.context["order_form"]["supplier"].value(), str(new_vendor.pk))

    def test_receive_cancel_actions_are_post_only_and_inventory_updates_once(self):
        self.client.force_login(self.employee)
        order = SupplierOrder.objects.create(supplier=self.supplier)
        SupplierOrderItem.objects.create(supplier_order=order, book=self.book,
                                         quantity_ordered=3, cost_each=Decimal("4.50"))
        receive = reverse("orders:receive_supplier_order", args=[order.pk])
        cancel = reverse("orders:cancel_supplier_order", args=[order.pk])
        self.client.get(receive)
        self.client.get(cancel)
        order.refresh_from_db()
        self.assertEqual(order.status, SupplierOrder.Status.ORDERED)

        self.client.post(receive)
        self.client.post(receive)
        self.client.post(cancel)
        self.book.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.book.quantity, 8)
        self.assertEqual(order.status, SupplierOrder.Status.RECEIVED)
        self.assertTrue(order.inventory_updated)

    def test_cancelled_order_cannot_update_stock_through_receive_view(self):
        self.client.force_login(self.employee)
        order = SupplierOrder.objects.create(supplier=self.supplier)
        SupplierOrderItem.objects.create(supplier_order=order, book=self.book,
                                         quantity_ordered=2, cost_each=Decimal("4.50"))
        self.client.post(reverse("orders:cancel_supplier_order", args=[order.pk]))
        self.client.post(reverse("orders:receive_supplier_order", args=[order.pk]))
        self.book.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(order.status, SupplierOrder.Status.CANCELLED)
        self.assertEqual(self.book.quantity, 5)

    def test_unknown_request_or_purchase_order_is_404(self):
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(reverse("orders:customer_request_detail", args=[99999])).status_code, 404)
        self.assertEqual(self.client.get(reverse("orders:supplier_order_detail", args=[99999])).status_code, 404)


class RequestValidationTests(TestCase):
    def setUp(self):
        self.employee = get_user_model().objects.create_user("employee", password="test-password")
        self.client.force_login(self.employee)
        self.customer = Customer.objects.create(full_name="Jamie", email="jamie@example.com")
        self.request_record = CustomerRequest.objects.create(
            customer=self.customer, requested_title="Book Title", requested_author="Writer"
        )

    def test_request_needs_contact_and_book_title_and_reuses_exact_customer(self):
        url = reverse("orders:create_customer_request")
        data = {"full_name": "Jamie", "email": "", "phone": "",
                "requested_title": "Another Book", "requested_author": ""}
        self.assertContains(self.client.post(url, data), "Enter an email or phone number")
        self.assertEqual(CustomerRequest.objects.count(), 1)
        data.update(email="jamie@example.com", requested_title="")
        self.assertEqual(self.client.post(url, data).status_code, 200)
        data["requested_title"] = "Another Book"
        self.assertRedirects(self.client.post(url, data), reverse("orders:customer_request_log"))
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(CustomerRequest.objects.get(requested_title="Another Book").status,
                         CustomerRequest.Status.PENDING)

    def test_request_edit_rejects_manually_setting_approved_or_completed(self):
        url = reverse("orders:customer_request_detail", args=[self.request_record.pk])
        for status in ("Approved", "Completed"):
            with self.subTest(status=status):
                response = self.client.post(url, {
                    "requested_title": "Book Title", "requested_author": "Writer", "status": status,
                })
                self.assertEqual(response.status_code, 200)
                self.request_record.refresh_from_db()
                self.assertEqual(self.request_record.status, CustomerRequest.Status.PENDING)

    def test_cancelled_request_can_reopen_and_then_link_po(self):
        url = reverse("orders:customer_request_detail", args=[self.request_record.pk])
        self.client.post(url, {"requested_title": "Book Title", "requested_author": "Writer",
                               "status": "Cancelled"})
        po_url = reverse("orders:create_supplier_order_for_request", args=[self.request_record.pk])
        self.assertEqual(self.client.get(po_url).status_code, 302)
        self.client.post(url, {"requested_title": "Book Title", "requested_author": "Writer",
                               "status": "Pending"})
        self.assertEqual(self.client.get(po_url).status_code, 200)

    def test_request_log_shows_po_link_and_completed_status_after_receive(self):
        supplier = Supplier.objects.create(name="Vendor")
        book = Book.objects.create(title="Book Title", author="Writer", quantity=0)
        order = SupplierOrder.objects.create(supplier=supplier)
        SupplierOrderItem.objects.create(supplier_order=order, book=book,
                                         quantity_ordered=2, cost_each=Decimal("5.00"))
        self.request_record.purchase_order = order
        self.request_record.status = CustomerRequest.Status.APPROVED
        self.request_record.save(update_fields=["purchase_order", "status"])
        self.client.post(reverse("orders:receive_supplier_order", args=[order.pk]))
        self.request_record.refresh_from_db()
        self.assertEqual(self.request_record.status, CustomerRequest.Status.COMPLETED)
        log = self.client.get(reverse("orders:customer_request_log"))
        self.assertContains(log, f"PO #{order.pk}")
        self.assertContains(log, "Completed")

    def test_linked_po_can_select_existing_matching_book(self):
        supplier = Supplier.objects.create(name="Vendor")
        book = Book.objects.create(title="Book Title", author="Writer", quantity=5)
        url = reverse("orders:create_supplier_order_for_request", args=[self.request_record.pk])
        response = self.client.post(url, {
            "supplier": supplier.pk,
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
            "items-0-book": book.pk,
            "items-0-quantity_ordered": "2", "items-0-cost_each": "7.00",
        })
        self.assertEqual(response.status_code, 302)
        self.request_record.refresh_from_db()
        self.assertEqual(self.request_record.status, CustomerRequest.Status.APPROVED)
        self.assertEqual(self.request_record.purchase_order.items.get().book_id, book.pk)
