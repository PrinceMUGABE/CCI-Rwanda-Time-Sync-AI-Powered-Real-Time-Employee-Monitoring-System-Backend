# views.py
from io import BytesIO
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Q, Avg, Sum, F
from django.utils.timezone import now
from datetime import date, datetime, timedelta
import json
import traceback

from userApp.models import CustomUser, UserLog
from notificationApp.models import Notification, NotificationPreference
from performanceApp.models import BreakLog
from requestApp.models import ShiftChangeRequest
from shiftApp.models import Shift, BreakTemplate
from taskApp.models import Task
from taskAssignmentApp.models import TaskAssignment
from .export_utils import ReportExporter
from .serializers import (
    AdminDashboardSummarySerializer, AllTimePerformanceSummarySerializer, SupervisorAllTimePerformanceSummarySerializer, SupervisorWeeklyPerformanceSummarySerializer, UserAnalyticsSummarySerializer,
    ShiftReportSummarySerializer, PerformanceReportSummarySerializer,
    TeamPerformanceSummarySerializer, AttendanceReportSummarySerializer,
    EmployeeDashboardSummarySerializer, BreakScheduleSummarySerializer,
    TaskScheduleSummarySerializer, ActivityLogSummarySerializer,
    ExportSummarySerializer, WeeklyPerformanceSummarySerializer
)
from django.db import models

# ==================== HELPER FUNCTIONS ====================
def check_role_permission(user, allowed_roles):
    """Check if user has permission based on role"""
    try:
        return user.role in allowed_roles
    except Exception as e:
        print(f"[PERMISSION ERROR] ❌ Error checking role permission: {str(e)}")
        print(traceback.format_exc())
        return False

def get_date_filters(filters):
    """Extract and validate date filters"""
    try:
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        
        if start_date:
            start_date = now().replace(hour=0, minute=0, second=0) - timedelta(days=int(start_date))
        if end_date:
            end_date = now().replace(hour=23, minute=59, second=59)
        
        return start_date, end_date
    except Exception as e:
        print(f"[DATE FILTER ERROR] ❌ Error parsing date filters: {str(e)}")
        print(traceback.format_exc())
        return None, None

def print_report_summary(report_type, summary, detailed_data=None):
    """Print report summary to terminal with detailed information"""
    try:
        print("\n" + "="*80)
        print(f"[REPORT LOG] ✅ {report_type.replace('_', ' ').title()} Report Generated")
        print("="*80)
        
        # Print summary data
        print("\n📊 SUMMARY DATA:")
        print("-" * 40)
        
        if report_type == 'admin_dashboard':
            users = summary.get('users', {})
            print(f"👥 Users: {users.get('total', 0)} total, {users.get('active', 0)} active")
            print(f"👨‍💼 Supervisors: {users.get('supervisors', 0)}")
            print(f"👷 Employees: {users.get('employees', 0)}")
            
            shifts = summary.get('shifts', {})
            print(f"🔄 Shifts: {shifts.get('total', 0)} total")
            
            tasks = summary.get('tasks', {})
            print(f"✅ Tasks: {tasks.get('total', 0)} total")
            
            requests = summary.get('requests', {})
            print(f"📋 Pending Requests: {requests.get('pending', 0)}")
        
        elif report_type == 'user_analytics':
            print(f"👥 Total Users: {summary.get('total_users', 0)}")
            print(f"✅ Active Today: {summary.get('active_today', 0)}")
            print(f"📈 Recent Registrations: {summary.get('recent_registrations', 0)}")
            print(f"💰 Average Salary: ${summary.get('average_salary', 0):,.2f}")
            
            # Print users by shift
            print("\n👥 Users by Shift:")
            for shift_data in summary.get('users_by_shift', []):
                print(f"  - {shift_data.get('name', 'Unknown')}: {shift_data.get('user_count', 0)} users")
        
        elif report_type == 'team_performance':
            print(f"👨‍💼 Supervisor: {summary.get('supervisor_name', '')}")
            print(f"👥 Team Members: {summary.get('total_employees', 0)}")
            print(f"📅 Time Period: {summary.get('time_period', '')}")
            
            # Print individual performance
            print("\n🎯 Individual Performance:")
            for emp in summary.get('team_performance', []):
                print(f"  - {emp.get('employee_name', '')}:")
                print(f"    Break Comp: {emp.get('break_performance', {}).get('completion_rate', 0)}%")
                print(f"    Task Comp: {emp.get('task_performance', {}).get('completion_rate', 0)}%")
                print(f"    Attendance: {emp.get('attendance', {}).get('attendance_rate', 0)}%")
        
        elif report_type == 'attendance_report':
            attendance = summary.get('attendance_summary', {})
            print(f"📅 Date: {summary.get('date', '')}")
            print(f"👥 Total: {attendance.get('total_employees', 0)}")
            print(f"✅ Present: {attendance.get('present', 0)}")
            print(f"❌ Absent: {attendance.get('absent', 0)}")
            print(f"📊 Attendance Rate: {attendance.get('attendance_rate', 0)}%")
        
        # Print detailed data counts if available
        if detailed_data:
            print("\n📋 DETAILED DATA COUNTS:")
            print("-" * 40)
            
            if report_type == 'admin_dashboard':
                print(f"👥 Users Detailed Records: {len(detailed_data.get('users', []))}")
                print(f"🔄 Shifts Detailed Records: {len(detailed_data.get('shifts', []))}")
                print(f"✅ Tasks Detailed Records: {len(detailed_data.get('tasks', []))}")
            
            elif report_type == 'team_performance':
                print(f"👥 Team Members Detailed: {len(detailed_data.get('employees', []))}")
                print(f"☕ Breaks Detailed: {len(detailed_data.get('break_logs', []))}")
                print(f"✅ Tasks Detailed: {len(detailed_data.get('task_assignments', []))}")
                print(f"📝 Logs Detailed: {len(detailed_data.get('user_logs', []))}")
        
        print(f"\n🕐 Generated At: {summary.get('generated_at', now())}")
        print("="*80 + "\n")
    except Exception as e:
        print(f"[PRINT REPORT ERROR] ❌ Error printing report summary: {str(e)}")
        print(traceback.format_exc())

