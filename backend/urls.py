# urls.py - ROOT URLS
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('userApp.urls')),
    path('shift/', include('shiftApp.urls')),
    path('performance/', include('performanceApp.urls')),
    path('notification/', include('notificationApp.urls')),
    path('task/', include('taskApp.urls')),
    path('task-assignment/', include('taskAssignmentApp.urls')),
    path('request/', include('requestApp.urls')),
    path('report/', include('reportApp.urls')),
    path('rules/', include('rulesApp.urls')),
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)