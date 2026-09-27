from datetime import datetime, timezone

import pytest
from django.test import override_settings

from apps.usage.models import DailyUsage


pytestmark = pytest.mark.django_db


@override_settings(USAGE_METRICS_TOKEN='scrape-secret')
def test_metrics_exposes_daily_usage_with_bearer_auth(client):
    DailyUsage.objects.create(
        day=datetime.now(timezone.utc).date(), user_identifier='alice',
        project_identifier=7, project_shortcut='research', model_name='bht/large',
        token_count=123, request_count=2,
    )

    response = client.get('/metrics', HTTP_AUTHORIZATION='Bearer scrape-secret')

    assert response.status_code == 200
    assert b'grantdeck_api_tokens_used' in response.content
    assert b'user="alice"' in response.content
    assert b' 123.0' in response.content


@override_settings(USAGE_METRICS_TOKEN='scrape-secret')
def test_metrics_rejects_missing_authentication(client):
    assert client.get('/metrics').status_code == 403
