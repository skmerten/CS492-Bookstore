#!/bin/bash

cd "$(dirname "$0")"

clear

echo "=========================================="
echo "      CS492 Bookstore"
echo "      Setup and Launcher"
echo "=========================================="
echo

# Check for Python
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo "ERROR: Python was not found."
    echo
    echo "Please install Python 3.12 or later from:"
    echo "https://www.python.org/downloads/"
    echo
    read -p "Press Enter to close..."
    exit 1
fi

echo "Python found."
echo

# Create virtual environment if needed
if [ ! -f ".venv/bin/python" ]; then
    echo "Creating Python virtual environment..."
    "$PYTHON" -m venv .venv

    if [ $? -ne 0 ]; then
        echo "ERROR: Unable to create virtual environment."
        read -p "Press Enter to close..."
        exit 1
    fi
fi

echo "Activating virtual environment..."
source .venv/bin/activate

echo
echo "Installing project requirements..."
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo
    echo "ERROR: Package installation failed."
    read -p "Press Enter to close..."
    exit 1
fi

# Create .env if needed
if [ ! -f ".env" ]; then
    echo
    echo "Creating local .env file..."

    SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")

    echo "DJANGO_SECRET_KEY=\"$SECRET_KEY\"" > .env

    echo "Django development secret key generated."
else
    echo
    echo "Existing .env file found. Leaving it unchanged."
fi

echo
echo "Preparing local database..."
python manage.py migrate

if [ $? -ne 0 ]; then
    echo
    echo "ERROR: Database migration failed."
    read -p "Press Enter to close..."
    exit 1
fi

echo
echo "Checking Django configuration..."
python manage.py check

if [ $? -ne 0 ]; then
    echo
    echo "ERROR: Django configuration check failed."
    read -p "Press Enter to close..."
    exit 1
fi

echo
echo "=========================================="
echo "Setup complete!"
echo
echo "Server:"
echo "http://127.0.0.1:8000/"
echo
echo "Press Control+C to stop the server."
echo "=========================================="
echo

open "http://127.0.0.1:8000/"

python manage.py runserver