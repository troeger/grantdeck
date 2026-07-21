from importlib.metadata import version

from django.conf import settings

from apps.authz.models import Project


APP_VERSION = version('grantdeck')


def branding(request):
    return {
        'brand_name': settings.BRAND_NAME,
        'app_version': APP_VERSION,
        'sso_login_button_text': settings.SSO_LOGIN_BUTTON_TEXT,
    }


def show_admin_link(user):
    return Project.can_use_admin(user)


def navigation(request):
    return {'show_admin_link': show_admin_link(request.user)}
