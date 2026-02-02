# userApp/serializers.py

from base64 import b64encode, b64decode
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import CustomUser, UserLog
import io
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
import random
import string
from shiftApp.models import Shift

def generate_secure_password():
    """Generate a secure random password that meets complexity requirements."""
    try:
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special_chars = "!@#$%^&*(),.?\":{}|<>"
        
        password = [
            random.choice(lowercase),
            random.choice(uppercase),
            random.choice(digits),
            random.choice(special_chars)
        ]
        
        all_chars = lowercase + uppercase + digits + special_chars
        password.extend(random.choice(all_chars) for _ in range(4))
        
        random.shuffle(password)
        return ''.join(password)
    except Exception as e:
        error_msg = f"Error generating secure password: {str(e)}"
        print(error_msg)
        return None        



class SupervisorSerializer(serializers.ModelSerializer):
    """Serializer for supervisor information"""
    profile_picture = serializers.SerializerMethodField()
    gender = serializers.ChoiceField(
        choices=CustomUser.GENDER_CHOICES,
        required=False  # Changed from write_only=True
    )
    
    class Meta:
        model = CustomUser
        fields = ['id', 'emp_number', 'names', 'email', 'phone_number', 'role', 
                  'status', 'created_at', 'gender', 'profile_picture', 'day_off', 'current_shift', 'salary', 'is_active']
        read_only_fields = fields

    def get_profile_picture(self, obj):
        """Convert binary profile picture to base64"""
        try:
            if obj.profile_picture:
                return b64encode(obj.profile_picture).decode('utf-8')
            return None
        except Exception as e:
            print(f"Error encoding profile picture: {str(e)}")
            return None


class EmployeeBasicSerializer(serializers.ModelSerializer):
    """Basic employee information"""
    profile_picture = serializers.SerializerMethodField()
    gender = serializers.ChoiceField(
        choices=CustomUser.GENDER_CHOICES,
        required=False  # Changed from write_only=True
    )
    
    class Meta:
        model = CustomUser
        fields = ['id', 'emp_number', 'names', 'email', 'phone_number', 'role', 
                  'status', 'created_at', 'gender', 'profile_picture', 'salary', 'day_off', 'current_shift']
        read_only_fields = fields

    def get_profile_picture(self, obj):
        """Convert binary profile picture to base64"""
        try:
            if obj.profile_picture:
                return b64encode(obj.profile_picture).decode('utf-8')
            return None
        except Exception as e:
            print(f"Error encoding profile picture: {str(e)}")
            return None


