# taskAssignmentApp/admin.py
from django.contrib import admin
from .models import TaskAssignment, ShiftTaskRotation, TaskOverload


@admin.register(TaskAssignment)
class TaskAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'task', 'assignment_date', 'start_time', 
        'end_time', 'status', 'sequence_order', 'is_modified'
    ]
    list_filter = [
        'status', 'assignment_date', 'shift', 'is_modified', 'priority'
    ]
    search_fields = [
        'user__names', 'user__emp_number', 'task__name'
    ]
    readonly_fields = [
        'actual_start_time', 'actual_end_time', 'reminder_sent',
        'reminder_sent_at', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Assignment Details', {
            'fields': (
                'user', 'task', 'shift', 'assignment_date',
                'sequence_order', 'priority'
            )
        }),
        ('Timing', {
            'fields': (
                'start_time', 'end_time',
                'actual_start_time', 'actual_end_time'
            )
        }),
        ('Status & Tracking', {
            'fields': (
                'status', 'is_modified', 'modification_reason'
            )
        }),
        ('Assignment Metadata', {
            'fields': (
                'assigned_by', 'modified_by', 'notes'
            )
        }),
        ('Notifications', {
            'fields': (
                'reminder_sent', 'reminder_sent_at'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'task', 'shift', 'assigned_by', 'modified_by')


@admin.register(ShiftTaskRotation)
class ShiftTaskRotationAdmin(admin.ModelAdmin):
    list_display = [
        'shift', 'rotation_interval_minutes', 'task_count',
        'is_active', 'allow_multiple_employees_per_task'
    ]
    list_filter = ['is_active', 'shift', 'created_at']
    search_fields = ['shift__name']
    filter_horizontal = ['tasks']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Shift Information', {
            'fields': ('shift', 'is_active')
        }),
        ('Task Configuration', {
            'fields': (
                'tasks', 'rotation_interval_minutes',
                'allow_multiple_employees_per_task'
            )
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )


@admin.register(TaskOverload)
class TaskOverloadAdmin(admin.ModelAdmin):
    list_display = [
        'task', 'shift', 'overload_date',
        'additional_employees_needed', 'is_resolved'
    ]
    list_filter = [
        'is_resolved', 'overload_date', 'shift', 'created_at'
    ]
    search_fields = ['task__name', 'shift__name', 'reason']
    readonly_fields = ['resolved_at', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Overload Details', {
            'fields': (
                'task', 'shift', 'overload_date',
                'additional_employees_needed'
            )
        }),
        ('Time Slot (Optional)', {
            'fields': ('time_slot_start', 'time_slot_end'),
            'description': 'Leave empty to apply to entire shift'
        }),
        ('Information', {
            'fields': ('reason',)
        }),
        ('Status', {
            'fields': ('is_resolved', 'resolved_at')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )