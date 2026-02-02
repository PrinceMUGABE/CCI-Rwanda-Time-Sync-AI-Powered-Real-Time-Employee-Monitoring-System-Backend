# rulesApp/serializers.py

from rest_framework import serializers
from .models import Rule


class RuleSerializer(serializers.ModelSerializer):
    """Serializer for rules"""
    
    class Meta:
        model = Rule
        fields = [
            'id',
            'title',
            'description',
            'rule_type',
            'user_type',
            'status',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class RuleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for rule lists"""
    
    class Meta:
        model = Rule
        fields = [
            'id',
            'title',
            'rule_type',
            'user_type',
            'status',
            'created_at',
            'description',
            'updated_at'
        ]