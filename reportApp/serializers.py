from rest_framework import serializers
from django.db.models import Count, Sum, Avg, Q
from django.utils.timezone import now
from datetime import timedelta

from notificationApp.models import Notification, NotificationPreference
from performanceApp.models import BreakLog
from requestApp.models import ShiftChangeRequest
from shiftApp.models import Shift, BreakTemplate
from taskApp.models import Task
from taskAssignmentApp.models import TaskAssignment
from userApp.models import CustomUser, UserLog


# ==================== USER APP SERIALIZERS ====================
class CustomUserSerializer(serializers.ModelSerializer):
    """Serializer for CustomUser model"""
    shift_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    supervisor_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'emp_number', 'names', 'email', 'phone_number',
            'role', 'gender', 'day_off', 'current_shift', 'shift_name',
            'salary', 'status', 'created_at', 'created_by', 'created_by_name',
            'supervisor_count', 'is_active', 'is_staff'
        ]
    
    def get_shift_name(self, obj):
        return obj.current_shift.name if obj.current_shift else None
    
    def get_created_by_name(self, obj):
        return obj.created_by.names if obj.created_by else None
    
    def get_supervisor_count(self, obj):
        return obj.supervisors.count()


class UserLogSerializer(serializers.ModelSerializer):
    """Serializer for UserLog model"""
    user_name = serializers.SerializerMethodField()
    shift_name = serializers.SerializerMethodField()
    time_difference = serializers.SerializerMethodField()
    
    class Meta:
        model = UserLog
        fields = [
            'id', 'user', 'user_name', 'log_type', 'status',
            'activity', 'system_generated_reason', 'scheduled_time',
            'actual_time', 'shift', 'shift_name', 'break_log',
            'ip_address', 'device_info', 'is_auto_generated',
            'notes', 'created_at', 'time_difference'
        ]
    
    def get_user_name(self, obj):
        return obj.user.names
    
    def get_shift_name(self, obj):
        return obj.shift.name if obj.shift else None
    
    def get_time_difference(self, obj):
        return obj.time_difference_minutes


