import io
import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.authz.quota_keys import exported_route_name
from apps.authz.models import ProjectLimitClass, ProjectModelLimit


pytestmark = pytest.mark.django_db


def export_documents():
    output = io.StringIO()
    call_command('export_quota_manifests', stdout=output)
    return [json.loads(document) for document in output.getvalue().split('---') if document.strip()]


def test_export_generates_class_model_routes_quota_and_auth_resources():
    policy_class = ProjectLimitClass.objects.create(name='Research', slug='research')
    ProjectModelLimit.objects.create(
        limit_class=policy_class,
        model_name='bht/large',
        daily_token_limit=250_000,
    )

    documents = export_documents()

    route = next(document for document in documents if document['kind'] == 'AIGatewayRoute')
    quota = next(document for document in documents if document['kind'] == 'BackendTrafficPolicy')
    security = next(document for document in documents if document['kind'] == 'SecurityPolicy')
    route_ref = exported_route_name(policy_class, 'bht/large')

    assert route['metadata']['name'] == route_ref
    headers = route['spec']['rules'][0]['matches'][0]['headers']
    assert headers == [
        {'name': 'x-current-quota-class', 'type': 'Exact', 'value': 'research'},
        {'name': 'x-ai-eg-model', 'type': 'Exact', 'value': 'bht/large'},
    ]
    assert quota['spec']['targetRefs'][0]['name'] == route_ref
    rule = quota['spec']['rateLimit']['global']['rules'][0]
    assert rule['clientSelectors'][0]['headers'] == [
        {'name': 'x-current-quota-key', 'type': 'Distinct'},
    ]
    assert rule['limit'] == {'requests': 250_000, 'unit': 'Day'}
    assert rule['cost']['response']['metadata']['key'] == 'llm_total_token'
    assert security['spec']['targetRefs'] == [{
        'group': 'gateway.networking.k8s.io',
        'kind': 'HTTPRoute',
        'name': route_ref,
    }]
    assert 'x-current-quota-class' in security['spec']['extAuth']['http']['headersToBackend']
    assert 'x-current-quota-key' in security['spec']['extAuth']['http']['headersToBackend']
    assert 'x-ai-eg-model' not in security['spec']['extAuth']['headersToExtAuth']


def test_export_fails_for_model_without_static_backend_mapping():
    policy_class = ProjectLimitClass.objects.create(name='Unsupported', slug='unsupported')
    ProjectModelLimit.objects.create(
        limit_class=policy_class,
        model_name='unknown/model',
        daily_token_limit=10_000,
    )

    with pytest.raises(CommandError, match='No AIGateway backend mapping'):
        export_documents()
