import os


os.environ.setdefault('GDK_ENV', 'development')
os.environ.setdefault('GDK_AIGATEWAY_GATEWAY_NAME', 'test-gateway')
os.environ.setdefault('GDK_AIGATEWAY_GATEWAY_NAMESPACE', 'test-gateway-system')
os.environ.setdefault('GDK_AIGATEWAY_GATEWAY_SECTION', 'test-api')
os.environ.setdefault('GDK_AIGATEWAY_GATEWAY_INTERNAL_SECTION', 'test-internal')
os.environ.setdefault('GDK_AIGATEWAY_MODELS_OWNER', 'test-owner')
os.environ.setdefault(
    'GDK_AIGATEWAY_MODEL_BACKENDS',
    '{"bht/large":{"name":"test-backend"}}',
)

from grantdeck.settings import *  # noqa: F403
