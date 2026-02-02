# requestApp/serializers.py

from rest_framework import serializers
from .models import ShiftChangeRequest
from userApp.models import CustomUser
from shiftApp.models import Shift
import base64


class ShiftDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Shift model"""
    duration_hours = serializers.ReadOnlyField()
    is_overnight = serializers.ReadOnlyField()
    
    class Meta:
        model = Shift
        fields = [
            'id',
            'name',
            'start_at',
            'end_at',
            'status',
            'description',
            'duration_hours',
            'is_overnight',
            'created_at',
            'updated_at'
        ]


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for CustomUser with profile picture"""
    profile_picture = serializers.SerializerMethodField()
    current_shift = ShiftDetailSerializer(read_only=True)
    is_admin = serializers.ReadOnlyField()
    is_supervisor = serializers.ReadOnlyField()
    is_employee = serializers.ReadOnlyField()
    
    class Meta:
        model = CustomUser
        fields = [
            'id',
            'emp_number',
            'names',
            'email',
            'phone_number',
            'salary',
            'role',
            'status',
            'gender',
            'day_off',
            'current_shift',
            'profile_picture',
            'is_admin',
            'is_supervisor',
            'is_employee',
            'created_at',
            'updated_at'
        ]
    
    def get_profile_picture(self, obj):
        """Convert binary profile picture to base64 string"""
        try:
            if obj.profile_picture:
                if isinstance(obj.profile_picture, bytes):
                    return base64.b64encode(obj.profile_picture).decode('utf-8')
                elif isinstance(obj.profile_picture, memoryview):
                    return base64.b64encode(bytes(obj.profile_picture)).decode('utf-8')
            return None
        except Exception as e:
            return None


class ShiftChangeRequestListSerializer(serializers.ModelSerializer):
    """Serializer for listing shift change requests (minimal data)"""
    user_name = serializers.CharField(source='user.names', read_only=True)
    user_emp_number = serializers.CharField(source='user.emp_number', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    current_shift_name = serializers.CharField(source='current_shift.name', read_only=True)
    new_shift_name = serializers.CharField(source='new_shift.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.names', read_only=True)
    cancelled_by_name = serializers.CharField(source='cancelled_by.names', read_only=True)
    days_until_effective = serializers.ReadOnlyField()
    user_details = UserDetailSerializer(read_only=True)
    
    class Meta:
        model = ShiftChangeRequest
        fields = [
            'id',
            'user_name',
            'user_emp_number',
            'change_type',
            'status',
            'current_shift_name',
            'new_shift_name',
            'current_day_off',
            'new_day_off',
            'start_date',
            'days_until_effective',
            'approved_by_name',
            'cancelled_by_name',
            'created_at',
            'reason',
            'user_details',
            'user_email'
        ]


class ShiftChangeRequestDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for shift change requests with full associated data"""
    user = UserDetailSerializer(read_only=True)
    current_shift = ShiftDetailSerializer(read_only=True)
    new_shift = ShiftDetailSerializer(read_only=True)
    approved_by = UserDetailSerializer(read_only=True)
    cancelled_by = UserDetailSerializer(read_only=True)
    
    # Read-only properties
    is_pending = serializers.ReadOnlyField()
    is_accepted = serializers.ReadOnlyField()
    is_cancelled = serializers.ReadOnlyField()
    can_be_modified = serializers.ReadOnlyField()
    days_until_effective = serializers.ReadOnlyField()
    user_details = UserDetailSerializer(source='user', read_only=True)
    
    class Meta:
        model = ShiftChangeRequest
        fields = [
            'id',
            'user',
            'change_type',
            'reason',
            'current_shift',
            'current_day_off',
            'new_shift',
            'new_day_off',
            'start_date',
            'status',
            'approved_by',
            'approved_at',
            'cancelled_by',
            'cancelled_at',
            'cancellation_reason',
            'created_at',
            'updated_at',
            'is_pending',
            'is_accepted',
            'is_cancelled',
            'can_be_modified',
            'days_until_effective',
            'user_details'
        ]


class ShiftChangeRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating shift change requests"""
    
    class Meta:
        model = ShiftChangeRequest
        fields = [
            'change_type',
            'reason',
            'new_shift',
            'new_day_off',
            'start_date'
        ]
    
    def validate(self, data):
        """Validate the request data"""
        change_type = data.get('change_type')
        new_shift = data.get('new_shift')
        new_day_off = data.get('new_day_off')
        
        # Validate based on change type
        if change_type == 'shift_only':
            if not new_shift:
                raise serializers.ValidationError({
                    'new_shift': 'New shift is required for shift-only change.'
                })
            if new_day_off:
                raise serializers.ValidationError({
                    'new_day_off': 'Day off should not be provided for shift-only change.'
                })
        
        elif change_type == 'day_off_only':
            if not new_day_off:
                raise serializers.ValidationError({
                    'new_day_off': 'New day off is required for day-off-only change.'
                })
            if new_shift:
                raise serializers.ValidationError({
                    'new_shift': 'Shift should not be provided for day-off-only change.'
                })
        
        elif change_type == 'both':
            if not new_shift:
                raise serializers.ValidationError({
                    'new_shift': 'New shift is required when changing both.'
                })
            if not new_day_off:
                raise serializers.ValidationError({
                    'new_day_off': 'New day off is required when changing both.'
                })
        
        return data
    
    def create(self, validated_data):
        """Create a new shift change request"""
        # Get user from context
        user = self.context['request'].user
        validated_data['user'] = user
        
        # Set current values
        validated_data['current_shift'] = user.current_shift
        validated_data['current_day_off'] = user.day_off
        
        return super().create(validated_data)


class ShiftChangeRequestUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating shift change requests (only pending ones)"""
    
    class Meta:
        model = ShiftChangeRequest
        fields = [
            'reason',
            'new_shift',
            'new_day_off',
            'start_date'
        ]
    
    def validate(self, data):
        """Validate update data"""
        instance = self.instance
        
        # Can only update pending requests
        if instance.status != 'pending':
            raise serializers.ValidationError(
                "Only pending requests can be updated."
            )
        
        # Validate based on change type
        change_type = instance.change_type
        new_shift = data.get('new_shift', instance.new_shift)
        new_day_off = data.get('new_day_off', instance.new_day_off)
        
        if change_type == 'shift_only':
            if not new_shift:
                raise serializers.ValidationError({
                    'new_shift': 'New shift is required for shift-only change.'
                })
        
        elif change_type == 'day_off_only':
            if not new_day_off:
                raise serializers.ValidationError({
                    'new_day_off': 'New day off is required for day-off-only change.'
                })
        
        elif change_type == 'both':
            if not new_shift or not new_day_off:
                raise serializers.ValidationError(
                    "Both new shift and new day off are required."
                )
        
        return data