# performanceApp/services.py
from django.utils import timezone
from datetime import datetime, timedelta
from .models import BreakLog
from userApp.models import CustomUser
from shiftApp.models import BreakTemplate


class BreakManagementService:
    """Service to handle automatic break creation and management"""
    
    @staticmethod
    def create_breaks_for_user_shift(user, date=None):
        """
        Create break logs for a user based on their assigned shift
        
        Args:
            user: CustomUser instance
            date: Date to create breaks for (defaults to today)
        """
        if date is None:
            date = timezone.now().date()
        
        print(f"DEBUG: Creating breaks for {user.names} on {date}")
        
        # Check if user has a shift assigned
        if not user.current_shift:
            print(f"DEBUG: User {user.names} has no shift assigned!")
            return []
        
        shift = user.current_shift
        print(f"DEBUG: User shift: {shift.name} ({shift.start_at} - {shift.end_at})")
        
        # Get all active breaks for this shift
        break_templates = shift.breaks.filter(status='active')
        print(f"DEBUG: Found {break_templates.count()} break templates")
        
        for bt in break_templates:
            print(f"  - {bt.name}: {bt.start_at} - {bt.end_at}")
        
        created_breaks = []
        for break_template in break_templates:
            # Calculate scheduled start and end times
            scheduled_start = datetime.combine(date, break_template.start_at)
            scheduled_end = datetime.combine(date, break_template.end_at)
            
            print(f"DEBUG: Processing {break_template.name}")
            print(f"  Scheduled: {scheduled_start.time()} - {scheduled_end.time()}")
            
            # Make timezone aware
            scheduled_start = timezone.make_aware(scheduled_start)
            scheduled_end = timezone.make_aware(scheduled_end)
            
            # Handle overnight breaks
            if break_template.end_at < break_template.start_at:
                scheduled_end += timedelta(days=1)
                print(f"  Overnight break adjusted")
            
            # Check if break log already exists
            existing_break = BreakLog.objects.filter(
                user=user,
                break_template=break_template,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end
            ).first()
            
            if existing_break:
                print(f"  Break log already exists (ID: {existing_break.id})")
            else:
                # Create new break log
                break_log = BreakLog.objects.create(
                    user=user,
                    break_template=break_template,
                    scheduled_start=scheduled_start,
                    scheduled_end=scheduled_end,
                    status='scheduled',
                    is_auto_recorded=True,
                    system_generated_reason=f"Auto-created for {shift.name} shift"
                )
                print(f"  Created new break log (ID: {break_log.id})")
                created_breaks.append(break_log)
        
        print(f"DEBUG: Created {len(created_breaks)} break logs for {user.names}")
        return created_breaks
    @staticmethod
    def create_breaks_for_all_users(date=None):
        """Create breaks for all active users with assigned shifts"""
        if date is None:
            date = timezone.now().date()
        
        # Get all active users with assigned shifts
        users = CustomUser.objects.filter(
            status='active',
            current_shift__isnull=False
        ).exclude(
            day_off=date.strftime('%A').lower()  # Exclude users on their day off
        )
        
        total_breaks = 0
        for user in users:
            breaks = BreakManagementService.create_breaks_for_user_shift(user, date)
            total_breaks += len(breaks)
        
        return total_breaks
    
    @staticmethod
    def auto_start_missed_breaks():
        """
        Automatically mark breaks as 'missed' if they weren't started
        and their end time has passed
        """
        now = timezone.now()
        
        # Find scheduled breaks where end time has passed
        missed_breaks = BreakLog.objects.filter(
            status='scheduled',
            scheduled_end__lt=now,
            is_active=True
        )
        
        count = 0
        for break_log in missed_breaks:
            break_log.status = 'missed'
            break_log.system_generated_reason = (
                f"Break was not started by user. "
                f"Scheduled: {break_log.scheduled_start.strftime('%H:%M')} - "
                f"{break_log.scheduled_end.strftime('%H:%M')}"
            )
            break_log.save()
            
            # Create notification for missed break
            BreakManagementService._create_missed_break_notification(break_log)
            
            # Create UserLog entry
            BreakManagementService._create_missed_break_log(break_log)
            
            count += 1
        
        return count
    
    @staticmethod
    def auto_end_extended_breaks():
        """
        Check for breaks that are still in 'started' status
        but should have ended (extended breaks)
        """
        now = timezone.now()
        
        # Find started breaks where scheduled end + grace period has passed
        grace_period_minutes = 10
        check_time = now - timedelta(minutes=grace_period_minutes)
        
        extended_breaks = BreakLog.objects.filter(
            status='started',
            scheduled_end__lt=check_time,
            is_active=True
        )
        
        count = 0
        for break_log in extended_breaks:
            # Calculate how much time has passed
            time_over = (now - break_log.scheduled_end).total_seconds() / 60
            
            break_log.status = 'extended'
            break_log.system_generated_reason = (
                f"Break extended by approximately {time_over:.0f} minutes. "
                f"User did not manually end the break."
            )
            break_log.save()
            
            # Create notification
            BreakManagementService._create_extended_break_notification(break_log)
            
            count += 1
        
        return count
    
    @staticmethod
    def _create_missed_break_log(break_log):
        """Create UserLog entry for missed break"""
        from userApp.models import UserLog
        
        UserLog.objects.create(
            user=break_log.user,
            log_type='system_event',
            status='absent',
            activity=f"Missed break: {break_log.break_template.name}",
            system_generated_reason=break_log.system_generated_reason,
            scheduled_time=break_log.scheduled_start,
            break_log=break_log,
            is_auto_generated=True,
            notes=f"Break was scheduled from {break_log.scheduled_start.strftime('%H:%M')} to {break_log.scheduled_end.strftime('%H:%M')}"
        )
    
    @staticmethod
    def _create_missed_break_notification(break_log):
        """Create notification for missed break"""
        try:
            from notificationApp.services import NotificationService
            NotificationService.create_missed_break_notification(break_log)
        except ImportError:
            pass  # NotificationService might not exist yet
    
    @staticmethod
    def _create_extended_break_notification(break_log):
        """Create notification for extended break"""
        try:
            from notificationApp.services import NotificationService
            NotificationService.create_break_extended_notification(break_log)
        except ImportError:
            pass



    @staticmethod
    def get_upcoming_breaks(minutes_ahead=5):
        """
        Get all breaks that should start in the next X minutes
        
        Args:
            minutes_ahead: Number of minutes to look ahead (default: 5)
        """
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        check_time = now + timedelta(minutes=minutes_ahead)
        
        # Get all active users with shifts
        users = CustomUser.objects.filter(
            status='active',
            current_shift__isnull=False
        ).exclude(
            day_off=now.strftime('%A').lower()
        )
        
        upcoming_breaks = []
        
        for user in users:
            shift = user.current_shift
            if not shift:
                continue
                
            # Get today's date
            today = now.date()
            
            # Get all active breaks for this shift
            break_templates = shift.breaks.filter(status='active')
            
            for break_template in break_templates:
                # Calculate scheduled start time
                scheduled_start = datetime.combine(today, break_template.start_at)
                scheduled_start = timezone.make_aware(scheduled_start)
                
                # Handle overnight breaks
                if break_template.end_at < break_template.start_at:
                    scheduled_start += timedelta(days=1)
                
                # Check if break is starting within the next X minutes
                time_until_start = (scheduled_start - now).total_seconds() / 60
                
                if 0 <= time_until_start <= minutes_ahead:
                    # Check if break log already exists
                    existing_break = BreakLog.objects.filter(
                        user=user,
                        break_template=break_template,
                        scheduled_start=scheduled_start
                    ).first()
                    
                    if not existing_break:
                        # Calculate end time
                        scheduled_end = datetime.combine(today, break_template.end_at)
                        scheduled_end = timezone.make_aware(scheduled_end)
                        if break_template.end_at < break_template.start_at:
                            scheduled_end += timedelta(days=1)
                        
                        upcoming_breaks.append({
                            'user': user,
                            'break_template': break_template,
                            'scheduled_start': scheduled_start,
                            'scheduled_end': scheduled_end,
                            'minutes_until_start': time_until_start
                        })
        
        return upcoming_breaks
    
    @staticmethod
    def create_upcoming_breaks(minutes_ahead=5):
        """
        Create breaks that will start in the next X minutes
        
        Args:
            minutes_ahead: Number of minutes to look ahead
        Returns:
            List of created break logs
        """
        upcoming = BreakManagementService.get_upcoming_breaks(minutes_ahead)
        created_breaks = []
        
        for break_info in upcoming:
            # Create the break log
            break_log = BreakLog.objects.create(
                user=break_info['user'],
                break_template=break_info['break_template'],
                scheduled_start=break_info['scheduled_start'],
                scheduled_end=break_info['scheduled_end'],
                status='scheduled',
                is_auto_recorded=True,
                system_generated_reason=(
                    f"Auto-created {minutes_ahead} minutes before scheduled start "
                    f"for {break_info['user'].current_shift.name} shift"
                )
            )
            created_breaks.append(break_log)
            
            print(
                f"Created break for {break_info['user'].names}: "
                f"{break_info['break_template'].name} at "
                f"{break_info['scheduled_start'].strftime('%H:%M')} "
                f"(in {break_info['minutes_until_start']:.1f} minutes)"
            )
        
        return created_breaks
    
    @staticmethod
    def create_and_notify_upcoming_breaks(minutes_ahead=5):
        """
        Create breaks 5 minutes before start and send notifications
        """
        from notificationApp.services import NotificationService
        
        upcoming = BreakManagementService.get_upcoming_breaks(minutes_ahead)
        created_breaks = []
        
        for break_info in upcoming:
            # Check if already exists
            existing = BreakLog.objects.filter(
                user=break_info['user'],
                break_template=break_info['break_template'],
                scheduled_start=break_info['scheduled_start']
            ).first()
            
            if existing:
                continue
                
            # Create break log
            break_log = BreakLog.objects.create(
                user=break_info['user'],
                break_template=break_info['break_template'],
                scheduled_start=break_info['scheduled_start'],
                scheduled_end=break_info['scheduled_end'],
                status='scheduled',
                is_auto_recorded=True,
                system_generated_reason=(
                    f"Auto-created {minutes_ahead} minutes before start time"
                )
            )
            created_breaks.append(break_log)
            
            # Send notification to user
            minutes_left = int(break_info['minutes_until_start'])
            if minutes_left > 0:
                try:
                    NotificationService.create_break_reminder_notification(
                        break_log,
                        minutes_left
                    )
                    print(f"Sent {minutes_left}-minute reminder for {break_info['user'].names}")
                except Exception as e:
                    print(f"Failed to send notification: {e}")
        
        return created_breaks
    



