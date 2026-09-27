from datetime import datetime, timezone

from django.conf import settings
from django.http import HttpResponse
from prometheus_client import CollectorRegistry, Gauge, generate_latest

from apps.usage.models import DailyUsage


def metrics_response(request):
    configured_token = settings.USAGE_METRICS_TOKEN
    supplied_token = request.headers.get('X-Metrics-Token', '')
    if not supplied_token:
        supplied_token = request.headers.get('Authorization', '')
        if supplied_token.lower().startswith('bearer '):
            supplied_token = supplied_token[7:]
    if not configured_token or supplied_token != configured_token:
        return HttpResponse(status=403)

    today = datetime.now(timezone.utc).date()
    registry = CollectorRegistry()
    metric = Gauge(
        'grantdeck_api_tokens_used',
        'Tokens consumed by API users during the current UTC day.',
        labelnames=['user', 'project', 'model'],
        registry=registry,
    )
    for row in DailyUsage.objects.filter(day=today).iterator():
        metric.labels(row.user_identifier, row.project_shortcut, row.model_name).set(row.token_count)
    return HttpResponse(
        generate_latest(registry),
        content_type='text/plain; version=0.0.4; charset=utf-8',
    )