class CustomUserSerializer(serializers.ModelSerializer):
    """Serializer for user operations"""
    supervisors = SupervisorSerializer(many=True, read_only=True)
    supervisor_ids = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(role='supervisor'),
        many=True,
        write_only=True,
        required=False,
        source='supervisors'
    )
    supervised_employees = EmployeeBasicSerializer(many=True, read_only=True)
    current_shift_name = serializers.CharField(source='current_shift.name', read_only=True)
    current_shift_id = serializers.IntegerField(source='current_shift.id', read_only=True)
    profile_picture = serializers.SerializerMethodField()
    profile_picture_upload = serializers.ImageField(write_only=True, required=False)
    
    gender = serializers.ChoiceField(
        choices=CustomUser.GENDER_CHOICES,
        required=False  # Changed from write_only=True
    )
    
    send_credentials = serializers.BooleanField(write_only=True, required=False, default=True)
    current_shift_field = serializers.PrimaryKeyRelatedField(
        queryset=Shift.objects.all(),
        write_only=True,
        required=False,
        source='current_shift',
        allow_null=True
    )
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'emp_number', 'names', 'email', 'profile_picture', 
            'profile_picture_upload', 'phone_number', 'salary', 'status', 
            'role', 'current_shift', 'current_shift_id', 'current_shift_name', 
            'current_shift_field',
            'supervisors', 'supervisor_ids', 'supervised_employees', 
            'created_at', 'updated_at', 'created_by', 
            'is_active', 'day_off', 'gender', 'send_credentials'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def get_profile_picture(self, obj):
        """Convert binary profile picture to base64"""
        try:
            if obj.profile_picture:
                return b64encode(obj.profile_picture).decode('utf-8')
            return None
        except Exception as e:
            print(f"Error encoding profile picture: {str(e)}")
            return None
    
    def validate(self, attrs):
        
        # Role-based validation
        role = attrs.get('role', self.instance.role if self.instance else None)
        supervisors = attrs.get('supervisors', [])
        
        if role == 'employee':
            if self.instance is None and not supervisors:
                raise serializers.ValidationError({
                    'supervisor_ids': 'Employees must have at least one supervisor assigned.'
                })
        
        if role in ['admin', 'supervisor'] and supervisors:
            raise serializers.ValidationError({
                'supervisor_ids': 'Admins and Supervisors cannot be assigned supervisors.'
            })
        
        return attrs
    
    def create(self, validated_data):
        try:
            # Extract send_credentials flag
            send_credentials = validated_data.pop('send_credentials', True)
            
            supervisors = validated_data.pop('supervisors', [])
            profile_picture_upload = validated_data.pop('profile_picture_upload', None)
            
            # Generate secure password
            generated_password = generate_secure_password()
            
            # Convert uploaded image to binary
            if profile_picture_upload:
                validated_data['profile_picture'] = profile_picture_upload.read()
            
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                validated_data['created_by'] = request.user
            
            # Create user with generated password
            user = CustomUser.objects.create_user(
                password=generated_password,
                **validated_data
            )
            
            if user.role == 'employee' and supervisors:
                user.supervisors.set(supervisors)
            
            # Send credentials email if requested and user is not created by themselves
            if send_credentials and request and request.user != user:
                self._send_credentials_email(user, generated_password, request.user)
            
            return user
        except Exception as e:
            print(f"Error creating user: {str(e)}")
            raise
    
    def update(self, instance, validated_data):
        try:
            # Extract send_credentials flag
            send_credentials = validated_data.pop('send_credentials', False)
            
            supervisors = validated_data.pop('supervisors', None)
            profile_picture_upload = validated_data.pop('profile_picture_upload', None)
            
            # Convert uploaded image to binary
            if profile_picture_upload:
                validated_data['profile_picture'] = profile_picture_upload.read()
            
            # Update all fields including gender
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            # Only generate and send new password if explicitly requested
            if send_credentials:
                generated_password = generate_secure_password()
                instance.set_password(generated_password)
                
                request = self.context.get('request')
                if request and request.user.is_authenticated and request.user != instance:
                    self._send_password_reset_email(instance, generated_password, request.user)
            
            instance.save()
            
            if supervisors is not None:
                if instance.role == 'employee':
                    instance.supervisors.set(supervisors)
                else:
                    instance.supervisors.clear()
            
            return instance
        except Exception as e:
            print(f"Error updating user: {str(e)}")
            raise
    
    def _send_credentials_email(self, user, password, created_by):
        """Send welcome email with credentials to new user"""
        try:
            subject = f"Welcome to TimeSync System - Your Account Details"
            
            message = f"""
Dear {user.names},

Welcome to TimeSync System!

Your account has been created by {created_by.names} ({created_by.role}).

Here are your login credentials:

Employee Number: {user.emp_number}
Temporary Password: {password}
Email: {user.email}

**Important Security Notice:**
1. Please login immediately and change your password
2. Your temporary password will expire in 7 days
3. You can login using:
   - Employee number and password
   - Face recognition (after uploading profile picture)
   - OTP verification

Login URL: {settings.FRONTEND_URL}/login

Role: {user.get_role_display()}
Status: {user.get_status_display()}

For security reasons, please:
1. Change your password immediately after first login
2. Upload a profile picture for face recognition login
3. Keep your login credentials confidential

If you have any questions, please contact your supervisor or system administrator.

Best regards,
TimeSync System Team
"""
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            
            print(f"Credentials email sent to {user.email}")
            
            # Also send notification to creator/admin
            admin_subject = f"New User Account Created: {user.emp_number}"
            admin_message = f"""
Hello {created_by.names},

You have successfully created a new user account:

User: {user.names}
Employee Number: {user.emp_number}
Email: {user.email}
Role: {user.get_role_display()}
Status: {user.get_status_display()}

Login credentials have been sent to the user's email address.

Note: The temporary password will expire in 7 days if not changed.

TimeSync System
"""
            
            send_mail(
                subject=admin_subject,
                message=admin_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[created_by.email],
                fail_silently=True,
            )
            
        except Exception as e:
            print(f"Error sending credentials email: {str(e)}")
            # Log error but don't fail user creation
    
    def _send_password_reset_email(self, user, new_password, updated_by):
        """Send password reset email to user"""
        try:
            subject = f"Your Password Has Been Reset - TimeSync System"
            
            message = f"""
Dear {user.names},

Your password has been reset by {updated_by.names} ({updated_by.role}).

Your new temporary password is: {new_password}

**Important:**
1. Please login and change your password immediately
2. This temporary password will expire in 24 hours
3. For security, change to a strong, memorable password

Login URL: {settings.FRONTEND_URL}/login

If you did not request this change, please contact your supervisor immediately.

Best regards,
TimeSync System Team
"""
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            
            print(f"Password reset email sent to {user.email}")
            
        except Exception as e:
            print(f"Error sending password reset email: {str(e)}")

