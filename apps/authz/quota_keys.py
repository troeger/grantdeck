import hashlib
import re


LEGACY_MODEL_ROUTES = {
    'bht/large': 'inference-large-grantdeck',
    'bht/medium': 'inference-medium-grantdeck',
    'bht/small': 'inference-small-grantdeck',
}


def exported_route_name(policy_class, model_name):
    model_slug = re.sub(r'[^a-z0-9]+', '-', model_name.lower()).strip('-')[:24].strip('-') or 'model'
    digest = hashlib.sha256(model_name.encode()).hexdigest()[:8]
    return f'grantdeck-c{policy_class.pk}-{model_slug}-{digest}'


def redis_glob_escape(value):
    """Escape Redis SCAN glob metacharacters in a descriptor value."""
    return ''.join('\\' + char if char in r'\\*?[]' else char for char in value)
