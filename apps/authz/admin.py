from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group
from django.db.models import Count
from social_django.models import Association, Nonce, UserSocialAuth

from apps.authz.models import Project, ProjectMembership, ProjectResource, Resource, StaticToken


admin.site.unregister([Group, UserSocialAuth, Nonce, Association])


class ProjectResourceInline(admin.TabularInline):
    model = ProjectResource
    extra = 0


class ProjectMembershipInline(admin.TabularInline):
    model = ProjectMembership
    extra = 0


class ProjectAdminForm(forms.ModelForm):
    join_code = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text='Set a new project code.',
    )
    clear_join_code = forms.BooleanField(required=False)

    class Meta:
        model = Project
        fields = ['name', 'shortcut', 'end_date', 'administrators', 'join_requires_approval']

    def clean_join_code(self):
        join_code = self.cleaned_data['join_code']
        if join_code:
            duplicate = Project.objects.filter(join_code_hash=Project.hash_join_code(join_code))
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise forms.ValidationError('Project code already exists.')
        return join_code


class SuperuserOnlyAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class ProjectScopedAdmin(admin.ModelAdmin):
    def can_use_project_admin(self, request, obj=None):
        if obj is None:
            return Project.can_use_admin(request.user)
        return Project.can_administer(request.user, self.project_for_object(obj))

    def has_module_permission(self, request):
        return Project.can_use_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return self.can_use_project_admin(request, obj)

    def has_add_permission(self, request):
        return Project.can_use_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return self.can_use_project_admin(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.can_use_project_admin(request, obj)


@admin.register(Project)
class ProjectAdmin(ProjectScopedAdmin):
    form = ProjectAdminForm
    list_display = ['name', 'shortcut', 'end_date', 'administrators_list', 'token_count', 'resource_count']
    search_fields = ['name', 'shortcut']
    filter_horizontal = ['administrators']
    inlines = [ProjectMembershipInline, ProjectResourceInline]

    def project_for_object(self, project):
        return project

    def get_queryset(self, request):
        queryset = (
            super()
            .get_queryset(request)
            .annotate(
                token_count_value=Count('tokens', distinct=True),
                resource_count_value=Count('resources', distinct=True),
            )
        )
        if request.user.is_superuser:
            return queryset
        return queryset.filter(pk__in=Project.administered_by(request.user))

    @admin.display(description='Administrators')
    def administrators_list(self, project):
        administrators = [user.get_username() for user in project.administrators.all()]
        return ', '.join(administrators) or '-'

    @admin.display(description='Bearer tokens')
    def token_count(self, project):
        return project.token_count_value

    @admin.display(description='Resources')
    def resource_count(self, project):
        return project.resource_count_value

    def get_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return ['name', 'shortcut', 'end_date', 'join_requires_approval', 'join_code', 'clear_join_code']
        return ['name', 'shortcut', 'end_date', 'administrators', 'join_requires_approval', 'join_code', 'clear_join_code']

    def get_inline_instances(self, request, obj=None):
        if request.user.is_superuser:
            return super().get_inline_instances(request, obj)
        return []

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        join_code = form.cleaned_data.get('join_code')
        if join_code:
            obj.set_join_code(join_code)
        elif form.cleaned_data.get('clear_join_code'):
            obj.set_join_code('')
        super().save_model(request, obj, form, change)


@admin.register(Resource)
class ResourceAdmin(SuperuserOnlyAdmin):
    list_display = ['url', 'description']
    search_fields = ['url', 'description']


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(ProjectScopedAdmin):
    list_display = ['project', 'user', 'status']
    list_filter = ['project', 'status']
    search_fields = ['project__name', 'user__username']

    def project_for_object(self, membership):
        return membership.project

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related('project', 'user')
        if request.user.is_superuser:
            return queryset
        return queryset.filter(project__in=Project.administered_by(request.user))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'project' and not request.user.is_superuser:
            kwargs['queryset'] = Project.administered_by(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(StaticToken)
class StaticTokenAdmin(SuperuserOnlyAdmin):
    list_display = ['name', 'token_indicator', 'user', 'project', 'allowed_count', 'denied_count', 'created_at', 'expires_at']
    list_filter = ['project']
    search_fields = ['name', 'user__username']
    readonly_fields = ['token_indicator', 'token_hash', 'created_at', 'allowed_count', 'denied_count']

    def get_fields(self, request, obj=None):
        return [
            'user',
            'name',
            'token_indicator',
            'project',
            'created_at',
            'expires_at',
            'allowed_count',
            'denied_count',
            'token_hash',
        ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'project')

    def has_add_permission(self, request):
        return False
