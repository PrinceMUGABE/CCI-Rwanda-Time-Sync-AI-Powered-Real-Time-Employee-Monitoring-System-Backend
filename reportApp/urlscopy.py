# reportApp/urls.py - UPDATED WITH EXPORT ENDPOINT

from django.urls import path
from . import viewscopy

app_name = 'reportApp'

urlpatterns = [
    # Dashboard endpoints
    path('dashboard/overview/', viewscopy.dashboard_overview, name='dashboard-overview'),
    path('dashboard/user-performance/', viewscopy.user_performance_dashboard, name='user-performance-dashboard'),
    
    # Report generation endpoints
    path('reports/attendance/', viewscopy.attendance_report, name='attendance-report'),
    path('reports/break-compliance/', viewscopy.break_compliance_report, name='break-compliance-report'),
    path('reports/task-completion/', viewscopy.task_completion_report, name='task-completion-report'),
    path('reports/shift-change-requests/', viewscopy.shift_change_request_report, name='shift-change-request-report'),
    path('reports/user-activity-log/', viewscopy.user_activity_log_report, name='user-activity-log-report'),
    path('reports/productivity/', viewscopy.productivity_report, name='productivity-report'),
    
    # Export endpoint - NEW
    path('reports/export/', viewscopy.export_report, name='export-report'),
]