from datetime import datetime
from pathlib import Path
import sqlite3

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

#Keeps the ten most recent local database backups.
MAX_BACKUPS = 10

class Command(BaseCommand):
    help = "Create a timestamped backup of the local SQLite database."

    def handle(self, *args, **options):
        database_config = settings.DATABASES["default"]

        #Command is designed for a local SQLite database for school project.
        if database_config["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError(
                "This command supports only the local SQLite database."
            )

        #Get the location of the local database file.
        database_path = Path(database_config["NAME"])

        #Stop before creating a backup if database file does note exist.
        if not database_path.is_file():
            raise CommandError(
                f"Local database file was not found: {database_path}"
            )

        #Create backups folder in the project when one does not exist.
        backup_directory = Path(settings.BASE_DIR) / "backups"
        backup_directory.mkdir(exist_ok=True)

        #Include the current date and time so each backup has a unique file name.
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = (
            backup_directory
            / f"bookstore_backup_{timestamp}.sqlite3"
        )

        #Use SQLite backup feature to create a consistent database copy
        with sqlite3.connect(database_path) as source_database:
            with sqlite3.connect(backup_path) as backup_database:
                source_database.backup(backup_database)

        #Find project backup files with the newest backup first
        backup_files = sorted(
            backup_directory.glob("bookstore_backup_*.sqlite3"),
            key=lambda backup_file: backup_file.stat().st_mtime,
            reverse=True,
        )

        #Remove backups older than ten most recent files.
        for old_backup in backup_files[MAX_BACKUPS:]:
            old_backup.unlink()

            #Report each removed backup in the terminal.
            self.stdout.write(
                self.style.WARNING(
                    f"Old backup removed:{old_backup.name}"
                )
            )

        #Display the backup location after command succeeds.
        self.stdout.write(
            self.style.SUCCESS(
                f"Database backup created: {backup_path}"
            )
        )