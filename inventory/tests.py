"""Inventory browsing, employee CRUD, and CSV import behavior."""

from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Book


class InventoryViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.book = Book.objects.create(
            title="The Night Library", author="Morgan Reed", isbn="9780000000001",
            price=Decimal("14.95"), quantity=8, shelf_location="A1",
        )
        cls.other = Book.objects.create(
            title="Garden Notes", author="Avery Stone", isbn="9780000000002",
            price=Decimal("9.50"), quantity=2,
        )
        cls.employee = get_user_model().objects.create_user(
            username="inventory_employee", password="test-password"
        )

    def form_data(self, **changes):
        return {
            "title": "A New Book", "author": "Test Writer", "isbn": "9780000000003",
            "price": "12.99", "quantity": "4", "shelf_location": "B2", **changes,
        }

    def test_anonymous_visitor_can_browse_and_search_title_author_or_isbn(self):
        url = reverse("books")
        self.assertContains(self.client.get(url), self.book.title)
        for term in ("NIGHT", "morgan", "9780000000001"):
            with self.subTest(term=term):
                response = self.client.get(url, {"search": term})
                self.assertContains(response, self.book.title)
                self.assertNotContains(response, self.other.title)
        self.assertEqual(list(self.client.get(url, {"search": "absent"}).context["books"]), [])

    def test_employee_management_pages_require_login(self):
        for url in (
            reverse("add_book"),
            reverse("edit_book", args=[self.book.pk]),
            reverse("delete_book", args=[self.book.pk]),
        ):
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"/login/?next={url}")
        self.assertRedirects(
            self.client.post(reverse("delete_book", args=[self.book.pk])),
            f"/login/?next={reverse('delete_book', args=[self.book.pk])}",
        )
        self.assertTrue(Book.objects.filter(pk=self.book.pk).exists())

    def test_employee_can_add_and_edit_book(self):
        self.client.force_login(self.employee)
        self.assertRedirects(self.client.post(reverse("add_book"), self.form_data()), reverse("books"))
        created = Book.objects.get(isbn="9780000000003")
        self.assertEqual(created.price, Decimal("12.99"))
        self.assertEqual(created.quantity, 4)

        self.assertRedirects(
            self.client.post(reverse("edit_book", args=[created.pk]), self.form_data(
                title="Revised Title", quantity="7", price="11.25"
            )), reverse("books"),
        )
        created.refresh_from_db()
        self.assertEqual((created.title, created.quantity, created.price),
                         ("Revised Title", 7, Decimal("11.25")))

    def test_invalid_book_form_does_not_save(self):
        self.client.force_login(self.employee)
        response = self.client.post(reverse("add_book"), self.form_data(title="", price="not a price"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("title", response.context["form"].errors)
        self.assertIn("price", response.context["form"].errors)
        self.assertFalse(Book.objects.filter(isbn="9780000000003").exists())

        response = self.client.post(
            reverse("edit_book", args=[self.book.pk]),
            self.form_data(title="", quantity="not an integer"),
        )
        self.assertEqual(response.status_code, 200)
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "The Night Library")

    def test_delete_requires_post_and_unknown_book_returns_404(self):
        self.client.force_login(self.employee)
        url = reverse("delete_book", args=[self.book.pk])
        self.client.get(url)
        self.assertTrue(Book.objects.filter(pk=self.book.pk).exists())
        self.assertRedirects(self.client.post(url), reverse("books"))
        self.assertFalse(Book.objects.filter(pk=self.book.pk).exists())
        self.assertEqual(self.client.get(reverse("edit_book", args=[99999])).status_code, 404)


class ImportBooksCommandTests(TestCase):
    def test_import_creates_then_updates_matching_isbn_without_duplicate(self):
        csv_content = (
            "isbn,title,author,price,quantity,shelf_location\n"
            "9780000000010,First Title,First Author,10.50,4,C3\n"
        )
        with TemporaryDirectory() as folder:
            csv_file = Path(folder) / "books.csv"
            csv_file.write_text(csv_content, encoding="utf-8")
            output = StringIO()
            call_command("import_books", str(csv_file), stdout=output)
            self.assertIn("1 created, 0 updated", output.getvalue())
            book = Book.objects.get(isbn="9780000000010")
            self.assertEqual((book.price, book.quantity), (Decimal("10.50"), 4))

            csv_file.write_text(csv_content.replace("First Title", "Revised Title")
                                .replace(",4,C3", ",9,D4"), encoding="utf-8")
            output = StringIO()
            call_command("import_books", str(csv_file), stdout=output)
            book.refresh_from_db()
            self.assertIn("0 created, 1 updated", output.getvalue())
            self.assertEqual((book.title, book.quantity, book.shelf_location),
                             ("Revised Title", 9, "D4"))
            self.assertEqual(Book.objects.filter(isbn=book.isbn).count(), 1)


class SiteAuthenticationTests(TestCase):
    def test_home_is_public_and_employee_login_and_logout_work(self):
        employee = get_user_model().objects.create_user(
            username="site_employee", password="test-password"
        )
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        login_url = reverse("login")
        self.assertEqual(self.client.get(login_url).status_code, 200)
        self.assertRedirects(self.client.post(login_url, {
            "username": employee.username, "password": "test-password"
        }), reverse("home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), employee.pk)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_wrong_password_does_not_log_in(self):
        get_user_model().objects.create_user("site_employee", password="test-password")
        response = self.client.post(reverse("login"), {
            "username": "site_employee", "password": "wrong-password"
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
