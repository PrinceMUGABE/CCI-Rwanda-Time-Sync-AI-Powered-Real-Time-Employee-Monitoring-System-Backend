# reportApp/serializers.py

from rest_framework import serializers
from userApp.models import CustomUser, UserLog
from shiftApp.models import Shift, BreakTemplate
from taskApp.models import Task
from taskAssignmentApp.models import TaskAssignment, ShiftTaskRotation, TaskOverload
from performanceApp.models import BreakLog
from requestApp.models import ShiftChangeRequest
from notificationApp.models import Notification, NotificationPreference


# ==================== User Serializers ====================

class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user information for nested serialization"""
    class Meta:
        model = CustomUser
        fields = ['id', 'emp_number', 'names', 'email', 'role', 'status']


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed user information for reports"""
    current_shift_details = serializers.SerializerMethodField()
    supervisors_details = serializers.SerializerMethodField()
    has_profile_picture = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'emp_number', 'names', 'email', 'phone_number',
            'salary', 'status', 'role', 'gender', 'day_off',
            'current_shift', 'current_shift_details', 'supervisors_details',
            'has_profile_picture', 'is_active', 'created_at', 'updated_at'
        ]
    
    def get_current_shift_details(self, obj):
        if obj.current_shift:
            return {
                'id': obj.current_shift.id,
                'name': obj.current_shift.name,
                'start_at': obj.current_shift.start_at,
                'end_at': obj.current_shift.end_at,
                'duration_hours': obj.current_shift.duration_hours
            }
        return None
    
    def get_supervisors_details(self, obj):
        return [
            {'id': sup.id, 'names': sup.names, 'emp_number': sup.emp_number}
            for sup in obj.supervisors.all()
        ]
    
    def get_has_profile_picture(self, obj):
        return obj.has_profile_picture()


class UserLogSerializer(serializers.ModelSerializer):
    """User log serializer for activity tracking"""
    user_details = UserBasicSerializer(source='user', read_only=True)
    shift_details = serializers.SerializerMethodField()
    time_difference = serializers.SerializerMethodField()
    punctuality = serializers.SerializerMethodField()
    
    class Meta:
        model = UserLog
        fields = [
            'id', 'user', 'user_details', 'log_type', 'status', 'activity',
            'system_generated_reason', 'scheduled_time', 'actual_time',
            'shift', 'shift_details', 'break_log', 'ip_address', 'device_info',
            'is_auto_generated', 'notes', 'time_difference', 'punctuality',
            'created_at', 'updated_at'
        ]
    
    def get_shift_details(self, obj):
        if obj.shift:
            return {
                'id': obj.shift.id,
                'name': obj.shift.name,
                'start_at': obj.shift.start_at,
                'end_at': obj.shift.end_at
            }
        return None
    
    def get_time_difference(self, obj):
        return obj.time_difference_minutes
    
    def get_punctuality(self, obj):
        return obj.punctuality_category


# ==================== Shift Serializers ====================

class BreakTemplateSerializer(serializers.ModelSerializer):
    """Break template serializer"""
    duration_minutes = serializers.ReadOnlyField()
    
    class Meta:
        model = BreakTemplate
        fields = [
            'id', 'shift', 'name', 'start_at', 'end_at',
            'status', 'duration_minutes', 'created_at', 'updated_at'
        ]


class ShiftSerializer(serializers.ModelSerializer):
    """Shift serializer with breaks"""
    breaks = BreakTemplateSerializer(many=True, read_only=True)
    duration_hours = serializers.ReadOnlyField()
    is_overnight = serializers.ReadOnlyField()
    working_hours_after_breaks = serializers.SerializerMethodField()
    assigned_users_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Shift
        fields = [
            'id', 'name', 'start_at', 'end_at', 'status', 'description',
            'duration_hours', 'is_overnight', 'working_hours_after_breaks',
            'breaks', 'assigned_users_count', 'created_at', 'updated_at'
        ]
    
    def get_working_hours_after_breaks(self, obj):
        return obj.get_working_hours_after_breaks()
    
    def get_assigned_users_count(self, obj):
        return obj.assigned_users.filter(status='active').count()


