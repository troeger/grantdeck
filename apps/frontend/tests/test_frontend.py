from datetime import timedelta
from itertools import count
import logging

import pytest
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from apps.authz.models import MEMBERSHIP_ACTIVE, Project, ProjectMembership, Resource, StaticToken, TokenResourceUsage
from apps.frontend.context_processors import show_admin_link
from apps.frontend.pipeline import log_oauth_response
from apps.frontend.views import NEW_STATIC_TOKEN_SESSION_KEY


pytestmark = pytest.mark.django_db

project_shortcuts = count(1)


def create_project(**fields):
    fields.setdefault('shortcut', f'frontend-project-{next(project_shortcuts)}')
    return Project.objects.create(**fields)


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username='oidc-user',
        password='correct-password',
    )


@pytest.fixture
def admin(django_user_model):
    return django_user_model.objects.create_superuser(
        username='admin',
        email='admin@example.test',
        password='correct-password',
    )


def message_text(response):
    return ' '.join(str(message) for message in get_messages(response.wsgi_request))


def test_home_redirects_anonymous_users_to_login(client):
    response = client.get('/')

    assert response.status_code == 302
    assert response.headers['Location'] == '/login/?next=/'


def test_authenticated_user_is_redirected_from_login_page(client, user):
    client.force_login(user)

    response = client.get('/login/')

    assert response.status_code == 302
    assert response.headers['Location'] == '/'


def test_authenticated_user_is_redirected_from_admin_login_page(client, user):
    client.force_login(user)

    response = client.get('/login/admin/')

    assert response.status_code == 302
    assert response.headers['Location'] == '/'


def test_local_account_login_redirects_authenticated_user(client, admin):
    response = client.post(
        '/login/admin/?next=/',
        {'username': admin.username, 'password': 'correct-password', 'next': '/'},
    )

    assert response.status_code == 302
    assert response.headers['Location'] == '/'


def test_local_account_login_rejects_invalid_credentials(client, admin):
    response = client.post('/login/admin/', {'username': admin.username, 'password': 'wrong-password'})

    assert response.status_code == 200
    assert not response.wsgi_request.user.is_authenticated


def test_default_login_does_not_accept_local_credentials(client, admin):
    response = client.post('/login/', {'username': admin.username, 'password': 'correct-password'})

    assert response.status_code == 200
    assert not response.wsgi_request.user.is_authenticated


def test_oauth_provider_response_is_logged(caplog):
    backend = type('Backend', (), {'name': 'oidc'})()
    details = {'email': 'user@example.test'}
    response = {'sub': '123', 'groups': ['admins'], 'access_token': 'token-value'}

    with caplog.at_level(logging.INFO, logger='apps.frontend.pipeline'):
        log_oauth_response(backend, details, response, '123')

    record = caplog.records[0]
    assert record.oauth_backend == 'oidc'
    assert record.oauth_uid == '123'
    assert record.oauth_details == details
    assert record.oauth_response == response
    assert '"access_token": "token-value"' in record.message


def test_home_renders_for_authenticated_users(client, user):
    client.force_login(user)

    response = client.get('/')

    assert response.status_code == 200
    assert response.wsgi_request.user == user
    assert response.context['can_create_token'] is False


def test_home_allows_token_creation_with_active_project(client, user):
    project = create_project(name='Project')
    ProjectMembership.objects.create(user=user, project=project, status=MEMBERSHIP_ACTIVE)
    client.force_login(user)

    response = client.get('/')

    assert response.context['can_create_token'] is True


def test_token_create_prefills_project_from_query(client, user):
    project = create_project(name='Project')
    ProjectMembership.objects.create(user=user, project=project, status=MEMBERSHIP_ACTIVE)
    client.force_login(user)

    response = client.get(f'/tokens/new/?project={project.pk}')

    assert response.status_code == 200
    assert response.context['token_form'].initial['project'] == str(project.pk)


def test_project_administrator_gets_admin_navigation_access(user):
    user.is_staff = True
    user.save(update_fields=['is_staff'])
    project = create_project(name='Project')
    project.administrators.add(user)

    assert show_admin_link(user)


