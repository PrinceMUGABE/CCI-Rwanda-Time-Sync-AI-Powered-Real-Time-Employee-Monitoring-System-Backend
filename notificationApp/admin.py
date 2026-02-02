# notificationApp/admin.py
from django.contrib import admin
from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'title', 'priority', 'is_read', 'created_at']
    list_filter = ['notification_type', 'priority', 'is_read', 'created_at']
    search_fields = ['user__names', 'user__emp_number', 'title', 'message']
    readonly_fields = ['created_at', 'updated_at', 'sent_at', 'read_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Notification Details', {
            'fields': ('notification_type', 'title', 'message', 'priority')
        }),
        ('Related Objects', {
            'fields': ('break_log', 'user_log')
        }),
        ('Status', {
            'fields': ('is_read', 'is_sent', 'read_at', 'sent_at', 'expires_at')
        }),
        ('Actions', {
            'fields': ('action_url', 'action_text')
        }),
        ('Metadata', {
            'fields': ('metadata', 'created_at', 'updated_at')
        }),
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'break_start_reminder', 'break_end_reminder', 'dnd_enabled']
    search_fields = ['user__names', 'user__emp_number']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Break Notifications', {
            'fields': (
                'break_start_reminder', 'break_start_reminder_minutes',
                'break_end_reminder', 'break_end_reminder_minutes',
                'break_missed_alert', 'break_extended_alert'
            )
        }),
        ('Shift Notifications', {
            'fields': (
                'shift_start_reminder', 'shift_start_reminder_minutes',
                'shift_end_reminder', 'shift_end_reminder_minutes'
            )
        }),
        ('Other Notifications', {
            'fields': (
                'login_reminder', 'logout_reminder',
                'system_alerts', 'performance_alerts'
            )
        }),
        ('Channels', {
            'fields': ('web_notifications', 'email_notifications')
        }),
        ('Do Not Disturb', {
            'fields': ('dnd_enabled', 'dnd_start_time', 'dnd_end_time')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )