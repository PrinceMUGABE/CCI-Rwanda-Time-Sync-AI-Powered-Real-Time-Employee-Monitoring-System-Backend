# backend/performanceApp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # ==================== BREAK MANAGEMENT ====================
    # Authenticated user's breaks
    path('breaks/my-breaks/', views.get_my_breaks, name='my-breaks'),
    path('breaks/current/', views.get_current_breaks, name='current-break'),
    path('breaks/upcoming/', views.get_upcoming_breaks, name='upcoming-breaks'),
    path('breaks/start/', views.start_break, name='start-break'),
    path('breaks/end/', views.end_break, name='end-current-break'),  # End current
    path('breaks/end/<int:break_log_id>/', views.end_break, name='end-specific-break'),
    
    # Specific user breaks (requires permission)
    path('breaks/user/<int:user_id>/', views.get_user_breaks, name='user-breaks'),
    
    # All users breaks (admin/supervisor only)
    path('breaks/all/', views.get_all_users_breaks, name='all-users-breaks'),
    
    # ==================== PERFORMANCE LOGS ====================
    # Authenticated user's performance
    path('my-performance/', views.get_my_performance, name='my-performance'),
    
    # Specific user performance (requires permission)
    path('user/<int:user_id>/', views.get_user_performance, name='user-performance'),
    
    # All users performance (admin/supervisor only)
    path('all/', views.get_all_users_performance, name='all-users-performance'),
]