# ==================== NOTIFICATION APP SERIALIZERS ====================
class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""
    user_name = serializers.SerializerMethodField()
    break_name = serializers.SerializerMethodField()
    is_expired_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'user_name', 'notification_type',
            'title', 'message', 'priority', 'break_log',
            'break_name', 'user_log', 'is_read', 'is_sent',
            'read_at', 'sent_at', 'action_url', 'action_text',
            'metadata', 'created_at', 'expires_at', 'is_expired_status'
        ]
    
    def get_user_name(self, obj):
        return obj.user.names
    
    def get_break_name(self, obj):
        return obj.break_log.break_template.name if obj.break_log else None
    
    def get_is_expired_status(self, obj):
        return obj.is_expired


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for NotificationPreference model"""
    user_name = serializers.SerializerMethodField()
    is_dnd_active = serializers.SerializerMethodField()
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'user', 'user_name', 'break_start_reminder',
            'break_start_reminder_minutes', 'break_end_reminder',
            'break_end_reminder_minutes', 'break_missed_alert',
            'break_extended_alert', 'shift_start_reminder',
            'shift_start_reminder_minutes', 'shift_end_reminder',
            'shift_end_reminder_minutes', 'login_reminder',
            'logout_reminder', 'system_alerts', 'performance_alerts',
            'web_notifications', 'email_notifications', 'dnd_enabled',
            'dnd_start_time', 'dnd_end_time', 'is_dnd_active'
        ]
    
    def get_user_name(self, obj):
        return obj.user.names
    
    def get_is_dnd_active(self, obj):
        return obj.is_dnd_active()


# ==================== PERFORMANCE APP SERIALIZERS ====================
class BreakLogSerializer(serializers.ModelSerializer):
    """Serializer for BreakLog model"""
    user_name = serializers.SerializerMethodField()
    break_name = serializers.SerializerMethodField()
    scheduled_duration = serializers.SerializerMethodField()
    actual_duration = serializers.SerializerMethodField()
    duration_deviation = serializers.SerializerMethodField()
    can_start_break_status = serializers.SerializerMethodField()
    
    class Meta:
        model = BreakLog
        fields = [
            'id', 'user', 'user_name', 'break_template', 'break_name',
            'scheduled_start', 'scheduled_end', 'actual_start',
            'actual_end', 'status', 'start_punctuality', 'end_punctuality',
            'system_generated_reason', 'is_auto_recorded', 'is_active',
            'was_user_logged_in', 'notes', 'scheduled_duration',
            'actual_duration', 'duration_deviation', 'can_start_break_status'
        ]
    
    def get_user_name(self, obj):
        return obj.user.names
    
    def get_break_name(self, obj):
        return obj.break_template.name
    
    def get_scheduled_duration(self, obj):
        return obj.scheduled_duration_minutes
    
    def get_actual_duration(self, obj):
        return obj.actual_duration_minutes
    
    def get_duration_deviation(self, obj):
        return obj.duration_deviation_minutes
    
    def get_can_start_break_status(self, obj):
        return obj.can_start_break()[0] if obj.can_start_break() else False


# ==================== REQUEST APP SERIALIZERS ====================
class ShiftChangeRequestSerializer(serializers.ModelSerializer):
    """Serializer for ShiftChangeRequest model"""
    user_name = serializers.SerializerMethodField()
    current_shift_name = serializers.SerializerMethodField()
    new_shift_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    cancelled_by_name = serializers.SerializerMethodField()
    days_until_effective = serializers.SerializerMethodField()
    
    class Meta:
        model = ShiftChangeRequest
        fields = [
            'id', 'user', 'user_name', 'change_type', 'reason',
            'current_shift', 'current_shift_name', 'current_day_off',
            'new_shift', 'new_shift_name', 'new_day_off', 'start_date',
            'status', 'approved_by', 'approved_by_name', 'approved_at',
            'cancelled_by', 'cancelled_by_name', 'cancelled_at',
            'cancellation_reason', 'created_at', 'days_until_effective',
            'is_pending', 'is_accepted', 'is_cancelled'
        ]
    
    def get_user_name(self, obj):
        return obj.user.names
    
    def get_current_shift_name(self, obj):
        return obj.current_shift.name if obj.current_shift else None
    
    def get_new_shift_name(self, obj):
        return obj.new_shift.name if obj.new_shift else None
    
    def get_approved_by_name(self, obj):
        return obj.approved_by.names if obj.approved_by else None
    
    def get_cancelled_by_name(self, obj):
        return obj.cancelled_by.names if obj.cancelled_by else None
    
    def get_days_until_effective(self, obj):
        return obj.days_until_effective


# ==================== SHIFT APP SERIALIZERS ====================
class ShiftSerializer(serializers.ModelSerializer):
    """Serializer for Shift model"""
    user_count = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    is_overnight_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Shift
        fields = [
            'id', 'name', 'start_at', 'end_at', 'status',
            'description', 'user_count', 'duration',
            'is_overnight_status', 'created_at'
        ]
    
    def get_user_count(self, obj):
        return obj.assigned_users.count()
    
    def get_duration(self, obj):
        return obj.duration_hours
    
    def get_is_overnight_status(self, obj):
        return obj.is_overnight


class BreakTemplateSerializer(serializers.ModelSerializer):
    """Serializer for BreakTemplate model"""
    shift_name = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = BreakTemplate
        fields = [
            'id', 'shift', 'shift_name', 'name', 'start_at',
            'end_at', 'status', 'duration', 'created_at'
        ]
    
    def get_shift_name(self, obj):
        return obj.shift.name
    
    def get_duration(self, obj):
        return obj.duration_minutes


# ==================== TASK APP SERIALIZERS ====================
class TaskSerializer(serializers.ModelSerializer):
    """Serializer for Task model"""
    created_by_name = serializers.SerializerMethodField()
    assignment_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'name', 'description', 'status', 'created_at',
            'updated_at', 'created_by', 'created_by_name', 'assignment_count'
        ]
    
    def get_created_by_name(self, obj):
        return obj.created_by.names if obj.created_by else None
    
    def get_assignment_count(self, obj):
        return obj.assignments.count()


# ==================== TASK ASSIGNMENT APP SERIALIZERS ====================
class TaskAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for TaskAssignment model"""
    user_name = serializers.SerializerMethodField()
    task_name = serializers.SerializerMethodField()
    shift_name = serializers.SerializerMethodField()
    assigned_by_name = serializers.SerializerMethodField()
    modified_by_name = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    actual_duration = serializers.SerializerMethodField()
    time_until_start = serializers.SerializerMethodField()
    time_until_end = serializers.SerializerMethodField()
    is_current_status = serializers.SerializerMethodField()
    
    class Meta:
        model = TaskAssignment
        fields = [
            'id', 'user', 'user_name', 'task', 'task_name', 'shift',
            'shift_name', 'assignment_date', 'start_time', 'end_time',
            'actual_start_time', 'actual_end_time', 'status', 'priority',
            'sequence_order', 'is_modified', 'modification_reason',
            'assigned_by', 'assigned_by_name', 'modified_by', 'modified_by_name',
            'notes', 'metadata', 'reminder_sent', 'reminder_sent_at',
            'duration', 'actual_duration', 'time_until_start', 'time_until_end',
            'is_current_status', 'can_start'
        ]
    
    def get_user_name(self, obj):
        return obj.user.names
    
    def get_task_name(self, obj):
        return obj.task.name
    
    def get_shift_name(self, obj):
        return obj.shift.name
    
    def get_assigned_by_name(self, obj):
        return obj.assigned_by.names if obj.assigned_by else None
    
    def get_modified_by_name(self, obj):
        return obj.modified_by.names if obj.modified_by else None
    
    def get_duration(self, obj):
        return obj.duration_minutes
    
    def get_actual_duration(self, obj):
        return obj.actual_duration_minutes
    
    def get_time_until_start(self, obj):
        return obj.time_until_start_minutes
    
    def get_time_until_end(self, obj):
        return obj.time_until_end_minutes
    
    def get_is_current_status(self, obj):
        return obj.is_current



