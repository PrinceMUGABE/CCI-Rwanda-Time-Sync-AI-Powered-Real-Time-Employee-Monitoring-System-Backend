# urls.py
from django.urls import path
from . import views

app_name = 'reportApp'

urlpatterns = [
    # ==================== ADMIN URLS ====================
    path('admin/dashboard/', 
         views.admin_dashboard_overview, 
         name='admin_dashboard_overview'),
    
    path('admin/users/analytics/', 
         views.admin_user_analytics, 
         name='admin_user_analytics'),
    
    path('admin/shifts/', 
         views.admin_shift_report, 
         name='admin_shift_report'),
    
    path('admin/performance/', 
         views.admin_performance_report, 
         name='admin_performance_report'),
    
    # ==================== SUPERVISOR URLS ====================
    path('supervisor/dashboard/', 
         views.supervisor_dashboard_overview, 
         name='supervisor_dashboard_overview'),
    
    path('supervisor/team/performance/', 
         views.supervisor_team_performance, 
         name='supervisor_team_performance'),
    
    path('supervisor/attendance/', 
         views.supervisor_attendance_report, 
         name='supervisor_attendance_report'),
    
    # ==================== EMPLOYEE URLS ====================
    path('employee/dashboard/', 
         views.employee_dashboard_overview, 
         name='employee_dashboard_overview'),
    
    path('employee/breaks/', 
         views.employee_break_schedule, 
         name='employee_break_schedule'),
    
    path('employee/tasks/', 
         views.employee_task_schedule, 
         name='employee_task_schedule'),
    
    path('employee/activities/', 
         views.employee_activity_log, 
         name='employee_activity_log'),
    
    # ==================== EXPORT URLS ====================
    path('export/', 
         views.export_report, 
         name='export_report'),


     # ==================== PERFORMANCE URLS ====================

     # Employee performance endpoints
     path('employee/performance/weekly/', 
          views.employee_weekly_performance, 
          name='employee_weekly_performance'),
     path('employee/performance/all-time/', 
          views.employee_all_time_performance, 
          name='employee_all_time_performance'),

     # Supervisor/Admin performance endpoints
     path('supervisor/performance/weekly/', 
          views.supervisor_weekly_performance, 
          name='supervisor_weekly_performance'),
     path('supervisor/performance/all-time/', 
          views.supervisor_all_time_performance, 
          name='supervisor_all_time_performance'),
]