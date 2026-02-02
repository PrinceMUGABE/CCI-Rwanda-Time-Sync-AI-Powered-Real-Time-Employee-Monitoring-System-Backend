from rest_framework import serializers
from .models import Task
from userApp.models import CustomUser


class TaskSerializer(serializers.ModelSerializer):
    created_by_details = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Task
        fields = [
            'id',
            'name',
            'description',
            'status',
            'status_display',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_details'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_created_by_details(self, obj):
        if obj.created_by:
            return {
                'id': obj.created_by.id,
                'emp_number': obj.created_by.emp_number,
                'names': obj.created_by.names,
                'email': obj.created_by.email,
                'role': obj.created_by.role
            }
        return None


    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Task name cannot be empty.")
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Task name must be at least 3 characters long.")
        return value.strip()

    def validate_description(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Task description cannot be empty.")
        return value.strip()

    def validate_status(self, value):
        valid_statuses = [choice[0] for choice in Task.STATUS_CHOICES]
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return value