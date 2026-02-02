# notificationApp/views.py
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Notification, NotificationPreference
from .serializers import NotificationSerializer, NotificationPreferenceSerializer
from .services import NotificationService


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_notifications(request):
    """Get notifications for the authenticated user"""
    user = request.user
    
    # Query parameters
    is_read = request.query_params.get('is_read')
    notification_type = request.query_params.get('type')
    priority = request.query_params.get('priority')
    limit = request.query_params.get('limit', 50)
    
    # Base queryset - exclude expired
    notifications = Notification.objects.filter(
        user=user
    ).exclude(
        expires_at__lt=timezone.now()
    )
    
    # Apply filters
    if is_read is not None:
        is_read_bool = is_read.lower() == 'true'
        notifications = notifications.filter(is_read=is_read_bool)
    
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    if priority:
        notifications = notifications.filter(priority=priority)
    
    # Limit results
    try:
        limit = int(limit)
        notifications = notifications[:limit]
    except (ValueError, TypeError):
        notifications = notifications[:50]
    
    # Serialize
    serializer = NotificationSerializer(notifications, many=True)
    
    # Get unread count
    unread_count = NotificationService.get_unread_count(user)
    
    return Response({
        'notifications': serializer.data,
        'unread_count': unread_count,
        'total_count': Notification.objects.filter(user=user).exclude(expires_at__lt=timezone.now()).count()
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_as_read(request, notification_id):
    """Mark a specific notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    
    notification.mark_as_read()
    
    serializer = NotificationSerializer(notification)
    
    return Response({
        'message': 'Notification marked as read',
        'notification': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_as_read(request):
    """Mark all notifications as read for the authenticated user"""
    count = NotificationService.mark_all_as_read(request.user)
    
    return Response({
        'message': f'{count} notifications marked as read',
        'count': count
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """Delete a specific notification"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    
    notification.delete()
    
    return Response({
        'message': 'Notification deleted successfully'
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_all_read_notifications(request):
    """Delete all read notifications for the authenticated user"""
    count = Notification.objects.filter(
        user=request.user,
        is_read=True
    ).delete()[0]
    
    return Response({
        'message': f'{count} notifications deleted',
        'count': count
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unread_count(request):
    """Get count of unread notifications"""
    count = NotificationService.get_unread_count(request.user)
    
    return Response({
        'unread_count': count
    }, status=status.HTTP_200_OK)


# ==================== NOTIFICATION PREFERENCES ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_notification_preferences(request):
    """Get notification preferences for the authenticated user"""
    prefs = NotificationService.get_or_create_preferences(request.user)
    
    serializer = NotificationPreferenceSerializer(prefs)
    
    return Response({
        'preferences': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_notification_preferences(request):
    """Update notification preferences for the authenticated user"""
    prefs = NotificationService.get_or_create_preferences(request.user)
    
    serializer = NotificationPreferenceSerializer(prefs, data=request.data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        
        return Response({
            'message': 'Notification preferences updated successfully',
            'preferences': serializer.data
        }, status=status.HTTP_200_OK)
    
    return Response({
        'message': 'Failed to update preferences',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


# ==================== ADMIN VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_notifications(request):
    """Get all notifications (admin only)"""
    if not request.user.is_admin:
        return Response({
            'message': 'You do not have permission to view all notifications'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Query parameters
    user_id = request.query_params.get('user_id')
    notification_type = request.query_params.get('type')
    priority = request.query_params.get('priority')
    is_read = request.query_params.get('is_read')
    limit = request.query_params.get('limit', 100)
    
    # Base queryset
    notifications = Notification.objects.all().exclude(
        expires_at__lt=timezone.now()
    )
    
    # Apply filters
    if user_id:
        notifications = notifications.filter(user_id=user_id)
    
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    if priority:
        notifications = notifications.filter(priority=priority)
    
    if is_read is not None:
        is_read_bool = is_read.lower() == 'true'
        notifications = notifications.filter(is_read=is_read_bool)
    
    # Limit results
    try:
        limit = int(limit)
        notifications = notifications[:limit]
    except (ValueError, TypeError):
        notifications = notifications[:100]
    
    # Serialize
    serializer = NotificationSerializer(notifications, many=True)
    
    return Response({
        'notifications': serializer.data,
        'total_count': notifications.count()
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_custom_notification(request):
    """Send a custom notification to user(s) (admin only)"""
    if not request.user.is_admin:
        return Response({
            'message': 'You do not have permission to send notifications'
        }, status=status.HTTP_403_FORBIDDEN)
    
    user_ids = request.data.get('user_ids', [])
    title = request.data.get('title')
    message = request.data.get('message')
    priority = request.data.get('priority', 'medium')
    notification_type = request.data.get('notification_type', 'system_alert')
    
    if not user_ids or not title or not message:
        return Response({
            'message': 'user_ids, title, and message are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    from userApp.models import CustomUser
    users = CustomUser.objects.filter(id__in=user_ids)
    
    notifications = []
    for user in users:
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority,
            expires_at=timezone.now() + timezone.timedelta(days=7)
        )
        notification.mark_as_sent()
        notifications.append(notification)
    
    return Response({
        'message': f'Notification sent to {len(notifications)} users',
        'count': len(notifications)
    }, status=status.HTTP_201_CREATED)