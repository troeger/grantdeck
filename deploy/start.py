import os

import django
from django.core.management import call_command


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "grantdeck.settings")
    django.setup()
    call_command("migrate", interactive=False)
    os.execvp(
        "gunicorn",
        ["gunicorn", "grantdeck.wsgi:application", "--bind", "0.0.0.0:8000"],
    )


if __name__ == "__main__":
    main()
