from django.contrib import admin
from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'created_by', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at', 'updated_at']
    search_fields = ['name', 'description', 'created_by__names']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Task Information', {
            'fields': ('name', 'description', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new task
            obj.created_by = request.user
        super().save_model(request, obj, form, change)