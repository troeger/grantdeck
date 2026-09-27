from datetime import datetime, timezone

import pytest

from apps.usage.models import DailyUsage, UsageEvent
from apps.usage.service import UsageRecord, record_usage


pytestmark = pytest.mark.django_db


def usage_record(request_id='request-1', token_count=42):
    return UsageRecord(
        request_id=request_id,
        user_identifier='alice',
        project_identifier=7,
        project_shortcut='research',
        model_name='bht/large',
        route_name='class-large',
        token_count=token_count,
        response_code=200,
        occurred_at=datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc),
    )


def test_record_usage_is_idempotent_and_aggregates():
    record = usage_record()

    assert record_usage(record) is True
    assert record_usage(record) is False
    assert UsageEvent.objects.count() == 1
    daily = DailyUsage.objects.get()
    assert daily.token_count == 42
    assert daily.request_count == 1


def test_record_usage_separates_models_and_users():
    record_usage(usage_record())
    record_usage(UsageRecord(
        request_id='request-2', user_identifier='bob', project_identifier=7,
        project_shortcut='research', model_name='bht/small', route_name='class-small',
        token_count=8, response_code=200,
        occurred_at=datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc),
    ))

    assert DailyUsage.objects.count() == 2
