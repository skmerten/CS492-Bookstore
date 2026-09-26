# Local Database Backup and Recovery

## Purpose

This document explains how to back up and recover the local SQLite database used for class demonstrations and development.

Local backups may contain customer contact information, sales records, customer requests, and inventory data. Backup files must not be committed to GitHub.

## Create a Backup

1. Open a terminal in the project folder.
2. Run:

   ```powershell
   py manage.py backup_local_database
   ```

3. The command creates a timestamped backup file in the `backups` folder.

Example output:

```text
Database backup created: backups\bookstore_backup_YYYY-MM-DD_HH-MM-SS.sqlite3
```

## Backup Retention

- The backup command automatically keeps the ten most recent local backup files.
- When an eleventh backup is created, the command removes the oldest project backup file.
- Only files named `bookstore_backup_*.sqlite3` are removed.
- The `backups` folder is ignored by Git so backup data is not uploaded to the repository.

## Restore a Local Backup

> Warning: Restoring replaces the current local `db.sqlite3` database.

1. Stop the Django development server by pressing `Ctrl + C` in its terminal.
2. Create a new backup before restoring, if possible:

   ```powershell
   py manage.py backup_local_database
   ```

3. List available backups:

   ```powershell
   Get-ChildItem backups
   ```

4. Replace `BACKUP_FILE_NAME.sqlite3` below with the backup file you want to restore:

   ```powershell
   Copy-Item -LiteralPath "backups\BACKUP_FILE_NAME.sqlite3" -Destination "db.sqlite3" -Force
   ```

5. Confirm the database schema is current:

   ```powershell
   py manage.py migrate
   ```

6. Restart the website:

   ```powershell
   py manage.py runserver
   ```

7. Verify that the expected inventory, sales, and customer request records are present.

## Recovery Verification

Test recovery before a demonstration or final submission:

1. Create a local backup.
2. Restore that backup using the steps above.
3. Start the server.
4. Confirm the website opens and expected records are visible.

## Production Note

## Deployed PostgreSQL Database

The live Vercel deployment uses PostgreSQL through an external database provider.

The `backup_local_database` command is intentionally limited to the local SQLite database. It will not run when the project is connected to PostgreSQL through `DATABASE_URL`.

For the deployed database:

1. Identify the PostgreSQL provider through the Vercel project’s Storage or Integrations area.
2. Enable or review the provider’s managed backup and point-in-time recovery options, when available.
3. Record the provider’s backup-retention period and recovery procedure.
4. Test database recovery only in a non-production environment.
5. Keep database credentials and `DATABASE_URL` values out of source code, documentation, and GitHub.

The local SQLite backup process remains the supported process for class demonstrations and local development.