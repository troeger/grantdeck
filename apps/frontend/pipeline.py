import json
import logging

from django.conf import settings


logger = logging.getLogger(__name__)


def log_oauth_response(backend, details, response, uid, *args, **kwargs):
    logger.info(
        'oauth login backend=%s uid=%s details=%s response=%s',
        backend.name,
        uid,
        json.dumps(details, default=str, sort_keys=True),
        json.dumps(response, default=str, sort_keys=True),
        extra={
            'oauth_backend': backend.name,
            'oauth_uid': uid,
            'oauth_details': details,
            'oauth_response': response,
        },
    )


def promote_oidc_admin(strategy, details, response, user=None, *args, **kwargs):
    """Promote the configured OIDC username after a successful login."""
    username = getattr(settings, 'GDK_OIDC_ADMIN_USERNAME', '')
    oidc_username = details.get('username') or response.get('preferred_username')
    if not username or user is None or username not in {user.username, oidc_username}:
        return

    if not (user.is_staff and user.is_superuser):
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=['is_staff', 'is_superuser'])
        logger.info('Promoted OIDC user %s to Django administrator', username)
