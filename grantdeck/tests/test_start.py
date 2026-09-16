import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured

from deploy.start import bootstrap_admin


pytestmark = pytest.mark.django_db


def test_bootstrap_admin_creates_superuser(monkeypatch):
    monkeypatch.setenv('GDK_ADMIN_USERNAME', 'initial-admin')
    monkeypatch.setenv('GDK_ADMIN_EMAIL', 'admin@example.test')
    monkeypatch.setenv('GDK_ADMIN_PASSWORD', 'a-secure-password')

    bootstrap_admin()

    user = get_user_model().objects.get(username='initial-admin')
    assert user.is_active and user.is_staff and user.is_superuser
    assert user.email == 'admin@example.test'
    assert user.check_password('a-secure-password')


def test_bootstrap_admin_is_idempotent_and_does_not_reset_password(monkeypatch):
    user_model = get_user_model()
    user_model.objects.create_superuser('initial-admin', 'old@example.test', 'old-password')
    monkeypatch.setenv('GDK_ADMIN_USERNAME', 'initial-admin')
    monkeypatch.setenv('GDK_ADMIN_EMAIL', 'new@example.test')
    monkeypatch.setenv('GDK_ADMIN_PASSWORD', 'new-password')

    bootstrap_admin()

    user = user_model.objects.get(username='initial-admin')
    assert user.check_password('old-password')
    assert user.email == 'old@example.test'
    assert user_model.objects.filter(username='initial-admin').count() == 1


def test_bootstrap_admin_rejects_existing_non_superuser(monkeypatch):
    user_model = get_user_model()
    user_model.objects.create_user('initial-admin', password='password')
    monkeypatch.setenv('GDK_ADMIN_USERNAME', 'initial-admin')
    monkeypatch.setenv('GDK_ADMIN_PASSWORD', 'a-secure-password')

    with pytest.raises(ImproperlyConfigured, match='already exists'):
        bootstrap_admin()


def test_bootstrap_admin_requires_password(monkeypatch):
    monkeypatch.setenv('GDK_ADMIN_USERNAME', 'initial-admin')
    monkeypatch.delenv('GDK_ADMIN_PASSWORD', raising=False)

    with pytest.raises(ImproperlyConfigured, match='GDK_ADMIN_PASSWORD'):
        bootstrap_admin()


def test_bootstrap_admin_skips_when_unconfigured(monkeypatch):
    monkeypatch.delenv('GDK_ADMIN_USERNAME', raising=False)
    monkeypatch.delenv('GDK_ADMIN_PASSWORD', raising=False)

    bootstrap_admin()

    assert not get_user_model().objects.exists()
