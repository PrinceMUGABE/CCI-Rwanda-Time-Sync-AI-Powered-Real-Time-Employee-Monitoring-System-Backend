# requestApp/urls.py

from django.urls import path
from . import views

app_name = 'requestApp'

urlpatterns = [
    # Create request
    path('create/', views.create_shift_change_request, name='create_request'),
    
    # Get requests
    path('all/', views.get_all_requests, name='get_all_requests'),
    path('<int:request_id>/', views.get_request_by_id, name='get_request_by_id'),
    path('my-requests/', views.get_my_requests, name='get_my_requests'),
    path('supervised/', views.get_supervised_requests, name='get_supervised_requests'),
    
    # Get requests by user
    path('employee/<str:emp_number>/', views.get_requests_for_employee, name='get_requests_for_employee'),
    path('supervisor/<str:emp_number>/', views.get_requests_for_supervisor, name='get_requests_for_supervisor'),
    
    # Update request
    path('<int:request_id>/update/', views.update_request, name='update_request'),
    
    # Accept/Cancel/Delete request
    path('<int:request_id>/accept/', views.accept_request, name='accept_request'),
    path('<int:request_id>/cancel/', views.cancel_request, name='cancel_request'),
    path('<int:request_id>/delete/', views.delete_request, name='delete_request'),
]