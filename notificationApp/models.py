# notificationApp/models.py
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """Store notifications for users"""
    NOTIFICATION_TYPES = [
        ('break_start_reminder', 'Break Start Reminder'),
        ('break_end_reminder', 'Break End Reminder'),
        ('break_missed', 'Break Missed'),
        ('break_extended', 'Break Extended'),
        ('shift_start_reminder', 'Shift Start Reminder'),
        ('shift_end_reminder', 'Shift End Reminder'),
        ('login_reminder', 'Login Reminder'),
        ('logout_reminder', 'Logout Reminder'),
        ('system_alert', 'System Alert'),
        ('performance_alert', 'Performance Alert'),
        ('task_end_reminder', 'Task End Reminder'),  # NEW
        ('task_missed_alert', 'Task Missed Alert'),  # NEW
        ('upcoming_task_alert', 'Upcoming Task Alert'),  # NEW
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    user = models.ForeignKey(
        'userApp.CustomUser',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='medium')
    
    # Related objects
    break_log = models.ForeignKey(
        'performanceApp.BreakLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    user_log = models.ForeignKey(
        'userApp.UserLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    # Status tracking
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Action buttons data (JSON)
    action_url = models.CharField(max_length=255, blank=True, null=True)
    action_text = models.CharField(max_length=100, blank=True, null=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When notification becomes irrelevant")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
            models.Index(fields=['notification_type', 'created_at']),
            models.Index(fields=['user', 'notification_type', 'is_read']),
        ]
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
    
    def __str__(self):
        return f"{self.user.names} - {self.notification_type} - {self.created_at}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at', 'updated_at'])
    
    def mark_as_sent(self):
        """Mark notification as sent"""
        if not self.is_sent:
            self.is_sent = True
            self.sent_at = timezone.now()
            self.save(update_fields=['is_sent', 'sent_at', 'updated_at'])
    
    @property
    def is_expired(self):
        """Check if notification has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @classmethod
    def create_break_notification(cls, user, break_log, notification_type, title, message, priority='medium', expires_in_minutes=60):
        """Helper method to create break-related notifications"""
        expires_at = timezone.now() + timezone.timedelta(minutes=expires_in_minutes)
        
        return cls.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority,
            break_log=break_log,
            expires_at=expires_at,
            metadata={
                'break_name': break_log.break_template.name,
                'scheduled_start': break_log.scheduled_start.isoformat(),
                'scheduled_end': break_log.scheduled_end.isoformat(),
            }
        )


class NotificationPreference(models.Model):
    """User preferences for notifications"""
    user = models.OneToOneField(
        'userApp.CustomUser',
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Break notifications
    break_start_reminder = models.BooleanField(default=True)
    break_start_reminder_minutes = models.IntegerField(default=5, help_text="Minutes before break start")
    
    break_end_reminder = models.BooleanField(default=True)
    break_end_reminder_minutes = models.IntegerField(default=5, help_text="Minutes before break end")
    
    break_missed_alert = models.BooleanField(default=True)
    break_extended_alert = models.BooleanField(default=True)
    
    # Shift notifications
    shift_start_reminder = models.BooleanField(default=True)
    shift_start_reminder_minutes = models.IntegerField(default=15, help_text="Minutes before shift start")
    
    shift_end_reminder = models.BooleanField(default=True)
    shift_end_reminder_minutes = models.IntegerField(default=15, help_text="Minutes before shift end")
    
    # Login/logout reminders
    login_reminder = models.BooleanField(default=True)
    logout_reminder = models.BooleanField(default=True)
    
    # System alerts
    system_alerts = models.BooleanField(default=True)
    performance_alerts = models.BooleanField(default=True)
    
    # Notification channels
    web_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=False)
    
    # Do Not Disturb
    dnd_enabled = models.BooleanField(default=False)
    dnd_start_time = models.TimeField(null=True, blank=True)
    dnd_end_time = models.TimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Task notifications
    task_end_reminder = models.BooleanField(default=True)
    task_end_reminder_minutes = models.IntegerField(default=5, help_text="Minutes before task end")
    
    upcoming_task_alert = models.BooleanField(default=True)
    task_missed_alerts = models.BooleanField(default=True, help_text="Receive alerts for missed tasks")
    
    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"{self.user.names} - Notification Preferences"
    
    def is_dnd_active(self):
        """Check if Do Not Disturb is currently active"""
        if not self.dnd_enabled or not self.dnd_start_time or not self.dnd_end_time:
            return False
        
        now = timezone.now().time()
        
        # Handle DND spanning midnight
        if self.dnd_start_time <= self.dnd_end_time:
            return self.dnd_start_time <= now <= self.dnd_end_time
        else:
            return now >= self.dnd_start_time or now <= self.dnd_end_time
    
    def should_send_notification(self, notification_type):
        """Check if notification should be sent based on preferences"""
        if self.is_dnd_active():
            return False
        
        notification_mapping = {
            'break_start_reminder': self.break_start_reminder,
            'break_end_reminder': self.break_end_reminder,
            'break_missed': self.break_missed_alert,
            'break_extended': self.break_extended_alert,
            'shift_start_reminder': self.shift_start_reminder,
            'shift_end_reminder': self.shift_end_reminder,
            'login_reminder': self.login_reminder,
            'logout_reminder': self.logout_reminder,
            'system_alert': self.system_alerts,
            'performance_alert': self.performance_alerts,
        }
        
        return notification_mapping.get(notification_type, True)