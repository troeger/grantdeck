import json
import logging


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