# ==================== REPORT SERIALIZERS ====================

class ReportSummarySerializer(serializers.Serializer):
    """Base serializer for report summaries"""
    success = serializers.BooleanField()
    message = serializers.CharField(required=False)
    generated_at = serializers.DateTimeField()
    time_period = serializers.CharField(required=False)
    total_count = serializers.IntegerField(required=False)


class AdminDashboardSummarySerializer(ReportSummarySerializer):
    """Admin dashboard summary"""
    users = serializers.DictField()
    shifts = serializers.DictField()
    tasks = serializers.DictField()
    notifications = serializers.DictField()
    breaks = serializers.DictField()
    requests = serializers.DictField()


class UserAnalyticsSummarySerializer(ReportSummarySerializer):
    """User analytics summary"""
    users_by_shift = serializers.ListField()
    users_by_gender = serializers.ListField()
    recent_registrations = serializers.IntegerField()
    active_today = serializers.IntegerField()
    total_users = serializers.IntegerField()
    average_salary = serializers.FloatField()


# AttendanceReportSummarySerializer:
# performanceApp/serializers.py

from rest_framework import serializers
from .models import *


class ReportSummarySerializer(serializers.Serializer):
    """Base report summary serializer"""
    success = serializers.BooleanField(default=True)
    generated_at = serializers.DateTimeField()


