# notificationApp/services.py
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from .models import Notification, NotificationPreference
from performanceApp.models import BreakLog
from userApp.models import CustomUser
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for creating and managing notifications"""
    
    @staticmethod
    def get_or_create_preferences(user):
        """Get or create notification preferences for a user"""
        prefs, created = NotificationPreference.objects.get_or_create(user=user)
        return prefs
    
    @staticmethod
    def create_break_start_reminder(break_log):
        """Create notification when break is about to start"""
        user = break_log.user
        prefs = NotificationService.get_or_create_preferences(user)
        
        if not prefs.should_send_notification('break_start_reminder'):
            return None
        
        title = f"Break Starting Soon"
        message = f"Your {break_log.break_template.name} is scheduled to start at {break_log.scheduled_start.strftime('%H:%M')}."
        
        notification = Notification.create_break_notification(
            user=user,
            break_log=break_log,
            notification_type='break_start_reminder',
            title=title,
            message=message,
            priority='medium',
            expires_in_minutes=30
        )
        
        notification.action_text = "Start Break"
        notification.action_url = f"/breaks/start/{break_log.id}/"
        notification.mark_as_sent()
        notification.save()
        
        logger.info(f"Created break start reminder for {user.emp_number}")
        return notification
    
    @staticmethod
    def create_break_end_reminder(break_log):
        """Create notification when break is about to end"""
        user = break_log.user
        prefs = NotificationService.get_or_create_preferences(user)
        
        if not prefs.should_send_notification('break_end_reminder'):
            return None
        
        title = f"Break Ending Soon"
        message = f"Your {break_log.break_template.name} is scheduled to end at {break_log.scheduled_end.strftime('%H:%M')}. Please return to work."
        
        notification = Notification.create_break_notification(
            user=user,
            break_log=break_log,
            notification_type='break_end_reminder',
            title=title,
            message=message,
            priority='high',
            expires_in_minutes=15
        )
        
        notification.action_text = "End Break"
        notification.action_url = f"/breaks/end/{break_log.id}/"
        notification.mark_as_sent()
        notification.save()
        
        logger.info(f"Created break end reminder for {user.emp_number}")
        return notification
    
    @staticmethod
    def create_break_missed_notification(break_log):
        """Create notification when user missed a break"""
        user = break_log.user
        prefs = NotificationService.get_or_create_preferences(user)
        
        if not prefs.should_send_notification('break_missed'):
            return None
        
        title = f"Break Missed"
        message = f"You missed your {break_log.break_template.name} scheduled at {break_log.scheduled_start.strftime('%H:%M')}."
        
        notification = Notification.create_break_notification(
            user=user,
            break_log=break_log,
            notification_type='break_missed',
            title=title,
            message=message,
            priority='medium',
            expires_in_minutes=120
        )
        
        notification.mark_as_sent()
        notification.save()
        
        logger.info(f"Created break missed notification for {user.emp_number}")
        return notification
    
    @staticmethod
    def create_break_extended_notification(break_log):
        """Create notification when break is extended beyond scheduled time"""
        user = break_log.user
        prefs = NotificationService.get_or_create_preferences(user)
        
        if not prefs.should_send_notification('break_extended'):
            return None
        
        extended_minutes = break_log.end_deviation_minutes
        
        title = f"Break Extended"
        message = f"Your {break_log.break_template.name} has been extended by {extended_minutes:.0f} minutes beyond the scheduled end time."
        
        notification = Notification.create_break_notification(
            user=user,
            break_log=break_log,
            notification_type='break_extended',
            title=title,
            message=message,
            priority='high',
            expires_in_minutes=60
        )
        
        notification.mark_as_sent()
        notification.save()
        
        logger.info(f"Created break extended notification for {user.emp_number}")
        return notification
    
    @staticmethod
    def notify_shift_users_about_break(break_log, notification_type):
        """Send notifications to all users in the same shift about a break"""
        shift = break_log.break_template.shift
        
        # Get all users assigned to this shift
        users_in_shift = CustomUser.objects.filter(
            current_shift=shift,
            is_active=True
        )
        
        notifications = []
        for user in users_in_shift:
            # Get user's break log for this break
            user_break_log = BreakLog.objects.filter(
                user=user,
                break_template=break_log.break_template,
                scheduled_start=break_log.scheduled_start,
                is_active=True
            ).first()
            
            if user_break_log:
                if notification_type == 'start':
                    notification = NotificationService.create_break_start_reminder(user_break_log)
                elif notification_type == 'end':
                    notification = NotificationService.create_break_end_reminder(user_break_log)
                
                if notification:
                    notifications.append(notification)
        
        logger.info(f"Sent {len(notifications)} {notification_type} notifications for shift {shift.name}")
        return notifications
    
    @staticmethod
    def mark_all_as_read(user):
        """Mark all notifications as read for a user"""
        count = Notification.objects.filter(
            user=user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
        
        logger.info(f"Marked {count} notifications as read for {user.emp_number}")
        return count
    
    @staticmethod
    def delete_expired_notifications():
        """Delete expired notifications"""
        count = Notification.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()[0]
        
        logger.info(f"Deleted {count} expired notifications")
        return count
    
    @staticmethod
    def get_unread_count(user):
        """Get count of unread notifications for a user"""
        return Notification.objects.filter(
            user=user,
            is_read=False
        ).exclude(
            expires_at__lt=timezone.now()
        ).count()


class BreakMonitoringService:
    """Service for monitoring breaks and updating their status"""
    
    @staticmethod
    def check_and_send_break_reminders():
        """Check for upcoming breaks and send reminders"""
        now = timezone.now()
        
        # Get all scheduled breaks
        scheduled_breaks = BreakLog.objects.filter(
            status='scheduled',
            is_active=True,
            scheduled_start__gte=now,
            scheduled_start__lte=now + timedelta(minutes=10)
        )
        
        for break_log in scheduled_breaks:
            user = break_log.user
            prefs = NotificationService.get_or_create_preferences(user)
            
            # Calculate time until break starts
            time_until_start = (break_log.scheduled_start - now).total_seconds() / 60
            
            # Send reminder if within user's preference window
            if time_until_start <= prefs.break_start_reminder_minutes:
                # Check if reminder already sent
                existing_notification = Notification.objects.filter(
                    user=user,
                    break_log=break_log,
                    notification_type='break_start_reminder',
                    created_at__gte=now - timedelta(minutes=15)
                ).exists()
                
                if not existing_notification:
                    NotificationService.notify_shift_users_about_break(break_log, 'start')
        
        logger.info(f"Checked and sent break start reminders")
    
    @staticmethod
    def check_and_mark_missed_breaks():
        """Check for breaks that were not started and mark them as missed"""
        now = timezone.now()
        
        # Get breaks that should have ended but were never started
        missed_breaks = BreakLog.objects.filter(
            status='scheduled',
            is_active=True,
            scheduled_end__lt=now
        )
        
        count = 0
        for break_log in missed_breaks:
            # Mark as missed
            break_log.status = 'missed'
            break_log.system_generated_reason = f"Break was not started. Scheduled: {break_log.scheduled_start.strftime('%H:%M')} - {break_log.scheduled_end.strftime('%H:%M')}"
            break_log.save()
            
            # Create notification
            NotificationService.create_break_missed_notification(break_log)
            
            # Create user log
            from userApp.utils.logging_utils import create_user_log
            create_user_log(
                user=break_log.user,
                log_type='system_event',
                activity=f"Missed {break_log.break_template.name}",
                status='absent',
                scheduled_time=break_log.scheduled_start,
                break_log=break_log,
                shift=break_log.user.current_shift,
                request=None,
                is_auto=True,
                notes=f"Break was not started by user. System marked as missed."
            )
            
            count += 1
        
        logger.info(f"Marked {count} breaks as missed")
        return count
    
    @staticmethod
    def check_active_breaks_for_end_reminders():
        """Send reminders for breaks that are about to end"""
        now = timezone.now()
        
        # Get breaks currently in progress
        active_breaks = BreakLog.objects.filter(
            status='started',
            is_active=True,
            scheduled_end__gte=now,
            scheduled_end__lte=now + timedelta(minutes=10)
        )
        
        for break_log in active_breaks:
            user = break_log.user
            prefs = NotificationService.get_or_create_preferences(user)
            
            # Calculate time until break ends
            time_until_end = (break_log.scheduled_end - now).total_seconds() / 60
            
            # Send reminder if within user's preference window
            if time_until_end <= prefs.break_end_reminder_minutes:
                # Check if reminder already sent
                existing_notification = Notification.objects.filter(
                    user=user,
                    break_log=break_log,
                    notification_type='break_end_reminder',
                    created_at__gte=now - timedelta(minutes=15)
                ).exists()
                
                if not existing_notification:
                    NotificationService.create_break_end_reminder(break_log)
        
        logger.info(f"Checked and sent break end reminders")
    
    @staticmethod
    def check_extended_breaks():
        """Check for breaks that have extended beyond scheduled time"""
        now = timezone.now()
        
        # Get breaks that are still active past their scheduled end time
        extended_breaks = BreakLog.objects.filter(
            status='started',
            is_active=True,
            scheduled_end__lt=now - timedelta(minutes=5)  # 5 minutes grace period
        )
        
        for break_log in extended_breaks:
            # Update status to extended
            if break_log.status != 'extended':
                break_log.status = 'extended'
                break_log.save()
                
                # Send notification
                NotificationService.create_break_extended_notification(break_log)
        
        logger.info(f"Checked {extended_breaks.count()} extended breaks")
    
    @staticmethod
    def run_all_checks():
        """Run all break monitoring checks"""
        logger.info("Starting break monitoring checks...")
        
        BreakMonitoringService.check_and_send_break_reminders()
        BreakMonitoringService.check_and_mark_missed_breaks()
        BreakMonitoringService.check_active_breaks_for_end_reminders()
        BreakMonitoringService.check_extended_breaks()
        NotificationService.delete_expired_notifications()
        
        logger.info("Break monitoring checks completed")



    @staticmethod
    def create_task_end_reminder(task_assignment):
        """Create notification when task is about to end (5 minutes before)"""
        user = task_assignment.user
        
        # Check user preferences
        prefs = NotificationService.get_or_create_preferences(user)
        if not prefs.web_notifications:
            return None
        
        title = f"Task Ending Soon: {task_assignment.task.name}"
        message = (
            f"Your current task '{task_assignment.task.name}' ends in 5 minutes. "
            f"Please prepare to complete your work on this task."
        )
        
        notification = Notification.objects.create(
            user=user,
            notification_type='task_end_reminder',
            title=title,
            message=message,
            priority='high',
            expires_at=timezone.now() + timedelta(minutes=10),
            metadata={
                'task_id': task_assignment.task.id,
                'task_name': task_assignment.task.name,
                'assignment_id': task_assignment.id,
                'end_time': task_assignment.end_time.isoformat(),
                'upcoming_task_id': None,  # Will be populated if exists
                'upcoming_task_name': None
            }
        )
        
        notification.mark_as_sent()
        notification.save()
        
        logger.info(f"Created task end reminder for {user.emp_number}, Task: {task_assignment.task.name}")
        return notification
    
    @staticmethod
    def create_upcoming_task_alert(task_assignment, next_assignment):
        """Create notification about upcoming task"""
        user = task_assignment.user
        
        # Check user preferences
        prefs = NotificationService.get_or_create_preferences(user)
        if not prefs.web_notifications:
            return None
        
        title = f"Upcoming Task: {next_assignment.task.name}"
        message = (
            f"Your current task '{task_assignment.task.name}' ends soon. "
            f"Your next task is '{next_assignment.task.name}' starting at "
            f"{next_assignment.start_time.strftime('%H:%M')}."
        )
        
        notification = Notification.objects.create(
            user=user,
            notification_type='upcoming_task_alert',
            title=title,
            message=message,
            priority='medium',
            expires_at=next_assignment.start_time + timedelta(minutes=30),
            metadata={
                'current_task_id': task_assignment.task.id,
                'current_task_name': task_assignment.task.name,
                'next_task_id': next_assignment.task.id,
                'next_task_name': next_assignment.task.name,
                'next_start_time': next_assignment.start_time.isoformat(),
                'assignment_id': task_assignment.id
            }
        )
        
        notification.mark_as_sent()
        notification.save()
        
        logger.info(f"Created upcoming task alert for {user.emp_number}, Next: {next_assignment.task.name}")
        return notification
    
    @staticmethod
    def create_task_missed_alert(task_assignment):
        """Create notification to supervisor/admin when task is missed"""
        user = task_assignment.user
        
        # Get supervisors for this employee
        supervisors = user.supervisors.all()
        
        # Also get all admins
        from userApp.models import CustomUser
        admins = CustomUser.objects.filter(role='admin', is_active=True)
        
        # Combine recipients
        recipients = list(supervisors) + list(admins)
        
        notifications = []
        for recipient in recipients:
            # Check recipient preferences
            prefs = NotificationService.get_or_create_preferences(recipient)
            if not prefs.performance_alerts:
                continue
            
            title = f"Task Missed: {user.names} - {task_assignment.task.name}"
            message = (
                f"Employee {user.names} ({user.emp_number}) has missed their assigned task:\n"
                f"• Task: {task_assignment.task.name}\n"
                f"• Scheduled: {task_assignment.start_time.strftime('%H:%M')} - {task_assignment.end_time.strftime('%H:%M')}\n"
                f"• Date: {task_assignment.assignment_date}\n"
                f"• Shift: {task_assignment.shift.name if task_assignment.shift else 'N/A'}"
            )
            
            notification = Notification.objects.create(
                user=recipient,
                notification_type='task_missed_alert',
                title=title,
                message=message,
                priority='urgent',
                expires_at=timezone.now() + timedelta(days=1),
                metadata={
                    'employee_id': user.id,
                    'employee_name': user.names,
                    'employee_emp_number': user.emp_number,
                    'task_id': task_assignment.task.id,
                    'task_name': task_assignment.task.name,
                    'assignment_id': task_assignment.id,
                    'assignment_date': task_assignment.assignment_date.isoformat(),
                    'scheduled_start': task_assignment.start_time.isoformat(),
                    'scheduled_end': task_assignment.end_time.isoformat(),
                    'shift_id': task_assignment.shift.id if task_assignment.shift else None,
                    'shift_name': task_assignment.shift.name if task_assignment.shift else None
                }
            )
            
            notification.mark_as_sent()
            notification.save()
            notifications.append(notification)
            
            logger.info(f"Created task missed alert for {recipient.emp_number} about {user.emp_number}")
        
        return notifications
    
    @staticmethod
    def send_task_end_and_upcoming_notifications():
        """Send notifications for tasks ending in 5 minutes with upcoming tasks"""
        from taskAssignmentApp.models import TaskAssignment
        
        now = timezone.now()
        
        # Get active assignments ending in 5 minutes (±1 minute buffer)
        upcoming_end_time = now + timedelta(minutes=5)
        
        active_assignments = TaskAssignment.objects.filter(
            status='active',
            end_time__gte=now + timedelta(minutes=4),
            end_time__lte=now + timedelta(minutes=6)
        ).select_related('user', 'task')
        
        for assignment in active_assignments:
            # Check if notification already sent recently (last 10 minutes)
            existing_notification = Notification.objects.filter(
                user=assignment.user,
                notification_type='task_end_reminder',
                metadata__assignment_id=assignment.id,
                created_at__gte=now - timedelta(minutes=10)
            ).exists()
            
            if not existing_notification:
                # Send task end reminder
                NotificationService.create_task_end_reminder(assignment)
            
            # Find next assignment for this user on same date
            next_assignment = TaskAssignment.objects.filter(
                user=assignment.user,
                assignment_date=assignment.assignment_date,
                start_time__gt=assignment.end_time,
                status='scheduled'
            ).order_by('start_time').first()
            
            if next_assignment:
                # Check if upcoming task notification already sent
                existing_upcoming_notification = Notification.objects.filter(
                    user=assignment.user,
                    notification_type='upcoming_task_alert',
                    metadata__assignment_id=assignment.id,
                    created_at__gte=now - timedelta(minutes=10)
                ).exists()
                
                if not existing_upcoming_notification:
                    # Send upcoming task alert
                    NotificationService.create_upcoming_task_alert(assignment, next_assignment)
        
        logger.info(f"Processed {active_assignments.count()} active assignments for end reminders")
        return active_assignments.count()