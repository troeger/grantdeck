from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.urls import include, path
from django.views.static import serve

from apps.authz import views as authz_views
from apps.frontend import views as frontend_views
from grantdeck import views as grantdeck_views

admin.site.site_header = 'GrantDeck administration'
admin.site.site_title = 'GrantDeck administration'
admin.site.index_title = 'GrantDeck administration'

urlpatterns = [
    path('static/<path:path>', serve, {'document_root': settings.STATIC_ROOT}),
    path('healthz/', grantdeck_views.healthz, name='healthz'),
    path('readyz/', grantdeck_views.readyz, name='readyz'),
    path('authz/check/', authz_views.envoy_authz_check, name='envoy_authz_check'),
    path('authz/check/<path:protected_path>', authz_views.envoy_authz_check, name='envoy_authz_check'),
    path('', frontend_views.token_overview, name='token_overview'),
    path('tokens/new/', frontend_views.token_create, name='token_create'),
    path('tokens/', frontend_views.create_token, name='create_token'),
    path('tokens/<int:token_id>/delete/', frontend_views.delete_token, name='delete_token'),
    path('projects/join/', frontend_views.join_project, name='join_project'),
    path('login/', frontend_views.login_page, name='login'),
    path('login/admin/', frontend_views.admin_login_page, name='admin_login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('social_django.urls', namespace='auth')),
    path('admin/', admin.site.urls),
]
