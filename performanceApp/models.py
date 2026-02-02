# backend/performanceApp/models.py
from django.db import models
from shiftApp.models import BreakTemplate
from django.utils import timezone
from django.core.exceptions import ValidationError


class BreakLog(models.Model):
    """Log of actual breaks taken by users"""
    BREAK_STATUS = [
        ('scheduled', 'Scheduled'),
        ('started', 'Started'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
        ('extended', 'Extended'),
        ('shortened', 'Shortened'),
    ]
    
    user = models.ForeignKey(
        'userApp.CustomUser',
        on_delete=models.CASCADE,
        related_name='break_logs'
    )
    
    break_template = models.ForeignKey(
        'shiftApp.BreakTemplate',
        on_delete=models.CASCADE,
        related_name='break_logs'
    )
    
    # Timing
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=BREAK_STATUS, default='scheduled')
    start_punctuality = models.CharField(max_length=20, choices=[
        ('early', 'Early'),
        ('on_time', 'On Time'),
        ('late', 'Late'),
    ], null=True, blank=True)
    
    end_punctuality = models.CharField(max_length=20, choices=[
        ('early', 'Early'),
        ('on_time', 'On Time'),
        ('late', 'Late'),
    ], null=True, blank=True)
    
    # System tracking
    system_generated_reason = models.TextField(blank=True, null=True)
    is_auto_recorded = models.BooleanField(default=False)
    
    # Flags
    is_active = models.BooleanField(default=True)
    was_user_logged_in = models.BooleanField(default=False, help_text="Whether user was logged in when break started")
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['scheduled_start']
        verbose_name = 'Break Log'
        verbose_name_plural = 'Break Logs'
    
    def __str__(self):
        return f"{self.user.names} - {self.break_template.name} - {self.status}"
    
    @property
    def scheduled_duration_minutes(self):
        """Calculate scheduled break duration in minutes"""
        return (self.scheduled_end - self.scheduled_start).total_seconds() / 60
    
    @property
    def actual_duration_minutes(self):
        """Calculate actual break duration in minutes"""
        if self.actual_start and self.actual_end:
            return (self.actual_end - self.actual_start).total_seconds() / 60
        return None
    
    @property
    def duration_deviation_minutes(self):
        """Calculate deviation from scheduled duration"""
        actual = self.actual_duration_minutes
        scheduled = self.scheduled_duration_minutes
        
        if actual is not None:
            return actual - scheduled
        return None
    
    @property
    def start_deviation_minutes(self):
        """Calculate start time deviation in minutes"""
        if self.actual_start:
            diff = (self.actual_start - self.scheduled_start).total_seconds() / 60
            return round(diff, 1)
        return None
    
    @property
    def end_deviation_minutes(self):
        """Calculate end time deviation in minutes"""
        if self.actual_end:
            diff = (self.actual_end - self.scheduled_end).total_seconds() / 60
            return round(diff, 1)
        return None
    
    def can_start_break(self, current_time=None):
        """
        Check if break can be started based on current time
        Returns (can_start, message)
        """
        if not current_time:
            current_time = timezone.now()
        
        # Calculate time difference
        time_to_start = (self.scheduled_start - current_time).total_seconds() / 60
        
        # Check if break is in the future
        if time_to_start > 5:  # More than 5 minutes early
            return False, f"Break cannot be started yet. It starts in {time_to_start:.0f} minutes."
        
        # Check if break is too late (missed)
        if time_to_start < -15:  # More than 15 minutes late
            return False, "Break time has passed. It's now considered missed."
        
        # Check if break is already started or completed
        if self.status != 'scheduled':
            return False, f"Break is already {self.status}."
        
        # Check if user is already on another break
        active_breaks = BreakLog.objects.filter(
            user=self.user,
            status__in=['started'],
            is_active=True
        ).exclude(id=self.id)
        
        if active_breaks.exists():
            return False, "You are already on another break."
        
        return True, "Break can be started"
    
    def calculate_start_punctuality(self):
        """Calculate and set start punctuality based on actual start time"""
        if not self.actual_start:
            return None
        
        deviation = self.start_deviation_minutes
        
        if deviation is None:
            return None
        
        if deviation < -15:  # More than 15 minutes early
            punctuality = 'very_early'
        elif -15 <= deviation < -5:  # 5-15 minutes early
            punctuality = 'early'
        elif -5 <= deviation <= 5:  # Within 5 minutes
            punctuality = 'on_time'
        elif 5 < deviation <= 15:  # 5-15 minutes late
            punctuality = 'late'
        else:  # More than 15 minutes late
            punctuality = 'very_late'
        
        self.start_punctuality = punctuality
        return punctuality
    
    def calculate_end_punctuality(self):
        """Calculate and set end punctuality based on actual end time"""
        if not self.actual_end:
            return None
        
        deviation = self.end_deviation_minutes
        
        if deviation is None:
            return None
        
        if deviation < -15:  # More than 15 minutes early
            punctuality = 'very_early'
        elif -15 <= deviation < -5:  # 5-15 minutes early
            punctuality = 'early'
        elif -5 <= deviation <= 5:  # Within 5 minutes
            punctuality = 'on_time'
        elif 5 < deviation <= 15:  # 5-15 minutes late
            punctuality = 'late'
        else:  # More than 15 minutes late
            punctuality = 'very_late'
        
        self.end_punctuality = punctuality
        return punctuality
    

    def start_break(self, user_logged_in=True, force=False):
        """
        Mark break as started with validation
        Args:
            user_logged_in: Whether user was logged in
            force: Force start even if validation fails (for admin/auto)
        """
        if not force:
            can_start, message = self.can_start_break()
            if not can_start:
                raise ValidationError(message)
        
        if self.status == 'scheduled':
            self.status = 'started'
            self.actual_start = timezone.now()
            self.was_user_logged_in = user_logged_in
            
            # Calculate and set start punctuality
            self.calculate_start_punctuality()
            
            self.save()
            
            # Create UserLog entry
            self._create_user_log('break_start')
            
            return True
        return False
    
    def end_break(self, force=False):
        """
        Mark break as completed and determine final status
        Args:
            force: Force end even if validation fails (for admin/auto)
        """
        if self.status not in ['started', 'extended']:
            if not force:
                raise ValidationError(f"Cannot end break with status: {self.status}")
        
        self.actual_end = timezone.now()
        
        # Calculate and set end punctuality
        self.calculate_end_punctuality()
        
        # Determine final status based on timing
        deviation = self.end_deviation_minutes
        if deviation:
            if deviation > 15:  # More than 15 minutes late
                self.status = 'extended'
            elif deviation < -15:  # More than 15 minutes early
                self.status = 'shortened'
            else:
                self.status = 'completed'
        else:
            self.status = 'completed'
        
        self.save()
        
        # Create UserLog entry
        self._create_user_log('break_end')
        
        # Create notification if break was extended
        if self.status == 'extended':
            try:
                from notificationApp.services import NotificationService
                NotificationService.create_break_extended_notification(self)
            except ImportError:
                pass  # Notification app might not be available
        
        return True

    def _create_user_log(self, log_type):
        """Create a UserLog entry for this break activity"""
        from userApp.models import UserLog  # Import here to avoid circular import
        
        # Determine status based on punctuality
        status = 'on_time'
        if log_type == 'break_start':
            status = self.start_punctuality or 'on_time'
        elif log_type == 'break_end':
            status = self.end_punctuality or 'on_time'
        
        # Generate system reason
        system_reason = self._generate_system_reason(log_type)
        
        UserLog.objects.create(
            user=self.user,
            log_type=log_type,
            status=status,
            activity=f"{self.break_template.name} - {log_type.replace('_', ' ').title()}",
            system_generated_reason=system_reason,
            scheduled_time=self.scheduled_start if log_type == 'break_start' else self.scheduled_end,
            actual_time=timezone.now(),
            break_log=self,
            is_auto_generated=False,
            notes=f"Break duration: {self.scheduled_duration_minutes:.1f} minutes"
        )
    
    def _generate_system_reason(self, log_type):
        """Generate system reason based on user status and timing"""
        reasons = []
        
        # Check if it's user's day off
        if self.user.day_off.lower() == timezone.now().strftime('%A').lower():
            reasons.append(f"User's scheduled day off ({self.user.day_off})")
        
        # Check user login status
        if not self.was_user_logged_in:
            reasons.append("User was not logged into the system")
        else:
            reasons.append("User was active in the system")
        
        # Add timing information
        if log_type == 'break_start':
            diff = self.start_deviation_minutes
            if diff:
                if diff > 0:
                    reasons.append(f"Started {diff:.1f} minutes late")
                elif diff < 0:
                    reasons.append(f"Started {abs(diff):.1f} minutes early")
                else:
                    reasons.append("Started exactly on time")
        
        return "; ".join(reasons)
    



    def get_punctuality_summary(self):
        """Get a summary of punctuality for this break"""
        summary = {
            'start_punctuality': self.start_punctuality,
            'end_punctuality': self.end_punctuality,
            'start_deviation_minutes': self.start_deviation_minutes,
            'end_deviation_minutes': self.end_deviation_minutes,
            'duration_deviation_minutes': self.duration_deviation_minutes,
            'was_on_time': self.start_punctuality == 'on_time' and self.end_punctuality == 'on_time',
        }
        
        return summary
    
    def mark_as_missed(self):
        """Mark break as missed"""
        if self.status == 'scheduled':
            self.status = 'missed'
            self.save()
            
            # Create UserLog for missed break
            try:
                from userApp.models import UserLog
                UserLog.objects.create(
                    user=self.user,
                    log_type='break_missed',
                    status='missed',
                    activity=f"{self.break_template.name} - Break Missed",
                    system_generated_reason="Break was not taken within allowed time window",
                    scheduled_time=self.scheduled_start,
                    actual_time=timezone.now(),
                    is_auto_generated=True,
                    notes="Break was automatically marked as missed"
                )
            except ImportError:
                pass