# rulesApp/admin.py

from django.contrib import admin
from .models import Rule


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ['title', 'rule_type', 'user_type', 'status', 'created_at']
    list_filter = ['rule_type', 'user_type', 'status']
    search_fields = ['title', 'description']
    ordering = ['-created_at']