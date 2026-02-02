# taskAssignmentApp/serializers.py
from base64 import b64encode
from rest_framework import serializers
from .models import TaskAssignment, ShiftTaskRotation, TaskOverload
from taskApp.models import Task
from userApp.models import CustomUser

from userApp.serializers import SupervisorSerializer, EmployeeBasicSerializer
from shiftApp.models import Shift
from django.core.mail import send_mail
from django.conf import settings


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
    

class TaskAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for task assignments"""
    user_name = serializers.CharField(source='user.names', read_only=True)
    user_emp_number = serializers.CharField(source='user.emp_number', read_only=True)
    task_name = serializers.CharField(source='task.name', read_only=True)
    task_description = serializers.CharField(source='task.description', read_only=True)
    shift_name = serializers.CharField(source='shift.name', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.names', read_only=True)
    modified_by_name = serializers.CharField(source='modified_by.names', read_only=True)
    
    duration_minutes = serializers.ReadOnlyField()
    actual_duration_minutes = serializers.ReadOnlyField()
    is_current = serializers.ReadOnlyField()
    can_start = serializers.ReadOnlyField()
    time_until_start_minutes = serializers.ReadOnlyField()
    time_until_end_minutes = serializers.ReadOnlyField()
    
    class Meta:
        model = TaskAssignment
        fields = [
            'id', 'user', 'user_name', 'user_emp_number',
            'task', 'task_name', 'task_description',
            'shift', 'shift_name',
            'assignment_date', 'start_time', 'end_time',
            'actual_start_time', 'actual_end_time',
            'status', 'priority', 'sequence_order',
            'is_modified', 'modification_reason',
            'assigned_by', 'assigned_by_name',
            'modified_by', 'modified_by_name',
            'notes', 'reminder_sent', 'reminder_sent_at',
            'duration_minutes', 'actual_duration_minutes',
            'is_current', 'can_start',
            'time_until_start_minutes', 'time_until_end_minutes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'actual_start_time', 'actual_end_time',
            'reminder_sent', 'reminder_sent_at',
            'created_at', 'updated_at'
        ]


class TaskAssignmentModifySerializer(serializers.Serializer):
    """Serializer for modifying task assignments"""
    assignment_id = serializers.IntegerField()
    new_task_id = serializers.IntegerField(required=False, allow_null=True)
    new_start_time = serializers.DateTimeField(required=False, allow_null=True)
    new_end_time = serializers.DateTimeField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class ShiftTaskRotationSerializer(serializers.ModelSerializer):
    """Serializer for shift task rotations"""
    shift_name = serializers.CharField(source='shift.name', read_only=True)
    task_count = serializers.ReadOnlyField()
    created_by_name = serializers.CharField(source='created_by.names', read_only=True)
    tasks_detail = serializers.SerializerMethodField()
    
    class Meta:
        model = ShiftTaskRotation
        fields = [
            'id', 'shift', 'shift_name', 'tasks', 'tasks_detail',
            'rotation_interval_minutes', 'is_active',
            'allow_multiple_employees_per_task',
            'task_count', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_tasks_detail(self, obj):
        return [{'id': task.id, 'name': task.name} for task in obj.tasks.all()]


class TaskOverloadSerializer(serializers.ModelSerializer):
    """Serializer for task overloads"""
    task_name = serializers.CharField(source='task.name', read_only=True)
    shift_name = serializers.CharField(source='shift.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.names', read_only=True)
    
    class Meta:
        model = TaskOverload
        fields = [
            'id', 'task', 'task_name', 'shift', 'shift_name',
            'overload_date', 'additional_employees_needed',
            'time_slot_start', 'time_slot_end', 'reason',
            'is_resolved', 'resolved_at',
            'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'resolved_at', 'created_at', 'updated_at']
        extra_kwargs = {
            'time_slot_start': {'required': False, 'allow_null': True},
            'time_slot_end': {'required': False, 'allow_null': True},
            'reason': {'required': False, 'allow_blank': True, 'allow_null': True}
        }
    
    def validate(self, data):
        """
        Custom validation for TaskOverload
        """
        # If one time slot is provided, both should be provided
        time_start = data.get('time_slot_start')
        time_end = data.get('time_slot_end')
        
        # Only validate if both are not None
        if time_start is not None and time_end is not None:
            if time_start >= time_end:
                raise serializers.ValidationError({
                    'time_slot_end': 'End time must be after start time'
                })
        
        # Validate additional_employees_needed is positive
        if 'additional_employees_needed' in data:
            if data['additional_employees_needed'] <= 0:
                raise serializers.ValidationError({
                    'additional_employees_needed': 'Must be greater than 0'
                })
        
        return data


class TaskOverloadCreateSerializer(serializers.Serializer):
    """
    Alternative serializer for creating task overloads with more flexible field names
    This handles both 'task' and 'task_id', 'shift' and 'shift_id'
    """
    task_id = serializers.IntegerField(required=False)
    task = serializers.IntegerField(required=False)
    shift_id = serializers.IntegerField(required=False)
    shift = serializers.IntegerField(required=False)
    overload_date = serializers.DateField()
    additional_employees_needed = serializers.IntegerField(min_value=1)
    time_slot_start = serializers.TimeField(required=False, allow_null=True)
    time_slot_end = serializers.TimeField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    def validate(self, data):
        """
        Ensure either task or task_id is provided, and either shift or shift_id
        """
        # Check for task
        if not data.get('task') and not data.get('task_id'):
            raise serializers.ValidationError({
                'task': 'Either task or task_id must be provided'
            })
        
        # Check for shift
        if not data.get('shift') and not data.get('shift_id'):
            raise serializers.ValidationError({
                'shift': 'Either shift or shift_id must be provided'
            })
        
        # Normalize to use 'task' and 'shift'
        if 'task_id' in data and 'task' not in data:
            data['task'] = data.pop('task_id')
        
        if 'shift_id' in data and 'shift' not in data:
            data['shift'] = data.pop('shift_id')
        
        # Validate time slots if both provided
        if data.get('time_slot_start') and data.get('time_slot_end'):
            if data['time_slot_start'] >= data['time_slot_end']:
                raise serializers.ValidationError({
                    'time_slot_end': 'End time must be after start time'
                })
        
        return data


