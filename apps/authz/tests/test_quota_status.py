from fnmatch import fnmatch
from types import SimpleNamespace

import pytest
import redis

from apps.authz import quota_status
from apps.authz.quota_keys import exported_route_name
from apps.authz.quota_status import current_usage


class FakeRedis:
    def __init__(self, values):
        self.values = values

    def scan_iter(self, *, match, count):
        return (key for key in self.values if fnmatch(key, match))

    def get(self, key):
        return self.values[key]


@pytest.fixture
def project():
    policy_class = SimpleNamespace(pk=17)
    return SimpleNamespace(
        limit_class=policy_class,
        limit_class_id=17,
        quota_key='qk_project_opaque',
        shortcut='admins',
    )


@pytest.fixture(autouse=True)
def stub_limit_classes(monkeypatch):
    monkeypatch.setattr(
        quota_status,
        'ProjectLimitClass',
        SimpleNamespace(objects=SimpleNamespace(values_list=lambda *_args, **_kwargs: [17])),
    )


def redis_key(route_name, identity, bucket_start=1_790_035_200):
    return (
        'envoy/default/https-sophia-api_httproute/bht-inference/'
        f'{route_name}/rule/0/match/0/sophia-api_rule-0-match-0_{identity}_{bucket_start}'
    )


def install_fake(monkeypatch, values):
    monkeypatch.setattr('apps.authz.quota_status._redis_client', lambda _url: FakeRedis(values))


def test_reads_current_deployed_counter_after_opaque_key_misses(monkeypatch, project):
    install_fake(monkeypatch, {
        redis_key('inference-medium-grantdeck', 'admins'): '19',
    })

    consumed, reset_at = current_usage(project, 'bht/medium', now=1_790_035_300)
    assert consumed == 19
    assert reset_at.timestamp() == 1_790_121_600


def test_prefers_new_opaque_key_counter(monkeypatch, project):
    route = exported_route_name(project.limit_class, 'bht/medium')
    install_fake(monkeypatch, {
        redis_key(route, project.quota_key): '42',
        redis_key('inference-medium-grantdeck', project.shortcut): '19',
    })

    consumed, _ = current_usage(project, 'bht/medium', now=1_790_035_300)
    assert consumed == 42


def test_sums_opaque_key_counters_across_class_route_changes(monkeypatch, project):
    route_for_previous_class = exported_route_name(SimpleNamespace(pk=21), 'bht/medium')
    route_for_current_class = exported_route_name(project.limit_class, 'bht/medium')
    install_fake(monkeypatch, {
        redis_key(route_for_previous_class, project.quota_key): '27',
        redis_key(route_for_current_class, project.quota_key): '42',
    })
    monkeypatch.setattr(
        quota_status,
        'ProjectLimitClass',
        SimpleNamespace(objects=SimpleNamespace(values_list=lambda *_args, **_kwargs: [17, 21])),
    )

    consumed, _ = current_usage(project, 'bht/medium', now=1_790_035_300)

    assert consumed == 69


def test_missing_current_day_key_means_zero(monkeypatch, project):
    install_fake(monkeypatch, {})

    consumed, reset_at = current_usage(project, 'bht/small', now=1_790_035_300)
    assert consumed == 0
    assert reset_at.timestamp() == 1_790_121_600


def test_redis_failure_is_unavailable(monkeypatch, project):
    class BrokenRedis:
        def scan_iter(self, **_kwargs):
            raise redis.RedisError('unavailable')

    monkeypatch.setattr('apps.authz.quota_status._redis_client', lambda _url: BrokenRedis())

    assert current_usage(project, 'bht/medium', now=1_790_035_300) == (None, None)


def test_ambiguous_counter_keys_are_unavailable(monkeypatch, project):
    install_fake(monkeypatch, {
        redis_key('inference-medium-grantdeck', 'admins'): '19',
        redis_key('inference-medium-grantdeck', 'admins').replace('envoy/default', 'other-domain'): '21',
    })

    assert current_usage(project, 'bht/medium', now=1_790_035_300) == (None, None)