# ==================== Task Serializers ====================

class TaskSerializer(serializers.ModelSerializer):
    """Task serializer"""
    created_by_details = UserBasicSerializer(source='created_by', read_only=True)
    total_assignments = serializers.SerializerMethodField()
    active_assignments = serializers.SerializerMethodField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'name', 'description', 'status',
            'created_by', 'created_by_details',
            'total_assignments', 'active_assignments',
            'created_at', 'updated_at'
        ]
    
    def get_total_assignments(self, obj):
        return obj.assignments.count()
    
    def get_active_assignments(self, obj):
        return obj.assignments.filter(status='active').count()


class TaskAssignmentSerializer(serializers.ModelSerializer):
    """Task assignment serializer"""
    user_details = UserBasicSerializer(source='user', read_only=True)
    task_details = TaskSerializer(source='task', read_only=True)
    shift_details = serializers.SerializerMethodField()
    duration_minutes = serializers.ReadOnlyField()
    actual_duration_minutes = serializers.ReadOnlyField()
    is_current = serializers.ReadOnlyField()
    
    class Meta:
        model = TaskAssignment
        fields = [
            'id', 'user', 'user_details', 'task', 'task_details',
            'shift', 'shift_details', 'assignment_date',
            'start_time', 'end_time', 'actual_start_time', 'actual_end_time',
            'status', 'priority', 'sequence_order', 'is_modified',
            'modification_reason', 'assigned_by', 'modified_by',
            'notes', 'duration_minutes', 'actual_duration_minutes',
            'is_current', 'reminder_sent', 'created_at', 'updated_at'
        ]
    
    def get_shift_details(self, obj):
        return {
            'id': obj.shift.id,
            'name': obj.shift.name,
            'start_at': obj.shift.start_at,
            'end_at': obj.shift.end_at
        }


class ShiftTaskRotationSerializer(serializers.ModelSerializer):
    """Shift task rotation serializer"""
    shift_details = ShiftSerializer(source='shift', read_only=True)
    tasks_details = TaskSerializer(source='tasks', many=True, read_only=True)
    task_count = serializers.ReadOnlyField()
    created_by_details = UserBasicSerializer(source='created_by', read_only=True)
    
    class Meta:
        model = ShiftTaskRotation
        fields = [
            'id', 'shift', 'shift_details', 'tasks', 'tasks_details',
            'rotation_interval_minutes', 'is_active',
            'allow_multiple_employees_per_task', 'task_count',
            'created_by', 'created_by_details', 'created_at', 'updated_at'
        ]


class TaskOverloadSerializer(serializers.ModelSerializer):
    """Task overload serializer"""
    task_details = TaskSerializer(source='task', read_only=True)
    shift_details = serializers.SerializerMethodField()
    created_by_details = UserBasicSerializer(source='created_by', read_only=True)
    
    class Meta:
        model = TaskOverload
        fields = [
            'id', 'task', 'task_details', 'shift', 'shift_details',
            'overload_date', 'additional_employees_needed',
            'time_slot_start', 'time_slot_end', 'reason',
            'is_resolved', 'resolved_at', 'created_by', 'created_by_details',
            'created_at', 'updated_at'
        ]
    
    def get_shift_details(self, obj):
        return {
            'id': obj.shift.id,
            'name': obj.shift.name,
            'start_at': obj.shift.start_at,
            'end_at': obj.shift.end_at
        }


# ==================== Performance Serializers ====================