class AttendanceDetailSerializer(serializers.Serializer):
    """Individual user attendance detail"""
    user_id = serializers.IntegerField()
    employee_name = serializers.CharField(max_length=200)
    employee_number = serializers.CharField(max_length=50)
    role = serializers.ChoiceField(
        choices=['admin', 'supervisor', 'employee'],
        required=False
    )
    shift = serializers.CharField(max_length=100, allow_null=True)
    day_off = serializers.CharField(max_length=20, allow_null=True, required=False)
    is_day_off = serializers.BooleanField(default=False, required=False)
    first_login_time = serializers.DateTimeField(allow_null=True, required=False)
    last_logout_time = serializers.DateTimeField(allow_null=True, required=False)
    total_logins = serializers.IntegerField(default=0, required=False)
    total_logouts = serializers.IntegerField(default=0, required=False)
    status = serializers.ChoiceField(
        choices=['Present', 'Absent', 'Error'],
        default='Absent'
    )
    hours_worked = serializers.FloatField(allow_null=True, required=False)


class AttendanceSummaryStatsSerializer(serializers.Serializer):
    """Attendance statistics"""
    total_users = serializers.IntegerField(min_value=0)
    present = serializers.IntegerField(min_value=0)
    absent = serializers.IntegerField(min_value=0)
    attendance_rate = serializers.FloatField(min_value=0, max_value=100)


class UserLogDetailSerializer(serializers.Serializer):
    """Detailed user log entry"""
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    user__names = serializers.CharField(max_length=200)
    user__emp_number = serializers.CharField(max_length=50)
    user__role = serializers.CharField(max_length=20, required=False)
    log_type = serializers.ChoiceField(
        choices=['login', 'logout', 'break_start', 'break_end', 
                'shift_start', 'shift_end', 'system_event']
    )
    status = serializers.ChoiceField(
        choices=['early', 'on_time', 'late', 'very_late', 'absent', 
                'day_off', 'system_auto', 'manual']
    )
    activity = serializers.CharField(max_length=255)
    system_generated_reason = serializers.CharField(allow_null=True, required=False)
    scheduled_time = serializers.DateTimeField(allow_null=True, required=False)
    actual_time = serializers.DateTimeField()
    shift_id = serializers.IntegerField(allow_null=True, required=False)
    shift__name = serializers.CharField(max_length=100, allow_null=True, required=False)
    break_log_id = serializers.IntegerField(allow_null=True, required=False)
    break_log__break_template__name = serializers.CharField(
        max_length=100, 
        allow_null=True, 
        required=False
    )
    ip_address = serializers.IPAddressField(allow_null=True, required=False)
    device_info = serializers.CharField(max_length=255, allow_null=True, required=False)
    is_auto_generated = serializers.BooleanField(default=False)
    notes = serializers.CharField(allow_null=True, required=False)
    time_difference_minutes = serializers.FloatField(allow_null=True, required=False)


class LogsByTypeSerializer(serializers.Serializer):
    """Logs organized by type"""
    login = UserLogDetailSerializer(many=True, required=False)
    logout = UserLogDetailSerializer(many=True, required=False)
    break_start = UserLogDetailSerializer(many=True, required=False)
    break_end = UserLogDetailSerializer(many=True, required=False)
    shift_start = UserLogDetailSerializer(many=True, required=False)
    shift_end = UserLogDetailSerializer(many=True, required=False)
    system_event = UserLogDetailSerializer(many=True, required=False)


class AttendanceReportSummarySerializer(ReportSummarySerializer):
    """
    Comprehensive attendance report summary serializer
    Supports both old format (for backward compatibility) and new format
    """
    # Report metadata
    report_generated_by = serializers.CharField(max_length=200)
    report_generator_role = serializers.ChoiceField(
        choices=['admin', 'supervisor', 'employee'],
        required=False
    )
    date = serializers.DateField()
    
    # Attendance statistics
    attendance_summary = AttendanceSummaryStatsSerializer()
    
    # Individual user details
    attendance_details = AttendanceDetailSerializer(many=True)
    
    # Backward compatibility fields (optional)
    supervisor_name = serializers.CharField(
        max_length=200, 
        required=False, 
        allow_blank=True
    )
    total_employees = serializers.IntegerField(required=False, min_value=0)


