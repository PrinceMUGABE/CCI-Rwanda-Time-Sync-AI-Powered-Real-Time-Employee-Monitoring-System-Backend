# requestApp/admin.py

from django.contrib import admin
from .models import ShiftChangeRequest


@admin.register(ShiftChangeRequest)
class ShiftChangeRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user',
        'change_type',
        'status',
        'start_date',
        'created_at',
        'approved_by',
        'approved_at'
    ]
    
    list_filter = [
        'status',
        'change_type',
        'start_date',
        'created_at'
    ]
    
    search_fields = [
        'user__names',
        'user__emp_number',
        'reason'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'approved_at',
        'cancelled_at'
    ]
    
    fieldsets = (
        ('Request Information', {
            'fields': (
                'user',
                'change_type',
                'reason',
                'start_date'
            )
        }),
        ('Current Values', {
            'fields': (
                'current_shift',
                'current_day_off'
            )
        }),
        ('Requested Values', {
            'fields': (
                'new_shift',
                'new_day_off'
            )
        }),
        ('Status & Approval', {
            'fields': (
                'status',
                'approved_by',
                'approved_at',
                'cancelled_by',
                'cancelled_at',
                'cancellation_reason'
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at'
            )
        })
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly after creation"""
        if obj:  # Editing existing object
            return self.readonly_fields + ('user', 'change_type')
        return self.readonly_fields