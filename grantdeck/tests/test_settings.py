import importlib

import pytest
from django.core.exceptions import ImproperlyConfigured

from grantdeck import settings


GDK_ENV_VARS = [
    'GDK_ENV',
    'GDK_SECRET_KEY',
    'GDK_DATABASE_URL',
    'GDK_ALLOWED_HOSTS',
    'GDK_OIDC_ENDPOINT',
    'GDK_OIDC_CLIENT_ID',
    'GDK_OIDC_CLIENT_SECRET',
    'GDK_STATIC_TOKEN_MAX_LIFETIME_DAYS',
]

PRODUCTION_ENV = {
    'GDK_SECRET_KEY': 'production-secret',
    'GDK_DATABASE_URL': 'postgres://user:pass@db.example:5432/grantdeck',
    'GDK_ALLOWED_HOSTS': 'grantdeck.example.test,grantdeck.internal',
    'GDK_OIDC_ENDPOINT': 'https://issuer.example.test',
    'GDK_OIDC_CLIENT_ID': 'client-id',
    'GDK_OIDC_CLIENT_SECRET': 'client-secret',
}


def reload_settings(monkeypatch, **env):
    for name in GDK_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return importlib.reload(settings)


@pytest.mark.parametrize('name', PRODUCTION_ENV)
def test_production_requires_environment(monkeypatch, name):
    env = PRODUCTION_ENV | {name: None}
    env = {key: value for key, value in env.items() if value is not None}

    with pytest.raises(ImproperlyConfigured, match=name):
        reload_settings(monkeypatch, **env)


@pytest.mark.parametrize('name', PRODUCTION_ENV)
def test_production_rejects_blank_required_values(monkeypatch, name):
    env = PRODUCTION_ENV | {name: ''}

    with pytest.raises(ImproperlyConfigured, match=name):
        reload_settings(monkeypatch, **env)


def test_production_settings_load_with_required_environment(monkeypatch):
    loaded = reload_settings(
        monkeypatch,
        **PRODUCTION_ENV,
        GDK_DEBUG='true',
    )

    assert loaded.DEBUG is False
    assert loaded.SECRET_KEY == 'production-secret'
    assert loaded.ALLOWED_HOSTS == ['grantdeck.example.test', 'grantdeck.internal']
    assert loaded.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql'
    assert loaded.SOCIAL_AUTH_OIDC_KEY == 'client-id'
    assert loaded.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https')
    assert loaded.USE_X_FORWARDED_HOST is True
    assert loaded.STATIC_TOKEN_MAX_LIFETIME_DAYS == 183
    assert loaded.STATIC_TOKEN_DEFAULT_LIFETIME_DAYS == 183


def test_development_settings_keep_local_defaults(monkeypatch):
    loaded = reload_settings(monkeypatch, GDK_ENV='development', GDK_DEBUG='false')

    assert loaded.DEBUG is True
    assert loaded.SECRET_KEY == 'dev-only-insecure-secret-key-change-me'
    assert loaded.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'
    assert loaded.DATABASES['default']['NAME'] == str(loaded.BASE_DIR / 'db.sqlite3')


def test_static_token_max_lifetime_can_be_configured(monkeypatch):
    loaded = reload_settings(
        monkeypatch,
        **PRODUCTION_ENV,
        GDK_STATIC_TOKEN_MAX_LIFETIME_DAYS='30',
    )

    assert loaded.STATIC_TOKEN_MAX_LIFETIME_DAYS == 30
    assert loaded.STATIC_TOKEN_DEFAULT_LIFETIME_DAYS == 30


def test_database_config_reads_gdk_database_url_in_development(monkeypatch):
    loaded = reload_settings(
        monkeypatch,
        GDK_ENV='development',
        GDK_DATABASE_URL='postgres://user:pass@db.example:5432/grantdeck',
    )

    database = loaded.database_config()['default']

    assert database['ENGINE'] == 'django.db.backends.postgresql'
    assert database['NAME'] == 'grantdeck'
    assert database['USER'] == 'user'
    assert database['PASSWORD'] == 'pass'
    assert database['HOST'] == 'db.example'
    assert database['PORT'] == 5432
