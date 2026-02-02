# taskAssignmentApp/models.py
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from django.db.models import Q


class TaskAssignment(models.Model):
    """Individual task assignment for an employee during their shift"""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
        ('reassigned', 'Reassigned'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    user = models.ForeignKey(
        'userApp.CustomUser',
        on_delete=models.CASCADE,
        related_name='task_assignments'
    )
    
    task = models.ForeignKey(
        'taskApp.Task',
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    
    shift = models.ForeignKey(
        'shiftApp.Shift',
        on_delete=models.CASCADE,
        related_name='task_assignments'
    )
    
    
    # Timing
    assignment_date = models.DateField(help_text="Date of the assignment")
    start_time = models.DateTimeField(help_text="When employee should start this task")
    end_time = models.DateTimeField(help_text="When employee should finish this task")
    
    # Actual timing
    actual_start_time = models.DateTimeField(null=True, blank=True)
    actual_end_time = models.DateTimeField(null=True, blank=True)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Assignment tracking
    sequence_order = models.IntegerField(
        help_text="Order of this task in employee's daily rotation",
        default=0
    )
    
    is_modified = models.BooleanField(
        default=False,
        help_text="True if assignment was manually modified by admin/supervisor"
    )
    
    modification_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for manual modification"
    )
    
    # Metadata
    assigned_by = models.ForeignKey(
        'userApp.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments_created'
    )
    
    modified_by = models.ForeignKey(
        'userApp.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments_modified'
    )
    
    notes = models.TextField(blank=True, null=True)

    metadata = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Store tracking data like sent reminders"
    )
    
    # Notification tracking
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['assignment_date', 'start_time', 'sequence_order']
        verbose_name = 'Task Assignment'
        verbose_name_plural = 'Task Assignments'
        indexes = [
            models.Index(fields=['user', 'assignment_date', 'status']),
            models.Index(fields=['assignment_date', 'start_time']),
            models.Index(fields=['status', 'start_time']),
        ]
        unique_together = ['user', 'assignment_date', 'sequence_order']
    
    def __str__(self):
        return f"{self.user.names} - {self.task.name} - {self.assignment_date} ({self.status})"
    
    def clean(self):
        """Validate assignment times"""
        super().clean()
        
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValidationError({
                    'end_time': 'End time must be after start time.'
                })
            
            # Check if assignment is within shift hours
            if self.shift:
                shift_start, shift_end = self.shift.get_datetime_range(self.assignment_date)
                
                if self.start_time < shift_start or self.end_time > shift_end:
                    raise ValidationError({
                        'start_time': 'Assignment must be within shift hours.',
                        'end_time': 'Assignment must be within shift hours.'
                    })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def duration_minutes(self):
        """Calculate scheduled duration in minutes"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 60
        return 0
    
    @property
    def actual_duration_minutes(self):
        """Calculate actual duration in minutes"""
        if self.actual_start_time and self.actual_end_time:
            return (self.actual_end_time - self.actual_start_time).total_seconds() / 60
        return None
    
    @property
    def is_current(self):
        """Check if this assignment is currently active"""
        now = timezone.now()
        return self.start_time <= now <= self.end_time and self.status in ['scheduled', 'active']
    
    @property
    def can_start(self):
        """Check if assignment can be started"""
        now = timezone.now()
        return (
            self.status == 'scheduled' and
            self.start_time <= now and
            now <= self.end_time
        )
    
    @property
    def time_until_start_minutes(self):
        """Calculate minutes until assignment starts"""
        now = timezone.now()
        if self.start_time > now:
            return (self.start_time - now).total_seconds() / 60
        return 0
    
    @property
    def time_until_end_minutes(self):
        """Calculate minutes until assignment ends"""
        now = timezone.now()
        if self.end_time > now:
            return (self.end_time - now).total_seconds() / 60
        return 0
    
    def start_assignment(self):
        """Mark assignment as active"""
        if not self.can_start:
            raise ValidationError("Assignment cannot be started at this time")
        
        self.status = 'active'
        self.actual_start_time = timezone.now()
        self.save()
        
        # Create user log
        self._create_user_log('task_start')
        
        return True
    
    def complete_assignment(self):
        """Mark assignment as completed"""
        if self.status != 'active':
            raise ValidationError("Only active assignments can be completed")
        
        self.status = 'completed'
        self.actual_end_time = timezone.now()
        self.save()
        
        # Create user log
        self._create_user_log('task_end')
        
        return True
    
    def _create_user_log(self, log_type):
        """Create user log entry for task activity"""
        from userApp.models import UserLog
        
        activity_map = {
            'task_start': f"Started task: {self.task.name}",
            'task_end': f"Completed task: {self.task.name}"
        }
        
        UserLog.objects.create(
            user=self.user,
            log_type='system_event',
            status='on_time',
            activity=activity_map.get(log_type, f"Task activity: {self.task.name}"),
            scheduled_time=self.start_time if log_type == 'task_start' else self.end_time,
            shift=self.shift,
            is_auto_generated=False,
            notes=f"Task assignment ID: {self.id}"
        )


    def save(self, *args, **kwargs):
        # Check if status is changing to 'missed'
        if self.pk:
            old_instance = TaskAssignment.objects.get(pk=self.pk)
            if old_instance.status != 'missed' and self.status == 'missed':
                # Create missed task notification
                try:
                    from notificationApp.services import NotificationService
                    NotificationService.create_task_missed_alert(self)
                except Exception as e:
                    print(f"Error creating missed task notification: {str(e)}")
        
        self.full_clean()
        super().save(*args, **kwargs)


class ShiftTaskRotation(models.Model):
    """Defines task rotation schedule for a shift"""
    shift = models.ForeignKey(
        'shiftApp.Shift',
        on_delete=models.CASCADE,
        related_name='task_rotations'
    )
    
    tasks = models.ManyToManyField(
        'taskApp.Task',
        related_name='shift_rotations',
        help_text="Tasks to rotate through during this shift"
    )
    
    rotation_interval_minutes = models.IntegerField(
        default=60,
        help_text="Minutes each employee works on a task before rotating"
    )
    
    is_active = models.BooleanField(default=True)
    
    # Overload handling
    allow_multiple_employees_per_task = models.BooleanField(
        default=False,
        help_text="Allow multiple employees on same task for overload"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'userApp.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rotations_created'
    )
    
    class Meta:
        verbose_name = 'Shift Task Rotation'
        verbose_name_plural = 'Shift Task Rotations'
    
    def __str__(self):
        return f"{self.shift.name} - Task Rotation"
    
    @property
    def task_count(self):
        """Get number of tasks in rotation"""
        return self.tasks.count()


class TaskOverload(models.Model):
    """Track task overload situations requiring multiple employees"""
    task = models.ForeignKey(
        'taskApp.Task',
        on_delete=models.CASCADE,
        related_name='overloads'
    )
    
    shift = models.ForeignKey(
        'shiftApp.Shift',
        on_delete=models.CASCADE,
        related_name='task_overloads'
    )
    
    overload_date = models.DateField()
    additional_employees_needed = models.IntegerField(
        default=1,
        help_text="Additional employees needed beyond normal rotation"
    )
    
    time_slot_start = models.TimeField(
        null=True,
        blank=True,
        help_text="Specific time slot start (optional)"
    )
    
    time_slot_end = models.TimeField(
        null=True,
        blank=True,
        help_text="Specific time slot end (optional)"
    )
    
    reason = models.TextField(help_text="Reason for overload")
    
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(
        'userApp.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='overloads_created'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Task Overload'
        verbose_name_plural = 'Task Overloads'
        ordering = ['-overload_date', '-created_at']
    
    def __str__(self):
        return f"{self.task.name} - {self.overload_date} (+{self.additional_employees_needed})"




