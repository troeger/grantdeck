from dataclasses import dataclass
from datetime import date, datetime, timezone

from django.db import IntegrityError, transaction
from django.db.models import F

from apps.usage.models import DailyUsage, UsageEvent


@dataclass(frozen=True)
class UsageRecord:
    request_id: str
    user_identifier: str
    project_identifier: int
    project_shortcut: str
    model_name: str
    route_name: str
    token_count: int
    response_code: int | None
    occurred_at: datetime

    @property
    def day(self) -> date:
        return self.occurred_at.astimezone(timezone.utc).date()


def record_usage(record: UsageRecord) -> bool:
    """Persist one ALS record exactly once and update its daily aggregate."""
    with transaction.atomic():
        try:
            with transaction.atomic():
                UsageEvent.objects.create(
                    request_id=record.request_id,
                    user_identifier=record.user_identifier,
                    project_identifier=record.project_identifier,
                    project_shortcut=record.project_shortcut,
                    model_name=record.model_name,
                    route_name=record.route_name,
                    token_count=record.token_count,
                    response_code=record.response_code,
                    occurred_at=record.occurred_at,
                )
        except IntegrityError:
            return False

        daily, created = DailyUsage.objects.get_or_create(
            day=record.day,
            user_identifier=record.user_identifier,
            project_identifier=record.project_identifier,
            project_shortcut=record.project_shortcut,
            model_name=record.model_name,
            defaults={
                'token_count': record.token_count,
                'request_count': 1,
            },
        )
        if not created:
            DailyUsage.objects.filter(pk=daily.pk).update(
                token_count=F('token_count') + record.token_count,
                request_count=F('request_count') + 1,
            )

    return True