class BreakLogSerializer(serializers.ModelSerializer):
    """Break log serializer"""
    user_details = UserBasicSerializer(source='user', read_only=True)
    break_template_details = BreakTemplateSerializer(source='break_template', read_only=True)
    scheduled_duration_minutes = serializers.ReadOnlyField()
    actual_duration_minutes = serializers.ReadOnlyField()
    duration_deviation_minutes = serializers.ReadOnlyField()
    start_deviation_minutes = serializers.ReadOnlyField()
    end_deviation_minutes = serializers.ReadOnlyField()
    punctuality_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = BreakLog
        fields = [
            'id', 'user', 'user_details', 'break_template', 'break_template_details',
            'scheduled_start', 'scheduled_end', 'actual_start', 'actual_end',
            'status', 'start_punctuality', 'end_punctuality',
            'system_generated_reason', 'is_auto_recorded',
            'is_active', 'was_user_logged_in', 'notes',
            'scheduled_duration_minutes', 'actual_duration_minutes',
            'duration_deviation_minutes', 'start_deviation_minutes',
            'end_deviation_minutes', 'punctuality_summary',
            'created_at', 'updated_at'
        ]
    
    def get_punctuality_summary(self, obj):
        return obj.get_punctuality_summary()


# ==================== Request Serializers ====================

class ShiftChangeRequestSerializer(serializers.ModelSerializer):
    """Shift change request serializer"""
    user_details = UserBasicSerializer(source='user', read_only=True)
    current_shift_details = serializers.SerializerMethodField()
    new_shift_details = serializers.SerializerMethodField()
    approved_by_details = UserBasicSerializer(source='approved_by', read_only=True)
    cancelled_by_details = UserBasicSerializer(source='cancelled_by', read_only=True)
    days_until_effective = serializers.ReadOnlyField()
    
    class Meta:
        model = ShiftChangeRequest
        fields = [
            'id', 'user', 'user_details', 'change_type', 'reason',
            'current_shift', 'current_shift_details', 'current_day_off',
            'new_shift', 'new_shift_details', 'new_day_off',
            'start_date', 'status', 'approved_by', 'approved_by_details',
            'approved_at', 'cancelled_by', 'cancelled_by_details',
            'cancelled_at', 'cancellation_reason', 'days_until_effective',
            'created_at', 'updated_at'
        ]
    
    def get_current_shift_details(self, obj):
        if obj.current_shift:
            return {
                'id': obj.current_shift.id,
                'name': obj.current_shift.name,
                'start_at': obj.current_shift.start_at,
                'end_at': obj.current_shift.end_at
            }
        return None
    
    def get_new_shift_details(self, obj):
        if obj.new_shift:
            return {
                'id': obj.new_shift.id,
                'name': obj.new_shift.name,
                'start_at': obj.new_shift.start_at,
                'end_at': obj.new_shift.end_at
            }
        return None


# ==================== Notification Serializers ====================

class NotificationSerializer(serializers.ModelSerializer):
    """Notification serializer"""
    user_details = UserBasicSerializer(source='user', read_only=True)
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'user_details', 'notification_type',
            'title', 'message', 'priority', 'break_log', 'user_log',
            'is_read', 'is_sent', 'read_at', 'sent_at',
            'action_url', 'action_text', 'metadata',
            'is_expired', 'created_at', 'updated_at', 'expires_at'
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Notification preference serializer"""
    user_details = UserBasicSerializer(source='user', read_only=True)
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'user', 'user_details',
            'break_start_reminder', 'break_start_reminder_minutes',
            'break_end_reminder', 'break_end_reminder_minutes',
            'break_missed_alert', 'break_extended_alert',
            'shift_start_reminder', 'shift_start_reminder_minutes',
            'shift_end_reminder', 'shift_end_reminder_minutes',
            'login_reminder', 'logout_reminder',
            'system_alerts', 'performance_alerts',
            'web_notifications', 'email_notifications',
            'dnd_enabled', 'dnd_start_time', 'dnd_end_time',
            'created_at', 'updated_at'
        ]