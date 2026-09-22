import secrets

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def populate_project_quota_keys(apps, schema_editor):
    Project = apps.get_model('authz', 'Project')
    for project in Project.objects.filter(quota_key__isnull=True):
        project.quota_key = f'qk_{secrets.token_urlsafe(32)}'
        project.save(update_fields=['quota_key'])


class Migration(migrations.Migration):
    dependencies = [
        ('authz', '0004_remove_inference_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectLimitClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('slug', models.SlugField(
                    max_length=48,
                    unique=True,
                    validators=[django.core.validators.RegexValidator(
                        '^[a-z][a-z0-9-]*$',
                        'Use a lowercase slug beginning with a letter.',
                    )],
                )),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'Project limit class',
                'verbose_name_plural': 'Project limit classes',
            },
        ),
        migrations.AddField(
            model_name='projectlimitclass',
            name='resources',
            field=models.ManyToManyField(blank=True, related_name='limit_classes', to='authz.resource'),
        ),
        migrations.CreateModel(
            name='ProjectModelLimit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model_name', models.CharField(max_length=200)),
                ('daily_token_limit', models.PositiveBigIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('limit_class', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='model_limits',
                    to='authz.projectlimitclass',
                )),
            ],
            options={
                'ordering': ['model_name'],
            },
        ),
        migrations.AddConstraint(
            model_name='projectmodellimit',
            constraint=models.UniqueConstraint(
                fields=('limit_class', 'model_name'),
                name='unique_project_limit_class_model',
            ),
        ),
        migrations.AddConstraint(
            model_name='projectmodellimit',
            constraint=models.CheckConstraint(
                condition=models.Q(('daily_token_limit__gt', 0)),
                name='project_model_daily_limit_positive',
            ),
        ),
        migrations.AddField(
            model_name='project',
            name='limit_class',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='projects',
                to='authz.projectlimitclass',
            ),
        ),
        migrations.AddField(
            model_name='project',
            name='quota_key',
            field=models.CharField(editable=False, max_length=48, null=True, unique=True),
        ),
        migrations.RunPython(populate_project_quota_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='project',
            name='quota_key',
            field=models.CharField(editable=False, max_length=48, unique=True),
        ),
    ]
