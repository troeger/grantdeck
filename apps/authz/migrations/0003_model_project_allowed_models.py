from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('authz', '0002_project_shortcut'),
    ]

    operations = [
        migrations.CreateModel(
            name='InferenceModel',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.CharField(max_length=120, unique=True)),
                ('description', models.TextField(blank=True)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.AddField(
            model_name='project',
            name='allowed_models',
            field=models.ManyToManyField(
                blank=True,
                related_name='projects',
                to='authz.inferencemodel',
            ),
        ),
    ]
