# performanceApp/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import BreakLog
from userApp.utils.logging_utils import auto_record_break_start

@shared_task
def auto_record_scheduled_breaks():
    """Automatically record breaks that should have started"""
    now = timezone.now()
    
    # Find breaks that were scheduled to start in the last 5-35 minutes
    # (giving 5 minutes grace period, checking up to 35 minutes past)
    start_time_range = now - timedelta(minutes=35)
    check_time = now - timedelta(minutes=5)
    
    scheduled_breaks = BreakLog.objects.filter(
        status='scheduled',
        scheduled_start__range=[start_time_range, check_time],
        is_active=True
    )
    
    for break_log in scheduled_breaks:
        auto_record_break_start(break_log)
    
    return f"Processed {scheduled_breaks.count()} breaks"





from celery import shared_task
from django.utils import timezone
from .services import BreakManagementService


@shared_task
def create_daily_breaks():
    """
    Create break logs for all users at the start of each day
    Run this task daily at midnight or early morning
    """
    total = BreakManagementService.create_breaks_for_all_users()
    return f"Created {total} break logs for today"


@shared_task
def check_missed_breaks():
    """
    Check for breaks that should have been started but weren't
    Run this task every 5-10 minutes
    """
    count = BreakManagementService.auto_start_missed_breaks()
    return f"Marked {count} breaks as missed"


@shared_task
def check_extended_breaks():
    """
    Check for breaks that have exceeded their scheduled end time
    Run this task every 5-10 minutes
    """
    count = BreakManagementService.auto_end_extended_breaks()
    return f"Marked {count} breaks as extended"



@shared_task
def create_upcoming_breaks():
    """
    Create breaks that will start in the next 5 minutes
    Runs every minute to catch all upcoming breaks
    """
    from .services import BreakManagementService
    
    try:
        created = BreakManagementService.create_upcoming_breaks(minutes_ahead=5)
        return f"Created {len(created)} upcoming breaks"
    except Exception as e:
        return f"Error creating upcoming breaks: {str(e)}"
    



# performanceApp/tasks.py

@shared_task
def monitor_and_create_breaks():
    """
    Monitor for breaks during shift hours (runs every minute)
    """
    from django.utils import timezone
    from datetime import datetime
    
    now = timezone.now()
    current_hour = now.hour
    
    # Only run during typical shift hours (6 AM to 10 PM)
    if 6 <= current_hour <= 22:
        from .services import BreakManagementService
        created = BreakManagementService.create_upcoming_breaks(minutes_ahead=5)
        
        # Also check for missed breaks during active hours
        if created:
            print(f"[{now.strftime('%H:%M')}] Created {len(created)} upcoming breaks")
        
        return len(created)
    return 0




