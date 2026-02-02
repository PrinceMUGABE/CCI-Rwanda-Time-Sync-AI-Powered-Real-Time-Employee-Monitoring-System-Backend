# rulesApp/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # User endpoints
    path('user/', views.get_user_rules, name='user-rules'),
    path('<int:rule_id>/', views.get_rule_detail, name='rule-detail'),
    path('type/<str:rule_type>/', views.get_rules_by_type, name='rules-by-type'),
    
    # Admin endpoints
    path('', views.get_all_rules, name='all-rules'),
    path('create/', views.create_rule, name='create-rule'),
    path('<int:rule_id>/update/', views.update_rule, name='update-rule'),
    path('<int:rule_id>/delete/', views.delete_rule, name='delete-rule'),
]