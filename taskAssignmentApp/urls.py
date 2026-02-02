# taskAssignmentApp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Employee endpoints
    path('my-assignments/', views.get_my_assignments, name='my-assignments'),
    path('current/', views.get_current_assignment, name='current-assignment'),
    path('next/', views.get_next_assignment, name='next-assignment'),
    path('<int:assignment_id>/start/', views.start_assignment, name='start-assignment'),
    path('<int:assignment_id>/complete/', views.complete_assignment, name='complete-assignment'),
    
    # Admin/Supervisor endpoints
    path('all/', views.get_all_assignments, name='all-assignments'),
    path('create-daily/', views.create_daily_assignments, name='create-daily-assignments'),
    path('modify/', views.modify_assignment, name='modify-assignment'),
    path('<int:assignment_id>/delete/', views.delete_assignment, name='delete-assignment'),
    
    # Shift rotation endpoints
    path('rotations/', views.manage_shift_rotations, name='shift-rotations'),
    path('rotations/<int:rotation_id>/', views.manage_shift_rotation_detail, name='shift-rotation-detail'),
    
    # Task overload endpoints
    path('overloads/', views.manage_task_overloads, name='task-overloads'),
    path('overloads/<int:overload_id>/resolve/', views.resolve_task_overload, name='resolve-overload'),
]
