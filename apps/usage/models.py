from django.db import models


class UsageEvent(models.Model):
    request_id = models.CharField(max_length=128, unique=True)
    user_identifier = models.CharField(max_length=150)
    project_identifier = models.PositiveBigIntegerField()
    project_shortcut = models.CharField(max_length=32)
    model_name = models.CharField(max_length=200)
    route_name = models.CharField(max_length=255, blank=True)
    token_count = models.PositiveBigIntegerField()
    response_code = models.PositiveSmallIntegerField(null=True, blank=True)
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['occurred_at', 'user_identifier', 'project_shortcut']),
        ]


class DailyUsage(models.Model):
    day = models.DateField()
    user_identifier = models.CharField(max_length=150)
    project_identifier = models.PositiveBigIntegerField()
    project_shortcut = models.CharField(max_length=32)
    model_name = models.CharField(max_length=200)
    token_count = models.PositiveBigIntegerField(default=0)
    request_count = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['project_shortcut', 'user_identifier', 'model_name']
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'day',
                    'user_identifier',
                    'project_identifier',
                    'project_shortcut',
                    'model_name',
                ],
                name='unique_daily_usage_identity',
            ),
        ]
        indexes = [
            models.Index(fields=['day', 'project_identifier', 'model_name']),
        ]