def test_home_lists_only_current_users_unexpired_tokens(client, user, django_user_model):
    other_user = django_user_model.objects.create_user(username='other')
    project = create_project(name='Project', end_date=timezone.localdate() + timedelta(days=30))
    other_project = create_project(name='Other project', end_date=timezone.localdate() + timedelta(days=30))
    ProjectMembership.objects.create(user=user, project=project, status=MEMBERSHIP_ACTIVE)
    current_token, _ = StaticToken.create_token(user, 'current', 30, project)
    StaticToken.create_token(other_user, 'other', 30, other_project)
    expired_token, _ = StaticToken.create_token(user, 'expired', 30, project)
    expired_token.expires_at = timezone.now() - timedelta(days=1)
    expired_token.save(update_fields=['expires_at'])
    client.force_login(user)

    response = client.get('/')
    membership = response.context['memberships'][0]

    assert list(membership.active_tokens) == [current_token]


def test_home_includes_current_token_usage(client, user):
    project = create_project(name='Project', end_date=timezone.localdate() + timedelta(days=30))
    resource = Resource.objects.create(url='http://testserver/api')
    ProjectMembership.objects.create(user=user, project=project, status=MEMBERSHIP_ACTIVE)
    token, _ = StaticToken.create_token(user, 'current', 30, project)
    TokenResourceUsage.objects.create(token=token, resource=resource, allowed_count=3)
    client.force_login(user)

    response = client.get('/')
    token = response.context['memberships'][0].active_tokens[0]

    assert token.allowed_count == 0
    assert list(token.resource_usage.all())[0].allowed_count == 3


def test_home_lists_current_users_project_memberships(client, user):
    project = create_project(name='Project', end_date=timezone.localdate() + timedelta(days=30))
    membership = ProjectMembership.objects.create(user=user, project=project)
    client.force_login(user)

    response = client.get('/')

    assert list(response.context['memberships']) == [membership]


def test_requested_membership_shows_project_without_token_creation(client, user):
    project = create_project(name='Project', end_date=timezone.localdate() + timedelta(days=30))
    membership = ProjectMembership.objects.create(user=user, project=project)
    client.force_login(user)

    response = client.get('/')
    listed_membership = response.context['memberships'][0]

    assert list(response.context['memberships']) == [membership]
    assert response.context['can_create_token'] is False
    assert list(listed_membership.active_tokens) == []


def test_home_lists_project_administrators(client, user, django_user_model):
    administrator = django_user_model.objects.create_user(
        username='admin-user',
        first_name='Admin',
        last_name='User',
    )
    project = create_project(name='Project', end_date=timezone.localdate() + timedelta(days=30))
    project.administrators.add(administrator)
    ProjectMembership.objects.create(user=user, project=project)
    client.force_login(user)

    response = client.get('/')
    membership = response.context['memberships'][0]

    assert list(membership.project.administrators.all()) == [administrator]


def test_home_lists_ended_project_memberships(client, user):
    project = create_project(name='Project', end_date=timezone.localdate() - timedelta(days=1))
    membership = ProjectMembership.objects.create(user=user, project=project, status=MEMBERSHIP_ACTIVE)
    client.force_login(user)

    response = client.get('/')

    assert list(response.context['memberships']) == [membership]
    assert 'project_join_form' in response.context


def test_user_can_join_project_with_code_pending_approval(client, user):
    project = create_project(name='Project')
    project.set_join_code('project-code')
    project.save(update_fields=['join_code_hash'])
    client.force_login(user)

    response = client.post('/projects/join/', {'join_code': 'project-code'})
    membership = ProjectMembership.objects.get(user=user, project=project)

    assert response.status_code == 302
    assert membership.status == 'requested'


def test_user_can_join_project_with_code_without_approval(client, user):
    project = create_project(name='Project')
    project.set_join_code('project-code')
    project.join_requires_approval = False
    project.save(update_fields=['join_code_hash', 'join_requires_approval'])
    client.force_login(user)

    response = client.post('/projects/join/', {'join_code': 'project-code'})
    membership = ProjectMembership.objects.get(user=user, project=project)

    assert response.status_code == 302
    assert membership.status == MEMBERSHIP_ACTIVE


