import logging
import os
from concurrent import futures

import django
import grpc


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grantdeck.settings')
    django.setup()
    from apps.usage import als
    from apps.usage.proto import usage_als_pb2_grpc
    port = int(os.environ.get('GDK_ALS_PORT', '8001'))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    usage_als_pb2_grpc.add_AccessLogServiceServicer_to_server(
        als.AccessLogService(),
        server,
    )
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logging.getLogger('apps.usage').info('Envoy ALS receiver listening on %s', port)
    server.wait_for_termination()


if __name__ == '__main__':
    main()