class DetailedDataSerializer(serializers.Serializer):
    """Detailed data section of the report"""
    logs_by_type = LogsByTypeSerializer(required=False)
    timeline = UserLogDetailSerializer(many=True, required=False)
    summary_by_log_type = serializers.DictField(
        child=serializers.IntegerField(min_value=0),
        required=False
    )
    
    # Backward compatibility (old format)
    login_logs = serializers.ListField(required=False)
    logout_logs = serializers.ListField(required=False)
    total_login_events = serializers.IntegerField(required=False, min_value=0)
    total_logout_events = serializers.IntegerField(required=False, min_value=0)


class ReportMetadataSerializer(serializers.Serializer):
    """Report metadata"""
    report_type = serializers.CharField(max_length=100)
    generated_by = serializers.CharField(max_length=200)
    generator_role = serializers.ChoiceField(
        choices=['admin', 'supervisor', 'employee'],
        required=False
    )
    generated_at = serializers.DateTimeField()
    date = serializers.DateField()
    scope = serializers.ChoiceField(
        choices=['all_users', 'supervisor_and_supervised'],
        required=False
    )
    total_records = serializers.DictField()


class ComprehensiveAttendanceReportSerializer(serializers.Serializer):
    """
    Complete attendance report response serializer
    Validates the entire response structure
    """
    success = serializers.BooleanField(default=True)
    summary = AttendanceReportSummarySerializer()
    detailed_data = DetailedDataSerializer()
    metadata = ReportMetadataSerializer()


# ============================================================================
# BACKWARD COMPATIBLE SERIALIZER (if you want to keep old code working)
# ============================================================================

class LegacyAttendanceDetailSerializer(serializers.Serializer):
    """Old format attendance detail (for backward compatibility)"""
    employee_id = serializers.IntegerField()
    employee_name = serializers.CharField(max_length=200)
    employee_number = serializers.CharField(max_length=50)
    shift = serializers.CharField(max_length=100, allow_null=True)
    login_time = serializers.DateTimeField(allow_null=True)
    logout_time = serializers.DateTimeField(allow_null=True)
    status = serializers.ChoiceField(choices=['Present', 'Absent', 'Error'])
    hours_worked = serializers.FloatField(allow_null=True)


class LegacyAttendanceReportSummarySerializer(ReportSummarySerializer):
    """Old attendance report summary format"""
    supervisor_name = serializers.CharField(required=False, allow_blank=True)
    date = serializers.DateField()
    attendance_summary = serializers.DictField()
    attendance_details = LegacyAttendanceDetailSerializer(many=True)
    total_employees = serializers.IntegerField(required=False)



# Update ShiftReportSummarySerializer:
class ShiftReportSummarySerializer(ReportSummarySerializer):
    """Shift report summary"""
    shifts = serializers.ListField(required=False)
    total_shifts = serializers.IntegerField(required=False)
    active_shifts = serializers.IntegerField(required=False)
    inactive_shifts = serializers.IntegerField(required=False)


class PerformanceReportSummarySerializer(ReportSummarySerializer):
    """Performance report summary"""
    break_performance = serializers.DictField()
    task_performance = serializers.DictField()


class TeamPerformanceSummarySerializer(ReportSummarySerializer):
    """Team performance summary"""
    supervisor_name = serializers.CharField()
    team_performance = serializers.ListField()
    total_employees = serializers.IntegerField()




class EmployeeDashboardSummarySerializer(ReportSummarySerializer):
    """Employee dashboard summary"""
    employee_name = serializers.CharField()
    employee_number = serializers.CharField()
    shift = serializers.CharField()
    day_off = serializers.CharField()
    today_summary = serializers.DictField()
    notifications = serializers.DictField()
    requests = serializers.DictField()
    latest_activity = serializers.CharField()


class BreakScheduleSummarySerializer(ReportSummarySerializer):
    """Break schedule summary"""
    employee_name = serializers.CharField()
    date = serializers.DateField()
    is_day_off = serializers.BooleanField()
    day_of_week = serializers.CharField()
    break_schedule = serializers.ListField()
    total_breaks = serializers.IntegerField()
    completed_breaks = serializers.IntegerField()


