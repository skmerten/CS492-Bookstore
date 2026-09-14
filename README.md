# CS492-Bookstore

Bookstore Capstone Project

This project is a Django web application developed for the CS492 Capstone Project. The instructions below are written for a computer that does not already have the project requirements installed.

## Prerequisites

Before beginning, install **Python 3.12**. Python 3.12 is recommended because it matches the Python version used by the deployed application.

A terminal will also be needed:

- **Windows:** PowerShell or Command Prompt
- **macOS/Linux:** Terminal

Verify that Python is installed before continuing.

### Windows

```powershell
py --version
```

### macOS/Linux

```bash
python3 --version
```

A Python 3.12.x installation is recommended.

---

## 1. Extract and Open the Project

Extract the submitted ZIP file to a folder on the computer.

Open a terminal and change into the extracted project folder that contains `manage.py`.

For example:

### Windows PowerShell

```powershell
cd "C:\path\to\Bookstore Project"
```

### macOS/Linux

```bash
cd "/path/to/Bookstore Project"
```

The correct project folder should contain files and folders similar to the following:

```text
Bookstore/
cart/
inventory/
orders/
sales/
templates/
manage.py
requirements.txt
README.md
.env.example
```

---

## 2. Create a Python Virtual Environment

A virtual environment keeps the packages required by this project separate from other Python installations and projects on the computer.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If Python 3.12 is the only installed Python version, the following also works:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Windows Command Prompt

```cmd
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

After activation, the terminal prompt should normally begin with `(.venv)`.

Example:

```text
(.venv) user@computer Bookstore Project %
```

Verify the active Python version:

```bash
python --version
```

---

## 3. Upgrade pip

With the virtual environment active, run:

```bash
python -m pip install --upgrade pip
```

---

## 4. Install the Project Requirements

Install all required Python packages from `requirements.txt`:

```bash
python -m pip install -r requirements.txt
```

No project packages need to be installed globally on the computer.

---

## 5. Local Setup

Before running the project, create a local `.env` file for the Django secret key.

1. Copy `.env.example`.
2. Rename the copied file to `.env`.
3. Replace the placeholder value with a private development key.

Do not commit the `.env` file. It is ignored by Git because it contains private configuration.

### Copy the environment template

#### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

#### Windows Command Prompt

```cmd
copy .env.example .env
```

#### macOS/Linux

```bash
cp .env.example .env
```

### Generate a Django development secret key

On Windows, run this command from the project folder while the virtual environment is active:

```powershell
py -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

If `py` does not use the active virtual environment, use:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

On macOS/Linux, run:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the generated value and place it in `.env` like this:

```text
DJANGO_SECRET_KEY="paste-the-generated-key-here"
```

Save the `.env` file before continuing.

---

## 6. Create the Local Database

The project uses **SQLite for local development by default**. PostgreSQL is not required to run the submitted project locally.

Run Django's database migrations:

```bash
python manage.py migrate
```

This creates the local `db.sqlite3` database and all required Django and application tables.

A successful migration will display multiple lines ending in `OK`.

---

## 7. Optional: Create an Administrator Account

An administrator account is not required to start the server, but it can be used to access Django's administrative interface.

Run:

```bash
python manage.py createsuperuser
```

Follow the prompts to create a username, email address, and password.

After the server is running, the administration page will be available at:

```text
http://127.0.0.1:8000/admin/
```

---

## 8. Verify the Django Configuration

Before starting the application, run:

```bash
python manage.py check
```

A correctly configured project should report:

```text
System check identified no issues (0 silenced).
```

---

## 9. Start the Development Server

Run:

```bash
python manage.py runserver
```

Django should display output similar to:

```text
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

Open a web browser and navigate to:

```text
http://127.0.0.1:8000/
```

The bookstore application should now be running locally.

To stop the development server, return to the terminal and press:

```text
Ctrl+C
```

---

## Returning to the Project Later

The virtual environment must be activated again each time a new terminal is opened.

### Windows PowerShell

```powershell
cd "C:\path\to\Bookstore Project"
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

### Windows Command Prompt

```cmd
cd "C:\path\to\Bookstore Project"
.venv\Scripts\activate.bat
python manage.py runserver
```

### macOS/Linux

```bash
cd "/path/to/Bookstore Project"
source .venv/bin/activate
python manage.py runserver
```

---

## Local Database vs. Deployed Database

The project's `settings.py` selects the database automatically:

- If no `DATABASE_URL` environment variable is present, Django uses the local SQLite database (`db.sqlite3`).
- If `DATABASE_URL` is present, Django uses the PostgreSQL database specified by that connection string.

For grading or local testing, **no PostgreSQL setup is necessary**. Following the instructions above uses SQLite automatically.

The production deployment uses PostgreSQL because the deployment environment is not intended for persistent SQLite database writes.

---

## Common Troubleshooting

### `python` or `py` is not recognized

Python is either not installed or is not available on the system PATH. Install Python and reopen the terminal before continuing.

### PowerShell will not activate `.venv`

If PowerShell reports that script execution is disabled, Command Prompt can be used instead:

```cmd
.venv\Scripts\activate.bat
```

Alternatively, PowerShell's execution policy can be adjusted according to the security requirements of the computer being used.

### `ModuleNotFoundError` for Django or another package

Confirm that the virtual environment is active and reinstall the requirements:

```bash
python -m pip install -r requirements.txt
```

### `DJANGO_SECRET_KEY` or environment configuration error

Confirm that:

1. `.env.example` was copied to `.env`.
2. `.env` contains a line in the following format:

```text
DJANGO_SECRET_KEY="your-generated-secret-key"
```

3. The `.env` file is saved in the same project folder as `manage.py`.

### `no such table` database error

Run the migrations:

```bash
python manage.py migrate
```

### Port 8000 is already in use

Django can be started on another port, such as port 8001:

```bash
python manage.py runserver 8001
```

Then browse to:

```text
http://127.0.0.1:8001/
```

## Quick Setup Summary

### Windows PowerShell

After extracting the ZIP file and opening PowerShell in the project folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
py -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# Paste the generated key into .env as DJANGO_SECRET_KEY="..."
python manage.py migrate
python manage.py check
python manage.py runserver
```

### macOS/Linux

After extracting the ZIP file and opening Terminal in the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# Paste the generated key into .env as DJANGO_SECRET_KEY="..."
python manage.py migrate
python manage.py check
python manage.py runserver
```

After the server starts, open **http://127.0.0.1:8000/** in a web browser.
