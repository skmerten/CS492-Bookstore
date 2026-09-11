# CS492-Bookstore
Bookstore Capstone Project

## Local setup

Before running the project, create a local `.env` file for the Django secret key.

1. Copy `.env.example`.
2. Rename the copied file to `.env`.
3. Replace the placeholder value with a private development key.

Do not commit the `.env` file. It is ignored by Git because it contains private configuration.

To create a development key, run this command from the project folder:

```powershell
py -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

Then place the generated value in `.env` like this: 
    DJANGO_SECRET_KEY="paste-the-generated-key-here"
