# performanceApp/scheduler.py

from celery import current_app
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
from datetime import datetime, timedelta
import json

class BreakScheduler:
    @staticmethod
    def schedule_break_creation(break_time, user_id, break_template_id):
        """
        Schedule a task to create a break 5 minutes before it starts
        
        Args:
            break_time: datetime when break starts
            user_id: ID of the user
            break_template_id: ID of the break template
        """
        # Calculate run time (5 minutes before break)
        run_time = break_time - timedelta(minutes=5)
        
        # Create a one-time scheduled task
        schedule, created = CrontabSchedule.objects.get_or_create(
            minute=run_time.minute,
            hour=run_time.hour,
            day_of_month=run_time.day,
            month_of_year=run_time.month,
            day_of_week='*',
        )
        
        task_name = f'create_break_{user_id}_{break_template_id}_{run_time.strftime("%Y%m%d%H%M")}'
        
        # Create the periodic task
        PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                'crontab': schedule,
                'task': 'performanceApp.tasks.create_specific_break',
                'args': json.dumps([user_id, break_template_id, run_time.date().isoformat()]),
                'one_off': True,  # Run only once
                'enabled': True,
            }
        )
    
    @staticmethod
    def schedule_all_upcoming_breaks():
        """
        Schedule creation tasks for all upcoming breaks in the next 24 hours
        """
        from .services import BreakManagementService
        from .models import BreakTemplate
        from userApp.models import CustomUser
        from django.utils import timezone
        
        now = timezone.now()
        tomorrow = now + timedelta(days=1)
        
        # Get all active users
        users = CustomUser.objects.filter(status='active', current_shift__isnull=False)
        
        for user in users:
            shift = user.current_shift
            if not shift:
                continue
                
            # Get today's breaks
            for break_template in shift.breaks.filter(status='active'):
                # Calculate today's break time
                break_start = datetime.combine(now.date(), break_template.start_at)
                break_start = timezone.make_aware(break_start)
                
                # Handle overnight
                if break_template.end_at < break_template.start_at:
                    break_start += timedelta(days=1)
                
                # If break is in the next 24 hours, schedule it
                if now <= break_start <= tomorrow:
                    BreakScheduler.schedule_break_creation(
                        break_start, user.id, break_template.id
                    )



                    