# ==================== ADMIN REPORTS ====================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard_overview(request):
    """Admin dashboard with overall system statistics"""
    try:
        user = request.user
        
        # Check permission
        if not check_role_permission(user, ['admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access admin dashboard")
            return Response({
                'success': False,
                'message': 'Permission denied. Admin access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 Admin dashboard requested by {user.names} ({user.role})")
        
        # Get all users data
        all_users = CustomUser.objects.all()
        
        # User statistics (summary)
        total_users = all_users.count()
        active_users = all_users.filter(status='active').count()
        supervisors = all_users.filter(role='supervisor').count()
        employees = all_users.filter(role='employee').count()
        
        # Shift statistics
        all_shifts = Shift.objects.filter(status='active')
        total_shifts = all_shifts.count()
        
        # Task statistics
        all_tasks = Task.objects.all()
        total_tasks = all_tasks.count()
        active_tasks = all_tasks.filter(status='active').count()
        
        # Notification statistics
        all_notifications = Notification.objects.all()
        total_notifications = all_notifications.count()
        unread_notifications = all_notifications.filter(is_read=False).count()
        
        # Break statistics
        today = now().date()
        all_breaks = BreakLog.objects.filter(scheduled_start__date=today)
        todays_breaks = all_breaks.count()
        completed_breaks = all_breaks.filter(status='completed').count()
        
        # Request statistics
        all_requests = ShiftChangeRequest.objects.all()
        pending_requests = all_requests.filter(status='pending').count()
        
        # Summary data
        summary = {
            'success': True,
            'users': {
                'total': total_users,
                'active': active_users,
                'supervisors': supervisors,
                'employees': employees,
                'by_status': list(CustomUser.objects.values('status').annotate(count=Count('id')))
            },
            'shifts': {
                'total': total_shifts,
                'active': total_shifts,
                'average_users_per_shift': round(employees / max(1, total_shifts), 2)
            },
            'tasks': {
                'total': total_tasks,
                'active': active_tasks,
                'inactive': total_tasks - active_tasks
            },
            'notifications': {
                'total': total_notifications,
                'unread': unread_notifications,
                'read_rate': round(((total_notifications - unread_notifications) / total_notifications * 100), 2) if total_notifications > 0 else 0
            },
            'breaks': {
                'today_scheduled': todays_breaks,
                'today_completed': completed_breaks,
                'completion_rate': round((completed_breaks / todays_breaks * 100), 2) if todays_breaks > 0 else 0
            },
            'requests': {
                'pending': pending_requests,
                'today': ShiftChangeRequest.objects.filter(created_at__date=today).count()
            },
            'generated_at': now()
        }
        
        # Detailed data
        detailed_data = {
            'users': list(CustomUser.objects.values('id', 'emp_number', 'names', 'email', 'role', 'status')),
            'shifts': list(Shift.objects.values('id', 'name', 'start_at', 'end_at', 'status')),
            'tasks': list(Task.objects.values('id', 'name', 'status', 'created_at')),
            'notifications': list(Notification.objects.values('id', 'notification_type', 'title', 'is_read', 'created_at')[:100]),
            'breaks': list(BreakLog.objects.filter(scheduled_start__date=today).values('id', 'user__names', 'break_template__name', 'status', 'scheduled_start')[:100]),
            'requests': list(ShiftChangeRequest.objects.values('id', 'user__names', 'change_type', 'status', 'created_at')[:100])
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'detailed_data': detailed_data,
            'metadata': {
                'report_type': 'admin_dashboard',
                'generated_by': user.names,
                'generated_at': now(),
                'total_records': {
                    'users': total_users,
                    'shifts': total_shifts,
                    'tasks': total_tasks,
                    'notifications': total_notifications,
                    'breaks': todays_breaks,
                    'requests': all_requests.count()
                }
            }
        }
        
        # Print report summary to terminal
        print_report_summary('admin_dashboard', summary, detailed_data)
        print(f"[REPORT SUCCESS] ✅ Admin dashboard generated successfully for {user.names}")
        
        # Validate with serializer
        serializer = AdminDashboardSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ Admin dashboard data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error generating admin dashboard: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ Admin Dashboard Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_user_analytics(request):
    """Detailed user analytics for admin"""
    try:
        user = request.user
        
        if not check_role_permission(user, ['admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access user analytics")
            return Response({
                'success': False,
                'message': 'Permission denied. Admin access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 User analytics requested by {user.names} ({user.role})")
        
        # Get filters from query params
        days_filter = request.GET.get('days', '30')
        
        # Calculate date range
        end_date = now()
        start_date = end_date - timedelta(days=int(days_filter))
        
        # Get all users data
        all_users = CustomUser.objects.all()
        
        # Users by shift (detailed)
        users_by_shift = Shift.objects.annotate(
            user_count=Count('assigned_users'),
            active_users=Count('assigned_users', filter=Q(assigned_users__status='active'))
        ).values('id', 'name', 'user_count', 'active_users')
        
        # Users by gender
        users_by_gender = CustomUser.objects.values('gender').annotate(
            count=Count('id')
        )
        
        # Recent users (last 30 days)
        recent_users = CustomUser.objects.filter(
            created_at__range=[start_date, end_date]
        ).count()
        
        # Active users today
        today_start = now().replace(hour=0, minute=0, second=0)
        active_today = UserLog.objects.filter(
            log_type='login',
            actual_time__gte=today_start
        ).values('user').distinct().count()
        
        # Calculate average salary
        salary_agg = CustomUser.objects.aggregate(avg_salary=Avg('salary'))
        average_salary = salary_agg['avg_salary'] or 0
        
        # Summary data
        summary = {
            'success': True,
            'time_period': f'Last {days_filter} days',
            'users_by_shift': list(users_by_shift),
            'users_by_gender': list(users_by_gender),
            'recent_registrations': recent_users,
            'active_today': active_today,
            'total_users': all_users.count(),
            'average_salary': float(average_salary),
            'generated_at': now()
        }
        
        # Get ALL users detailed data (not limited)
        users_detailed = list(all_users.values(
            'id', 'emp_number', 'names', 'email', 'role', 
            'gender', 'status', 'created_at', 'current_shift__name'
        ))
        
        # Recent users list
        recent_users_list = list(CustomUser.objects.filter(
            created_at__range=[start_date, end_date]
        ).values('id', 'names', 'email', 'role', 'created_at'))
        
        # Active users today
        active_users_today = list(UserLog.objects.filter(
            log_type='login',
            actual_time__gte=today_start
        ).select_related('user').values(
            'user__id', 
            'user__names', 
            'user__emp_number',
            'actual_time'
        ))
        
        # Detailed data - includes ALL user records
        detailed_data = {
            'all_users': users_detailed,
            'users_by_shift_detailed': list(users_by_shift),
            'users_by_gender_detailed': list(users_by_gender),
            'recent_users': recent_users_list,
            'active_users_today': active_users_today
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'detailed_data': detailed_data,
            'metadata': {
                'report_type': 'admin_user_analytics',
                'generated_by': user.names,
                'generated_at': now(),
                'time_period': f'Last {days_filter} days',
                'total_records': {
                    'all_users': len(users_detailed),
                    'recent_users': len(recent_users_list),
                    'active_today': len(active_users_today)
                }
            }
        }
        
        # ==================== ENHANCED TERMINAL OUTPUT ====================
        print("\n" + "="*100)
        print(f"[REPORT GENERATED] ✅ User Analytics Report for {user.names}")
        print("="*100)
        
        # Print summary
        print(f"\n📊 SUMMARY DATA:")
        print("-" * 50)
        print(f"👥 Total Users: {summary['total_users']}")
        print(f"✅ Active Today: {summary['active_today']}")
        print(f"📈 Recent Registrations: {summary['recent_registrations']}")
        print(f"💰 Average Salary: ${summary['average_salary']:,.2f}")
        
        print(f"\n👥 Users by Shift Distribution:")
        for shift in summary['users_by_shift']:
            print(f"  - {shift['name']}: {shift['user_count']} users ({shift['active_users']} active)")
        
        print(f"\n👤 Users by Gender:")
        for gender_data in summary['users_by_gender']:
            gender = gender_data['gender'] if gender_data['gender'] else 'Not Specified'
            print(f"  - {gender}: {gender_data['count']} users")
        
        # Print detailed data
        print(f"\n📋 DETAILED DATA:")
        print("-" * 50)
        print(f"📁 Total User Records: {len(users_detailed)}")
        print(f"\nFirst 5 User Records:")
        for i, user_data in enumerate(users_detailed[:5], 1):
            print(f"  {i}. {user_data['names']} ({user_data['emp_number']}) - {user_data['role']} - {user_data['status']}")
        
        if len(users_detailed) > 5:
            print(f"  ... and {len(users_detailed) - 5} more records")
        
        print(f"\n📊 Report Metadata:")
        print(f"  Generated At: {now()}")
        print(f"  Time Period: Last {days_filter} days")
        print(f"  Generated By: {user.names}")
        print("="*100 + "\n")
        # ==================== END TERMINAL OUTPUT ====================
        
        print(f"[REPORT SUCCESS] ✅ User analytics generated successfully for {user.names}")
        
        # Validate with serializer
        serializer = UserAnalyticsSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ User analytics data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except ValueError as ve:
        error_msg = f"Invalid parameter value: {str(ve)}"
        print(f"\n[PARAMETER ERROR] ❌ User Analytics Error: {error_msg}")
        traceback.print_exc()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'parameter_error'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error generating user analytics: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ User Analytics Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_shift_report(request):
    """Admin shift report with detailed data"""
    try:
        user = request.user
        
        if not check_role_permission(user, ['admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access shift report")
            return Response({
                'success': False,
                'message': 'Permission denied. Admin access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 Shift report requested by {user.names} ({user.role})")
        
        # Get filters
        status_filter = request.GET.get('status', 'all')
        
        # Filter shifts
        if status_filter == 'active':
            all_shifts = Shift.objects.filter(status='active')
        elif status_filter == 'inactive':
            all_shifts = Shift.objects.filter(status='inactive')
        else:
            all_shifts = Shift.objects.all()
        
        # Get shift statistics
        active_shifts = all_shifts.filter(status='active').count()
        inactive_shifts = all_shifts.filter(status='inactive').count()
        total_shifts = all_shifts.count()
        
        # Get users per shift
        shifts_with_users = []
        for shift in all_shifts:
            users_in_shift = shift.assigned_users.all()
            shifts_with_users.append({
                'shift_id': shift.id,
                'shift_name': shift.name,
                'user_count': users_in_shift.count(),
                'active_users': users_in_shift.filter(status='active').count(),
                'users': list(users_in_shift.values('id', 'names', 'emp_number', 'email', 'status')[:5])  # Limit to 5 for summary
            })
        
        # Get ALL shifts detailed data
        shifts_detailed = list(all_shifts.values(
            'id', 'name', 'start_at', 'end_at', 'status', 'description'
        ))
        
        # Get ALL break templates
        break_templates_detailed = list(BreakTemplate.objects.values(
            'id', 'shift__name', 'name', 'start_at', 'end_at', 'status'
        ))
        
        # Summary data
        summary = {
            'success': True,
            'total_shifts': total_shifts,
            'active_shifts': active_shifts,
            'inactive_shifts': inactive_shifts,
            'average_users_per_shift': round(CustomUser.objects.filter(role='employee').count() / max(1, active_shifts), 2),
            'shifts_with_users': shifts_with_users,
            'generated_at': now()
        }
        
        # Detailed data - includes ALL records
        detailed_data = {
            'shifts': shifts_detailed,
            'break_templates': break_templates_detailed,
            'shifts_detailed': list(all_shifts.values('id', 'name', 'start_at', 'end_at', 'status', 'description'))
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'detailed_data': detailed_data,
            'metadata': {
                'report_type': 'admin_shift_report',
                'generated_by': user.names,
                'generated_at': now(),
                'filters': {'status': status_filter},
                'total_records': {
                    'shifts': total_shifts,
                    'break_templates': len(break_templates_detailed)
                }
            }
        }
        
        # ==================== ENHANCED TERMINAL OUTPUT ====================
        print("\n" + "="*100)
        print(f"[REPORT GENERATED] ✅ Shift Report for {user.names}")
        print("="*100)
        
        print(f"\n📊 SHIFT SUMMARY:")
        print("-" * 50)
        print(f"📋 Total Shifts: {total_shifts}")
        print(f"✅ Active Shifts: {active_shifts}")
        print(f"❌ Inactive Shifts: {inactive_shifts}")
        print(f"👥 Average Users per Shift: {summary['average_users_per_shift']}")
        
        print(f"\n🏢 Shifts with User Distribution:")
        for shift in shifts_with_users:
            print(f"  - {shift['shift_name']}: {shift['user_count']} users ({shift['active_users']} active)")
        
        print(f"\n📋 DETAILED DATA:")
        print("-" * 50)
        print(f"📁 Total Shift Records: {len(shifts_detailed)}")
        print(f"⏰ Total Break Templates: {len(break_templates_detailed)}")
        
        print(f"\nFirst 5 Shift Records:")
        for i, shift in enumerate(shifts_detailed[:5], 1):
            print(f"  {i}. {shift['name']} ({shift['status']}) - {shift['start_at']} to {shift['end_at']}")
        
        print(f"\nFirst 5 Break Templates:")
        for i, template in enumerate(break_templates_detailed[:5], 1):
            print(f"  {i}. {template['name']} for {template['shift__name']} - {template['start_at']} to {template['end_at']}")
        
        print(f"\n📊 Report Metadata:")
        print(f"  Generated At: {now()}")
        print(f"  Status Filter: {status_filter}")
        print(f"  Generated By: {user.names}")
        print("="*100 + "\n")
        # ==================== END TERMINAL OUTPUT ====================
        
        print(f"[REPORT SUCCESS] ✅ Shift report generated successfully for {user.names}")
        
        # Validate with serializer
        serializer = ShiftReportSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ Shift report data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error generating shift report: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ Shift Report Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_performance_report(request):
    """Admin performance report with detailed data"""
    try:
        user = request.user
        
        if not check_role_permission(user, ['admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access performance report")
            return Response({
                'success': False,
                'message': 'Permission denied. Admin access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 Performance report requested by {user.names} ({user.role})")
        
        # Get filters
        days_filter = int(request.GET.get('days', '30'))
        start_date = now() - timedelta(days=days_filter)
        
        # Break performance statistics
        breaks = BreakLog.objects.filter(scheduled_start__gte=start_date)
        break_performance = {
            'total': breaks.count(),
            'completed': breaks.filter(status='completed').count(),
            'on_time_starts': breaks.filter(start_punctuality='on_time').count(),
            'on_time_ends': breaks.filter(end_punctuality='on_time').count(),
            'late_starts': breaks.filter(start_punctuality='late').count(),
            'early_ends': breaks.filter(end_punctuality='early').count()
        }
        
        # Task performance statistics
        tasks = TaskAssignment.objects.filter(assignment_date__gte=start_date.date())
        task_performance = {
            'total': tasks.count(),
            'completed': tasks.filter(status='completed').count(),
            'in_progress': tasks.filter(status='in_progress').count(),
            'pending': tasks.filter(status='pending').count(),
            'cancelled': tasks.filter(status='cancelled').count()
        }
        
        # Summary data
        summary = {
            'success': True,
            'time_period': f'Last {days_filter} days',
            'break_performance': break_performance,
            'task_performance': task_performance,
            'break_completion_rate': round((break_performance['completed'] / break_performance['total'] * 100), 2) if break_performance['total'] > 0 else 0,
            'task_completion_rate': round((task_performance['completed'] / task_performance['total'] * 100), 2) if task_performance['total'] > 0 else 0,
            'generated_at': now()
        }
        
        # Detailed data
        detailed_data = {
            'break_logs': list(breaks.values(
                'id', 'user__names', 'break_template__name', 'scheduled_start',
                'scheduled_end', 'actual_start', 'actual_end', 'status',
                'start_punctuality', 'end_punctuality'
            )[:200]),
            'task_assignments': list(tasks.values(
                'id', 'user__names', 'task__name', 'assignment_date',
                'start_time', 'end_time', 'actual_start_time', 'actual_end_time',
                'status', 'priority'
            )[:200])
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'detailed_data': detailed_data,
            'metadata': {
                'report_type': 'admin_performance_report',
                'generated_by': user.names,
                'generated_at': now(),
                'time_period': f'Last {days_filter} days',
                'total_records': {
                    'break_logs': breaks.count(),
                    'task_assignments': tasks.count()
                }
            }
        }
        
        # Print report summary to terminal
        print_report_summary('performance_report', summary, detailed_data)
        print(f"[REPORT SUCCESS] ✅ Performance report generated successfully for {user.names}")
        
        # Validate with serializer
        serializer = PerformanceReportSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ Performance report data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except ValueError as ve:
        error_msg = f"Invalid days parameter: {str(ve)}"
        print(f"\n[PARAMETER ERROR] ❌ Performance Report Error: {error_msg}")
        traceback.print_exc()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'parameter_error'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error generating performance report: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ Performance Report Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==================== SUPERVISOR REPORTS ====================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supervisor_dashboard_overview(request):
    """Supervisor dashboard with team overview"""
    try:
        user = request.user
        
        if not check_role_permission(user, ['supervisor', 'admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access supervisor dashboard")
            return Response({
                'success': False,
                'message': 'Permission denied. Supervisor access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 Supervisor dashboard requested by {user.names} ({user.role})")
        
        # Get supervised employees
        if user.role == 'admin':
            supervised_employees = CustomUser.objects.filter(role='employee')
        else:
            supervised_employees = user.supervised_employees.all()
        
        # Get today's date
        today = now().date()
        
        # Today's statistics
        today_attendance = UserLog.objects.filter(
            user__in=supervised_employees,
            log_type='login',
            actual_time__date=today
        ).count()
        
        today_breaks = BreakLog.objects.filter(
            user__in=supervised_employees,
            scheduled_start__date=today
        ).count()
        
        today_tasks = TaskAssignment.objects.filter(
            user__in=supervised_employees,
            assignment_date=today
        ).count()
        
        # Pending requests
        pending_requests = ShiftChangeRequest.objects.filter(
            user__in=supervised_employees,
            status='pending'
        ).count()
        
        # Summary data
        summary = {
            'success': True,
            'supervisor_name': user.names,
            'total_team_members': supervised_employees.count(),
            'today_attendance': today_attendance,
            'today_breaks': today_breaks,
            'today_tasks': today_tasks,
            'pending_requests': pending_requests,
            'attendance_rate': round((today_attendance / supervised_employees.count() * 100), 2) if supervised_employees.count() > 0 else 0,
            'generated_at': now()
        }
        
        # Detailed data
        detailed_data = {
            'team_members': list(supervised_employees.values('id', 'names', 'emp_number', 'email', 'current_shift__name', 'status')),
            'today_attendance_details': list(UserLog.objects.filter(
                user__in=supervised_employees,
                log_type='login',
                actual_time__date=today
            ).values('id', 'user__names', 'actual_time', 'activity')[:50]),
            'pending_requests_details': list(ShiftChangeRequest.objects.filter(
                user__in=supervised_employees,
                status='pending'
            ).values('id', 'user__names', 'change_type', 'reason', 'created_at')[:50])
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'detailed_data': detailed_data,
            'metadata': {
                'report_type': 'supervisor_dashboard',
                'generated_by': user.names,
                'generated_at': now(),
                'date': today,
                'total_records': {
                    'team_members': supervised_employees.count(),
                    'today_attendance': today_attendance,
                    'pending_requests': pending_requests
                }
            }
        }
        
        # Print report summary to terminal
        print_report_summary('supervisor_dashboard', summary, detailed_data)
        print(f"[REPORT SUCCESS] ✅ Supervisor dashboard generated successfully for {user.names}")
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        error_msg = f"Error generating supervisor dashboard: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ Supervisor Dashboard Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supervisor_team_performance(request):
    """Team performance report for supervisor with detailed data"""
    try:
        user = request.user
        
        if not check_role_permission(user, ['supervisor', 'admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access team performance report")
            return Response({
                'success': False,
                'message': 'Permission denied. Supervisor access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 Team performance report requested by {user.names} ({user.role})")
        
        # Get supervised employees
        if user.role == 'admin':
            supervised_employees = CustomUser.objects.filter(role='employee')
        else:
            supervised_employees = user.supervised_employees.all()
        
        # Get date filter
        days_filter = int(request.GET.get('days', '7'))
        start_date = now().date() - timedelta(days=days_filter)
        
        team_performance = []
        detailed_performance_data = []
        
        for employee in supervised_employees:
            try:
                # Break performance
                employee_breaks = BreakLog.objects.filter(
                    user=employee,
                    scheduled_start__date__gte=start_date
                )
                
                total_breaks = employee_breaks.count()
                completed_breaks = employee_breaks.filter(status='completed').count()
                on_time_starts = employee_breaks.filter(start_punctuality='on_time').count()
                on_time_ends = employee_breaks.filter(end_punctuality='on_time').count()
                
                # Task performance
                employee_tasks = TaskAssignment.objects.filter(
                    user=employee,
                    assignment_date__gte=start_date
                )
                
                total_tasks = employee_tasks.count()
                completed_tasks = employee_tasks.filter(status='completed').count()
                
                # Attendance
                logs = UserLog.objects.filter(
                    user=employee,
                    log_type='login',
                    actual_time__date__gte=start_date
                )
                
                logins = logs.count()
                
                # Summary for this employee
                employee_summary = {
                    'employee_id': employee.id,
                    'employee_name': employee.names,
                    'employee_number': employee.emp_number,
                    'shift': employee.current_shift.name if employee.current_shift else 'Not Assigned',
                    'status': employee.status,
                    'break_performance': {
                        'total': total_breaks,
                        'completed': completed_breaks,
                        'completion_rate': round((completed_breaks / total_breaks * 100), 2) if total_breaks > 0 else 0,
                        'on_time_start_rate': round((on_time_starts / total_breaks * 100), 2) if total_breaks > 0 else 0,
                        'on_time_end_rate': round((on_time_ends / total_breaks * 100), 2) if total_breaks > 0 else 0
                    },
                    'task_performance': {
                        'total': total_tasks,
                        'completed': completed_tasks,
                        'completion_rate': round((completed_tasks / total_tasks * 100), 2) if total_tasks > 0 else 0
                    },
                    'attendance': {
                        'logins': logins,
                        'days_present': logins,
                        'attendance_rate': round((logins / days_filter * 100), 2) if days_filter > 0 else 0
                    }
                }
                
                team_performance.append(employee_summary)
                
                # Detailed data for this employee
                detailed_performance_data.append({
                    'employee': {
                        'id': employee.id,
                        'names': employee.names,
                        'emp_number': employee.emp_number,
                        'email': employee.email,
                        'current_shift': employee.current_shift.name if employee.current_shift else None
                    },
                    'breaks': list(employee_breaks.values(
                        'id', 'break_template__name', 'scheduled_start', 'actual_start',
                        'scheduled_end', 'actual_end', 'status', 'start_punctuality',
                        'end_punctuality'
                    )[:20]),
                    'tasks': list(employee_tasks.values(
                        'id', 'task__name', 'assignment_date', 'start_time', 'end_time',
                        'actual_start_time', 'actual_end_time', 'status', 'priority'
                    )[:20]),
                    'logs': list(logs.values('id', 'actual_time', 'activity', 'status')[:20]),
                    'summary': employee_summary
                })
            except Exception as emp_error:
                print(f"[EMPLOYEE ERROR] ❌ Error processing employee {employee.id}: {str(emp_error)}")
                # Continue with other employees even if one fails
                continue
        
        # Summary data
        summary = {
            'success': True,
            'supervisor_name': user.names,
            'time_period': f'Last {days_filter} days',
            'team_performance': team_performance,
            'total_employees': len(team_performance),
            'generated_at': now()
        }
        
        # Response with both summary and detailed data
        response_data = {
            'success': True,
            'summary': summary,
            'detailed_data': {
                'employees': list(supervised_employees.values('id', 'names', 'emp_number', 'email', 'current_shift__name')),
                'performance_details': detailed_performance_data,
                'break_logs': list(BreakLog.objects.filter(
                    user__in=supervised_employees,
                    scheduled_start__date__gte=start_date
                ).values(
                    'id', 'user__names', 'break_template__name', 'scheduled_start',
                    'actual_start', 'status', 'start_punctuality'
                )[:100]),
                'task_assignments': list(TaskAssignment.objects.filter(
                    user__in=supervised_employees,
                    assignment_date__gte=start_date
                ).values(
                    'id', 'user__names', 'task__name', 'assignment_date',
                    'status', 'priority'
                )[:100]),
                'user_logs': list(UserLog.objects.filter(
                    user__in=supervised_employees,
                    actual_time__date__gte=start_date
                ).values(
                    'id', 'user__names', 'log_type', 'actual_time', 'activity'
                )[:100])
            },
            'metadata': {
                'report_type': 'supervisor_team_performance',
                'generated_by': user.names,
                'generated_at': now(),
                'time_period': f'Last {days_filter} days',
                'total_records': {
                    'employees': supervised_employees.count(),
                    'break_logs': BreakLog.objects.filter(
                        user__in=supervised_employees,
                        scheduled_start__date__gte=start_date
                    ).count(),
                    'task_assignments': TaskAssignment.objects.filter(
                        user__in=supervised_employees,
                        assignment_date__gte=start_date
                    ).count(),
                    'user_logs': UserLog.objects.filter(
                        user__in=supervised_employees,
                        actual_time__date__gte=start_date
                    ).count()
                }
            }
        }
        
        # Print report summary to terminal
        print_report_summary('team_performance', summary, response_data['detailed_data'])
        print(f"[REPORT SUCCESS] ✅ Team performance report generated successfully for {user.names}")
        
        # Validate with serializer
        serializer = TeamPerformanceSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ Team performance data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except ValueError as ve:
        error_msg = f"Invalid days parameter: {str(ve)}"
        print(f"\n[PARAMETER ERROR] ❌ Team Performance Error: {error_msg}")
        traceback.print_exc()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'parameter_error'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error generating team performance: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ Team Performance Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supervisor_attendance_report(request):
    """
    Comprehensive attendance report for supervisors and admins.
    
    Role-based access:
    - Admin: Gets logs for ALL users (admin, supervisors, employees)
    - Supervisor: Gets logs for themselves + their supervised employees
    
    Returns all log types: login, logout, break_start, break_end, shift_start, shift_end, system_event
    """
    try:
        user = request.user
        
        # Permission check
        if not check_role_permission(user, ['supervisor', 'admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access attendance report")
            return Response({
                'success': False,
                'message': 'Permission denied. Supervisor or Admin access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 Attendance report requested by {user.names} ({user.role})")
        
        # Get date filter
        date_filter = request.GET.get('date')
        if date_filter:
            try:
                target_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            except ValueError:
                error_msg = f"Invalid date format. Use YYYY-MM-DD format."
                print(f"[PARAMETER ERROR] ❌ {error_msg}")
                return Response({
                    'success': False,
                    'message': error_msg,
                    'error_type': 'parameter_error'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            target_date = now().date()
        
        print(f"[DATE FILTER] 📅 Generating report for date: {target_date}")
        
        # Determine which users to include based on role
        if user.role == 'admin':
            # Admin sees ALL users (including other admins, supervisors, and employees)
            target_users = CustomUser.objects.all()
            print(f"[ADMIN ACCESS] 👑 Retrieving logs for ALL {target_users.count()} users")
        else:  # supervisor
            # Supervisor sees themselves + their supervised employees
            supervised_employees = user.supervised_employees.all()
            target_users = CustomUser.objects.filter(
                models.Q(id=user.id) | models.Q(id__in=supervised_employees.values_list('id', flat=True))
            ).distinct()
            print(f"[SUPERVISOR ACCESS] 👥 Retrieving logs for supervisor + {supervised_employees.count()} supervised employees")
        
        # ============================================================================
        # PART 1: ATTENDANCE SUMMARY (Login/Logout focused)
        # ============================================================================
        attendance_details = []
        present_count = 0
        
        for employee in target_users:
            try:
                # Get the FIRST login for the day (earliest login time)
                first_login = UserLog.objects.filter(
                    user=employee,
                    log_type='login',
                    actual_time__date=target_date
                ).order_by('actual_time').first()
                
                # Get the LAST logout for the day (latest logout time)
                last_logout = UserLog.objects.filter(
                    user=employee,
                    log_type='logout',
                    actual_time__date=target_date
                ).order_by('-actual_time').first()
                
                # Count total login/logout events
                total_logins = UserLog.objects.filter(
                    user=employee,
                    log_type='login',
                    actual_time__date=target_date
                ).count()
                
                total_logouts = UserLog.objects.filter(
                    user=employee,
                    log_type='logout',
                    actual_time__date=target_date
                ).count()
                
                is_present = first_login is not None
                
                if is_present:
                    present_count += 1
                
                # Calculate hours worked if both login and logout exist
                hours_worked = None
                if first_login and last_logout:
                    time_diff = last_logout.actual_time - first_login.actual_time
                    hours_worked = round(time_diff.total_seconds() / 3600, 2)
                
                # Check if it's their day off
                is_day_off = False
                day_off_name = None
                if employee.day_off and employee.day_off != 'none':
                    current_day = target_date.strftime('%A').lower()
                    if current_day == employee.day_off.lower():
                        is_day_off = True
                        day_off_name = employee.day_off.capitalize()
                
                # Debug logging
                print(f"[USER CHECK] 👤 {employee.names} (ID: {employee.id}, Role: {employee.role})")
                print(f"  - First Login: {first_login.actual_time if first_login else 'None'}")
                print(f"  - Last Logout: {last_logout.actual_time if last_logout else 'None'}")
                print(f"  - Total Logins: {total_logins}, Total Logouts: {total_logouts}")
                print(f"  - Status: {'Present' if is_present else 'Absent'}")
                print(f"  - Day Off: {day_off_name if is_day_off else 'No'}")
                print(f"  - Hours: {hours_worked if hours_worked else 'N/A'}")
                
                attendance_details.append({
                    'user_id': employee.id,
                    'employee_name': employee.names,
                    'employee_number': employee.emp_number,
                    'role': employee.role,
                    'shift': employee.current_shift.name if employee.current_shift else 'Not Assigned',
                    'day_off': day_off_name,
                    'is_day_off': is_day_off,
                    'first_login_time': first_login.actual_time.isoformat() if first_login else None,
                    'last_logout_time': last_logout.actual_time.isoformat() if last_logout else None,
                    'total_logins': total_logins,
                    'total_logouts': total_logouts,
                    'status': 'Present' if is_present else 'Absent',
                    'hours_worked': hours_worked
                })
            except Exception as emp_error:
                print(f"[USER ERROR] ❌ Error processing attendance for user {employee.id}: {str(emp_error)}")
                traceback.print_exc()
                # Add basic info even if there's an error
                attendance_details.append({
                    'user_id': employee.id,
                    'employee_name': employee.names,
                    'employee_number': employee.emp_number,
                    'role': employee.role,
                    'shift': 'Error',
                    'day_off': None,
                    'is_day_off': False,
                    'first_login_time': None,
                    'last_logout_time': None,
                    'total_logins': 0,
                    'total_logouts': 0,
                    'status': 'Error',
                    'hours_worked': None
                })
        
        # ============================================================================
        # PART 2: ALL LOGS BY TYPE (Comprehensive activity log)
        # ============================================================================
        
        # Define all log types to retrieve
        log_types = ['login', 'logout', 'break_start', 'break_end', 'shift_start', 'shift_end', 'system_event']
        
        # Dictionary to store logs by type
        logs_by_type = {}
        total_events = 0
        
        for log_type in log_types:
            logs = UserLog.objects.filter(
                user__in=target_users,
                log_type=log_type,
                actual_time__date=target_date
            ).select_related('user', 'shift', 'break_log').order_by('actual_time').values(
                'id',
                'user_id',
                'user__names',
                'user__emp_number',
                'user__role',
                'log_type',
                'status',
                'activity',
                'system_generated_reason',
                'scheduled_time',
                'actual_time',
                'shift_id',
                'shift__name',
                'break_log_id',
                'break_log__break_template__name',
                'ip_address',
                'device_info',
                'is_auto_generated',
                'notes'
            )
            
            # Convert QuerySet to list and format datetime fields
            logs_list = []
            for log in logs:
                log_copy = dict(log)
                # Format datetime fields
                if log_copy.get('scheduled_time'):
                    log_copy['scheduled_time'] = log_copy['scheduled_time'].isoformat()
                if log_copy.get('actual_time'):
                    log_copy['actual_time'] = log_copy['actual_time'].isoformat()
                
                # Calculate time difference if scheduled_time exists
                if log.get('scheduled_time') and log.get('actual_time'):
                    diff = log['actual_time'] - log['scheduled_time']
                    log_copy['time_difference_minutes'] = round(diff.total_seconds() / 60, 2)
                else:
                    log_copy['time_difference_minutes'] = None
                
                logs_list.append(log_copy)
            
            logs_by_type[log_type] = logs_list
            total_events += len(logs_list)
            print(f"[LOG TYPE] 📝 {log_type}: {len(logs_list)} events")
        
        # ============================================================================
        # PART 3: COMBINED TIMELINE (All events in chronological order)
        # ============================================================================
        
        all_logs_timeline = UserLog.objects.filter(
            user__in=target_users,
            actual_time__date=target_date
        ).select_related('user', 'shift', 'break_log').order_by('actual_time').values(
            'id',
            'user_id',
            'user__names',
            'user__emp_number',
            'user__role',
            'log_type',
            'status',
            'activity',
            'system_generated_reason',
            'scheduled_time',
            'actual_time',
            'shift_id',
            'shift__name',
            'break_log_id',
            'ip_address',
            'device_info',
            'is_auto_generated',
            'notes'
        )
        
        # Convert timeline to list with formatted dates
        timeline_list = []
        for log in all_logs_timeline:
            log_copy = dict(log)
            if log_copy.get('scheduled_time'):
                log_copy['scheduled_time'] = log_copy['scheduled_time'].isoformat()
            if log_copy.get('actual_time'):
                log_copy['actual_time'] = log_copy['actual_time'].isoformat()
            timeline_list.append(log_copy)
        
        # ============================================================================
        # PART 4: BUILD RESPONSE
        # ============================================================================
        
        summary = {
            'success': True,
            'report_generated_by': user.names,
            'report_generator_role': user.role,
            'date': target_date.isoformat(),
            'attendance_summary': {
                'total_users': len(target_users),
                'present': present_count,
                'absent': len(target_users) - present_count,
                'attendance_rate': round((present_count / len(target_users) * 100), 2) if len(target_users) > 0 else 0
            },
            'attendance_details': attendance_details,
            'generated_at': now().isoformat()
        }
        
        detailed_data = {
            'logs_by_type': logs_by_type,
            'timeline': timeline_list,
            'summary_by_log_type': {
                log_type: len(logs_by_type[log_type]) 
                for log_type in log_types
            }
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'detailed_data': detailed_data,
            'metadata': {
                'report_type': 'comprehensive_attendance_report',
                'generated_by': user.names,
                'generator_role': user.role,
                'generated_at': now().isoformat(),
                'date': target_date.isoformat(),
                'scope': 'all_users' if user.role == 'admin' else 'supervisor_and_supervised',
                'total_records': {
                    'users_in_report': len(target_users),
                    'present': present_count,
                    'absent': len(target_users) - present_count,
                    'total_events': total_events,
                    'events_by_type': {
                        log_type: len(logs_by_type[log_type]) 
                        for log_type in log_types
                    }
                }
            }
        }
        
        # ============================================================================
        # PART 5: CONSOLE SUMMARY
        # ============================================================================
        
        print(f"\n{'='*80}")
        print(f"[REPORT SUMMARY] 📊 {user.role.upper()} ATTENDANCE REPORT")
        print(f"{'='*80}")
        print(f"Generated by: {user.names} ({user.role})")
        print(f"Date: {target_date}")
        print(f"Scope: {'All Users' if user.role == 'admin' else 'Supervisor + Supervised Employees'}")
        print(f"\n[ATTENDANCE]")
        print(f"  - Total Users: {len(target_users)}")
        print(f"  - Present: {present_count}")
        print(f"  - Absent: {len(target_users) - present_count}")
        print(f"  - Attendance Rate: {round((present_count / len(target_users) * 100), 2)}%")
        print(f"\n[ACTIVITY BREAKDOWN]")
        for log_type in log_types:
            count = len(logs_by_type[log_type])
            print(f"  - {log_type.replace('_', ' ').title()}: {count}")
        print(f"  - Total Events: {total_events}")
        print(f"{'='*80}\n")
        
        print_report_summary('comprehensive_attendance_report', summary, detailed_data)
        print(f"[REPORT SUCCESS] ✅ Comprehensive attendance report generated successfully\n")
        
        # Validate with serializer (if you have one)
        serializer = AttendanceReportSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ Report data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        error_msg = f"Error generating comprehensive attendance report: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ Attendance Report Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_dashboard_overview(request):
    """Employee dashboard overview"""
    try:
        user = request.user
        
        if not check_role_permission(user, ['employee', 'supervisor', 'admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access employee dashboard")
            return Response({
                'success': False,
                'message': 'Permission denied. Employee access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 Employee dashboard requested by {user.names} ({user.role})")
        
        # Get today's date
        today = now().date()
        
        # Today's statistics for this employee
        today_logins = UserLog.objects.filter(
            user=user,
            log_type='login',
            actual_time__date=today
        ).count()
        
        today_breaks = BreakLog.objects.filter(
            user=user,
            scheduled_start__date=today
        ).count()
        
        completed_breaks = BreakLog.objects.filter(
            user=user,
            scheduled_start__date=today,
            status='completed'
        ).count()
        
        today_tasks = TaskAssignment.objects.filter(
            user=user,
            assignment_date=today
        ).count()
        
        completed_tasks = TaskAssignment.objects.filter(
            user=user,
            assignment_date=today,
            status='completed'
        ).count()
        
        # Notifications
        unread_notifications = Notification.objects.filter(
            user=user,
            is_read=False
        ).count()
        
        # Pending requests
        pending_requests = ShiftChangeRequest.objects.filter(
            user=user,
            status='pending'
        ).count()
        
        # Latest activity
        latest_activity = UserLog.objects.filter(
            user=user
        ).order_by('-actual_time').first()
        
        # Summary data
        summary = {
            'success': True,
            'employee_name': user.names,
            'employee_number': user.emp_number,
            'shift': user.current_shift.name if user.current_shift else 'Not Assigned',
            'day_off': user.day_off,
            'today_summary': {
                'logins': today_logins,
                'breaks_scheduled': today_breaks,
                'breaks_completed': completed_breaks,
                'tasks_scheduled': today_tasks,
                'tasks_completed': completed_tasks,
                'break_completion_rate': round((completed_breaks / today_breaks * 100), 2) if today_breaks > 0 else 0,
                'task_completion_rate': round((completed_tasks / today_tasks * 100), 2) if today_tasks > 0 else 0
            },
            'notifications': {
                'unread': unread_notifications,
                'total': Notification.objects.filter(user=user).count()
            },
            'requests': {
                'pending': pending_requests,
                'total': ShiftChangeRequest.objects.filter(user=user).count()
            },
            'latest_activity': latest_activity.activity if latest_activity else 'No recent activity',
            'generated_at': now()
        }
        
        # Detailed data
        detailed_data = {
            'today_breaks': list(BreakLog.objects.filter(
                user=user,
                scheduled_start__date=today
            ).values('id', 'break_template__name', 'scheduled_start', 'actual_start', 'status')),
            'today_tasks': list(TaskAssignment.objects.filter(
                user=user,
                assignment_date=today
            ).values('id', 'task__name', 'start_time', 'end_time', 'status', 'priority')),
            'notifications': list(Notification.objects.filter(user=user).values(
                'id', 'title', 'message', 'is_read', 'created_at'
            )[:20]),
            'pending_requests': list(ShiftChangeRequest.objects.filter(
                user=user,
                status='pending'
            ).values('id', 'change_type', 'reason', 'created_at')),
            'recent_activities': list(UserLog.objects.filter(user=user).values(
                'id', 'log_type', 'actual_time', 'activity'
            ).order_by('-actual_time')[:20])
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'detailed_data': detailed_data,
            'metadata': {
                'report_type': 'employee_dashboard',
                'generated_by': user.names,
                'generated_at': now(),
                'date': today,
                'total_records': {
                    'today_breaks': today_breaks,
                    'today_tasks': today_tasks,
                    'unread_notifications': unread_notifications,
                    'pending_requests': pending_requests
                }
            }
        }
        
        # Print report summary to terminal
        print_report_summary('employee_dashboard', summary, detailed_data)
        print(f"[REPORT SUCCESS] ✅ Employee dashboard generated successfully for {user.names}")
        
        # Validate with serializer
        serializer = EmployeeDashboardSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ Employee dashboard data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error generating employee dashboard: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ Employee Dashboard Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_break_schedule(request):
    """Employee break schedule report"""
    try:
        user = request.user
        
        if not check_role_permission(user, ['employee', 'supervisor', 'admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access break schedule")
            return Response({
                'success': False,
                'message': 'Permission denied. Employee access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 Break schedule requested by {user.names} ({user.role})")
        
        # Get date filter
        date_filter = request.GET.get('date')
        if date_filter:
            try:
                target_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            except ValueError:
                error_msg = f"Invalid date format. Use YYYY-MM-DD format."
                print(f"[PARAMETER ERROR] ❌ {error_msg}")
                return Response({
                    'success': False,
                    'message': error_msg,
                    'error_type': 'parameter_error'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            target_date = now().date()
        
        # Check if it's day off
        is_day_off = user.day_off == target_date.strftime('%A')
        
        # Get break schedule for the day
        break_schedule = BreakLog.objects.filter(
            user=user,
            scheduled_start__date=target_date
        ).order_by('scheduled_start')
        
        break_schedule_list = []
        for break_log in break_schedule:
            try:
                break_schedule_list.append({
                    'break_name': break_log.break_template.name if break_log.break_template else 'Break',
                    'scheduled_start': break_log.scheduled_start,
                    'scheduled_end': break_log.scheduled_end,
                    'actual_start': break_log.actual_start,
                    'actual_end': break_log.actual_end,
                    'status': break_log.status,
                    'start_punctuality': break_log.start_punctuality,
                    'end_punctuality': break_log.end_punctuality
                })
            except Exception as break_error:
                print(f"[BREAK ERROR] ❌ Error processing break log {break_log.id}: {str(break_error)}")
                # Add basic info even if there's an error
                break_schedule_list.append({
                    'break_name': 'Error',
                    'scheduled_start': None,
                    'scheduled_end': None,
                    'actual_start': None,
                    'actual_end': None,
                    'status': 'Error',
                    'start_punctuality': 'Error',
                    'end_punctuality': 'Error'
                })
        
        # Summary data
        summary = {
            'success': True,
            'employee_name': user.names,
            'date': target_date,
            'is_day_off': is_day_off,
            'day_of_week': target_date.strftime('%A'),
            'break_schedule': break_schedule_list,
            'total_breaks': break_schedule.count(),
            'completed_breaks': break_schedule.filter(status='completed').count(),
            'generated_at': now()
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'metadata': {
                'report_type': 'employee_break_schedule',
                'generated_by': user.names,
                'generated_at': now(),
                'date': target_date
            }
        }
        
        # Print report summary to terminal
        print_report_summary('break_schedule', summary)
        print(f"[REPORT SUCCESS] ✅ Break schedule generated successfully for {user.names}")
        
        # Validate with serializer
        serializer = BreakScheduleSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ Break schedule data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error generating break schedule: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ Break Schedule Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_task_schedule(request):
    """Employee task schedule report"""
    try:
        user = request.user
        
        if not check_role_permission(user, ['employee', 'supervisor', 'admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access task schedule")
            return Response({
                'success': False,
                'message': 'Permission denied. Employee access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 Task schedule requested by {user.names} ({user.role})")
        
        # Get date filter
        date_filter = request.GET.get('date')
        if date_filter:
            try:
                target_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            except ValueError:
                error_msg = f"Invalid date format. Use YYYY-MM-DD format."
                print(f"[PARAMETER ERROR] ❌ {error_msg}")
                return Response({
                    'success': False,
                    'message': error_msg,
                    'error_type': 'parameter_error'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            target_date = now().date()
        
        # Get task schedule for the day
        task_schedule = TaskAssignment.objects.filter(
            user=user,
            assignment_date=target_date
        ).order_by('start_time')
        
        task_schedule_list = []
        for task in task_schedule:
            try:
                task_schedule_list.append({
                    'task_name': task.task.name if task.task else 'Task',
                    'assignment_date': task.assignment_date,
                    'start_time': task.start_time,
                    'end_time': task.end_time,
                    'actual_start_time': task.actual_start_time,
                    'actual_end_time': task.actual_end_time,
                    'status': task.status,
                    'priority': task.priority,
                    'sequence_order': task.sequence_order
                })
            except Exception as task_error:
                print(f"[TASK ERROR] ❌ Error processing task assignment {task.id}: {str(task_error)}")
                # Add basic info even if there's an error
                task_schedule_list.append({
                    'task_name': 'Error',
                    'assignment_date': None,
                    'start_time': None,
                    'end_time': None,
                    'actual_start_time': None,
                    'actual_end_time': None,
                    'status': 'Error',
                    'priority': 'Error',
                    'sequence_order': None
                })
        
        # Summary data
        summary = {
            'success': True,
            'employee_name': user.names,
            'date': target_date,
            'task_schedule': task_schedule_list,
            'total_tasks': task_schedule.count(),
            'completed_tasks': task_schedule.filter(status='completed').count(),
            'active_tasks': task_schedule.filter(status='in_progress').count(),
            'upcoming_tasks': task_schedule.filter(status='pending').count(),
            'generated_at': now()
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'metadata': {
                'report_type': 'employee_task_schedule',
                'generated_by': user.names,
                'generated_at': now(),
                'date': target_date
            }
        }
        
        # Print report summary to terminal
        print_report_summary('task_schedule', summary)
        print(f"[REPORT SUCCESS] ✅ Task schedule generated successfully for {user.names}")
        
        # Validate with serializer
        serializer = TaskScheduleSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ Task schedule data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error generating task schedule: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ Task Schedule Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_activity_log(request):
    """Employee activity log report"""
    try:
        user = request.user
        
        if not check_role_permission(user, ['employee', 'supervisor', 'admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access activity log")
            return Response({
                'success': False,
                'message': 'Permission denied. Employee access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 Activity log requested by {user.names} ({user.role})")
        
        # Get date filter
        days_filter = int(request.GET.get('days', '7'))
        start_date = now() - timedelta(days=days_filter)
        
        # Get activity logs
        activity_logs = UserLog.objects.filter(
            user=user,
            actual_time__gte=start_date
        ).order_by('-actual_time')
        
        # Activity summary
        login_count = activity_logs.filter(log_type='login').count()
        logout_count = activity_logs.filter(log_type='logout').count()
        break_start_count = activity_logs.filter(activity__icontains='break start').count()
        break_end_count = activity_logs.filter(activity__icontains='break end').count()
        
        # Detailed activity list
        activity_details = []
        for log in activity_logs[:50]:  # Limit to 50 most recent
            try:
                activity_details.append({
                    'id': log.id,
                    'log_type': log.log_type,
                    'activity': log.activity,
                    'actual_time': log.actual_time,
                    'status': log.status,
                    'system_generated_reason': log.system_generated_reason
                })
            except Exception as log_error:
                print(f"[LOG ERROR] ❌ Error processing log {log.id}: {str(log_error)}")
                # Add basic info even if there's an error
                activity_details.append({
                    'id': log.id,
                    'log_type': 'Error',
                    'activity': 'Error processing log',
                    'actual_time': None,
                    'status': 'Error',
                    'system_generated_reason': 'Error'
                })
        
        # Summary data
        summary = {
            'success': True,
            'employee_name': user.names,
            'time_period': f'Last {days_filter} days',
            'activity_summary': {
                'total_activities': activity_logs.count(),
                'logins': login_count,
                'logouts': logout_count,
                'break_starts': break_start_count,
                'break_ends': break_end_count,
                'other_activities': activity_logs.count() - (login_count + logout_count + break_start_count + break_end_count)
            },
            'activity_details': activity_details,
            'generated_at': now()
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'metadata': {
                'report_type': 'employee_activity_log',
                'generated_by': user.names,
                'generated_at': now(),
                'time_period': f'Last {days_filter} days',
                'total_records': activity_logs.count()
            }
        }
        
        # Print report summary to terminal
        print_report_summary('activity_log', summary)
        print(f"[REPORT SUCCESS] ✅ Activity log generated successfully for {user.names}")
        
        # Validate with serializer
        serializer = ActivityLogSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ Activity log data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except ValueError as ve:
        error_msg = f"Invalid days parameter: {str(ve)}"
        print(f"\n[PARAMETER ERROR] ❌ Activity Log Error: {error_msg}")
        traceback.print_exc()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'parameter_error'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error generating activity log: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ Activity Log Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==================== EXPORT FUNCTION ====================


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_report(request):
    """Export report in various formats (PDF, Excel, CSV)"""
    try:
        user = request.user
        data = request.data
        
        print(f"[EXPORT START] 🚀 Export requested by {user.names} ({user.role})")
        print(f"[EXPORT DATA] 📦 Request data: {json.dumps(data, indent=2)}")
        
        # Required parameters
        report_type = data.get('report_type')  # 'users', 'tasks', 'attendance', etc.
        export_format = data.get('format', 'pdf')
        filters = data.get('filters', {})
        config = data.get('config', {})
        
        if not report_type:
            error_msg = "Report type is required"
            print(f"[EXPORT ERROR] ❌ {error_msg}")
            return Response({
                'success': False,
                'message': error_msg,
                'error_type': 'parameter_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Map frontend report types to backend functions
        report_type_mapping = {
            'users': ('admin_user_analytics', ['admin']),
            'tasks': ('admin_performance_report', ['admin']),
            'performance': ('admin_performance_report', ['admin']),
            'assignments': ('admin_shift_report', ['admin']),
            'shifts': ('admin_shift_report', ['admin']),
            'attendance': ('supervisor_attendance_report', ['supervisor', 'admin']),
            'dashboard': ('admin_dashboard_overview', ['admin'])
        }
        
        if report_type not in report_type_mapping:
            error_msg = f"Unsupported report type: {report_type}"
            print(f"[EXPORT ERROR] ❌ {error_msg}")
            return Response({
                'success': False,
                'message': error_msg,
                'error_type': 'parameter_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        backend_function_name, required_roles = report_type_mapping[report_type]
        
        # Check permissions
        if not check_role_permission(user, required_roles):
            error_msg = f"Permission denied. {required_roles[0].title()} access required for {report_type} reports."
            print(f"[EXPORT ERROR] ❌ {error_msg}")
            return Response({
                'success': False,
                'message': error_msg,
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[EXPORT PROCESS] ⚙️ Generating {report_type} report in {export_format} format...")
        
        # Generate report data by calling the appropriate function
        report_data = None
        
        try:
            # Import the function
            from . import views
            
            # Get the function
            report_function = getattr(views, backend_function_name)
            
            # Create a mock request with filters
            from django.test import RequestFactory
            factory = RequestFactory()
            
            # Build query string from filters
            query_string = '&'.join([f'{key}={value}' for key, value in filters.items() if value])
            path = f'/dummy/?{query_string}' if query_string else '/dummy/'
            
            mock_request = factory.get(path)
            mock_request.user = user
            mock_request.query_params = filters  # Add query params
            
            # Call the report function
            response = report_function(mock_request)
            
            if response.status_code == 200:
                report_data = response.data
                print(f"[EXPORT PROCESS] ✅ Report data generated successfully")
            else:
                error_msg = f"Failed to generate report data: {response.data.get('message', 'Unknown error')}"
                print(f"[EXPORT ERROR] ❌ {error_msg}")
                return Response({
                    'success': False,
                    'message': error_msg,
                    'error_type': 'data_generation_error'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as data_error:
            error_msg = f"Error generating report data: {str(data_error)}"
            print(f"[EXPORT ERROR] ❌ {error_msg}")
            print(f"[TRACEBACK]:")
            traceback.print_exc()
            return Response({
                'success': False,
                'message': error_msg,
                'error_type': 'data_generation_error',
                'details': str(data_error)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        if not report_data or not report_data.get('success', False):
            error_msg = 'Could not generate report data'
            print(f"[EXPORT ERROR] ❌ {error_msg}")
            return Response({
                'success': False,
                'message': error_msg,
                'error_type': 'data_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"[EXPORT PROCESS] 📊 Report data generated successfully, preparing {export_format} export...")
        
        # Export configuration
        export_config = {
            'title': config.get('title', f'{report_type.replace("_", " ").title()} Report'),
            'organization': config.get('organization', 'Employee Management System'),
            'system': config.get('system', 'Shift & Task Management System'),
            'generated_by': config.get('generated_by', user.names if hasattr(user, 'names') else 'System')
        }
        
        # Export based on format
        try:
            if export_format == 'pdf':
                print("[EXPORT PROCESS] 📄 Generating PDF export...")
                pdf_content = ReportExporter.export_pdf(report_type, report_data, filters, export_config, user)
                response = HttpResponse(content_type='application/pdf')
                filename = f"{report_type}_report_{now().strftime('%Y%m%d_%H%M%S')}.pdf"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response.write(pdf_content)
                print(f"[EXPORT SUCCESS] ✅ PDF export completed: {filename}")
                return response
                
            elif export_format == 'excel':
                print("[EXPORT PROCESS] 📊 Generating Excel export...")
                excel_content = ReportExporter.export_excel(report_type, report_data, filters, export_config, user)
                response = HttpResponse(
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                filename = f"{report_type}_report_{now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response.write(excel_content)
                print(f"[EXPORT SUCCESS] ✅ Excel export completed: {filename}")
                return response
                
            elif export_format == 'csv':
                print("[EXPORT PROCESS] 📝 Generating CSV export...")
                csv_content = ReportExporter.export_csv(report_type, report_data, filters, export_config, user)
                response = HttpResponse(content_type='text/csv')
                filename = f"{report_type}_report_{now().strftime('%Y%m%d_%H%M%S')}.csv"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response.write(csv_content.encode('utf-8'))
                print(f"[EXPORT SUCCESS] ✅ CSV export completed: {filename}")
                return response
            else:
                error_msg = f'Unsupported export format: {export_format}'
                print(f"[EXPORT ERROR] ❌ {error_msg}")
                return Response({
                    'success': False,
                    'message': error_msg,
                    'error_type': 'parameter_error'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as export_error:
            error_msg = f'Error during export: {str(export_error)}'
            print(f"\n[EXPORT ERROR] ❌ Export Error: {error_msg}")
            print(f"[TRACEBACK]:")
            traceback.print_exc()
            print()
            return Response({
                'success': False,
                'message': error_msg,
                'error_type': 'export_error',
                'details': str(export_error)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except json.JSONDecodeError as je:
        error_msg = f'Invalid JSON data: {str(je)}'
        print(f"\n[EXPORT ERROR] ❌ JSON Error: {error_msg}")
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'json_error'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f'Error exporting report: {str(e)}'
        print(f"\n[EXPORT ERROR] ❌ Report Export Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)







# ==================== PERFORMANCE HELPER FUNCTIONS ====================

def get_week_dates(date=None):
    """Get start and end dates of the week for a given date"""
    if not date:
        date = now().date()
    
    # Monday as start of week (0=Monday, 6=Sunday)
    start_date = date - timedelta(days=date.weekday())
    end_date = start_date + timedelta(days=6)
    
    return start_date, end_date


def calculate_performance_rating(score):
    """Calculate performance rating based on score"""
    if score >= 90:
        return 'Excellent', '#10B981'  # Green
    elif score >= 75:
        return 'Good', '#3B82F6'       # Blue
    elif score >= 60:
        return 'Average', '#F59E0B'    # Yellow
    elif score >= 40:
        return 'Needs Improvement', '#EF4444'  # Red
    else:
        return 'Poor', '#DC2626'       # Dark Red


def get_employee_weekly_performance(user, week_start_date=None):
    """Calculate weekly performance for an employee"""
    if not week_start_date:
        week_start_date, week_end_date = get_week_dates()
    else:
        week_end_date = week_start_date + timedelta(days=6)
    
    print(f"[PERFORMANCE] 📊 Calculating weekly performance for {user.names} from {week_start_date} to {week_end_date}")
    
    # Initialize daily performance array
    daily_performance = []
    total_hours_worked = 0
    total_breaks_scheduled = 0
    total_breaks_completed = 0
    total_tasks_scheduled = 0
    total_tasks_completed = 0
    total_punctuality_score = 0
    days_with_punctuality = 0
    
    # Process each day of the week
    for day_offset in range(7):
        current_date = week_start_date + timedelta(days=day_offset)
        
        # Check if it's day off
        is_day_off = False
        if user.day_off and user.day_off != 'none':
            current_day_name = current_date.strftime('%A').lower()
            if current_day_name == user.day_off.lower():
                is_day_off = True
        
        # Get login/logout for the day
        logins = UserLog.objects.filter(
            user=user,
            log_type='login',
            actual_time__date=current_date
        ).order_by('actual_time')
        
        logouts = UserLog.objects.filter(
            user=user,
            log_type='logout',
            actual_time__date=current_date
        ).order_by('-actual_time')
        
        first_login = logins.first()
        last_logout = logouts.first()
        
        # Determine attendance status
        if is_day_off:
            attendance_status = 'Day Off'
        elif first_login:
            attendance_status = 'Present'
        else:
            attendance_status = 'Absent'
        
        # Calculate hours worked
        hours_worked = None
        if first_login and last_logout:
            time_diff = last_logout.actual_time - first_login.actual_time
            hours_worked = round(time_diff.total_seconds() / 3600, 2)
            total_hours_worked += hours_worked
        
        # Break performance for the day
        daily_breaks = BreakLog.objects.filter(
            user=user,
            scheduled_start__date=current_date
        )
        
        breaks_scheduled = daily_breaks.count()
        breaks_completed = daily_breaks.filter(status='completed').count()
        total_breaks_scheduled += breaks_scheduled
        total_breaks_completed += breaks_completed
        
        # Task performance for the day
        daily_tasks = TaskAssignment.objects.filter(
            user=user,
            assignment_date=current_date
        )
        
        tasks_scheduled = daily_tasks.count()
        tasks_completed = daily_tasks.filter(status='completed').count()
        total_tasks_scheduled += tasks_scheduled
        total_tasks_completed += tasks_completed
        
        # Calculate daily punctuality
        daily_punctuality = 0
        punctuality_items = 0
        
        # Login punctuality
        if first_login and first_login.status in ['on_time', 'early']:
            daily_punctuality += 100
            punctuality_items += 1
        elif first_login and first_login.status == 'late':
            daily_punctuality += 60
            punctuality_items += 1
        
        # Break punctuality
        on_time_breaks = daily_breaks.filter(
            Q(start_punctuality='on_time') | Q(start_punctuality='early')
        ).count()
        
        if breaks_scheduled > 0:
            daily_punctuality += (on_time_breaks / breaks_scheduled * 100)
            punctuality_items += 1
        
        # Task punctuality
        on_time_tasks = daily_tasks.filter(
            Q(status='completed') | Q(status='in_progress')
        ).count()
        
        if tasks_scheduled > 0:
            daily_punctuality += (on_time_tasks / tasks_scheduled * 100)
            punctuality_items += 1
        
        # Average daily punctuality
        if punctuality_items > 0:
            daily_punctuality_score = daily_punctuality / punctuality_items
            total_punctuality_score += daily_punctuality_score
            days_with_punctuality += 1
        
        # Add daily performance
        daily_performance.append({
            'date': current_date,
            'day_of_week': current_date.strftime('%A'),
            'is_day_off': is_day_off,
            'attendance_status': attendance_status,
            'breaks': {
                'scheduled': breaks_scheduled,
                'completed': breaks_completed,
                'completion_rate': round((breaks_completed / breaks_scheduled * 100), 2) if breaks_scheduled > 0 else 0
            },
            'tasks': {
                'scheduled': tasks_scheduled,
                'completed': tasks_completed,
                'completion_rate': round((tasks_completed / tasks_scheduled * 100), 2) if tasks_scheduled > 0 else 0
            },
            'hours_worked': hours_worked,
            'punctuality_score': round(daily_punctuality_score, 2) if punctuality_items > 0 else 0
        })
    
    # Calculate summary statistics
    days_present = sum(1 for day in daily_performance if day['attendance_status'] == 'Present')
    days_absent = sum(1 for day in daily_performance if day['attendance_status'] == 'Absent')
    days_day_off = sum(1 for day in daily_performance if day['attendance_status'] == 'Day Off')
    
    # Calculate rates
    attendance_rate = round((days_present / 7 * 100), 2) if 7 > 0 else 0
    break_completion_rate = round((total_breaks_completed / total_breaks_scheduled * 100), 2) if total_breaks_scheduled > 0 else 0
    task_completion_rate = round((total_tasks_completed / total_tasks_scheduled * 100), 2) if total_tasks_scheduled > 0 else 0
    average_hours_per_day = round((total_hours_worked / days_present), 2) if days_present > 0 else 0
    overall_punctuality = round((total_punctuality_score / days_with_punctuality), 2) if days_with_punctuality > 0 else 0
    
    # Calculate overall performance score
    overall_score = (
        attendance_rate * 0.3 + 
        break_completion_rate * 0.2 + 
        task_completion_rate * 0.3 + 
        overall_punctuality * 0.2
    )
    
    performance_rating, rating_color = calculate_performance_rating(overall_score)
    
    return {
        'employee_name': user.names,
        'employee_number': user.emp_number,
        'week_start_date': week_start_date,
        'week_end_date': week_end_date,
        'shift_name': user.current_shift.name if user.current_shift else None,
        'day_off': user.day_off,
        'total_days_in_week': 7,
        'days_present': days_present,
        'days_absent': days_absent,
        'days_day_off': days_day_off,
        'attendance_rate': attendance_rate,
        'average_hours_per_day': average_hours_per_day,
        'total_hours_worked': total_hours_worked,
        'break_completion_rate': break_completion_rate,
        'task_completion_rate': task_completion_rate,
        'overall_punctuality': overall_punctuality,
        'overall_score': round(overall_score, 2),
        'daily_performance': daily_performance,
        'performance_rating': performance_rating,
        'rating_color': rating_color
    }


def get_employee_all_time_performance(user):
    """Calculate all-time performance for an employee"""
    print(f"[PERFORMANCE] 📊 Calculating all-time performance for {user.names}")
    
    # Get employment start date
    employment_start = user.created_at.date()
    total_days_employed = (now().date() - employment_start).days + 1
    
    # Get all logs
    all_logins = UserLog.objects.filter(user=user, log_type='login')
    all_breaks = BreakLog.objects.filter(user=user)
    all_tasks = TaskAssignment.objects.filter(user=user)
    
    # Attendance statistics
    unique_login_dates = all_logins.dates('actual_time', 'day').count()
    
    # Break performance
    total_breaks = all_breaks.count()
    completed_breaks = all_breaks.filter(status='completed').count()
    on_time_breaks = all_breaks.filter(start_punctuality__in=['on_time', 'early']).count()
    
    # Task performance
    total_tasks = all_tasks.count()
    completed_tasks = all_tasks.filter(status='completed').count()
    
    # Login punctuality
    on_time_logins = all_logins.filter(status__in=['on_time', 'early']).count()
    
    # Calculate rates
    attendance_rate = round((unique_login_dates / total_days_employed * 100), 2) if total_days_employed > 0 else 0
    break_completion_rate = round((completed_breaks / total_breaks * 100), 2) if total_breaks > 0 else 0
    break_punctuality = round((on_time_breaks / total_breaks * 100), 2) if total_breaks > 0 else 0
    task_completion_rate = round((completed_tasks / total_tasks * 100), 2) if total_tasks > 0 else 0
    login_punctuality = round((on_time_logins / all_logins.count() * 100), 2) if all_logins.count() > 0 else 0
    
    # Calculate overall performance score
    overall_score = (
        attendance_rate * 0.25 + 
        break_completion_rate * 0.2 + 
        task_completion_rate * 0.25 + 
        ((break_punctuality + login_punctuality) / 2) * 0.3
    )
    
    performance_rating, _ = calculate_performance_rating(overall_score)
    
    # Determine trend (simplified - could be enhanced with historical data)
    trend = 'stable'
    
    return {
        'employee_name': user.names,
        'employee_number': user.emp_number,
        'current_shift': user.current_shift.name if user.current_shift else None,
        'employment_start': employment_start,
        'total_days_employed': total_days_employed,
        'total_work_days': total_days_employed,
        'total_present_days': unique_login_dates,
        'total_absent_days': total_days_employed - unique_login_dates,
        'total_day_off_days': 0,  # Could be enhanced to calculate actual day offs
        'overall_attendance_rate': attendance_rate,
        'total_breaks_assigned': total_breaks,
        'total_breaks_completed': completed_breaks,
        'overall_break_completion_rate': break_completion_rate,
        'break_punctuality_score': break_punctuality,
        'total_tasks_assigned': total_tasks,
        'total_tasks_completed': completed_tasks,
        'overall_task_completion_rate': task_completion_rate,
        'task_punctuality_score': 0,  # Could be enhanced
        'total_logins': all_logins.count(),
        'on_time_logins': on_time_logins,
        'login_punctuality_rate': login_punctuality,
        'overall_performance_score': round(overall_score, 2),
        'performance_rating': performance_rating,
        'performance_trend': trend
    }


def get_supervised_employees_weekly_performance(supervisor_user, week_start_date=None):
    """Get weekly performance for all supervised employees"""
    if not week_start_date:
        week_start_date, week_end_date = get_week_dates()
    
    # Get supervised employees
    if supervisor_user.role == 'admin':
        supervised_employees = CustomUser.objects.filter(role='employee')
    else:
        supervised_employees = supervisor_user.supervised_employees.all()
    
    employees_performance = []
    total_attendance = 0
    total_break_completion = 0
    total_task_completion = 0
    total_punctuality = 0
    
    for employee in supervised_employees:
        try:
            # Get weekly performance for each employee
            weekly_perf = get_employee_weekly_performance(employee, week_start_date)
            
            # Check for issues
            has_issues = False
            issues = []
            
            if weekly_perf['attendance_rate'] < 60:
                has_issues = True
                issues.append('Low attendance rate')
            
            if weekly_perf['break_completion_rate'] < 50:
                has_issues = True
                issues.append('Low break completion')
            
            if weekly_perf['task_completion_rate'] < 50:
                has_issues = True
                issues.append('Low task completion')
            
            # Add to employee performance list
            employees_performance.append({
                'employee_id': employee.id,
                'employee_name': employee.names,
                'employee_number': employee.emp_number,
                'shift_name': employee.current_shift.name if employee.current_shift else None,
                'attendance_rate': weekly_perf['attendance_rate'],
                'break_completion_rate': weekly_perf['break_completion_rate'],
                'task_completion_rate': weekly_perf['task_completion_rate'],
                'average_hours_per_day': weekly_perf['average_hours_per_day'],
                'punctuality_score': weekly_perf['overall_punctuality'],
                'overall_score': weekly_perf['overall_score'],
                'performance_rating': weekly_perf['performance_rating'],
                'status': employee.status,
                'has_issues': has_issues,
                'issues': issues
            })
            
            # Update totals for averages
            total_attendance += weekly_perf['attendance_rate']
            total_break_completion += weekly_perf['break_completion_rate']
            total_task_completion += weekly_perf['task_completion_rate']
            total_punctuality += weekly_perf['overall_punctuality']
            
        except Exception as e:
            print(f"[ERROR] ❌ Error processing employee {employee.id}: {str(e)}")
            continue
    
    # Calculate averages
    employee_count = len(employees_performance)
    if employee_count > 0:
        average_attendance = total_attendance / employee_count
        average_break_completion = total_break_completion / employee_count
        average_task_completion = total_task_completion / employee_count
        average_punctuality = total_punctuality / employee_count
    else:
        average_attendance = average_break_completion = average_task_completion = average_punctuality = 0
    
    # Get performance distribution
    performance_distribution = {
        'Excellent': 0,
        'Good': 0,
        'Average': 0,
        'Needs Improvement': 0,
        'Poor': 0
    }
    
    for emp in employees_performance:
        if emp['performance_rating'] in performance_distribution:
            performance_distribution[emp['performance_rating']] += 1
    
    # Get employees present today
    today = now().date()
    employees_present_today = UserLog.objects.filter(
        user__in=supervised_employees,
        log_type='login',
        actual_time__date=today
    ).values('user').distinct().count()
    
    # Get common issues
    all_issues = []
    for emp in employees_performance:
        all_issues.extend(emp.get('issues', []))
    
    from collections import Counter
    common_issues = [issue for issue, count in Counter(all_issues).most_common(5)]
    
    return {
        'supervisor_name': supervisor_user.names,
        'week_start_date': week_start_date,
        'week_end_date': week_start_date + timedelta(days=6),
        'total_employees': employee_count,
        'active_employees': supervised_employees.filter(status='active').count(),
        'employees_present_today': employees_present_today,
        'average_attendance_rate': round(average_attendance, 2),
        'average_break_completion': round(average_break_completion, 2),
        'average_task_completion': round(average_task_completion, 2),
        'average_punctuality': round(average_punctuality, 2),
        'performance_distribution': performance_distribution,
        'employees_performance': employees_performance,
        'total_issues': len(all_issues),
        'common_issues': common_issues
    }


def get_supervised_employees_all_time_performance(supervisor_user):
    """Get all-time performance for all supervised employees"""
    # Get supervised employees
    if supervisor_user.role == 'admin':
        supervised_employees = CustomUser.objects.filter(role='employee')
    else:
        supervised_employees = supervisor_user.supervised_employees.all()
    
    employees_all_time_performance = []
    total_attendance = 0
    total_break_completion = 0
    total_task_completion = 0
    total_punctuality = 0
    
    for employee in supervised_employees:
        try:
            # Get all-time performance for each employee
            all_time_perf = get_employee_all_time_performance(employee)
            
            # Simplified version for supervisor view
            employees_all_time_performance.append({
                'employee_id': employee.id,
                'employee_name': employee.names,
                'employee_number': employee.emp_number,
                'shift_name': employee.current_shift.name if employee.current_shift else None,
                'attendance_rate': all_time_perf['overall_attendance_rate'],
                'break_completion_rate': all_time_perf['overall_break_completion_rate'],
                'task_completion_rate': all_time_perf['overall_task_completion_rate'],
                'overall_score': all_time_perf['overall_performance_score'],
                'performance_rating': all_time_perf['performance_rating'],
                'status': employee.status
            })
            
            # Update totals for averages
            total_attendance += all_time_perf['overall_attendance_rate']
            total_break_completion += all_time_perf['overall_break_completion_rate']
            total_task_completion += all_time_perf['overall_task_completion_rate']
            
        except Exception as e:
            print(f"[ERROR] ❌ Error processing employee {employee.id} all-time performance: {str(e)}")
            continue
    
    # Calculate overall averages
    employee_count = len(employees_all_time_performance)
    if employee_count > 0:
        overall_attendance = total_attendance / employee_count
        overall_break_completion = total_break_completion / employee_count
        overall_task_completion = total_task_completion / employee_count
    else:
        overall_attendance = overall_break_completion = overall_task_completion = 0
    
    # Get top performers and those needing improvement
    sorted_performance = sorted(
        employees_all_time_performance, 
        key=lambda x: x['overall_score'], 
        reverse=True
    )
    
    top_performers = sorted_performance[:5]  # Top 5
    need_improvement = sorted_performance[-5:] if len(sorted_performance) >= 5 else []  # Bottom 5
    
    # Monthly trend (simplified - last 6 months)
    monthly_trend = []
    for i in range(5, -1, -1):
        month_date = now() - timedelta(days=30*i)
        month_str = month_date.strftime('%b %Y')
        
        # Simplified calculation - in real app, calculate actual monthly performance
        monthly_trend.append({
            'month': month_str,
            'average_score': 75 + (i * 2),  # Sample data
            'attendance_rate': 80 + i,
            'employees_count': employee_count
        })
    
    # Summary statistics
    summary_statistics = {
        'total_employees': employee_count,
        'average_overall_score': round(sum(emp['overall_score'] for emp in employees_all_time_performance) / employee_count, 2) if employee_count > 0 else 0,
        'excellent_performers': sum(1 for emp in employees_all_time_performance if emp['performance_rating'] == 'Excellent'),
        'good_performers': sum(1 for emp in employees_all_time_performance if emp['performance_rating'] == 'Good'),
        'average_performers': sum(1 for emp in employees_all_time_performance if emp['performance_rating'] == 'Average'),
        'needs_improvement': sum(1 for emp in employees_all_time_performance if emp['performance_rating'] == 'Needs Improvement'),
        'poor_performers': sum(1 for emp in employees_all_time_performance if emp['performance_rating'] == 'Poor')
    }
    
    return {
        'supervisor_name': supervisor_user.names,
        'total_employees': employee_count,
        'overall_attendance_rate': round(overall_attendance, 2),
        'overall_break_completion': round(overall_break_completion, 2),
        'overall_task_completion': round(overall_task_completion, 2),
        'overall_punctuality': 75,  # Could be calculated
        'top_performers': top_performers,
        'need_improvement': need_improvement,
        'monthly_trend': monthly_trend,
        'summary_statistics': summary_statistics
    }





# ==================== EMPLOYEE PERFORMANCE ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_weekly_performance(request):
    """Get weekly performance for logged-in employee"""
    try:
        user = request.user
        
        if not check_role_permission(user, ['employee', 'supervisor', 'admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access weekly performance")
            return Response({
                'success': False,
                'message': 'Permission denied. Employee access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 Weekly performance requested by {user.names} ({user.role})")
        
        # Get week parameter
        week_offset = int(request.GET.get('week', '0'))  # 0 = current week, -1 = last week, etc.
        base_date = now().date() + timedelta(weeks=week_offset)
        
        # Calculate weekly performance
        weekly_performance = get_employee_weekly_performance(user, get_week_dates(base_date)[0])
        
        # Add metadata
        summary = {
            'success': True,
            **weekly_performance,
            'generated_at': now()
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'metadata': {
                'report_type': 'employee_weekly_performance',
                'generated_by': user.names,
                'generated_at': now(),
                'week_offset': week_offset,
                'base_date': base_date.isoformat()
            }
        }
        
        # Print summary to terminal
        print(f"\n{'='*80}")
        print(f"[PERFORMANCE REPORT] 🏆 WEEKLY PERFORMANCE FOR {user.names}")
        print(f"{'='*80}")
        print(f"Week: {summary['week_start_date']} to {summary['week_end_date']}")
        print(f"Shift: {summary['shift_name'] or 'Not assigned'}")
        print(f"Day Off: {summary['day_off'] or 'None'}")
        print(f"\n📊 PERFORMANCE SUMMARY:")
        print(f"  Attendance Rate: {summary['attendance_rate']}%")
        print(f"  Break Completion: {summary['break_completion_rate']}%")
        print(f"  Task Completion: {summary['task_completion_rate']}%")
        print(f"  Punctuality: {summary['overall_punctuality']}%")
        print(f"  Total Hours: {summary['total_hours_worked']}")
        print(f"  Avg Hours/Day: {summary['average_hours_per_day']}")
        print(f"\n🏆 RATING: {summary['performance_rating']}")
        print(f"🎯 SCORE: {summary['overall_score']}/100")
        print(f"{'='*80}\n")
        
        # Validate with serializer
        serializer = WeeklyPerformanceSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ Weekly performance data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except ValueError as ve:
        error_msg = f"Invalid parameter value: {str(ve)}"
        print(f"\n[PARAMETER ERROR] ❌ Weekly Performance Error: {error_msg}")
        traceback.print_exc()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'parameter_error'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error generating weekly performance: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ Weekly Performance Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_all_time_performance(request):
    """Get all-time performance for logged-in employee"""
    try:
        user = request.user
        
        if not check_role_permission(user, ['employee', 'supervisor', 'admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access all-time performance")
            return Response({
                'success': False,
                'message': 'Permission denied. Employee access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 All-time performance requested by {user.names} ({user.role})")
        
        # Calculate all-time performance
        all_time_performance = get_employee_all_time_performance(user)
        
        # Add metadata
        summary = {
            'success': True,
            **all_time_performance,
            'generated_at': now()
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'metadata': {
                'report_type': 'employee_all_time_performance',
                'generated_by': user.names,
                'generated_at': now(),
                'employment_duration_days': summary['total_days_employed']
            }
        }
        
        # Print summary to terminal
        print(f"\n{'='*80}")
        print(f"[PERFORMANCE REPORT] 🏆 ALL-TIME PERFORMANCE FOR {user.names}")
        print(f"{'='*80}")
        print(f"Employee: {summary['employee_number']} - {summary['employee_name']}")
        print(f"Shift: {summary['current_shift'] or 'Not assigned'}")
        print(f"Employment Start: {summary['employment_start']}")
        print(f"Days Employed: {summary['total_days_employed']}")
        print(f"\n📊 OVERALL PERFORMANCE:")
        print(f"  Attendance Rate: {summary['overall_attendance_rate']}%")
        print(f"  Break Completion: {summary['overall_break_completion_rate']}%")
        print(f"  Task Completion: {summary['overall_task_completion_rate']}%")
        print(f"  Break Punctuality: {summary['break_punctuality_score']}%")
        print(f"  Login Punctuality: {summary['login_punctuality_rate']}%")
        print(f"\n📈 STATISTICS:")
        print(f"  Total Breaks: {summary['total_breaks_assigned']} ({summary['total_breaks_completed']} completed)")
        print(f"  Total Tasks: {summary['total_tasks_assigned']} ({summary['total_tasks_completed']} completed)")
        print(f"  Total Logins: {summary['total_logins']} ({summary['on_time_logins']} on time)")
        print(f"\n🏆 OVERALL RATING: {summary['performance_rating']}")
        print(f"🎯 SCORE: {summary['overall_performance_score']}/100")
        print(f"📊 TREND: {summary['performance_trend'].title()}")
        print(f"{'='*80}\n")
        
        # Validate with serializer
        serializer = AllTimePerformanceSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ All-time performance data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error generating all-time performance: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ All-time Performance Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== SUPERVISOR/ADMIN PERFORMANCE ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supervisor_weekly_performance(request):
    """Get weekly performance for all supervised employees (for supervisor/admin)"""
    try:
        user = request.user
        
        if not check_role_permission(user, ['supervisor', 'admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access supervisor weekly performance")
            return Response({
                'success': False,
                'message': 'Permission denied. Supervisor or Admin access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 Supervisor weekly performance requested by {user.names} ({user.role})")
        
        # Get week parameter
        week_offset = int(request.GET.get('week', '0'))  # 0 = current week, -1 = last week, etc.
        base_date = now().date() + timedelta(weeks=week_offset)
        
        # Calculate weekly performance for all supervised employees
        weekly_performance = get_supervised_employees_weekly_performance(
            user, 
            get_week_dates(base_date)[0]
        )
        
        # Add metadata
        summary = {
            'success': True,
            **weekly_performance,
            'generated_at': now()
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'detailed_data': {
                'employees_performance': weekly_performance['employees_performance'],
                'performance_distribution': weekly_performance['performance_distribution'],
                'common_issues': weekly_performance['common_issues']
            },
            'metadata': {
                'report_type': 'supervisor_weekly_performance',
                'generated_by': user.names,
                'generated_at': now(),
                'week_offset': week_offset,
                'base_date': base_date.isoformat(),
                'total_employees': summary['total_employees']
            }
        }
        
        # Print summary to terminal
        print(f"\n{'='*80}")
        print(f"[PERFORMANCE REPORT] 👥 TEAM WEEKLY PERFORMANCE FOR {user.names}")
        print(f"{'='*80}")
        print(f"Supervisor: {summary['supervisor_name']}")
        print(f"Week: {summary['week_start_date']} to {summary['week_end_date']}")
        print(f"\n📊 TEAM SUMMARY:")
        print(f"  Total Employees: {summary['total_employees']}")
        print(f"  Active Today: {summary['employees_present_today']}")
        print(f"  Avg Attendance: {summary['average_attendance_rate']}%")
        print(f"  Avg Break Completion: {summary['average_break_completion']}%")
        print(f"  Avg Task Completion: {summary['average_task_completion']}%")
        print(f"  Avg Punctuality: {summary['average_punctuality']}%")
        print(f"  Total Issues: {summary['total_issues']}")
        print(f"\n📈 PERFORMANCE DISTRIBUTION:")
        for rating, count in summary['performance_distribution'].items():
            if count > 0:
                print(f"  {rating}: {count} employees")
        print(f"\n⚠️  COMMON ISSUES:")
        for issue in summary['common_issues']:
            print(f"  • {issue}")
        print(f"\n🏆 TOP PERFORMERS (first 3):")
        for i, emp in enumerate(summary['employees_performance'][:3], 1):
            print(f"  {i}. {emp['employee_name']} - {emp['performance_rating']} ({emp['overall_score']}/100)")
        print(f"{'='*80}\n")
        
        # Validate with serializer
        serializer = SupervisorWeeklyPerformanceSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ Supervisor weekly performance data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except ValueError as ve:
        error_msg = f"Invalid parameter value: {str(ve)}"
        print(f"\n[PARAMETER ERROR] ❌ Supervisor Weekly Performance Error: {error_msg}")
        traceback.print_exc()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'parameter_error'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error generating supervisor weekly performance: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ Supervisor Weekly Performance Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supervisor_all_time_performance(request):
    """Get all-time performance for all supervised employees (for supervisor/admin)"""
    try:
        user = request.user
        
        if not check_role_permission(user, ['supervisor', 'admin']):
            print(f"[PERMISSION DENIED] ❌ User {user.id} ({user.role}) attempted to access supervisor all-time performance")
            return Response({
                'success': False,
                'message': 'Permission denied. Supervisor or Admin access required.',
                'error_type': 'permission_error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        print(f"[REPORT START] 🚀 Supervisor all-time performance requested by {user.names} ({user.role})")
        
        # Calculate all-time performance for all supervised employees
        all_time_performance = get_supervised_employees_all_time_performance(user)
        
        # Add metadata
        summary = {
            'success': True,
            **all_time_performance,
            'generated_at': now()
        }
        
        response_data = {
            'success': True,
            'summary': summary,
            'detailed_data': {
                'top_performers': summary['top_performers'],
                'need_improvement': summary['need_improvement'],
                'monthly_trend': summary['monthly_trend'],
                'summary_statistics': summary['summary_statistics']
            },
            'metadata': {
                'report_type': 'supervisor_all_time_performance',
                'generated_by': user.names,
                'generated_at': now(),
                'total_employees': summary['total_employees']
            }
        }
        
        # Print summary to terminal
        print(f"\n{'='*80}")
        print(f"[PERFORMANCE REPORT] 👥 TEAM ALL-TIME PERFORMANCE FOR {user.names}")
        print(f"{'='*80}")
        print(f"Supervisor: {summary['supervisor_name']}")
        print(f"Total Employees: {summary['total_employees']}")
        print(f"\n📊 TEAM OVERALL PERFORMANCE:")
        print(f"  Overall Attendance: {summary['overall_attendance_rate']}%")
        print(f"  Overall Break Completion: {summary['overall_break_completion']}%")
        print(f"  Overall Task Completion: {summary['overall_task_completion']}%")
        print(f"  Overall Punctuality: {summary['overall_punctuality']}%")
        print(f"\n🏆 TOP PERFORMERS:")
        for i, emp in enumerate(summary['top_performers'][:3], 1):
            print(f"  {i}. {emp['employee_name']} - {emp['performance_rating']} ({emp['overall_score']}/100)")
        print(f"\n📈 PERFORMANCE DISTRIBUTION:")
        for key, value in summary['summary_statistics'].items():
            if 'performers' in key and value > 0:
                label = key.replace('_', ' ').title()
                print(f"  {label}: {value}")
        print(f"\n📊 SUMMARY STATISTICS:")
        print(f"  Average Overall Score: {summary['summary_statistics']['average_overall_score']}/100")
        print(f"{'='*80}\n")
        
        # Validate with serializer
        serializer = SupervisorAllTimePerformanceSummarySerializer(data=summary)
        if serializer.is_valid():
            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"[VALIDATION ERROR] ❌ Supervisor all-time performance data validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Data validation error',
                'errors': serializer.errors,
                'error_type': 'validation_error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_msg = f"Error generating supervisor all-time performance: {str(e)}"
        print(f"\n[REPORT ERROR] ❌ Supervisor All-time Performance Error: {error_msg}")
        print(f"[TRACEBACK]:")
        traceback.print_exc()
        print()
        return Response({
            'success': False,
            'message': error_msg,
            'error_type': 'server_error',
            'details': str(e) if str(e) != error_msg else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)