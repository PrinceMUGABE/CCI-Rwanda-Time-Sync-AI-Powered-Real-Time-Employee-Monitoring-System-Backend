# userApp/urls.py
from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Existing URLs
    path('register/', views.register_user, name='register_user'),
    path('login/credentials/', views.login_with_credentials, name='login_with_credentials'),
    path('login/face/', views.login_with_face, name='login_with_face'),
    path('logout/', views.logout, name='logout'),
    path('users/', views.list_users, name='list_users'),
    path('users/<int:user_id>/', views.get_user, name='get_user'),
    path('profile/', views.get_my_profile, name='get_my_profile'),
    path('profile/update/', views.update_my_profile, name='update_my_profile'),
    path('users/<int:user_id>/update/', views.update_user, name='update_user'),
    path('users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('change-password/', views.change_password, name='change_password'),
    path('supervisors/', views.get_supervisors, name='get_supervisors'),
    path('supervisors/<int:supervisor_id>/employees/', views.get_supervised_employees, name='get_supervised_employees'),
    path('users/<int:user_id>/assign-supervisors/', views.assign_supervisors, name='assign_supervisors'),
    
    # New OTP and Password Reset URLs
    path('login/otp/request/', views.login_with_otp_request, name='login_otp_request'),
    path('login/otp/verify/', views.login_with_otp_verify, name='login_otp_verify'),
    path('auth/password-reset/request-otp/', views.password_reset_request, name='password_reset_request'),
    path('auth/password-reset/verify-otp/', views.password_reset_verify, name='password_reset_verify'),
    path('auth/password-reset/confirm/', views.password_reset_confirm, name='password_reset_confirm'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('verify-token/', views.verify_token, name='verify-token'),

    path('users/<int:user_id>/reset-password/', views.admin_reset_user_password, name='admin-reset-user-password'),
    path('my-supervised-employees/', views.get_my_supervised_employees, name='get_my_supervised_employees'),
    path('users/supervised/', views.my_get_supervised_employees, name='my_get_supervised_employees'),
]