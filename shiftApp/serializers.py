# shiftApp/serializers.py

from datetime import datetime, timedelta
from rest_framework import serializers
from django.utils import timezone
from .models import Shift, BreakTemplate
from userApp.models import CustomUser


class BreakTemplateSerializer(serializers.ModelSerializer):
    """Serializer for break template operations"""
    duration_minutes = serializers.ReadOnlyField()
    
    class Meta:
        model = BreakTemplate
        fields = [
            'id', 'shift', 'name', 'start_at', 'end_at', 'status',
            'duration_minutes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        start_at = attrs.get('start_at')
        end_at = attrs.get('end_at')
        shift = attrs.get('shift')
        
        if start_at and end_at and shift:
            # Check if break times are within shift hours
            shift_start_dt = datetime.combine(datetime.today(), shift.start_at)
            shift_end_dt = datetime.combine(datetime.today(), shift.end_at)
            break_start_dt = datetime.combine(datetime.today(), start_at)
            break_end_dt = datetime.combine(datetime.today(), end_at)
            
            # Handle overnight shifts
            if shift.end_at < shift.start_at:
                shift_end_dt += timedelta(days=1)
            
            # Handle overnight breaks
            if end_at < start_at:
                break_end_dt += timedelta(days=1)
            
            # Check if break is within shift
            if not (shift_start_dt <= break_start_dt <= shift_end_dt and
                    shift_start_dt <= break_end_dt <= shift_end_dt):
                raise serializers.ValidationError({
                    'start_at': 'Break must be within shift hours.',
                    'end_at': 'Break must be within shift hours.'
                })
            
            # Check for overlapping breaks in the same shift
            existing_breaks = BreakTemplate.objects.filter(
                shift=shift,
                status='active'
            ).exclude(id=self.instance.id if self.instance else None)
            
            for existing_break in existing_breaks:
                existing_start = datetime.combine(datetime.today(), existing_break.start_at)
                existing_end = datetime.combine(datetime.today(), existing_break.end_at)
                
                if existing_break.end_at < existing_break.start_at:
                    existing_end += timedelta(days=1)
                
                # Check for overlap
                if (break_start_dt < existing_end) and (existing_start < break_end_dt):
                    raise serializers.ValidationError({
                        'start_at': f'This break overlaps with another break: {existing_break.name}',
                        'end_at': f'This break overlaps with another break: {existing_break.name}'
                    })
        
        return attrs


class ShiftSerializer(serializers.ModelSerializer):
    """Serializer for shift operations"""
    duration_hours = serializers.ReadOnlyField()
    is_overnight = serializers.ReadOnlyField()
    assigned_users_count = serializers.SerializerMethodField()
    formatted_time_range = serializers.SerializerMethodField()
    breaks = BreakTemplateSerializer(many=True, read_only=True)
    working_hours_after_breaks = serializers.ReadOnlyField()
    
    class Meta:
        model = Shift
        fields = [
            'id', 'name', 'start_at', 'end_at', 'status', 'description',
            'duration_hours', 'is_overnight', 'assigned_users_count',
            'formatted_time_range', 'working_hours_after_breaks',
            'breaks', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_assigned_users_count(self, obj):
        today = timezone.now().date()
        # Check which relationships exist on the Shift model
        if hasattr(obj, 'assigned_users'):
            # If CustomUser has current_shift relationship
            return obj.assigned_users.filter(
                is_active=True
            ).count()
        else:
            # Return 0 or handle gracefully
            return 0
    
    def get_formatted_time_range(self, obj):
        return f"{obj.start_at.strftime('%H:%M')} - {obj.end_at.strftime('%H:%M')}"
    

    
class ShiftListSerializer(serializers.ModelSerializer):
    """Serializer for shift list"""
    duration_hours = serializers.ReadOnlyField()
    is_overnight = serializers.ReadOnlyField()
    formatted_time_range = serializers.SerializerMethodField()
    breaks_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Shift
        fields = [
            'id', 'name', 'start_at', 'end_at', 'status',
            'duration_hours', 'is_overnight', 'formatted_time_range',
            'breaks_count'
        ]
        read_only_fields = fields
    
    def get_formatted_time_range(self, obj):
        return f"{obj.start_at.strftime('%H:%M')} - {obj.end_at.strftime('%H:%M')}"
    
    def get_breaks_count(self, obj):
        return obj.breaks.filter(status='active').count()
