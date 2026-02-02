# notificationApp/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .services import BreakMonitoringService, NotificationService
from performanceApp.models import BreakLog
from userApp.models import CustomUser
import logging

logger = logging.getLogger(__name__)


@shared_task
def monitor_breaks():
    """Monitor all break activities - runs every 2 minutes"""
    try:
        logger.info("Starting break monitoring task...")
        BreakMonitoringService.run_all_checks()
        logger.info("Break monitoring task completed successfully")
        return "Break monitoring completed"
    except Exception as e:
        logger.error(f"Error in break monitoring task: {str(e)}")
        raise


@shared_task
def cleanup_expired_notifications():
    """Clean up expired notifications - runs every hour"""
    try:
        count = NotificationService.delete_expired_notifications()
        logger.info(f"Cleanup task removed {count} expired notifications")
        return f"Deleted {count} expired notifications"
    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")
        raise


@shared_task
def check_missed_breaks():
    """Check and mark missed breaks - runs every 10 minutes"""
    try:
        count = BreakMonitoringService.check_and_mark_missed_breaks()
        logger.info(f"Marked {count} breaks as missed")
        return f"Marked {count} breaks as missed"
    except Exception as e:
        logger.error(f"Error checking missed breaks: {str(e)}")
        raise


@shared_task
def send_shift_start_reminders():
    """Send shift start reminders - runs every 15 minutes"""
    try:
        now = timezone.now()
        users = CustomUser.objects.filter(
            is_active=True,
            current_shift__isnull=False
        )
        
        notifications_sent = 0
        for user in users:
            if user.current_shift:
                prefs = NotificationService.get_or_create_preferences(user)
                
                if not prefs.should_send_notification('shift_start_reminder'):
                    continue
                
                shift_start, _ = user.current_shift.get_datetime_range(now.date())
                time_until_start = (shift_start - now).total_seconds() / 60
                
                if 0 < time_until_start <= prefs.shift_start_reminder_minutes:
                    from .models import Notification
                    
                    existing = Notification.objects.filter(
                        user=user,
                        notification_type='shift_start_reminder',
                        created_at__date=now.date()
                    ).exists()
                    
                    if not existing:
                        notification = Notification.objects.create(
                            user=user,
                            notification_type='shift_start_reminder',
                            title='Shift Starting Soon',
                            message=f'Your shift starts at {shift_start.strftime("%H:%M")}.',
                            priority='medium',
                            expires_at=shift_start + timedelta(hours=1),
                            metadata={
                                'shift_name': user.current_shift.name,
                                'shift_start': shift_start.isoformat(),
                            }
                        )
                        notification.mark_as_sent()
                        notifications_sent += 1
        
        logger.info(f"Sent {notifications_sent} shift start reminders")
        return f"Sent {notifications_sent} reminders"
        
    except Exception as e:
        logger.error(f"Error sending shift start reminders: {str(e)}")
        raise


@shared_task
def send_shift_end_reminders():
    """Send shift end reminders - runs every 15 minutes"""
    try:
        now = timezone.now()
        users = CustomUser.objects.filter(
            is_active=True,
            current_shift__isnull=False
        )
        
        notifications_sent = 0
        for user in users:
            if user.current_shift:
                prefs = NotificationService.get_or_create_preferences(user)
                
                if not prefs.should_send_notification('shift_end_reminder'):
                    continue
                
                _, shift_end = user.current_shift.get_datetime_range(now.date())
                time_until_end = (shift_end - now).total_seconds() / 60
                
                if 0 < time_until_end <= prefs.shift_end_reminder_minutes:
                    from .models import Notification
                    
                    existing = Notification.objects.filter(
                        user=user,
                        notification_type='shift_end_reminder',
                        created_at__date=now.date()
                    ).exists()
                    
                    if not existing:
                        notification = Notification.objects.create(
                            user=user,
                            notification_type='shift_end_reminder',
                            title='Shift Ending Soon',
                            message=f'Your shift ends at {shift_end.strftime("%H:%M")}.',
                            priority='medium',
                            expires_at=shift_end + timedelta(hours=1),
                            metadata={
                                'shift_name': user.current_shift.name,
                                'shift_end': shift_end.isoformat(),
                            }
                        )
                        notification.mark_as_sent()
                        notifications_sent += 1
        
        logger.info(f"Sent {notifications_sent} shift end reminders")
        return f"Sent {notifications_sent} reminders"
        
    except Exception as e:
        logger.error(f"Error sending shift end reminders: {str(e)}")
        raise