class TaskScheduleSummarySerializer(ReportSummarySerializer):
    """Task schedule summary"""
    employee_name = serializers.CharField()
    date = serializers.DateField()
    task_schedule = serializers.ListField()
    total_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    active_tasks = serializers.IntegerField()
    upcoming_tasks = serializers.IntegerField()


class ActivityLogSummarySerializer(ReportSummarySerializer):
    """Activity log summary"""
    employee_name = serializers.CharField()
    activity_summary = serializers.DictField()
    activity_details = serializers.ListField()


# ==================== EXPORT SERIALIZERS ====================

class ExportSummarySerializer(serializers.Serializer):
    """Export summary data"""
    report_type = serializers.CharField()
    export_format = serializers.CharField()
    generated_at = serializers.DateTimeField()
    generated_by = serializers.CharField()
    filters_applied = serializers.DictField(required=False)
    total_records = serializers.IntegerField()
    summary_data = serializers.DictField()





# ==================== PERFORMANCE REPORT SERIALIZERS ====================

class WeeklyPerformanceDetailSerializer(serializers.Serializer):
    """Weekly performance details for each day"""
    date = serializers.DateField()
    day_of_week = serializers.CharField()
    is_day_off = serializers.BooleanField()
    attendance_status = serializers.CharField()
    breaks = serializers.DictField()
    tasks = serializers.DictField()
    hours_worked = serializers.FloatField(allow_null=True)
    punctuality_score = serializers.FloatField(min_value=0, max_value=100)


class WeeklyPerformanceSummarySerializer(ReportSummarySerializer):
    """Weekly performance summary"""
    employee_name = serializers.CharField()
    employee_number = serializers.CharField()
    week_start_date = serializers.DateField()
    week_end_date = serializers.DateField()
    shift_name = serializers.CharField(allow_null=True)
    day_off = serializers.CharField(allow_null=True)
    
    # Summary statistics
    total_days_in_week = serializers.IntegerField(min_value=0, max_value=7)
    days_present = serializers.IntegerField(min_value=0, max_value=7)
    days_absent = serializers.IntegerField(min_value=0, max_value=7)
    days_day_off = serializers.IntegerField(min_value=0, max_value=7)
    
    # Performance metrics
    attendance_rate = serializers.FloatField(min_value=0, max_value=100)
    average_hours_per_day = serializers.FloatField(min_value=0)
    total_hours_worked = serializers.FloatField(min_value=0)
    break_completion_rate = serializers.FloatField(min_value=0, max_value=100)
    task_completion_rate = serializers.FloatField(min_value=0, max_value=100)
    overall_punctuality = serializers.FloatField(min_value=0, max_value=100)
    
    # Daily breakdown
    daily_performance = WeeklyPerformanceDetailSerializer(many=True)
    
    # Performance rating
    performance_rating = serializers.ChoiceField(
        choices=['Excellent', 'Good', 'Average', 'Needs Improvement', 'Poor'],
        required=False
    )
    rating_color = serializers.CharField(required=False)


