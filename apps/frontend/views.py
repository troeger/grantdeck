from collections import defaultdict

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.views.decorators.cache import never_cache
from django.utils.http import url_has_allowed_host_and_scheme

from apps.authz.forms import ProjectJoinForm, StaticTokenForm
from apps.authz.models import MEMBERSHIP_ACTIVE, Project, ProjectMembership, StaticToken
from apps.authz.quota_status import rows_for_projects


NEW_STATIC_TOKEN_SESSION_KEY = '_new_static_token'
PROJECT_JOIN_ATTEMPTS_CACHE_KEY = 'project-join-attempts:{user_id}'


def safe_redirect_to(request):
    redirect_to = request.POST.get('next') or request.GET.get('next') or '/'
    if url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to
    return '/'


def project_join_limited(user):
    key = PROJECT_JOIN_ATTEMPTS_CACHE_KEY.format(user_id=user.pk)
    cache.add(key, 0, settings.PROJECT_JOIN_ATTEMPT_WINDOW_SECONDS)
    return cache.incr(key) > settings.PROJECT_JOIN_ATTEMPT_LIMIT


def reset_project_join_limit(user):
    cache.delete(PROJECT_JOIN_ATTEMPTS_CACHE_KEY.format(user_id=user.pk))


def render_token_overview(request, project_join_form=None, status=200):
    new_static_token = request.session.pop(NEW_STATIC_TOKEN_SESSION_KEY, None)
    can_create_token = Project.token_projects_for_user(request.user).exists()
    quota_rows = rows_for_projects(
        Project.objects.filter(
            Q(projectmembership__user=request.user, projectmembership__status=MEMBERSHIP_ACTIVE)
            | Q(administrators=request.user)
        )
        .distinct()
        .select_related('limit_class')
        .prefetch_related('limit_class__model_limits')
    )
    quota_rows_by_project = defaultdict(list)
    for row in quota_rows:
        quota_rows_by_project[row['project'].pk].append(row)

    return render(
        request,
        'frontend/token_overview.html',
        {
            'active_nav': 'overview',
            'new_static_token': new_static_token,
            'memberships': ProjectMembership.objects.filter(user=request.user).select_related('project'),
            'project_join_form': project_join_form or ProjectJoinForm(),
            'can_create_token': can_create_token,
            'quota_rows': quota_rows,
            'quota_rows_by_project': quota_rows_by_project,
        },
        status=status,
    )


@login_required
def token_overview(request):
    return render_token_overview(request)


@login_required
def admin_quota_usage(request):
    if not request.user.is_staff:
        return HttpResponseForbidden()

    projects = (
        Project.objects.all()
        .select_related('limit_class')
        .prefetch_related('limit_class__model_limits')
    )
    return render(
        request,
        'frontend/quota_usage.html',
        {
            'active_nav': 'quota_usage',
            'quota_rows': rows_for_projects(projects),
            'admin_view': True,
        },
    )


@login_required
def token_create(request):
    return render(
        request,
        'frontend/token_create.html',
        {
            'active_nav': 'create',
            'token_form': StaticTokenForm(user=request.user, initial={'project': request.GET.get('project')}),
        },
    )


@login_required
def create_token(request):
    if request.method != 'POST':
        return redirect('token_create')

    form = StaticTokenForm(request.POST, user=request.user)
    if form.is_valid():
        token, raw_token = form.save(request.user)
        request.session[NEW_STATIC_TOKEN_SESSION_KEY] = {
            'id': token.id,
            'name': token.name,
            'value': raw_token,
        }
        return redirect('token_overview')

    return render(
        request,
        'frontend/token_create.html',
        {
            'active_nav': 'create',
            'token_form': form,
        },
    )


@login_required
def join_project(request):
    if request.method != 'POST':
        return redirect('token_overview')

    if project_join_limited(request.user):
        messages.error(request, 'Too many wrong project codes. Try again later.')
        return render_token_overview(request, ProjectJoinForm(request.POST), status=429)

    form = ProjectJoinForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Enter a project code.')
        return render_token_overview(request, form)

    membership = Project.join_user_by_code(request.user, form.cleaned_data['join_code'])
    if membership is None:
        messages.error(request, 'The project code is invalid or expired.')
        return render_token_overview(request, form)

    reset_project_join_limit(request.user)
    return redirect('token_overview')


@login_required
def delete_token(request, token_id):
    if request.method == 'POST':
        token = get_object_or_404(StaticToken, pk=token_id, user=request.user)
        token.delete()
    return redirect('token_overview')


@never_cache
def login_page(request):
    if request.user.is_authenticated:
        return redirect('token_overview')
    return render(request, 'frontend/login.html', {'next': safe_redirect_to(request)})


@never_cache
def admin_login_page(request):
    if request.user.is_authenticated:
        return redirect('token_overview')

    redirect_to = safe_redirect_to(request)
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect(redirect_to)

    return render(
        request,
        'frontend/admin_login.html',
        {
            'form': form,
            'next': redirect_to,
        },
    )