def test_joined_project_without_approval_allows_token_creation(client, user):
    project = create_project(name='Project')
    project.set_join_code('project-code')
    project.join_requires_approval = False
    project.save(update_fields=['join_code_hash', 'join_requires_approval'])
    client.force_login(user)

    client.post('/projects/join/', {'join_code': 'project-code'})
    response = client.post('/tokens/', {'name': 'deploy', 'project': project.pk, 'lifetime_days': '183'})

    assert response.status_code == 302
    assert StaticToken.objects.filter(user=user, project=project, name='deploy').exists()


def test_duplicate_project_join_is_noop(client, user):
    project = create_project(name='Project')
    project.set_join_code('project-code')
    project.save(update_fields=['join_code_hash'])
    ProjectMembership.objects.create(user=user, project=project)
    client.force_login(user)

    response = client.post('/projects/join/', {'join_code': 'project-code'})

    assert response.status_code == 302
    assert ProjectMembership.objects.filter(user=user, project=project).count() == 1


def test_wrong_project_join_code_returns_forbidden(client, user):
    project = create_project(name='Project')
    project.set_join_code('project-code')
    project.save(update_fields=['join_code_hash'])
    client.force_login(user)

    response = client.post('/projects/join/', {'join_code': 'wrong-code'})

    assert response.status_code == 200
    assert response.context['active_nav'] == 'overview'
    assert 'invalid or expired' in message_text(response)
    assert not ProjectMembership.objects.filter(user=user).exists()


@override_settings(PROJECT_JOIN_ATTEMPT_LIMIT=2)
def test_project_join_rate_limit_blocks_repeated_attempts(client, user):
    cache.clear()
    project = create_project(name='Project')
    project.set_join_code('project-code')
    project.save(update_fields=['join_code_hash'])
    client.force_login(user)

    assert client.post('/projects/join/', {'join_code': 'wrong-1'}).status_code == 200
    assert client.post('/projects/join/', {'join_code': 'wrong-2'}).status_code == 200
    response = client.post('/projects/join/', {'join_code': 'project-code'})

    assert response.status_code == 429
    assert 'Too many wrong project codes' in message_text(response)
    assert not ProjectMembership.objects.filter(user=user).exists()


@override_settings(PROJECT_JOIN_ATTEMPT_LIMIT=2)
def test_successful_project_join_resets_rate_limit(client, user):
    cache.clear()
    project = create_project(name='Project')
    project.set_join_code('project-code')
    project.save(update_fields=['join_code_hash'])
    client.force_login(user)

    assert client.post('/projects/join/', {'join_code': 'wrong-code'}).status_code == 200
    assert client.post('/projects/join/', {'join_code': 'project-code'}).status_code == 302
    assert client.post('/projects/join/', {'join_code': 'project-code'}).status_code == 302


def test_membership_join_for_ended_project_returns_forbidden(client, user):
    project = create_project(name='Project', end_date=timezone.localdate() - timedelta(days=1))
    project.set_join_code('project-code')
    project.save(update_fields=['join_code_hash'])
    client.force_login(user)

    response = client.post('/projects/join/', {'join_code': 'project-code'})

    assert response.status_code == 200
    assert 'invalid or expired' in message_text(response)
    assert not ProjectMembership.objects.filter(user=user, project=project).exists()


def test_create_token_uses_default_lifetime_and_shows_raw_token_once(client, user):
    project = create_project(name='Project', end_date=timezone.localdate() + timedelta(days=30))
    ProjectMembership.objects.create(user=user, project=project, status=MEMBERSHIP_ACTIVE)
    client.force_login(user)

    response = client.post('/tokens/', {'name': 'deploy', 'project': project.pk, 'lifetime_days': '183'})
    token = StaticToken.objects.get(user=user, name='deploy')

    assert response.status_code == 302
    assert response.headers['Location'] == '/'
    assert token.expires_at > timezone.now() + timedelta(days=182)
    assert token.project == project
    assert client.session[NEW_STATIC_TOKEN_SESSION_KEY]['id'] == token.id
    assert client.session[NEW_STATIC_TOKEN_SESSION_KEY]['value'].startswith('gdk_')
    client.get('/')
    assert NEW_STATIC_TOKEN_SESSION_KEY not in client.session
    assert StaticToken.objects.filter(user=user, name='deploy').count() == 1


