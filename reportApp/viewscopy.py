# reportApp/views.py - UPDATED WITH EXPORT FUNCTIONALITY

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Q, Avg, Sum, F, Case, When, IntegerField
from django.utils import timezone
from datetime import datetime, timedelta, date
from collections import defaultdict

from userApp.models import CustomUser, UserLog
from shiftApp.models import Shift, BreakTemplate
from taskApp.models import Task
from taskAssignmentApp.models import TaskAssignment, ShiftTaskRotation, TaskOverload
from performanceApp.models import BreakLog
from requestApp.models import ShiftChangeRequest
from notificationApp.models import Notification

from .serializerscopy import (
    UserDetailSerializer, UserLogSerializer, ShiftSerializer,
    TaskSerializer, TaskAssignmentSerializer, BreakLogSerializer,
    ShiftChangeRequestSerializer, NotificationSerializer
)

# Import the export utility
from .export_utils import ReportExporter


# ==================== Helper Functions ====================

def get_user_queryset_by_role(user):
    """Get queryset of users based on requesting user's role"""
    if user.is_admin:
        # Admin can see all users
        return CustomUser.objects.all()
    elif user.is_supervisor:
        # Supervisor can see their supervised employees and themselves
        return CustomUser.objects.filter(
            Q(id=user.id) | Q(supervisors=user)
        ).distinct()
    else:
        # Employee can only see themselves
        return CustomUser.objects.filter(id=user.id)


def get_date_range(period='today', start_date=None, end_date=None):
    """Get date range based on period or custom dates"""
    today = timezone.now().date()
    
    if start_date and end_date:
        return start_date, end_date
    
    if period == 'today':
        return today, today
    elif period == 'yesterday':
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    elif period == 'this_week':
        start = today - timedelta(days=today.weekday())
        return start, today
    elif period == 'last_week':
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return start, end
    elif period == 'this_month':
        start = today.replace(day=1)
        return start, today
    elif period == 'last_month':
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end
    elif period == 'this_year':
        start = today.replace(month=1, day=1)
        return start, today
    else:
        return today, today