class UserListSerializer(serializers.ModelSerializer):
    """Serializer for user list"""
    supervisor_count = serializers.SerializerMethodField()
    employee_count = serializers.SerializerMethodField()
    current_shift_name = serializers.CharField(source='current_shift.name', read_only=True)
    profile_picture = serializers.SerializerMethodField()
    

    # UPDATE: Make gender readable (remove write_only=True)
    gender = serializers.ChoiceField(
        choices=CustomUser.GENDER_CHOICES,
        required=False  # Changed from write_only=True
    )
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'emp_number', 'names', 'email', 'phone_number', 
            'role', 'status', 'salary', 'current_shift_name',
            'supervisor_count', 'employee_count', 'created_at', 
            'profile_picture', 'day_off', 'gender'
        ]
        read_only_fields = [
            'id', 'emp_number', 'created_at', 'supervisor_count', 
            'employee_count', 'current_shift_name', 'profile_picture'
        ]
    
    def get_profile_picture(self, obj):
        """Convert binary profile picture to base64"""
        try:
            if obj.profile_picture:
                return b64encode(obj.profile_picture).decode('utf-8')
            return None
        except Exception as e:
            print(f"Error encoding profile picture: {str(e)}")
            return None
    
    def get_supervisor_count(self, obj):
        try:
            if obj.role == 'employee':
                return obj.supervisors.count()
            return 0
        except Exception as e:
            print(f"Error getting supervisor count: {str(e)}")
            return 0
    
    def get_employee_count(self, obj):
        try:
            if obj.role == 'supervisor':
                return obj.supervised_employees.count()
            return 0
        except Exception as e:
            print(f"Error getting employee count: {str(e)}")
            return 0

