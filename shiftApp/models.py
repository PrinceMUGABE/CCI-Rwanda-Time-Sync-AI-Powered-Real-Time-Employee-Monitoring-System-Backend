# shiftApp/models.py

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import time, datetime, timedelta


class Shift(models.Model):
    """Template for shifts that can be assigned to users on different dates"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    name = models.CharField(max_length=200, help_text="e.g., Morning Shift, Night Shift")
    start_at = models.TimeField(help_text="Time when shift starts (e.g., 08:00)")
    end_at = models.TimeField(help_text="Time when shift ends (e.g., 16:00)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['start_at']
        verbose_name = 'Shift'
        verbose_name_plural = 'Shifts'
    
    def __str__(self):
        return f"{self.name} ({self.start_at.strftime('%H:%M')} - {self.end_at.strftime('%H:%M')})"
    
    def clean(self):
        """Validate shift times"""
        super().clean()
        if self.start_at and self.end_at:
            # Convert to datetime for calculation
            start_dt = datetime.combine(datetime.today(), self.start_at)
            end_dt = datetime.combine(datetime.today(), self.end_at)
            
            # Handle overnight shifts (e.g., 22:00 - 06:00)
            if self.end_at < self.start_at:
                end_dt += timedelta(days=1)
            
            # Check if shift duration is reasonable (not more than 24 hours)
            duration = (end_dt - start_dt).total_seconds() / 3600
            if duration > 24:
                raise ValidationError({
                    'end_at': 'Shift duration cannot exceed 24 hours.'
                })
            
            # Minimum shift duration (e.g., 1 hour)
            if duration < 1:
                raise ValidationError({
                    'end_at': 'Shift duration must be at least 1 hour.'
                })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def duration_hours(self):
        """Calculate shift duration in hours"""
        if self.start_at and self.end_at:
            start_dt = datetime.combine(datetime.today(), self.start_at)
            end_dt = datetime.combine(datetime.today(), self.end_at)
            
            # Handle overnight shifts
            if self.end_at < self.start_at:
                end_dt += timedelta(days=1)
            
            return (end_dt - start_dt).total_seconds() / 3600
        return 0
    
    @property
    def is_overnight(self):
        """Check if shift spans across midnight"""
        return self.end_at < self.start_at
    
    def get_datetime_range(self, date):
        """Get actual datetime range for a specific date"""
        start_datetime = datetime.combine(date, self.start_at)
        end_datetime = datetime.combine(date, self.end_at)
        
        # If overnight shift, end time is next day
        if self.is_overnight:
            end_datetime += timedelta(days=1)
        
        # Make timezone aware
        if timezone.is_naive(start_datetime):
            start_datetime = timezone.make_aware(start_datetime)
        if timezone.is_naive(end_datetime):
            end_datetime = timezone.make_aware(end_datetime)
        
        return start_datetime, end_datetime
    
    def get_working_hours_after_breaks(self):
        """Calculate actual working hours after deducting breaks"""
        total_breaks = self.breaks.filter(status='active').aggregate(
            total_duration=models.Sum(models.F('duration_minutes'))
        )['total_duration'] or 0
        
        return self.duration_hours - (total_breaks / 60)


class BreakTemplate(models.Model):
    """Template for breaks within a shift"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    shift = models.ForeignKey(
        Shift,
        on_delete=models.CASCADE,
        related_name='breaks'
    )
    name = models.CharField(max_length=200, help_text="e.g., Lunch Break, Tea Break")
    start_at = models.TimeField(help_text="Time when break starts (e.g., 12:00)")
    end_at = models.TimeField(help_text="Time when break ends (e.g., 13:00)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['shift', 'start_at']
        verbose_name = 'Break Template'
        verbose_name_plural = 'Break Templates'
        unique_together = ['shift', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.start_at.strftime('%H:%M')} - {self.end_at.strftime('%H:%M')})"
    
    def clean(self):
        """Validate break times"""
        super().clean()
        if self.start_at and self.end_at:
            # Convert to datetime for calculation
            start_dt = datetime.combine(datetime.today(), self.start_at)
            end_dt = datetime.combine(datetime.today(), self.end_at)
            
            # Handle overnight breaks (within overnight shifts)
            if self.end_at < self.start_at:
                end_dt += timedelta(days=1)
            
            # Check break duration
            duration = (end_dt - start_dt).total_seconds() / 60  # in minutes
            
            # Minimum break duration
            if duration < 5:
                raise ValidationError({
                    'end_at': 'Break duration must be at least 5 minutes.'
                })
            
            # Maximum break duration
            if duration > 180:
                raise ValidationError({
                    'end_at': 'Break duration cannot exceed 3 hours.'
                })
            
            # Check if break is within shift hours
            if self.shift_id:
                shift_start_dt = datetime.combine(datetime.today(), self.shift.start_at)
                shift_end_dt = datetime.combine(datetime.today(), self.shift.end_at)
                
                if self.shift.is_overnight:
                    if self.shift.end_at < self.shift.start_at:
                        shift_end_dt += timedelta(days=1)
                
                # For overnight shifts and breaks
                if self.shift.is_overnight:
                    if self.end_at < self.start_at:
                        # Break spans midnight
                        break_within_shift = (
                            (shift_start_dt <= start_dt <= shift_end_dt) or
                            (shift_start_dt <= end_dt <= shift_end_dt)
                        )
                    else:
                        # Break doesn't span midnight
                        break_within_shift = (
                            shift_start_dt <= start_dt <= shift_end_dt and
                            shift_start_dt <= end_dt <= shift_end_dt
                        )
                else:
                    # Normal shift
                    break_within_shift = (
                        shift_start_dt <= start_dt <= shift_end_dt and
                        shift_start_dt <= end_dt <= shift_end_dt
                    )
                
                if not break_within_shift:
                    raise ValidationError({
                        'start_at': 'Break must be within shift hours.',
                        'end_at': 'Break must be within shift hours.'
                    })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def duration_minutes(self):
        """Calculate break duration in minutes"""
        if self.start_at and self.end_at:
            start_dt = datetime.combine(datetime.today(), self.start_at)
            end_dt = datetime.combine(datetime.today(), self.end_at)
            
            if self.end_at < self.start_at:
                end_dt += timedelta(days=1)
            
            return (end_dt - start_dt).total_seconds() / 60
        return 0

