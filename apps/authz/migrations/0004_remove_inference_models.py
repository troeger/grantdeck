from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('authz', '0003_model_project_allowed_models'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='project',
            name='allowed_models',
        ),
        migrations.DeleteModel(
            name='InferenceModel',
        ),
    ]
