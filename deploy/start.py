import logging
import os
from importlib.metadata import version

import django
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command


def bootstrap_admin():
    username = os.environ.get('GDK_ADMIN_USERNAME', '').strip()
    if not username:
        return

    password = os.environ.get('GDK_ADMIN_PASSWORD', '')
    if not password:
        raise ImproperlyConfigured('GDK_ADMIN_PASSWORD must be set when GDK_ADMIN_USERNAME is configured')

    user_model = get_user_model()
    user = user_model.objects.filter(username=username).first()
    if user is not None:
        if not user.is_superuser:
            raise ImproperlyConfigured(
                f'GDK_ADMIN_USERNAME {username!r} already exists and is not a superuser'
            )
        return

    user_model.objects.create_superuser(
        username=username,
        email=os.environ.get('GDK_ADMIN_EMAIL', '').strip(),
        password=password,
    )


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "grantdeck.settings")
    django.setup()
    release_tag = os.environ.get('GDK_RELEASE_TAG') or version('grantdeck')
    logging.getLogger('apps').info('Starting GrantDeck version %s', release_tag)
    call_command("migrate", interactive=False)
    bootstrap_admin()
    os.execvp(
        "gunicorn",
        ["gunicorn", "grantdeck.wsgi:application", "--bind", "0.0.0.0:8000"],
    )


if __name__ == "__main__":
    main()
