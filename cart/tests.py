"""Session cart behavior at the public endpoints."""

from decimal import Decimal
from unittest import expectedFailure

from django.test import TestCase
from django.urls import reverse

from inventory.models import Book


class CartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.book = Book.objects.create(title="Cart Book", price=Decimal("12.50"), quantity=5)
        cls.no_price = Book.objects.create(title="Unpriced Book", quantity=3)

    def test_add_caps_at_available_stock_and_counts_cart_copies(self):
        url = reverse("cart:add", args=[self.book.pk])
        self.assertRedirects(self.client.post(url, {"quantity": "3"}), reverse("books"))
        self.client.post(url, {"quantity": "4"})
        self.assertEqual(self.client.session["cart"][str(self.book.pk)], 5)
        response = self.client.get(reverse("cart:detail"))
        self.assertEqual(response.context["subtotal"], Decimal("62.50"))
        self.assertEqual(response.context["cart_count"], 5)

    def test_invalid_add_quantity_does_not_change_cart(self):
        url = reverse("cart:add", args=[self.book.pk])
        for invalid in ("0", "-1", "letters"):
            with self.subTest(quantity=invalid):
                response = self.client.post(url, {"quantity": invalid})
                self.assertRedirects(response, reverse("books"))
                self.assertNotIn(str(self.book.pk), self.client.session.get("cart", {}))

    def test_update_caps_quantity_then_zero_removes_item(self):
        self.client.post(reverse("cart:add", args=[self.book.pk]), {"quantity": "2"})
        update = reverse("cart:update", args=[self.book.pk])
        self.client.post(update, {"quantity": "99"})
        self.assertEqual(self.client.session["cart"][str(self.book.pk)], 5)
        self.client.post(update, {"quantity": "0"})
        self.assertNotIn(str(self.book.pk), self.client.session["cart"])

    def test_non_numeric_update_removes_item(self):
        self.client.post(reverse("cart:add", args=[self.book.pk]), {"quantity": "2"})
        self.client.post(reverse("cart:update", args=[self.book.pk]), {"quantity": "not a number"})
        self.assertNotIn(str(self.book.pk), self.client.session["cart"])

    def test_remove_one_item_preserves_other_items_and_unpriced_book_has_zero_subtotal(self):
        self.client.post(reverse("cart:add", args=[self.book.pk]), {"quantity": "1"})
        self.client.post(reverse("cart:add", args=[self.no_price.pk]), {"quantity": "2"})
        self.client.post(reverse("cart:remove", args=[self.book.pk]))
        response = self.client.get(reverse("cart:detail"))
        self.assertEqual(response.context["subtotal"], Decimal("0.00"))
        self.assertEqual(response.context["cart_count"], 2)
        self.assertEqual(list(self.client.session["cart"]), [str(self.no_price.pk)])

    def test_cart_mutations_reject_get_and_missing_book_returns_404(self):
        for name in ("add", "remove", "update"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(f"cart:{name}", args=[self.book.pk])).status_code, 405)
        self.assertEqual(self.client.post(reverse("cart:add", args=[99999])).status_code, 404)

    @expectedFailure  # Current add view stores a zero-quantity entry when stock is zero.
    def test_out_of_stock_book_is_not_added_to_cart(self):
        unavailable = Book.objects.create(title="Unavailable", quantity=0)
        self.client.post(reverse("cart:add", args=[unavailable.pk]), {"quantity": "1"})
        self.assertNotIn(str(unavailable.pk), self.client.session.get("cart", {}))
