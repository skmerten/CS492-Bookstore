@echo off
title CS492 Bookstore Setup and Launcher
cd /d "%~dp0"

echo ==========================================
echo       CS492 Bookstore
echo       Setup and Launcher
echo ==========================================
echo.

REM Check for Python
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PYTHON=py
) else (
    where python >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set PYTHON=python
    ) else (
        echo ERROR: Python was not found.
        echo.
        echo Please install Python 3.12 or later from:
        echo https://www.python.org/downloads/
        echo.
        echo During installation, select:
        echo "Add Python to PATH"
        echo.
        pause
        exit /b 1
    )
)

echo Python found.
echo.

REM Create virtual environment if needed
if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    %PYTHON% -m venv .venv

    if errorlevel 1 (
        echo ERROR: Unable to create virtual environment.
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo Installing project requirements...
python -m pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Package installation failed.
    pause
    exit /b 1
)

REM Create .env if it does not exist
if not exist ".env" (
    echo.
    echo Creating local .env file...

    for /f "delims=" %%i in ('python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"') do set SECRET_KEY=%%i

    echo DJANGO_SECRET_KEY="%SECRET_KEY%" > .env

    echo Django development secret key generated.
) else (
    echo.
    echo Existing .env file found. Leaving it unchanged.
)

echo.
echo Preparing local database...
python manage.py migrate

if errorlevel 1 (
    echo.
    echo ERROR: Database migration failed.
    pause
    exit /b 1
)

echo.
echo Checking Django configuration...
python manage.py check

if errorlevel 1 (
    echo.
    echo ERROR: Django configuration check failed.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Setup complete!
echo.
echo Server:
echo http://127.0.0.1:8000/
echo.
echo Press CTRL+C to stop the server.
echo ==========================================
echo.

start "" http://127.0.0.1:8000/

python manage.py runserver

pause