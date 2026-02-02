from django.db import models
from django.utils.timezone import now
from userApp.models import CustomUser


class Task(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('not-active', 'Not Active'),
    ]

    name = models.CharField(max_length=255, verbose_name="Task Name")
    description = models.TextField(verbose_name="Task Description")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Task Status"
    )
    created_at = models.DateTimeField(default=now, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tasks',
        verbose_name="Created By"
    )

    def __str__(self):
        return f"{self.name} - {self.status}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'