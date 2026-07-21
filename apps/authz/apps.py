from django.apps import AppConfig
from django.db.models.signals import m2m_changed


def update_project_administrators_staff(sender, instance, action, reverse, pk_set, **kwargs):
    if action != 'post_add' or not pk_set:
        return

    from django.contrib.auth import get_user_model

    User = get_user_model()
    if reverse:
        instance.is_staff = True
        instance.save(update_fields=['is_staff'])
    else:
        User.objects.filter(pk__in=pk_set, is_staff=False).update(is_staff=True)


class AuthzConfig(AppConfig):
    name = 'apps.authz'

    def ready(self):
        from apps.authz.models import Project

        m2m_changed.connect(
            update_project_administrators_staff,
            sender=Project.administrators.through,
            dispatch_uid='apps.authz.update_project_administrators_staff',
        )
