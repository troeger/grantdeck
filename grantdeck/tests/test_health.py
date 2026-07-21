import pytest


pytestmark = pytest.mark.django_db


def test_healthz_returns_ok(client):
    response = client.get('/healthz/')

    assert response.status_code == 200
    assert response.content == b''


def test_readyz_returns_ok(client):
    response = client.get('/readyz/')

    assert response.status_code == 200
    assert response.content == b''


def test_readyz_returns_unavailable_when_database_check_fails(client, monkeypatch):
    monkeypatch.setattr('grantdeck.views.database_ready', lambda: False)

    response = client.get('/readyz/')

    assert response.status_code == 503
    assert response.content == b''