class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile (excluding sensitive fields)"""
    supervisors = SupervisorSerializer(many=True, read_only=True)
    current_shift_name = serializers.CharField(source='current_shift.name', read_only=True)
    current_shift_id = serializers.IntegerField(source='current_shift.id', read_only=True)
    profile_picture = serializers.SerializerMethodField()
    profile_picture_upload = serializers.ImageField(write_only=True, required=False)

    gender = serializers.ChoiceField(
        choices=CustomUser.GENDER_CHOICES,
        write_only=True,
        required=False
    )
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'emp_number', 'names', 'email', 'phone_number', 
            'profile_picture', 'profile_picture_upload', 'role', 'status',
            'current_shift', 'current_shift_id', 'current_shift_name',
            'supervisors', 'created_at', 'updated_at', 'gender'
        ]
        read_only_fields = ['id', 'emp_number', 'role', 'current_shift', 
                            'current_shift_id', 'current_shift_name', 
                            'supervisors', 'created_at', 'updated_at']
    
    def get_profile_picture(self, obj):
        """Convert binary profile picture to base64"""
        try:
            if obj.profile_picture:
                return b64encode(obj.profile_picture).decode('utf-8')
            return None
        except Exception as e:
            print(f"Error encoding profile picture: {str(e)}")
            return None
    
    def update(self, instance, validated_data):
        try:
            profile_picture_upload = validated_data.pop('profile_picture_upload', None)
            
            # Convert uploaded image to binary
            if profile_picture_upload:
                validated_data['profile_picture'] = profile_picture_upload.read()
            
            # Only update allowed fields
            allowed_fields = ['names', 'email', 'phone_number', 'profile_picture']
            for attr, value in validated_data.items():
                if attr in allowed_fields:
                    setattr(instance, attr, value)
            
            instance.save()
            return instance
        except Exception as e:
            print(f"Error updating profile: {str(e)}")
            raise


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change"""
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True, write_only=True)
    
    def validate_old_password(self, value):
        try:
            user = self.context['request'].user
            if not user.check_password(value):
                raise serializers.ValidationError('Old password is incorrect.')
            return value
        except Exception as e:
            print(f"Error validating old password: {str(e)}")
            raise
    
    def validate(self, attrs):
        try:
            if attrs['new_password'] != attrs['new_password_confirm']:
                raise serializers.ValidationError({
                    'new_password_confirm': 'New passwords do not match.'
                })
            return attrs
        except Exception as e:
            print(f"Error validating passwords: {str(e)}")
            raise
    
    def save(self):
        try:
            user = self.context['request'].user
            user.set_password(self.validated_data['new_password'])
            user.save()
            return user
        except Exception as e:
            print(f"Error saving new password: {str(e)}")
            raise


class FaceLoginSerializer(serializers.Serializer):
    """Serializer for face-based login"""
    face_image = serializers.ImageField(required=True, write_only=True)
    emp_number = serializers.CharField(required=False, write_only=True)




class LoginOTPRequestSerializer(serializers.Serializer):
    """Serializer for OTP login request"""
    emp_number = serializers.CharField(required=True, write_only=True)
    password = serializers.CharField(required=True, write_only=True)

class LoginOTPVerifySerializer(serializers.Serializer):
    """Serializer for OTP verification"""
    emp_number = serializers.CharField(required=True, write_only=True)
    otp = serializers.CharField(required=True, write_only=True, max_length=6, min_length=6)

class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""
    email = serializers.EmailField(required=True, write_only=True)

class PasswordResetVerifySerializer(serializers.Serializer):
    """Serializer for password reset OTP verification"""
    email = serializers.EmailField(required=True, write_only=True)
    otp = serializers.CharField(required=True, write_only=True, max_length=6, min_length=6)

class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation"""
    email = serializers.EmailField(required=True, write_only=True)
    otp = serializers.CharField(required=True, write_only=True, max_length=6, min_length=6)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': 'Passwords do not match.'
            })
        return attrs




class UserLogSerializer(serializers.ModelSerializer):
    """Serializer for user logs"""
    user_name = serializers.CharField(source='user.names', read_only=True)
    user_emp_number = serializers.CharField(source='user.emp_number', read_only=True)
    shift_name = serializers.CharField(source='shift.name', read_only=True)
    break_name = serializers.CharField(source='break_log.break_template.name', read_only=True)
    time_difference_minutes = serializers.ReadOnlyField()
    punctuality_category = serializers.ReadOnlyField()
    
    class Meta:
        model = UserLog
        fields = [
            'id', 'user', 'user_name', 'user_emp_number',
            'log_type', 'status', 'activity', 'system_generated_reason',
            'scheduled_time', 'actual_time', 'time_difference_minutes',
            'punctuality_category', 'shift', 'shift_name',
            'break_log', 'break_name', 'ip_address', 'device_info',
            'is_auto_generated', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = fields