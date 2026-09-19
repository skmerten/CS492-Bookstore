import csv

from django.core.management.base import BaseCommand
from inventory.models import Book


class Command(BaseCommand):
    help = "Import books from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help="Path to the CSV file"
        )

    def handle(self, *args, **options):
        csv_file = options["csv_file"]

        created_count = 0
        updated_count = 0

        with open(csv_file, newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            for row in reader:

                book, created = Book.objects.update_or_create(
                    isbn=row["isbn"].strip(),
                    defaults={
                        "title": row["title"].strip(),
                        "author": row["author"].strip(),
                        "price": row["price"],
                        "quantity": int(row["quantity"]),
                        "shelf_location": row["shelf_location"].strip(),
                    },
                )

                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Created: {book.title}"
                        )
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Updated: {book.title}"
                        )
                    )

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete: "
                f"{created_count} created, "
                f"{updated_count} updated."
            )
        )