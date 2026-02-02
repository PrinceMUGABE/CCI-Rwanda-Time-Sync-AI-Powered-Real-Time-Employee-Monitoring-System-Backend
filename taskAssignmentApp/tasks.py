# taskAssignmentApp/tasks.py (FIXED VERSION)
from celery import shared_task
from django.utils import timezone
from datetime import timedelta, datetime, time
from .services import TaskAssignmentService, TaskNotificationService
from shiftApp.models import Shift
from userApp.models import CustomUser
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_task_reminders():
    """
    FIXED: Send reminders at 30, 15, 10, and 5 minutes before task ends
    Runs every 2 minutes to catch all reminder windows
    """
    try:
        logger.info("Starting task reminder check...")
        TaskNotificationService.send_task_reminders()
        logger.info("Task reminder check completed")
        return "Task reminders sent"
    except Exception as e:
        logger.error(f"Error sending task reminders: {str(e)}")
        raise


@shared_task
def check_missed_assignments():
    """Check and mark missed assignments - runs every 10 minutes"""
    try:
        logger.info("Starting missed assignments check...")
        count = TaskNotificationService.check_missed_assignments()
        logger.info(f"Marked {count} assignments as missed")
        return f"Marked {count} assignments as missed"
    except Exception as e:
        logger.error(f"Error checking missed assignments: {str(e)}")
        raise


@shared_task
def auto_create_assignments_before_shifts():
    """
    FIXED: Auto-create assignments 10 minutes before each shift starts
    This task should run every minute to catch shifts starting soon
    """
    try:
        now = timezone.now()
        trigger_time = now + timedelta(minutes=10)
        
        # Get all active shifts
        active_shifts = Shift.objects.filter(status='active')
        
        assignments_created = 0
        shifts_processed = []
        
        for shift in active_shifts:
            # Get shift start time for today
            today = now.date()
            shift_start, shift_end = shift.get_datetime_range(today)
            
            # Check if shift starts in approximately 10 minutes (±2 minute window)
            time_diff = (shift_start - now).total_seconds() / 60
            
            if 8 <= time_diff <= 12:  # 10 minutes ± 2 minute tolerance
                # Check if assignments already exist
                from .models import TaskAssignment
                existing = TaskAssignment.objects.filter(
                    assignment_date=today,
                    shift=shift
                ).exists()
                
                if not existing:
                    logger.info(
                        f"Auto-creating assignments for {shift.name} "
                        f"(starts in {time_diff:.1f} minutes at {shift_start.strftime('%H:%M')})"
                    )
                    
                    assignments = TaskAssignmentService.create_daily_assignments(
                        date=today,
                        shift=shift,
                        assigned_by=None  # System generated
                    )
                    
                    assignments_created += len(assignments)
                    shifts_processed.append(shift.name)
        
        if assignments_created > 0:
            logger.info(
                f"Auto-created {assignments_created} assignments for shifts: {', '.join(shifts_processed)}"
            )
            return f"Created {assignments_created} assignments for {len(shifts_processed)} shift(s)"
        else:
            return "No assignments needed at this time"
            
    except Exception as e:
        logger.error(f"Error in auto-create assignments: {str(e)}")
        raise


@shared_task
def create_daily_assignments_manual(date_str, shift_id, admin_user_id=None):
    """
    Manual task assignment creation (for admin use)
    """
    try:
        assignment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        shift = Shift.objects.get(id=shift_id)
        
        assigned_by = None
        if admin_user_id:
            assigned_by = CustomUser.objects.get(id=admin_user_id)
        
        assignments = TaskAssignmentService.create_daily_assignments(
            date=assignment_date,
            shift=shift,
            assigned_by=assigned_by
        )
        
        logger.info(f"Manually created {len(assignments)} assignments for {shift.name} on {date_str}")
        return f"Created {len(assignments)} assignments"
        
    except Exception as e:
        logger.error(f"Error in manual assignment creation: {str(e)}")
        raise


@shared_task
def generate_assignments_for_tomorrow():
    """
    BACKUP: Generate assignments for tomorrow for all active shifts
    This runs daily at 6 PM as a backup in case the 10-minute trigger misses anything
    """
    try:
        from .models import TaskAssignment
        
        tomorrow = timezone.now().date() + timedelta(days=1)
        active_shifts = Shift.objects.filter(status='active')
        
        total_created = 0
        for shift in active_shifts:
            # Check if assignments already exist
            existing = TaskAssignment.objects.filter(
                assignment_date=tomorrow,
                shift=shift
            ).exists()
            
            if not existing:
                assignments = TaskAssignmentService.create_daily_assignments(
                    date=tomorrow,
                    shift=shift,
                    assigned_by=None
                )
                total_created += len(assignments)
                logger.info(f"Backup: Created {len(assignments)} assignments for {shift.name} tomorrow")
        
        if total_created > 0:
            logger.info(f"Backup task: Generated {total_created} assignments for {tomorrow}")
        return f"Backup: Generated {total_created} assignments for tomorrow"
        
    except Exception as e:
        logger.error(f"Error in backup assignment generation: {str(e)}")
        raise