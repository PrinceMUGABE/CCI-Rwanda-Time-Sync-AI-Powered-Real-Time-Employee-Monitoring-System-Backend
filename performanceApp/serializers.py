# backend/performanceApp/serializers.py
from rest_framework import serializers
from .models import BreakLog


class BreakLogSerializer(serializers.ModelSerializer):
    """Serializer for break logs"""
    user_name = serializers.CharField(source='user.names', read_only=True)
    user_emp_number = serializers.CharField(source='user.emp_number', read_only=True)
    break_name = serializers.CharField(source='break_template.name', read_only=True)
    shift_name = serializers.CharField(source='shift.name', read_only=True)
    duration_minutes = serializers.ReadOnlyField()
    is_current = serializers.ReadOnlyField()
    
    class Meta:
        model = BreakLog
        fields = [
            'id', 'user', 'user_name', 'user_emp_number',
            'shift_name',
            'break_template', 'break_name',
            'scheduled_start', 'scheduled_end',
            'actual_start', 'actual_end',
            'status', 'duration_minutes', 'is_current',
            'is_active', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