# notificationApp/tasks.py - Add new combined task
@shared_task
def send_shift_reminders():
    """Send shift start and end reminders - runs every minute"""
    try:
        now = timezone.now()
        users = CustomUser.objects.filter(
            is_active=True,
            current_shift__isnull=False
        )
        
        start_reminders_sent = 0
        end_reminders_sent = 0
        
        for user in users:
            if user.current_shift:
                prefs = NotificationService.get_or_create_preferences(user)
                
                # Check shift start
                shift_start, shift_end = user.current_shift.get_datetime_range(now.date())
                
                # Shift start reminder
                if prefs.shift_start_reminder:
                    time_until_start = (shift_start - now).total_seconds() / 60
                    
                    # Send reminder if within user's preference window (checking exactly at the right time)
                    if 0 < time_until_start <= prefs.shift_start_reminder_minutes:
                        from .models import Notification
                        existing = Notification.objects.filter(
                            user=user,
                            notification_type='shift_start_reminder',
                            created_at__date=now.date()
                        ).exists()
                        
                        if not existing:
                            notification = Notification.objects.create(
                                user=user,
                                notification_type='shift_start_reminder',
                                title='Shift Starting Soon',
                                message=f'Your shift starts at {shift_start.strftime("%H:%M")}.',
                                priority='medium',
                                expires_at=shift_start + timedelta(hours=1),
                                metadata={
                                    'shift_name': user.current_shift.name,
                                    'shift_start': shift_start.isoformat(),
                                }
                            )
                            notification.mark_as_sent()
                            start_reminders_sent += 1
                
                # Shift end reminder
                if prefs.shift_end_reminder:
                    time_until_end = (shift_end - now).total_seconds() / 60
                    
                    if 0 < time_until_end <= prefs.shift_end_reminder_minutes:
                        existing = Notification.objects.filter(
                            user=user,
                            notification_type='shift_end_reminder',
                            created_at__date=now.date()
                        ).exists()
                        
                        if not existing:
                            notification = Notification.objects.create(
                                user=user,
                                notification_type='shift_end_reminder',
                                title='Shift Ending Soon',
                                message=f'Your shift ends at {shift_end.strftime("%H:%M")}.',
                                priority='medium',
                                expires_at=shift_end + timedelta(hours=1),
                                metadata={
                                    'shift_name': user.current_shift.name,
                                    'shift_end': shift_end.isoformat(),
                                }
                            )
                            notification.mark_as_sent()
                            end_reminders_sent += 1
        
        logger.info(f"Sent {start_reminders_sent} shift start and {end_reminders_sent} shift end reminders")
        return f"Sent {start_reminders_sent} start, {end_reminders_sent} end reminders"
        
    except Exception as e:
        logger.error(f"Error sending shift reminders: {str(e)}")
        raise


@shared_task
def check_task_end_reminders():
    """Check and send task end reminders - runs every minute"""
    try:
        from .services import TaskNotificationMonitor
        result = TaskNotificationMonitor.check_and_send_task_notifications()
        logger.info(f"Task monitor completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in task end reminders: {str(e)}")
        raise


@shared_task
def check_missed_tasks():
    """Check for missed tasks and notify supervisors/admins - runs every 10 minutes"""
    try:
        from taskAssignmentApp.models import TaskAssignment
        from .services import NotificationService
        
        now = timezone.now()
        
        # Find missed tasks (status='missed' and assignment_date is today or recent)
        missed_tasks = TaskAssignment.objects.filter(
            status='missed',
            assignment_date__gte=now.date() - timedelta(days=1),  # Last 24 hours
            assignment_date__lte=now.date()
        ).select_related('user', 'task', 'shift')
        
        notifications_sent = 0
        for task in missed_tasks:
            # Check if notification already sent
            from .models import Notification
            existing_notification = Notification.objects.filter(
                notification_type='task_missed_alert',
                metadata__assignment_id=task.id,
                created_at__gte=now - timedelta(hours=1)  # Don't send again within an hour
            ).exists()
            
            if not existing_notification:
                notifications = NotificationService.create_task_missed_alert(task)
                notifications_sent += len(notifications)
        
        logger.info(f"Found {missed_tasks.count()} missed tasks, sent {notifications_sent} alerts")
        return f"Processed {missed_tasks.count()} missed tasks, sent {notifications_sent} alerts"
        
    except Exception as e:
        logger.error(f"Error checking missed tasks: {str(e)}")
        raise