class AllTimePerformanceSummarySerializer(ReportSummarySerializer):
    """All-time performance summary"""
    employee_name = serializers.CharField()
    employee_number = serializers.CharField()
    current_shift = serializers.CharField(allow_null=True)
    employment_start = serializers.DateField(allow_null=True)
    total_days_employed = serializers.IntegerField(min_value=0)
    
    # Attendance statistics
    total_work_days = serializers.IntegerField(min_value=0)
    total_present_days = serializers.IntegerField(min_value=0)
    total_absent_days = serializers.IntegerField(min_value=0)
    total_day_off_days = serializers.IntegerField(min_value=0)
    overall_attendance_rate = serializers.FloatField(min_value=0, max_value=100)
    
    # Break performance
    total_breaks_assigned = serializers.IntegerField(min_value=0)
    total_breaks_completed = serializers.IntegerField(min_value=0)
    overall_break_completion_rate = serializers.FloatField(min_value=0, max_value=100)
    break_punctuality_score = serializers.FloatField(min_value=0, max_value=100)
    
    # Task performance
    total_tasks_assigned = serializers.IntegerField(min_value=0)
    total_tasks_completed = serializers.IntegerField(min_value=0)
    overall_task_completion_rate = serializers.FloatField(min_value=0, max_value=100)
    task_punctuality_score = serializers.FloatField(min_value=0, max_value=100)
    
    # Log performance
    total_logins = serializers.IntegerField(min_value=0)
    on_time_logins = serializers.IntegerField(min_value=0)
    login_punctuality_rate = serializers.FloatField(min_value=0, max_value=100)
    
    # Overall performance
    overall_performance_score = serializers.FloatField(min_value=0, max_value=100)
    performance_rating = serializers.CharField()
    performance_trend = serializers.ChoiceField(
        choices=['improving', 'stable', 'declining'],
        required=False
    )


class EmployeeWeeklyPerformanceSerializer(serializers.Serializer):
    """Individual employee weekly performance for supervisor/admin"""
    employee_id = serializers.IntegerField()
    employee_name = serializers.CharField()
    employee_number = serializers.CharField()
    shift_name = serializers.CharField(allow_null=True)
    
    # Weekly metrics
    attendance_rate = serializers.FloatField(min_value=0, max_value=100)
    break_completion_rate = serializers.FloatField(min_value=0, max_value=100)
    task_completion_rate = serializers.FloatField(min_value=0, max_value=100)
    average_hours_per_day = serializers.FloatField(min_value=0)
    punctuality_score = serializers.FloatField(min_value=0, max_value=100)
    
    # Performance indicators
    performance_rating = serializers.CharField()
    status = serializers.ChoiceField(
        choices=['active', 'inactive', 'on_leave'],
        required=False
    )
    has_issues = serializers.BooleanField(default=False)
    issues = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )


class SupervisorWeeklyPerformanceSummarySerializer(ReportSummarySerializer):
    """Weekly performance summary for supervisor/admin"""
    supervisor_name = serializers.CharField()
    week_start_date = serializers.DateField()
    week_end_date = serializers.DateField()
    
    # Team statistics
    total_employees = serializers.IntegerField(min_value=0)
    active_employees = serializers.IntegerField(min_value=0)
    employees_present_today = serializers.IntegerField(min_value=0)
    
    # Performance averages
    average_attendance_rate = serializers.FloatField(min_value=0, max_value=100)
    average_break_completion = serializers.FloatField(min_value=0, max_value=100)
    average_task_completion = serializers.FloatField(min_value=0, max_value=100)
    average_punctuality = serializers.FloatField(min_value=0, max_value=100)
    
    # Performance distribution
    performance_distribution = serializers.DictField(
        child=serializers.IntegerField(min_value=0)
    )
    
    # Individual performances
    employees_performance = EmployeeWeeklyPerformanceSerializer(many=True)
    
    # Issues summary
    total_issues = serializers.IntegerField(min_value=0)
    common_issues = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )


class SupervisorAllTimePerformanceSummarySerializer(ReportSummarySerializer):
    """All-time performance summary for supervisor/admin"""
    supervisor_name = serializers.CharField()
    total_employees = serializers.IntegerField(min_value=0)
    
    # Overall team statistics
    overall_attendance_rate = serializers.FloatField(min_value=0, max_value=100)
    overall_break_completion = serializers.FloatField(min_value=0, max_value=100)
    overall_task_completion = serializers.FloatField(min_value=0, max_value=100)
    overall_punctuality = serializers.FloatField(min_value=0, max_value=100)
    
    # Performance metrics
    top_performers = EmployeeWeeklyPerformanceSerializer(many=True, required=False)
    need_improvement = EmployeeWeeklyPerformanceSerializer(many=True, required=False)
    
    # Trends
    monthly_trend = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )
    
    # Summary statistics
    summary_statistics = serializers.DictField()