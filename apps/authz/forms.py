from django import forms
from django.conf import settings

from apps.authz.models import Project, StaticToken


class StaticTokenForm(forms.Form):
    name = forms.CharField(max_length=120)
    project = forms.ModelChoiceField(queryset=Project.objects.none())

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['project'].queryset = Project.token_projects_for_user(user)
        self.fields['lifetime_days'] = forms.IntegerField(
            min_value=1,
            max_value=settings.STATIC_TOKEN_MAX_LIFETIME_DAYS,
            initial=settings.STATIC_TOKEN_DEFAULT_LIFETIME_DAYS,
        )

    def save(self, user):
        return StaticToken.create_token(
            user,
            self.cleaned_data['name'],
            self.cleaned_data['lifetime_days'],
            self.cleaned_data['project'],
        )


class ProjectJoinForm(forms.Form):
    join_code = forms.CharField(max_length=120, label='Project code')
