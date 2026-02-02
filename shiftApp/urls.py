# shiftApp/urls.py

from django.urls import path
from . import views

app_name = 'shifts'

urlpatterns = [
    # Shift Template Management
    path('shifts/', views.list_shifts, name='list_shifts'),
    path('shifts/create/', views.create_shift, name='create_shift'),
    path('shifts/<int:shift_id>/', views.get_shift, name='get_shift'),
    path('shifts/<int:shift_id>/update/', views.update_shift, name='update_shift'),
    path('shifts/<int:shift_id>/delete/', views.delete_shift, name='delete_shift'),
    
    # Break Template Management
    path('breaks/create/', views.create_break_template, name='create_break_template'),
    path('shifts/<int:shift_id>/breaks/', views.get_shift_breaks, name='get_shift_breaks'),
    path('breaks/<int:break_id>/update/', views.update_break_template, name='update_break_template'),
    path('breaks/<int:break_id>/delete/', views.delete_break_template, name='delete_break_template'),
    path('breaks/', views.list_break_templates, name='list_break_templates'),
]