def test_create_token_accepts_shorter_lifetime(client, user):
    project = create_project(name='Project', end_date=timezone.localdate() + timedelta(days=30))
    ProjectMembership.objects.create(user=user, project=project, status=MEMBERSHIP_ACTIVE)
    client.force_login(user)

    client.post('/tokens/', {'name': 'short', 'project': project.pk, 'lifetime_days': '7'})

    assert StaticToken.objects.get(user=user, name='short').expires_at < timezone.now() + timedelta(days=8)


def test_create_token_rejects_invalid_lifetime(client, user):
    project = create_project(name='Project', end_date=timezone.localdate() + timedelta(days=30))
    ProjectMembership.objects.create(user=user, project=project, status=MEMBERSHIP_ACTIVE)
    client.force_login(user)

    response = client.post('/tokens/', {'name': 'bad', 'project': project.pk, 'lifetime_days': '184'})

    assert response.status_code == 200
    assert not StaticToken.objects.filter(user=user, name='bad').exists()


@override_settings(STATIC_TOKEN_MAX_LIFETIME_DAYS=7, STATIC_TOKEN_DEFAULT_LIFETIME_DAYS=7)
def test_create_token_uses_configured_max_lifetime(client, user):
    project = create_project(name='Project', end_date=timezone.localdate() + timedelta(days=30))
    ProjectMembership.objects.create(user=user, project=project, status=MEMBERSHIP_ACTIVE)
    client.force_login(user)

    response = client.post('/tokens/', {'name': 'bad', 'project': project.pk, 'lifetime_days': '8'})

    assert response.status_code == 200
    assert not StaticToken.objects.filter(user=user, name='bad').exists()


def test_user_cannot_create_token_without_project(client, user):
    client.force_login(user)

    response = client.post('/tokens/', {'name': 'bad', 'lifetime_days': '183'})

    assert response.status_code == 200
    assert not StaticToken.objects.filter(user=user, name='bad').exists()


def test_requested_membership_does_not_allow_token_creation(client, user):
    project = create_project(name='Project', end_date=timezone.localdate() + timedelta(days=30))
    ProjectMembership.objects.create(user=user, project=project)
    client.force_login(user)

    response = client.post('/tokens/', {'name': 'bad', 'project': project.pk, 'lifetime_days': '183'})

    assert response.status_code == 200
    assert not StaticToken.objects.filter(user=user, name='bad').exists()


def test_superuser_cannot_create_token_without_project(client, admin):
    client.force_login(admin)

    response = client.post('/tokens/', {'name': 'admin-token', 'lifetime_days': '183'})

    assert response.status_code == 200
    assert not StaticToken.objects.filter(user=admin, name='admin-token').exists()


def test_superuser_can_create_token_for_active_project(client, admin):
    project = create_project(name='Project')
    client.force_login(admin)

    response = client.post('/tokens/', {'name': 'admin-token', 'project': project.pk, 'lifetime_days': '183'})
    token = StaticToken.objects.get(user=admin, name='admin-token')

    assert response.status_code == 302
    assert token.project == project


def test_delete_token_removes_current_users_token(client, user):
    project = create_project(name='Project', end_date=timezone.localdate() + timedelta(days=30))
    token, _ = StaticToken.create_token(user, 'delete-me', 30, project)
    client.force_login(user)

    response = client.post(f'/tokens/{token.id}/delete/')

    assert response.status_code == 302
    assert response.headers['Location'] == '/'
    assert not StaticToken.objects.filter(pk=token.pk).exists()


def test_delete_token_does_not_remove_other_users_token(client, user, django_user_model):
    project = create_project(name='Project', end_date=timezone.localdate() + timedelta(days=30))
    token, _ = StaticToken.create_token(django_user_model.objects.create_user(username='other'), 'keep-me', 30, project)
    client.force_login(user)

    response = client.post(f'/tokens/{token.id}/delete/')

    assert response.status_code == 404
    assert StaticToken.objects.filter(pk=token.pk).exists()
