# rulesApp/models.py

from django.db import models
from django.utils.timezone import now
from userApp.models import CustomUser


class Rule(models.Model):
    """
    Simplified model for company rules and regulations
    """
    RULE_TYPE_CHOICES = [
        ('rule', 'Rule'),
        ('regulation', 'Regulation'),
    ]
    
    USER_TYPE_CHOICES = [
        ('all', 'All Users'),
        ('employee', 'Employees Only'),
        ('supervisor', 'Supervisors Only'),
        ('both', 'Employees & Supervisors'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    # Basic Information
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    # Type and Access Control
    rule_type = models.CharField(
        max_length=20,
        choices=RULE_TYPE_CHOICES,
        default='rule'
    )
    
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='all'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Rule'
        verbose_name_plural = 'Rules'
    
    def __str__(self):
        return f"{self.title} ({self.rule_type})"
    
    def can_user_view(self, user_role):
        """
        Check if user can view this rule based on role
        """
        if self.user_type == 'all':
            return True
        elif self.user_type == 'employee':
            return user_role == 'employee'
        elif self.user_type == 'supervisor':
            return user_role == 'supervisor'
        elif self.user_type == 'both':
            return user_role in ['employee', 'supervisor']
        return False