# ==================== Dashboard Views ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_overview(request):
    """
    Get dashboard overview based on user role
    Admin: All system data
    Supervisor: Their supervised employees data
    Employee: Their own data
    """
    user = request.user
    period = request.GET.get('period', 'today')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Parse dates if provided
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    date_start, date_end = get_date_range(period, start_date, end_date)
    
    # Get users based on role
    users_queryset = get_user_queryset_by_role(user)
    
    # Basic statistics
    total_users = users_queryset.filter(status='active').count()
    
    # User logs in date range
    user_logs = UserLog.objects.filter(
        user__in=users_queryset,
        created_at__date__range=[date_start, date_end]
    )
    
    # Attendance statistics
    login_logs = user_logs.filter(log_type='login')
    logout_logs = user_logs.filter(log_type='logout')
    
    attendance_stats = {
        'total_logins': login_logs.count(),
        'total_logouts': logout_logs.count(),
        'on_time_logins': login_logs.filter(status='on_time').count(),
        'late_logins': login_logs.filter(status__in=['late', 'very_late']).count(),
        'early_logins': login_logs.filter(status='early').count(),
    }
    
    # Break statistics
    break_logs = BreakLog.objects.filter(
        user__in=users_queryset,
        scheduled_start__date__range=[date_start, date_end]
    )
    
    break_stats = {
        'total_breaks': break_logs.count(),
        'completed_breaks': break_logs.filter(status='completed').count(),
        'missed_breaks': break_logs.filter(status='missed').count(),
        'extended_breaks': break_logs.filter(status='extended').count(),
        'on_time_breaks': break_logs.filter(
            start_punctuality='on_time',
            end_punctuality='on_time'
        ).count(),
    }
    
    # Task assignment statistics
    task_assignments = TaskAssignment.objects.filter(
        user__in=users_queryset,
        assignment_date__range=[date_start, date_end]
    )
    
    task_stats = {
        'total_assignments': task_assignments.count(),
        'completed_tasks': task_assignments.filter(status='completed').count(),
        'active_tasks': task_assignments.filter(status='active').count(),
        'scheduled_tasks': task_assignments.filter(status='scheduled').count(),
        'missed_tasks': task_assignments.filter(status='missed').count(),
    }
    
    # Shift change requests
    shift_requests = ShiftChangeRequest.objects.filter(
        user__in=users_queryset,
        created_at__date__range=[date_start, date_end]
    )
    
    request_stats = {
        'total_requests': shift_requests.count(),
        'pending_requests': shift_requests.filter(status='pending').count(),
        'accepted_requests': shift_requests.filter(status='accepted').count(),
        'cancelled_requests': shift_requests.filter(status='cancelled').count(),
    }
    
    # Notifications
    notifications = Notification.objects.filter(
        user__in=users_queryset,
        created_at__date__range=[date_start, date_end]
    )
    
    notification_stats = {
        'total_notifications': notifications.count(),
        'unread_notifications': notifications.filter(is_read=False).count(),
        'read_notifications': notifications.filter(is_read=True).count(),
    }
    
    # Performance metrics
    if user.is_admin:
        # Overall system performance
        active_users_today = UserLog.objects.filter(
            log_type='login',
            created_at__date=timezone.now().date()
        ).values('user').distinct().count()
        
        performance_metrics = {
            'active_users_today': active_users_today,
            'attendance_rate': round((attendance_stats['on_time_logins'] / max(attendance_stats['total_logins'], 1)) * 100, 2),
            'break_compliance_rate': round((break_stats['on_time_breaks'] / max(break_stats['total_breaks'], 1)) * 100, 2),
            'task_completion_rate': round((task_stats['completed_tasks'] / max(task_stats['total_assignments'], 1)) * 100, 2),
        }
    else:
        performance_metrics = {
            'attendance_rate': round((attendance_stats['on_time_logins'] / max(attendance_stats['total_logins'], 1)) * 100, 2),
            'break_compliance_rate': round((break_stats['on_time_breaks'] / max(break_stats['total_breaks'], 1)) * 100, 2),
            'task_completion_rate': round((task_stats['completed_tasks'] / max(task_stats['total_assignments'], 1)) * 100, 2),
        }
    
    return Response({
        'period': period,
        'date_range': {
            'start': date_start,
            'end': date_end
        },
        'user_role': user.role,
        'total_users': total_users,
        'attendance': attendance_stats,
        'breaks': break_stats,
        'tasks': task_stats,
        'shift_requests': request_stats,
        'notifications': notification_stats,
        'performance_metrics': performance_metrics,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_performance_dashboard(request):
    """
    Get detailed performance dashboard for users
    """
    user = request.user
    user_id = request.GET.get('user_id')
    period = request.GET.get('period', 'this_month')
    
    # Determine target user
    if user_id:
        try:
            target_user = CustomUser.objects.get(id=user_id)
            # Check permission
            if not (user.is_admin or (user.is_supervisor and user.can_supervise(target_user)) or user == target_user):
                return Response(
                    {'error': 'You do not have permission to view this user\'s performance'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    else:
        target_user = user
    
    date_start, date_end = get_date_range(period)
    
    # User logs analysis
    user_logs = UserLog.objects.filter(
        user=target_user,
        created_at__date__range=[date_start, date_end]
    )
    
    # Attendance analysis
    login_logs = user_logs.filter(log_type='login')
    logout_logs = user_logs.filter(log_type='logout')
    
    punctuality_breakdown = {
        'on_time': login_logs.filter(status='on_time').count(),
        'early': login_logs.filter(status='early').count(),
        'late': login_logs.filter(status='late').count(),
        'very_late': login_logs.filter(status='very_late').count(),
    }
    
    # Break performance
    break_logs = BreakLog.objects.filter(
        user=target_user,
        scheduled_start__date__range=[date_start, date_end]
    )
    
    break_performance = {
        'total_breaks': break_logs.count(),
        'completed': break_logs.filter(status='completed').count(),
        'missed': break_logs.filter(status='missed').count(),
        'extended': break_logs.filter(status='extended').count(),
        'shortened': break_logs.filter(status='shortened').count(),
        'average_deviation_minutes': break_logs.exclude(
            actual_start__isnull=True,
            actual_end__isnull=True
        ).aggregate(
            avg_deviation=Avg(
                (F('actual_end') - F('actual_start')) - (F('scheduled_end') - F('scheduled_start'))
            )
        )['avg_deviation'],
    }
    
    # Task performance
    task_assignments = TaskAssignment.objects.filter(
        user=target_user,
        assignment_date__range=[date_start, date_end]
    )
    
    task_performance = {
        'total_assignments': task_assignments.count(),
        'completed': task_assignments.filter(status='completed').count(),
        'active': task_assignments.filter(status='active').count(),
        'scheduled': task_assignments.filter(status='scheduled').count(),
        'missed': task_assignments.filter(status='missed').count(),
        'completion_rate': round(
            (task_assignments.filter(status='completed').count() / max(task_assignments.count(), 1)) * 100, 2
        ),
    }
    
    # Recent activities
    recent_logs = user_logs.order_by('-created_at')[:10]
    
    # Shift change requests
    shift_requests = ShiftChangeRequest.objects.filter(
        user=target_user,
        created_at__date__range=[date_start, date_end]
    )
    
    return Response({
        'user': UserDetailSerializer(target_user).data,
        'period': period,
        'date_range': {
            'start': date_start,
            'end': date_end
        },
        'attendance': {
            'total_logins': login_logs.count(),
            'total_logouts': logout_logs.count(),
            'punctuality_breakdown': punctuality_breakdown,
        },
        'break_performance': break_performance,
        'task_performance': task_performance,
        'shift_requests': {
            'total': shift_requests.count(),
            'pending': shift_requests.filter(status='pending').count(),
            'accepted': shift_requests.filter(status='accepted').count(),
            'cancelled': shift_requests.filter(status='cancelled').count(),
        },
        'recent_activities': UserLogSerializer(recent_logs, many=True).data,
    })


# ==================== Report Generation Views ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attendance_report(request):
    """
    Generate attendance report based on user role and filters
    """
    user = request.user
    period = request.GET.get('period', 'this_month')
    user_id = request.GET.get('user_id')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Parse dates if provided
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    date_start, date_end = get_date_range(period, start_date, end_date)
    
    # Get users based on role
    if user_id:
        try:
            target_user = CustomUser.objects.get(id=user_id)
            if not (user.is_admin or (user.is_supervisor and user.can_supervise(target_user)) or user == target_user):
                return Response(
                    {'error': 'You do not have permission to view this report'},
                    status=status.HTTP_403_FORBIDDEN
                )
            users_queryset = CustomUser.objects.filter(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    else:
        users_queryset = get_user_queryset_by_role(user)
    
    # Get login logs
    login_logs = UserLog.objects.filter(
        user__in=users_queryset,
        log_type='login',
        created_at__date__range=[date_start, date_end]
    ).select_related('user', 'shift').order_by('-created_at')
    
    # Get logout logs
    logout_logs = UserLog.objects.filter(
        user__in=users_queryset,
        log_type='logout',
        created_at__date__range=[date_start, date_end]
    ).select_related('user', 'shift').order_by('-created_at')
    
    # Aggregate statistics by user
    user_stats = []
    for usr in users_queryset:
        user_login_logs = login_logs.filter(user=usr)
        user_logout_logs = logout_logs.filter(user=usr)
        
        user_stats.append({
            'user': UserDetailSerializer(usr).data,
            'total_logins': user_login_logs.count(),
            'total_logouts': user_logout_logs.count(),
            'on_time': user_login_logs.filter(status='on_time').count(),
            'early': user_login_logs.filter(status='early').count(),
            'late': user_login_logs.filter(status='late').count(),
            'very_late': user_login_logs.filter(status='very_late').count(),
            'attendance_rate': round(
                (user_login_logs.filter(status='on_time').count() / max(user_login_logs.count(), 1)) * 100, 2
            ),
        })
    
    return Response({
        'report_type': 'attendance',
        'period': period,
        'date_range': {
            'start': date_start,
            'end': date_end
        },
        'generated_by': {
            'id': user.id,
            'name': user.names,
            'role': user.role
        },
        'generated_at': timezone.now(),
        'total_logins': login_logs.count(),
        'total_logouts': logout_logs.count(),
        'user_statistics': user_stats,
        'login_logs': UserLogSerializer(login_logs, many=True).data,
        'logout_logs': UserLogSerializer(logout_logs, many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def break_compliance_report(request):
    """
    Generate break compliance report
    """
    user = request.user
    period = request.GET.get('period', 'this_month')
    user_id = request.GET.get('user_id')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Parse dates
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    date_start, date_end = get_date_range(period, start_date, end_date)
    
    # Get users based on role
    if user_id:
        try:
            target_user = CustomUser.objects.get(id=user_id)
            if not (user.is_admin or (user.is_supervisor and user.can_supervise(target_user)) or user == target_user):
                return Response(
                    {'error': 'You do not have permission to view this report'},
                    status=status.HTTP_403_FORBIDDEN
                )
            users_queryset = CustomUser.objects.filter(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    else:
        users_queryset = get_user_queryset_by_role(user)
    
    # Get break logs
    break_logs = BreakLog.objects.filter(
        user__in=users_queryset,
        scheduled_start__date__range=[date_start, date_end]
    ).select_related('user', 'break_template').order_by('-scheduled_start')
    
    # Aggregate by user
    user_stats = []
    for usr in users_queryset:
        user_breaks = break_logs.filter(user=usr)
        
        user_stats.append({
            'user': UserDetailSerializer(usr).data,
            'total_breaks': user_breaks.count(),
            'completed': user_breaks.filter(status='completed').count(),
            'missed': user_breaks.filter(status='missed').count(),
            'extended': user_breaks.filter(status='extended').count(),
            'shortened': user_breaks.filter(status='shortened').count(),
            'on_time': user_breaks.filter(
                start_punctuality='on_time',
                end_punctuality='on_time'
            ).count(),
            'compliance_rate': round(
                (user_breaks.filter(status='completed').count() / max(user_breaks.count(), 1)) * 100, 2
            ),
        })
    
    return Response({
        'report_type': 'break_compliance',
        'period': period,
        'date_range': {
            'start': date_start,
            'end': date_end
        },
        'generated_by': {
            'id': user.id,
            'name': user.names,
            'role': user.role
        },
        'generated_at': timezone.now(),
        'total_breaks': break_logs.count(),
        'user_statistics': user_stats,
        'break_logs': BreakLogSerializer(break_logs, many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def task_completion_report(request):
    """
    Generate task completion report
    """
    user = request.user
    period = request.GET.get('period', 'this_month')
    user_id = request.GET.get('user_id')
    task_id = request.GET.get('task_id')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Parse dates
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    date_start, date_end = get_date_range(period, start_date, end_date)
    
    # Get users based on role
    if user_id:
        try:
            target_user = CustomUser.objects.get(id=user_id)
            if not (user.is_admin or (user.is_supervisor and user.can_supervise(target_user)) or user == target_user):
                return Response(
                    {'error': 'You do not have permission to view this report'},
                    status=status.HTTP_403_FORBIDDEN
                )
            users_queryset = CustomUser.objects.filter(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    else:
        users_queryset = get_user_queryset_by_role(user)
    
    # Get task assignments
    task_assignments = TaskAssignment.objects.filter(
        user__in=users_queryset,
        assignment_date__range=[date_start, date_end]
    ).select_related('user', 'task', 'shift')
    
    # Filter by task if specified
    if task_id:
        task_assignments = task_assignments.filter(task_id=task_id)
    
    # Aggregate by user
    user_stats = []
    for usr in users_queryset:
        user_assignments = task_assignments.filter(user=usr)
        
        user_stats.append({
            'user': UserDetailSerializer(usr).data,
            'total_assignments': user_assignments.count(),
            'completed': user_assignments.filter(status='completed').count(),
            'active': user_assignments.filter(status='active').count(),
            'scheduled': user_assignments.filter(status='scheduled').count(),
            'missed': user_assignments.filter(status='missed').count(),
            'completion_rate': round(
                (user_assignments.filter(status='completed').count() / max(user_assignments.count(), 1)) * 100, 2
            ),
        })
    
    # Aggregate by task
    task_stats = []
    tasks = Task.objects.filter(
        assignments__in=task_assignments
    ).distinct()
    
    for task in tasks:
        task_task_assignments = task_assignments.filter(task=task)
        
        task_stats.append({
            'task': TaskSerializer(task).data,
            'total_assignments': task_task_assignments.count(),
            'completed': task_task_assignments.filter(status='completed').count(),
            'active': task_task_assignments.filter(status='active').count(),
            'scheduled': task_task_assignments.filter(status='scheduled').count(),
            'missed': task_task_assignments.filter(status='missed').count(),
            'completion_rate': round(
                (task_task_assignments.filter(status='completed').count() / max(task_task_assignments.count(), 1)) * 100, 2
            ),
        })
    
    return Response({
        'report_type': 'task_completion',
        'period': period,
        'date_range': {
            'start': date_start,
            'end': date_end
        },
        'generated_by': {
            'id': user.id,
            'name': user.names,
            'role': user.role
        },
        'generated_at': timezone.now(),
        'total_assignments': task_assignments.count(),
        'user_statistics': user_stats,
        'task_statistics': task_stats,
        'assignments': TaskAssignmentSerializer(task_assignments.order_by('-assignment_date'), many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def shift_change_request_report(request):
    """
    Generate shift change request report
    """
    user = request.user
    period = request.GET.get('period', 'this_month')
    status_filter = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Parse dates
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    date_start, date_end = get_date_range(period, start_date, end_date)
    
    # Get users based on role
    users_queryset = get_user_queryset_by_role(user)
    
    # Get shift change requests
    requests = ShiftChangeRequest.objects.filter(
        user__in=users_queryset,
        created_at__date__range=[date_start, date_end]
    ).select_related('user', 'current_shift', 'new_shift', 'approved_by', 'cancelled_by')
    
    # Filter by status if specified
    if status_filter:
        requests = requests.filter(status=status_filter)
    
    # Aggregate statistics
    total_requests = requests.count()
    pending = requests.filter(status='pending').count()
    accepted = requests.filter(status='accepted').count()
    cancelled = requests.filter(status='cancelled').count()
    
    # Breakdown by change type
    change_type_breakdown = {
        'shift_only': requests.filter(change_type='shift_only').count(),
        'day_off_only': requests.filter(change_type='day_off_only').count(),
        'both': requests.filter(change_type='both').count(),
    }
    
    return Response({
        'report_type': 'shift_change_requests',
        'period': period,
        'date_range': {
            'start': date_start,
            'end': date_end
        },
        'generated_by': {
            'id': user.id,
            'name': user.names,
            'role': user.role
        },
        'generated_at': timezone.now(),
        'summary': {
            'total_requests': total_requests,
            'pending': pending,
            'accepted': accepted,
            'cancelled': cancelled,
            'acceptance_rate': round((accepted / max(total_requests, 1)) * 100, 2),
        },
        'change_type_breakdown': change_type_breakdown,
        'requests': ShiftChangeRequestSerializer(requests.order_by('-created_at'), many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_activity_log_report(request):
    """
    Generate comprehensive user activity log report
    """
    user = request.user
    period = request.GET.get('period', 'today')
    user_id = request.GET.get('user_id')
    log_type = request.GET.get('log_type')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Parse dates
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    date_start, date_end = get_date_range(period, start_date, end_date)
    
    # Get users based on role
    if user_id:
        try:
            target_user = CustomUser.objects.get(id=user_id)
            if not (user.is_admin or (user.is_supervisor and user.can_supervise(target_user)) or user == target_user):
                return Response(
                    {'error': 'You do not have permission to view this report'},
                    status=status.HTTP_403_FORBIDDEN
                )
            users_queryset = CustomUser.objects.filter(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    else:
        users_queryset = get_user_queryset_by_role(user)
    
    # Get user logs
    user_logs = UserLog.objects.filter(
        user__in=users_queryset,
        created_at__date__range=[date_start, date_end]
    ).select_related('user', 'shift', 'break_log').order_by('-created_at')
    
    # Filter by log type if specified
    if log_type:
        user_logs = user_logs.filter(log_type=log_type)
    
    # Activity breakdown
    activity_breakdown = {}
    for log in user_logs:
        log_type_key = log.log_type
        if log_type_key not in activity_breakdown:
            activity_breakdown[log_type_key] = 0
        activity_breakdown[log_type_key] += 1
    
    return Response({
        'report_type': 'user_activity_log',
        'period': period,
        'date_range': {
            'start': date_start,
            'end': date_end
        },
        'generated_by': {
            'id': user.id,
            'name': user.names,
            'role': user.role
        },
        'generated_at': timezone.now(),
        'total_logs': user_logs.count(),
        'activity_breakdown': activity_breakdown,
        'logs': UserLogSerializer(user_logs, many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def productivity_report(request):
    """
    Generate comprehensive productivity report
    Combines attendance, breaks, and tasks
    """
    user = request.user
    period = request.GET.get('period', 'this_month')
    user_id = request.GET.get('user_id')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Parse dates
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    date_start, date_end = get_date_range(period, start_date, end_date)
    
    # Get users based on role
    if user_id:
        try:
            target_user = CustomUser.objects.get(id=user_id)
            if not (user.is_admin or (user.is_supervisor and user.can_supervise(target_user)) or user == target_user):
                return Response(
                    {'error': 'You do not have permission to view this report'},
                    status=status.HTTP_403_FORBIDDEN
                )
            users_queryset = CustomUser.objects.filter(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    else:
        users_queryset = get_user_queryset_by_role(user)
    
    # Calculate productivity metrics for each user
    user_productivity = []
    
    for usr in users_queryset:
        # Attendance
        login_logs = UserLog.objects.filter(
            user=usr,
            log_type='login',
            created_at__date__range=[date_start, date_end]
        )
        
        # Breaks
        break_logs = BreakLog.objects.filter(
            user=usr,
            scheduled_start__date__range=[date_start, date_end]
        )
        
        # Tasks
        task_assignments = TaskAssignment.objects.filter(
            user=usr,
            assignment_date__range=[date_start, date_end]
        )
        
        # Calculate scores
        attendance_score = round(
            (login_logs.filter(status='on_time').count() / max(login_logs.count(), 1)) * 100, 2
        )
        
        break_compliance_score = round(
            (break_logs.filter(status='completed').count() / max(break_logs.count(), 1)) * 100, 2
        )
        
        task_completion_score = round(
            (task_assignments.filter(status='completed').count() / max(task_assignments.count(), 1)) * 100, 2
        )
        
        # Overall productivity score (weighted average)
        overall_score = round(
            (attendance_score * 0.3) + (break_compliance_score * 0.3) + (task_completion_score * 0.4), 2
        )
        
        user_productivity.append({
            'user': UserDetailSerializer(usr).data,
            'attendance_score': attendance_score,
            'break_compliance_score': break_compliance_score,
            'task_completion_score': task_completion_score,
            'overall_productivity_score': overall_score,
            'total_working_days': login_logs.values('created_at__date').distinct().count(),
            'total_tasks_completed': task_assignments.filter(status='completed').count(),
        })
    
    # Sort by overall score
    user_productivity.sort(key=lambda x: x['overall_productivity_score'], reverse=True)
    
    return Response({
        'report_type': 'productivity',
        'period': period,
        'date_range': {
            'start': date_start,
            'end': date_end
        },
        'generated_by': {
            'id': user.id,
            'name': user.names,
            'role': user.role
        },
        'generated_at': timezone.now(),
        'user_productivity': user_productivity,
    })


# ==================== Export Endpoints ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_report(request):
    """
    Export report in specified format (PDF, Excel, or CSV)
    
    Query Parameters:
    - report_type: Type of report (attendance, break_compliance, task_completion, etc.)
    - format: Export format (pdf, excel, csv)
    - period: Time period (today, this_week, this_month, etc.)
    - start_date: Custom start date (YYYY-MM-DD)
    - end_date: Custom end date (YYYY-MM-DD)
    - user_id: Filter by specific user (optional)
    """
    user = request.user
    report_type = request.GET.get('report_type', 'dashboard')
    export_format = request.GET.get('format', 'pdf').lower()
    
    # Validate format
    if export_format not in ['pdf', 'excel', 'csv']:
        return Response(
            {'error': 'Invalid export format. Choose from: pdf, excel, csv'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get report data based on report type
    report_data = None
    metadata = {
        'generated_by': {
            'id': user.id,
            'name': user.names,
            'role': user.role
        }
    }
    
    # Call appropriate report function and get data
    if report_type == 'attendance':
        response = attendance_report(request)
        report_data = response.data
    elif report_type == 'break_compliance':
        response = break_compliance_report(request)
        report_data = response.data
    elif report_type == 'task_completion':
        response = task_completion_report(request)
        report_data = response.data
    elif report_type == 'shift_change_requests':
        response = shift_change_request_report(request)
        report_data = response.data
    elif report_type == 'user_activity_log':
        response = user_activity_log_report(request)
        report_data = response.data
    elif report_type == 'productivity':
        response = productivity_report(request)
        report_data = response.data
    elif report_type == 'dashboard':
        response = dashboard_overview(request)
        report_data = response.data
    elif report_type == 'user_performance':
        response = user_performance_dashboard(request)
        report_data = response.data
    else:
        return Response(
            {'error': 'Invalid report type'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Extract metadata from report data
    metadata['date_range'] = report_data.get('date_range', {})
    metadata['period'] = report_data.get('period', '')
    
    # Create exporter instance
    exporter = ReportExporter(report_type, report_data, metadata)
    
    # Export based on format
    try:
        if export_format == 'pdf':
            return exporter.export_to_pdf()
        elif export_format == 'excel':
            return exporter.export_to_excel()
        elif export_format == 'csv':
            return exporter.export_to_csv()
    except Exception as e:
        return Response(
            {'error': f'Export failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )