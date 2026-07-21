from django.db import connection
from django.http import HttpResponse


def database_ready():
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception:
        return False
    return True


def healthz(request):
    return HttpResponse(status=200)


def readyz(request):
    return HttpResponse(status=200 if database_ready() else 503)
