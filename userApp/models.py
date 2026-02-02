# userApp/models.py

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from shiftApp.models import Shift, BreakTemplate


class CustomUserManager(BaseUserManager):
    def create_user(self, emp_number, email, names, phone_number, salary=0, 
                    role='employee', status='active', password=None, created_by=None,
                    **extra_fields):  # Add **extra_fields to accept additional fields
        if not emp_number:
            raise ValueError("The employee number must be provided")
        if not email:
            raise ValueError("The email must be provided")
        if not names:
            raise ValueError("The name must be provided")
        if not phone_number:
            raise ValueError("The phone number must be provided")
        if role not in [choice[0] for choice in CustomUser.ROLE_CHOICES]:
            raise ValueError("Invalid role selected")

        email = self.normalize_email(email)
        user = self.model(
            emp_number=emp_number,
            email=email,
            names=names,
            phone_number=phone_number,
            salary=salary,
            role=role,
            status=status,
            created_by=created_by,
            **extra_fields  # Pass extra fields like current_shift, day_off, gender, etc.
        )
        
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, emp_number, email, names, phone_number, password=None, **extra_fields):
        if not password:
            raise ValueError("The password must be provided for superuser")
        
        # Set default values for superuser
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('status', 'active')
        
        user = self.create_user(
            emp_number=emp_number,
            email=email,
            names=names,
            phone_number=phone_number,
            password=password,
            **extra_fields  # Pass all extra fields including salary
        )
        
        # Ensure superuser flags are set
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)
        return user
class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('supervisor', 'Supervisor'),
        ('employee', 'Employee'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say'),
    ]

    emp_number = models.CharField(max_length=50, unique=True, verbose_name="Employee Number")
    names = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    profile_picture = models.BinaryField(blank=True, null=True)
    phone_number = models.CharField(max_length=15, unique=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        default='prefer_not_to_say'
    )

    day_off = models.CharField(
        max_length=20,
        choices=[
            ('monday', 'Monday'),
            ('tuesday', 'Tuesday'),
            ('wednesday', 'Wednesday'),
            ('thursday', 'Thursday'),
            ('friday', 'Friday'),
            ('saturday', 'Saturday'),
            ('sunday', 'Sunday'),
            ('none', 'No Day Off')  # Default value
        ],
        default='none',
        verbose_name="Weekly Day Off"
    )
    
    # Shift assignment
    current_shift = models.ForeignKey(
        'shiftApp.Shift',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_users'
    )
    
    # Supervisor relationship
    supervisors = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='supervised_employees',
        limit_choices_to={'role': 'supervisor'}
    )
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users'
    )

    USERNAME_FIELD = 'emp_number'
    REQUIRED_FIELDS = ['email', 'names', 'phone_number']

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.emp_number} - {self.names}"

    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_supervisor(self):
        return self.role == 'supervisor'
    
    @property
    def is_employee(self):
        return self.role == 'employee'
    
    def can_manage_users(self):
        """Check if user can manage other users"""
        return self.role == 'admin'
    
    def can_supervise(self, employee):
        """Check if this user can supervise the given employee"""
        if self.role == 'admin':
            return True
        if self.role == 'supervisor':
            return employee in self.supervised_employees.all()
        return False
    
    def has_profile_picture(self):
        """Check if user has uploaded profile picture"""
        try:
            if self.profile_picture:
                # Check if it's bytes and has content
                if isinstance(self.profile_picture, bytes):
                    return len(self.profile_picture) > 0
                # Check if it's memoryview
                elif isinstance(self.profile_picture, memoryview):
                    return len(self.profile_picture) > 0
                return bool(self.profile_picture)
            return False
        except Exception:
            return False
    
    def clean(self):
        """Validate user data"""
        super().clean()
        
        # Supervisors and admins cannot be supervised
        if self.role in ['admin', 'supervisor'] and self.pk:
            if self.supervisors.exists():
                raise ValidationError({
                    'supervisors': 'Admins and Supervisors cannot be assigned supervisors.'
                })
    
    def save(self, *args, **kwargs):
        # Set is_staff for admin users
        if self.role == 'admin':
            self.is_staff = True
        
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User'
        verbose_name_plural = 'Users'






class UserLog(models.Model):
    """Comprehensive user activity logging system"""
    LOG_TYPE_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('break_start', 'Break Start'),
        ('break_end', 'Break End'),
        ('shift_start', 'Shift Start'),
        ('shift_end', 'Shift End'),
        ('system_event', 'System Event'),
    ]
    
    STATUS_CHOICES = [
        ('early', 'Early'),
        ('on_time', 'On Time'),
        ('late', 'Late'),
        ('very_late', 'Very Late'),
        ('absent', 'Absent'),
        ('day_off', 'Day Off'),
        ('system_auto', 'System Auto'),
        ('manual', 'Manual'),
    ]
    
    user = models.ForeignKey(
        'userApp.CustomUser',
        on_delete=models.CASCADE,
        related_name='user_logs'
    )
    log_type = models.CharField(max_length=20, choices=LOG_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    activity = models.CharField(max_length=255, help_text="Description of the activity")
    system_generated_reason = models.TextField(blank=True, null=True)
    
    # Timing information
    scheduled_time = models.DateTimeField(null=True, blank=True, help_text="When it was supposed to happen")
    actual_time = models.DateTimeField(auto_now_add=True, help_text="When it actually happened")
    
    # Related objects (optional)
    shift = models.ForeignKey(
        'shiftApp.Shift',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_logs'
    )
    
    break_log = models.ForeignKey(
        'performanceApp.BreakLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_logs'
    )

    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.CharField(max_length=255, blank=True, null=True)
    is_auto_generated = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-actual_time']
        indexes = [
            models.Index(fields=['user', 'log_type', 'actual_time']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['log_type', 'status']),
        ]
        verbose_name = 'User Log'
        verbose_name_plural = 'User Logs'
    
    def __str__(self):
        return f"{self.user.names} - {self.log_type} - {self.status} - {self.actual_time}"
    
    @property
    def time_difference_minutes(self):
        """Calculate time difference in minutes (negative = early, positive = late)"""
        if self.scheduled_time and self.actual_time:
            diff = self.actual_time - self.scheduled_time
            return diff.total_seconds() / 60
        return None
    
    @property
    def punctuality_category(self):
        """Categorize punctuality"""
        diff = self.time_difference_minutes
        
        if diff is None:
            return "unknown"
        
        if diff < -15:  # More than 15 minutes early
            return "very_early"
        elif -15 <= diff < 0:  # Up to 15 minutes early
            return "early"
        elif 0 <= diff <= 5:  # Up to 5 minutes late
            return "on_time"
        elif 5 < diff <= 30:  # 5-30 minutes late
            return "late"
        else:  # More than 30 minutes late
            return "very_late"