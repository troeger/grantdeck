"""Read-only view of Envoy ratelimit's daily Redis counters."""

from datetime import datetime, timezone as datetime_timezone
from functools import lru_cache
import time
from types import SimpleNamespace

import redis
from django.conf import settings

from apps.authz.models import ProjectLimitClass
from apps.authz.quota_keys import LEGACY_MODEL_ROUTES, exported_route_name, redis_glob_escape


SECONDS_PER_DAY = 24 * 60 * 60
DESCRIPTOR_KEY = 'rule-0-match-0'


@lru_cache(maxsize=4)
def _redis_client(redis_url):
    if not redis_url:
        return None
    return redis.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
        health_check_interval=30,
    )


def _counter_for(client, route_name, descriptor_value, bucket_start):
    pattern = (
        f'*{redis_glob_escape(route_name)}*{DESCRIPTOR_KEY}_'
        f'{redis_glob_escape(descriptor_value)}_{bucket_start}'
    )
    keys = list(client.scan_iter(match=pattern, count=100))
    if len(keys) > 1:
        # Multiple domains for the same route/descriptor are ambiguous; don't
        # present a partial or potentially double-counted value.
        return None, True
    if not keys:
        return 0, False
    value = client.get(keys[0])
    if value is None:
        return 0, False
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None, True
    return (count, True) if count >= 0 else (None, True)


def current_usage(project, model_name, *, now=None, class_ids=None):
    """Return ``(consumed_tokens, reset_at)``; unavailable reads return Nones.

    New manifests key counters by the opaque project quota key and generated
    class/model route. While the currently deployed manifests still use the
    project shortcut and legacy route names, that verified format is used as a
    fallback.
    """
    client = _redis_client(getattr(settings, 'QUOTA_REDIS_URL', ''))
    if client is None:
        return None, None

    epoch = int(time.time() if now is None else now)
    bucket_start = (epoch // SECONDS_PER_DAY) * SECONDS_PER_DAY
    reset_at = datetime.fromtimestamp(bucket_start + SECONDS_PER_DAY, tz=datetime_timezone.utc)

    try:
        if project.limit_class_id and project.quota_key:
            # Route names are class-specific, but the opaque project key is
            # stable. Include any older class route's bucket so reassignment
            # within the same day does not reset that project's consumption.
            values = []
            if class_ids is None:
                class_ids = ProjectLimitClass.objects.values_list('pk', flat=True)
            for class_id in class_ids:
                policy_class = SimpleNamespace(pk=class_id)
                route = exported_route_name(policy_class, model_name)
                value, found = _counter_for(client, route, project.quota_key, bucket_start)
                if value is None:
                    return None, None
                if found:
                    values.append(value)
            if values:
                return sum(values), reset_at

        legacy_route = LEGACY_MODEL_ROUTES.get(model_name)
        if legacy_route and project.shortcut:
            value, found = _counter_for(client, legacy_route, project.shortcut, bucket_start)
            if found or value is None:
                return (value, reset_at) if value is not None else (None, None)

        # A successful scan with no key means no requests in the active UTC
        # daily bucket. The bucket epoch prevents stale prior-day values from
        # being added here, even while Redis retains them for TTL jitter.
        return 0, reset_at
    except (redis.RedisError, OSError, ValueError):
        return None, None


def rows_for_projects(projects):
    rows = []
    class_ids = list(ProjectLimitClass.objects.values_list('pk', flat=True))
    for project in projects:
        policy_class = project.limit_class
        limits = list(policy_class.model_limits.all()) if policy_class else []
        if not limits:
            rows.append({
                'project': project,
                'policy_class': policy_class,
                'model_name': None,
                'consumed_tokens': None,
                'daily_token_limit': None,
                'reset_at': None,
            })
            continue

        for model_limit in limits:
            consumed_tokens, reset_at = current_usage(
                project,
                model_limit.model_name,
                class_ids=class_ids,
            )
            rows.append({
                'project': project,
                'policy_class': policy_class,
                'model_name': model_limit.model_name,
                'consumed_tokens': consumed_tokens,
                'daily_token_limit': model_limit.daily_token_limit,
                'reset_at': reset_at,
            })
    return rows
