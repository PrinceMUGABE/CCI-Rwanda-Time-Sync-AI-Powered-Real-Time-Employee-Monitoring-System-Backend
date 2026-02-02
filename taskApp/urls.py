from django.urls import path
from . import views

app_name = 'taskApp'

urlpatterns = [
    # Create task
    path('create/', views.create_task, name='create_task'),
    
    # Get all tasks
    path('all/', views.get_all_tasks, name='get_all_tasks'),
    
    # Get task by ID
    path('<int:task_id>/', views.get_task_by_id, name='get_task_by_id'),
    
    # Get task by name
    path('name/<str:task_name>/', views.get_task_by_name, name='get_task_by_name'),
    
    # Update task
    path('update/<int:task_id>/', views.update_task, name='update_task'),
    
    # Delete task
    path('delete/<int:task_id>/', views.delete_task, name='delete_task'),
]