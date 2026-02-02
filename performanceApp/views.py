# performanceApp/views.py
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import BreakLog
from .serializers import BreakLogSerializer
from userApp.models import CustomUser, UserLog
from userApp.serializers import UserLogSerializer


# ==================== BREAK MANAGEMENT VIEWS ====================

# Update the start_break function in performanceApp/views.py
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_break(request):
    """Start a break for the authenticated user"""
    user = request.user
    
    # Get break_log_id from request if provided (for specific break)
    break_log_id = request.data.get('break_log_id')
    
    if break_log_id:
        # Start specific break
        break_log = get_object_or_404(BreakLog, id=break_log_id, user=user)
    else:
        # Get the next scheduled break for this user
        now = timezone.now()
        break_log = BreakLog.objects.filter(
            user=user,
            status='scheduled',
            is_active=True,
            scheduled_start__lte=now + timedelta(minutes=5)  # Allow starting 5 minutes early
        ).order_by('scheduled_start').first()
        
        if not break_log:
            return Response({
                'message': 'No scheduled break available to start'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Check if break can be started
        can_start, message = break_log.can_start_break()
        
        if not can_start:
            return Response({
                'message': message
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user is already on a break
        current_break = BreakLog.objects.filter(
            user=user,
            status__in='started',
            is_active=True
        ).exists()
        
        if current_break:
            return Response({
                'message': 'You are already on a break. Please end your current break first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Start the break with user login status
        user_logged_in = True  # User is logged in since they're making this request
        break_log.start_break(user_logged_in=user_logged_in)
        
        serializer = BreakLogSerializer(break_log, context={'request': request})
        
        # Get punctuality summary
        punctuality_summary = break_log.get_punctuality_summary()
        
        return Response({
            'message': 'Break started successfully',
            'break': serializer.data,
            'punctuality': punctuality_summary,
            'start_deviation_minutes': break_log.start_deviation_minutes,
            'start_punctuality': break_log.start_punctuality
        }, status=status.HTTP_200_OK)
        
    except ValidationError as e:
        return Response({
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_break(request, break_log_id=None):
    """End a break - can be current active break or specific break"""
    user = request.user
    
    if break_log_id:
        # End specific break
        break_log = get_object_or_404(BreakLog, id=break_log_id)
    else:
        # End current active break
        break_log = BreakLog.objects.filter(
            user=user,
            status__in=['started', 'extended'],
            is_active=True
        ).order_by('-actual_start').first()
        
        if not break_log:
            return Response({
                'message': 'You do not have an active break to end'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if user can end break
    if not request.user.is_admin and break_log.user != request.user:
        return Response({
            'message': 'You can only end your own breaks'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if break can be ended
    if break_log.status not in ['started', 'extended']:
        return Response({
            'message': f'Break cannot be ended. Current status: {break_log.status}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # End the break
    break_log.end_break()
    
    serializer = BreakLogSerializer(break_log, context={'request': request})
    
    # Prepare status message
    status_message = 'Break ended successfully'
    if break_log.status == 'extended':
        deviation = break_log.end_deviation_minutes
        status_message += f'. Break was extended by {deviation:.0f} minutes.'
    elif break_log.status == 'shortened':
        deviation = abs(break_log.end_deviation_minutes)
        status_message += f'. Break was shortened by {deviation:.0f} minutes.'
    
    return Response({
        'message': status_message,
        'break': serializer.data,
        'final_status': break_log.status
    }, status=status.HTTP_200_OK)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_breaks(request):
    """Get breaks for the authenticated user"""
    user = request.user
    
    # Get date range from query params
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    break_status = request.query_params.get('status')
    
    # Base queryset
    breaks = BreakLog.objects.filter(user=user, is_active=True)
    
    # Apply date filters
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            breaks = breaks.filter(scheduled_start__date__gte=start_date_obj)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            breaks = breaks.filter(scheduled_start__date__lte=end_date_obj)
        except ValueError:
            pass
    
    # Filter by status if specified
    if break_status:
        breaks = breaks.filter(status=break_status)
    
    # Order by scheduled start time
    breaks = breaks.order_by('-scheduled_start')
    
    # Serialize data
    serializer = BreakLogSerializer(breaks, many=True, context={'request': request})
    
    # Calculate summary statistics
    summary = {
        'total_breaks': breaks.count(),
        'scheduled': breaks.filter(status='scheduled').count(),
        'started': breaks.filter(status='started').count(),
        'completed': breaks.filter(status='completed').count(),
        'missed': breaks.filter(status='missed').count(),
        'extended': breaks.filter(status='extended').count(),
        'shortened': breaks.filter(status='shortened').count(),
        'on_time_starts': breaks.filter(start_punctuality='on_time').count(),
        'early_starts': breaks.filter(start_punctuality='early').count(),
        'late_starts': breaks.filter(start_punctuality='late').count(),
        'very_late_starts': breaks.filter(start_punctuality='very_late').count(),
        'on_time_ends': breaks.filter(end_punctuality='on_time').count(),
        'early_ends': breaks.filter(end_punctuality='early').count(),
        'late_ends': breaks.filter(end_punctuality='late').count(),
        'very_late_ends': breaks.filter(end_punctuality='very_late').count(),
    }

    print("Breaks Summary:", summary)
    
    return Response({
        'summary': summary,
        'breaks': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_breaks(request, user_id):
    """Get breaks for a specific user (requires permission)"""
    user = get_object_or_404(CustomUser, id=user_id)
    
    # Check permissions
    if not request.user.is_admin and not request.user.can_supervise(user) and request.user != user:
        return Response({
            'message': 'You do not have permission to view these breaks'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get date range from query params
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    break_status = request.query_params.get('status')
    
    # Base queryset
    breaks = BreakLog.objects.filter(user=user, is_active=True)
    
    # Apply date filters
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            breaks = breaks.filter(scheduled_start__date__gte=start_date_obj)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            breaks = breaks.filter(scheduled_start__date__lte=end_date_obj)
        except ValueError:
            pass
    
    # Filter by status if specified
    if break_status:
        breaks = breaks.filter(status=break_status)
    
    # Order by scheduled start time
    breaks = breaks.order_by('-scheduled_start')
    
    # Serialize data
    serializer = BreakLogSerializer(breaks, many=True, context={'request': request})
    
    # Calculate summary statistics
    summary = {
        'total_breaks': breaks.count(),
        'scheduled': breaks.filter(status='scheduled').count(),
        'started': breaks.filter(status='started').count(),
        'completed': breaks.filter(status='completed').count(),
        'missed': breaks.filter(status='missed').count(),
        'extended': breaks.filter(status='extended').count(),
        'shortened': breaks.filter(status='shortened').count(),
    }
    
    return Response({
        'user': {
            'id': user.id,
            'emp_number': user.emp_number,
            'names': user.names,
            'email': user.email
        },
        'summary': summary,
        'breaks': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_users_breaks(request):
    """Get breaks for all users (admin and supervisors only)"""
    user = request.user
    
    # Check permissions
    if not user.is_admin and not user.is_supervisor:
        return Response({
            'message': 'You do not have permission to view all users breaks'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get date range from query params
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    break_status = request.query_params.get('status')
    
    # Base queryset - supervisors only see their supervised employees
    if user.is_admin:
        breaks = BreakLog.objects.filter(is_active=True)
    else:
        supervised_users = user.supervised_employees.all()
        breaks = BreakLog.objects.filter(user__in=supervised_users, is_active=True)
    
    # Apply date filters
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            breaks = breaks.filter(scheduled_start__date__gte=start_date_obj)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            breaks = breaks.filter(scheduled_start__date__lte=end_date_obj)
        except ValueError:
            pass
    
    # Filter by status if specified
    if break_status:
        breaks = breaks.filter(status=break_status)
    
    # Order by scheduled start time
    breaks = breaks.order_by('-scheduled_start')
    
    # Serialize data
    serializer = BreakLogSerializer(breaks, many=True, context={'request': request})
    
    # Calculate summary statistics
    summary = {
        'total_breaks': breaks.count(),
        'scheduled': breaks.filter(status='scheduled').count(),
        'started': breaks.filter(status='started').count(),
        'completed': breaks.filter(status='completed').count(),
        'missed': breaks.filter(status='missed').count(),
        'extended': breaks.filter(status='extended').count(),
        'shortened': breaks.filter(status='shortened').count(),
    }
    
    return Response({
        'summary': summary,
        'breaks': serializer.data
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_breaks(request):
    """Get breaks for the authenticated user"""
    user = request.user
    
    # Get date range from query params
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    break_status = request.query_params.get('status')
    
    # Base queryset
    breaks = BreakLog.objects.filter(user=user, is_active=True)
    
    # Apply date filters
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            breaks = breaks.filter(scheduled_start__date__gte=start_date_obj)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            breaks = breaks.filter(scheduled_start__date__lte=end_date_obj)
        except ValueError:
            pass
    
    # Filter by status if specified
    if break_status:
        breaks = breaks.filter(status=break_status)
    
    # Order by scheduled start time
    breaks = breaks.order_by('-scheduled_start')
    
    # Serialize data
    serializer = BreakLogSerializer(breaks, many=True, context={'request': request})
    
    # Get all breaks for summary calculation
    all_breaks = breaks.all()  # Get the queryset
    
    # Calculate summary statistics for all statuses
    summary = {
        # Status counts
        'total_breaks': all_breaks.count(),
        'scheduled': all_breaks.filter(status='scheduled').count(),
        'started': all_breaks.filter(status='started').count(),
        'completed': all_breaks.filter(status='completed').count(),
        'missed': all_breaks.filter(status='missed').count(),
        'extended': all_breaks.filter(status='extended').count(),
        'shortened': all_breaks.filter(status='shortened').count(),
        
        # Start punctuality counts (only for started/completed/extended/shortened breaks)
        'on_time_starts': all_breaks.filter(
            start_punctuality='on_time'
        ).exclude(status='scheduled').exclude(status='missed').count(),
        'early_starts': all_breaks.filter(
            start_punctuality__in=['early', 'very_early']
        ).exclude(status='scheduled').exclude(status='missed').count(),
        'late_starts': all_breaks.filter(
            start_punctuality__in=['late', 'very_late']
        ).exclude(status='scheduled').exclude(status='missed').count(),
        'very_late_starts': all_breaks.filter(
            start_punctuality='very_late'
        ).exclude(status='scheduled').exclude(status='missed').count(),
        
        # End punctuality counts (only for completed/extended/shortened breaks)
        'on_time_ends': all_breaks.filter(
            end_punctuality='on_time'
        ).filter(status__in=['completed', 'extended', 'shortened']).count(),
        'early_ends': all_breaks.filter(
            end_punctuality__in=['early', 'very_early']
        ).filter(status__in=['completed', 'extended', 'shortened']).count(),
        'late_ends': all_breaks.filter(
            end_punctuality__in=['late', 'very_late']
        ).filter(status__in=['completed', 'extended', 'shortened']).count(),
        'very_late_ends': all_breaks.filter(
            end_punctuality='very_late'
        ).filter(status__in=['completed', 'extended', 'shortened']).count(),
        
        # Additional statistics
        'total_started_breaks': all_breaks.filter(status__in=['started']).count(),
        'total_completed_breaks': all_breaks.filter(status__in=['completed']).count(),
        'punctual_breaks': all_breaks.filter(
            start_punctuality='on_time',
            end_punctuality='on_time'
        ).filter(status__in=['completed']).count(),
        'on_time_rate': 0,  # Will calculate below
    }
    
    # Calculate on-time rate (percentage)
    if summary['total_completed_breaks'] > 0:
        summary['on_time_rate'] = round(
            (summary['punctual_breaks'] / summary['total_completed_breaks']) * 100, 
            1
        )
    
    print("Breaks Summary:", summary)
    
    return Response({
        'summary': summary,
        'breaks': serializer.data,
        'meta': {
            'date_range': {
                'start_date': start_date,
                'end_date': end_date
            },
            'total_breaks': summary['total_breaks'],
            'breaks_returned': len(serializer.data)
        }
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_upcoming_breaks(request):
    """Get user's upcoming scheduled breaks"""
    user = request.user
    
    # Get upcoming breaks for today and tomorrow
    now = timezone.now()
    tomorrow = now + timedelta(days=1)
    
    upcoming_breaks = BreakLog.objects.filter(
        user=user,
        status='scheduled',
        is_active=True,
        scheduled_start__gte=now,
        scheduled_start__lte=tomorrow
    ).order_by('scheduled_start')[:5]
    
    serializer = BreakLogSerializer(upcoming_breaks, many=True, context={'request': request})
    
    return Response({
        'message': 'Upcoming breaks retrieved',
        'count': upcoming_breaks.count(),
        'breaks': serializer.data
    }, status=status.HTTP_200_OK)


# ==================== PERFORMANCE LOGS VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_performance(request):
    """Get performance logs for the authenticated user"""
    user = request.user
    
    # Get date range from query params
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    log_type = request.query_params.get('log_type')
    
    # Base queryset
    logs = UserLog.objects.filter(user=user)
    
    # Apply date filters
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            logs = logs.filter(actual_time__date__gte=start_date_obj)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            logs = logs.filter(actual_time__date__lte=end_date_obj)
        except ValueError:
            pass
    
    # Filter by log type if specified
    if log_type:
        logs = logs.filter(log_type=log_type)
    
    # Order by time
    logs = logs.order_by('-actual_time')
    
    # Serialize data
    serializer = UserLogSerializer(logs, many=True, context={'request': request})
    
    # Calculate summary statistics
    summary = {
        'total_logs': logs.count(),
        'logins': logs.filter(log_type='login').count(),
        'logouts': logs.filter(log_type='logout').count(),
        'break_starts': logs.filter(log_type='break_start').count(),
        'break_ends': logs.filter(log_type='break_end').count(),
        'shift_starts': logs.filter(log_type='shift_start').count(),
        'shift_ends': logs.filter(log_type='shift_end').count(),
        'early_count': logs.filter(status='early').count(),
        'on_time_count': logs.filter(status='on_time').count(),
        'late_count': logs.filter(status='late').count(),
        'very_late_count': logs.filter(status='very_late').count(),
        'day_off_count': logs.filter(status='day_off').count(),
    }
    
    return Response({
        'summary': summary,
        'logs': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_performance(request, user_id):
    """Get comprehensive performance logs for a specific user"""
    user = get_object_or_404(CustomUser, id=user_id)
    
    # Check permissions
    if not request.user.is_admin and not request.user.can_supervise(user) and request.user != user:
        return Response({
            'message': 'You do not have permission to view these logs'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get date range from query params
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    log_type = request.query_params.get('log_type')
    
    # Base queryset
    logs = UserLog.objects.filter(user=user)
    
    # Apply date filters
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            logs = logs.filter(actual_time__date__gte=start_date_obj)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            logs = logs.filter(actual_time__date__lte=end_date_obj)
        except ValueError:
            pass
    
    # Filter by log type if specified
    if log_type:
        logs = logs.filter(log_type=log_type)
    
    # Order by time
    logs = logs.order_by('-actual_time')
    
    # Serialize data
    serializer = UserLogSerializer(logs, many=True, context={'request': request})
    
    # Calculate summary statistics
    summary = {
        'total_logs': logs.count(),
        'logins': logs.filter(log_type='login').count(),
        'logouts': logs.filter(log_type='logout').count(),
        'break_starts': logs.filter(log_type='break_start').count(),
        'break_ends': logs.filter(log_type='break_end').count(),
        'shift_starts': logs.filter(log_type='shift_start').count(),
        'shift_ends': logs.filter(log_type='shift_end').count(),
        'early_count': logs.filter(status='early').count(),
        'on_time_count': logs.filter(status='on_time').count(),
        'late_count': logs.filter(status='late').count(),
        'very_late_count': logs.filter(status='very_late').count(),
        'day_off_count': logs.filter(status='day_off').count(),
    }
    
    return Response({
        'user': {
            'id': user.id,
            'emp_number': user.emp_number,
            'names': user.names,
            'email': user.email,
            'role': user.role
        },
        'summary': summary,
        'logs': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_users_performance(request):
    """Get performance logs for all users (admin and supervisors only)"""
    user = request.user
    
    # Check permissions
    if not user.is_admin and not user.is_supervisor:
        return Response({
            'message': 'You do not have permission to view all users performance'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get date range from query params
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    log_type = request.query_params.get('log_type')
    
    # Base queryset - supervisors only see their supervised employees
    if user.is_admin:
        logs = UserLog.objects.all()
    else:
        supervised_users = user.supervised_employees.all()
        logs = UserLog.objects.filter(user__in=supervised_users)
    
    # Apply date filters
    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            logs = logs.filter(actual_time__date__gte=start_date_obj)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            logs = logs.filter(actual_time__date__lte=end_date_obj)
        except ValueError:
            pass
    
    # Filter by log type if specified
    if log_type:
        logs = logs.filter(log_type=log_type)
    
    # Order by time
    logs = logs.order_by('-actual_time')
    
    # Serialize data
    serializer = UserLogSerializer(logs, many=True, context={'request': request})
    
    # Calculate summary statistics
    summary = {
        'total_logs': logs.count(),
        'logins': logs.filter(log_type='login').count(),
        'logouts': logs.filter(log_type='logout').count(),
        'break_starts': logs.filter(log_type='break_start').count(),
        'break_ends': logs.filter(log_type='break_end').count(),
        'shift_starts': logs.filter(log_type='shift_start').count(),
        'shift_ends': logs.filter(log_type='shift_end').count(),
        'early_count': logs.filter(status='early').count(),
        'on_time_count': logs.filter(status='on_time').count(),
        'late_count': logs.filter(status='late').count(),
        'very_late_count': logs.filter(status='very_late').count(),
        'day_off_count': logs.filter(status='day_off').count(),
    }
    
    return Response({
        'summary': summary,
        'logs': serializer.data
    }, status=status.HTTP_200_OK)