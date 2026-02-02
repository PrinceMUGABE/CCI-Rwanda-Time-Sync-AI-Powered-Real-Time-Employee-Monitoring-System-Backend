# notificationApp/serializers.py
from datetime import timedelta
from time import timezone
from rest_framework import serializers
from .models import Notification, NotificationPreference
from .services import NotificationService


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications"""
    user_name = serializers.CharField(source='user.names', read_only=True)
    user_emp_number = serializers.CharField(source='user.emp_number', read_only=True)
    break_name = serializers.CharField(source='break_log.break_template.name', read_only=True)
    is_expired = serializers.ReadOnlyField()
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'user_name', 'user_emp_number',
            'notification_type', 'title', 'message', 'priority',
            'break_log', 'break_name', 'user_log',
            'is_read', 'is_sent', 'read_at', 'sent_at',
            'action_url', 'action_text', 'metadata',
            'created_at', 'updated_at', 'expires_at',
            'is_expired', 'time_ago'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_sent', 'sent_at']
    
    def get_time_ago(self, obj):
        """Get human-readable time difference"""
        from django.utils import timezone
        now = timezone.now()
        diff = now - obj.created_at
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for notification preferences"""
    user_name = serializers.CharField(source='user.names', read_only=True)
    user_emp_number = serializers.CharField(source='user.emp_number', read_only=True)
    is_dnd_active = serializers.ReadOnlyField()
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'user', 'user_name', 'user_emp_number',
            'break_start_reminder', 'break_start_reminder_minutes',
            'break_end_reminder', 'break_end_reminder_minutes',
            'break_missed_alert', 'break_extended_alert',
            'shift_start_reminder', 'shift_start_reminder_minutes',
            'shift_end_reminder', 'shift_end_reminder_minutes',
            'login_reminder', 'logout_reminder',
            'system_alerts', 'performance_alerts',
            'web_notifications', 'email_notifications',
            'dnd_enabled', 'dnd_start_time', 'dnd_end_time',
            'is_dnd_active', 'created_at', 'updated_at', 'task_end_reminder',
            'upcoming_task_alert', 'task_missed_alert'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']





# notificationApp/services.py - Add a comprehensive monitoring service
class TaskNotificationMonitor:
    """Monitor for task notifications and send them"""
    
    @staticmethod
    def check_and_send_task_notifications():
        """Check for tasks that need notifications and send them"""
        try:
            from taskAssignmentApp.models import TaskAssignment
            
            now = timezone.now()
            print(f"[Task Monitor] Checking task notifications at {now}")
            
            # 1. Check for tasks ending in 5 minutes
            task_end_count = NotificationService.send_task_end_and_upcoming_notifications()
            
            # 2. Check for missed tasks
            missed_tasks = TaskAssignment.objects.filter(
                status='missed',
                assignment_date__gte=now.date() - timedelta(days=1),
                assignment_date__lte=now.date()
            ).select_related('user', 'task', 'shift')
            
            missed_alerts_sent = 0
            for task in missed_tasks:
                # Check if notification already sent recently
                existing = Notification.objects.filter(
                    notification_type='task_missed_alert',
                    metadata__assignment_id=task.id,
                    created_at__gte=now - timedelta(hours=1)
                ).exists()
                
                if not existing:
                    notifications = NotificationService.create_task_missed_alert(task)
                    missed_alerts_sent += len(notifications)
            
            print(f"[Task Monitor] Sent {task_end_count} task end reminders and {missed_alerts_sent} missed task alerts")
            return {
                'task_end_reminders': task_end_count,
                'missed_task_alerts': missed_alerts_sent,
                'total_missed_tasks': missed_tasks.count()
            }
            
        except Exception as e:
            print(f"[Task Monitor] Error: {str(e)}")
            raise