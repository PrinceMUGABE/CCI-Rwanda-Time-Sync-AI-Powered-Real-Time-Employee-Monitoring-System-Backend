# requestApp/models.py

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from userApp.models import CustomUser
from shiftApp.models import Shift


class ShiftChangeRequest(models.Model):
    """Model for handling shift and day-off change requests"""
    
    CHANGE_TYPE_CHOICES = [
        ('shift_only', 'Shift Only'),
        ('day_off_only', 'Day Off Only'),
        ('both', 'Both Shift and Day Off'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('cancelled', 'Cancelled'),
    ]
    
    DAY_CHOICES = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
        ('none', 'No Day Off'),
    ]
    
    # Request metadata
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='shift_change_requests',
        help_text="Employee making the request"
    )
    
    change_type = models.CharField(
        max_length=20,
        choices=CHANGE_TYPE_CHOICES,
        help_text="What is being requested to change"
    )
    
    reason = models.TextField(
        help_text="Reason for the change request"
    )
    
    # Current values (stored for reference)
    current_shift = models.ForeignKey(
        Shift,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_shift_requests',
        help_text="Current shift of the employee"
    )
    
    current_day_off = models.CharField(
        max_length=20,
        choices=DAY_CHOICES,
        blank=True,
        null=True,
        help_text="Current day off of the employee"
    )
    
    # Requested new values
    new_shift = models.ForeignKey(
        Shift,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='new_shift_requests',
        help_text="Requested new shift"
    )
    
    new_day_off = models.CharField(
        max_length=20,
        choices=DAY_CHOICES,
        blank=True,
        null=True,
        help_text="Requested new day off"
    )
    
    # Effective date
    start_date = models.DateField(
        help_text="Date when the change should take effect if accepted"
    )
    
    # Status and approval
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    approved_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_shift_requests',
        help_text="Supervisor or admin who approved the request"
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when request was approved"
    )
    
    cancelled_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_shift_requests',
        help_text="User who cancelled the request"
    )
    
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when request was cancelled"
    )
    
    cancellation_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for cancellation"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Exact time the request was sent"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Shift Change Request'
        verbose_name_plural = 'Shift Change Requests'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['start_date']),
        ]
    
    def __str__(self):
        return f"{self.user.names} - {self.change_type} - {self.status} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    def clean(self):
        """Validate the request data"""
        super().clean()
        
        # Validate based on change type
        if self.change_type == 'shift_only':
            if not self.new_shift:
                raise ValidationError({
                    'new_shift': 'New shift must be provided for shift-only change.'
                })
            if self.new_day_off:
                raise ValidationError({
                    'new_day_off': 'Day off should not be provided for shift-only change.'
                })
        
        elif self.change_type == 'day_off_only':
            if not self.new_day_off:
                raise ValidationError({
                    'new_day_off': 'New day off must be provided for day-off-only change.'
                })
            if self.new_shift:
                raise ValidationError({
                    'new_shift': 'Shift should not be provided for day-off-only change.'
                })
        
        elif self.change_type == 'both':
            if not self.new_shift:
                raise ValidationError({
                    'new_shift': 'New shift must be provided when changing both.'
                })
            if not self.new_day_off:
                raise ValidationError({
                    'new_day_off': 'New day off must be provided when changing both.'
                })
        
        # Validate start date is not in the past
        if self.start_date and self.start_date < timezone.now().date():
            raise ValidationError({
                'start_date': 'Start date cannot be in the past.'
            })
        
        # Validate that new values are different from current values
        if self.change_type in ['shift_only', 'both']:
            if self.new_shift and self.current_shift and self.new_shift == self.current_shift:
                raise ValidationError({
                    'new_shift': 'New shift must be different from current shift.'
                })
        
        if self.change_type in ['day_off_only', 'both']:
            if self.new_day_off and self.current_day_off and self.new_day_off == self.current_day_off:
                raise ValidationError({
                    'new_day_off': 'New day off must be different from current day off.'
                })
    
    def save(self, *args, **kwargs):
        """Override save to perform validation and set current values"""
        # Set current values from user if not already set
        if not self.pk:  # Only on creation
            if not self.current_shift:
                self.current_shift = self.user.current_shift
            if not self.current_day_off:
                self.current_day_off = self.user.day_off
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def approve(self, approved_by_user):
        """Approve the request and apply changes to user"""
        if self.status != 'pending':
            raise ValidationError("Only pending requests can be approved.")
        
        # Check if approver has permission
        if not (approved_by_user.is_admin or 
                (approved_by_user.is_supervisor and approved_by_user.can_supervise(self.user))):
            raise ValidationError("You don't have permission to approve this request.")
        
        # Update request status
        self.status = 'accepted'
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.save()
        
        # Apply changes to user
        if self.change_type in ['shift_only', 'both']:
            self.user.current_shift = self.new_shift
        
        if self.change_type in ['day_off_only', 'both']:
            self.user.day_off = self.new_day_off
        
        self.user.save()
    
    def cancel(self, cancelled_by_user, reason=None):
        """Cancel the request"""
        if self.status != 'pending':
            raise ValidationError("Only pending requests can be cancelled.")
        
        # Check if user has permission to cancel
        if not (cancelled_by_user == self.user or 
                cancelled_by_user.is_admin or 
                (cancelled_by_user.is_supervisor and cancelled_by_user.can_supervise(self.user))):
            raise ValidationError("You don't have permission to cancel this request.")
        
        self.status = 'cancelled'
        self.cancelled_by = cancelled_by_user
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.save()
    
    @property
    def is_pending(self):
        """Check if request is pending"""
        return self.status == 'pending'
    
    @property
    def is_accepted(self):
        """Check if request is accepted"""
        return self.status == 'accepted'
    
    @property
    def is_cancelled(self):
        """Check if request is cancelled"""
        return self.status == 'cancelled'
    
    @property
    def can_be_modified(self):
        """Check if request can still be modified"""
        return self.status == 'pending'
    
    @property
    def days_until_effective(self):
        """Calculate days until the change becomes effective"""
        if self.start_date:
            delta = self.start_date - timezone.now().date()
            return delta.days
        return None