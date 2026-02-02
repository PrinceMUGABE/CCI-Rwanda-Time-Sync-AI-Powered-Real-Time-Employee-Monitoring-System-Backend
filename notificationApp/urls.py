# notificationApp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # User notifications
    path('my-notifications/', views.get_my_notifications, name='my-notifications'),
    path('unread-count/', views.get_unread_count, name='unread-count'),
    path('<int:notification_id>/mark-read/', views.mark_notification_as_read, name='mark-notification-read'),
    path('mark-all-read/', views.mark_all_as_read, name='mark-all-read'),
    path('<int:notification_id>/delete/', views.delete_notification, name='delete-notification'),
    path('delete-all-read/', views.delete_all_read_notifications, name='delete-all-read'),
    
    # Notification preferences
    path('preferences/', views.get_my_notification_preferences, name='my-preferences'),
    path('preferences/update/', views.update_notification_preferences, name='update-preferences'),
    
    # Admin views
    path('all/', views.get_all_notifications, name='all-notifications'),
    path('send-custom/', views.send_custom_notification, name='send-custom-notification'),
]