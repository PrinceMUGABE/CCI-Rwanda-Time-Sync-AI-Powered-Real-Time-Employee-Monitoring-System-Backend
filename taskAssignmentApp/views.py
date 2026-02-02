# taskAssignmentApp/views.py
import traceback
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta

from .models import TaskAssignment, ShiftTaskRotation, TaskOverload
from .serializers import (
    TaskAssignmentSerializer, TaskAssignmentModifySerializer,
    ShiftTaskRotationSerializer, TaskOverloadSerializer
)
from .services import TaskAssignmentService, TaskNotificationService
from userApp.models import CustomUser
from shiftApp.models import Shift
from taskApp.models import Task
from .serializers import CustomUserSerializer


# ==================== EMPLOYEE VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_assignments(request):
    """Get assignments for the authenticated employee"""
    user = request.user
    
    # Query parameters
    date_str = request.query_params.get('date')
    status_filter = request.query_params.get('status')
    
    # Parse date
    if date_str:
        try:
            assignment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }, status=status.HTTP_400_BAD_REQUEST)
    else:
        assignment_date = timezone.now().date()
    
    # Get assignments
    assignments = TaskAssignment.objects.filter(
        user=user,
        assignment_date=assignment_date
    ).order_by('start_time', 'sequence_order')
    
    # Apply status filter
    if status_filter:
        assignments = assignments.filter(status=status_filter)
    
    serializer = TaskAssignmentSerializer(assignments, many=True)
    
    return Response({
        'date': assignment_date,
        'assignments': serializer.data,
        'total_count': assignments.count()
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_assignment(request):
    """Get the current active assignment for the employee"""
    user = request.user
    
    current_assignment = TaskAssignmentService.get_current_assignment(user)
    
    if not current_assignment:
        return Response({
            'message': 'No current assignment',
            'assignment': None
        }, status=status.HTTP_200_OK)
    
    serializer = TaskAssignmentSerializer(current_assignment)
    
    return Response({
        'assignment': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_assignment(request):
    """Get the next scheduled assignment for the employee"""
    user = request.user
    
    next_assignment = TaskAssignmentService.get_next_assignment(user)
    
    if not next_assignment:
        return Response({
            'message': 'No upcoming assignment',
            'assignment': None
        }, status=status.HTTP_200_OK)
    
    serializer = TaskAssignmentSerializer(next_assignment)
    
    return Response({
        'assignment': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_assignment(request, assignment_id):
    """Start a task assignment"""
    user = request.user
    
    try:
        assignment = TaskAssignment.objects.get(id=assignment_id, user=user)
        
        if not assignment.can_start:
            return Response({
                'message': 'Assignment cannot be started at this time',
                'details': {
                    'status': assignment.status,
                    'start_time': assignment.start_time,
                    'end_time': assignment.end_time,
                    'current_time': timezone.now()
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        assignment.start_assignment()
        
        serializer = TaskAssignmentSerializer(assignment)
        
        return Response({
            'message': 'Assignment started successfully',
            'assignment': serializer.data
        }, status=status.HTTP_200_OK)
        
    except TaskAssignment.DoesNotExist:
        return Response({
            'message': 'Assignment not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'message': f'Error starting assignment: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_assignment(request, assignment_id):
    """Complete a task assignment"""
    user = request.user
    
    try:
        assignment = TaskAssignment.objects.get(id=assignment_id, user=user)
        
        if assignment.status != 'active':
            return Response({
                'message': f'Cannot complete assignment with status: {assignment.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        assignment.complete_assignment()
        
        serializer = TaskAssignmentSerializer(assignment)
        
        # Get next assignment
        next_assignment = TaskAssignmentService.get_next_assignment(user)
        next_serializer = TaskAssignmentSerializer(next_assignment) if next_assignment else None
        
        return Response({
            'message': 'Assignment completed successfully',
            'assignment': serializer.data,
            'next_assignment': next_serializer.data if next_serializer else None
        }, status=status.HTTP_200_OK)
        
    except TaskAssignment.DoesNotExist:
        return Response({
            'message': 'Assignment not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'message': f'Error completing assignment: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ADMIN/SUPERVISOR VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_assignments(request):
    """Get all assignments (admin/supervisor only)"""
    user = request.user
    
    if not (user.is_admin or user.is_supervisor):
        return Response({
            'message': 'You do not have permission to view all assignments'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Query parameters
    date_str = request.query_params.get('date')
    user_id = request.query_params.get('user_id')
    shift_id = request.query_params.get('shift_id')
    status_filter = request.query_params.get('status')
    
    # Parse date
    if date_str:
        try:
            assignment_date = datetime.strptime(date_str, '%Y-%m-%d').date()  # FIXED: Removed space
        except ValueError:
            assignment_date = timezone.now().date()
    else:
        assignment_date = timezone.now().date()
    
    # Base queryset
    assignments = TaskAssignment.objects.filter(
        assignment_date=assignment_date
    )
    
    # For supervisors, filter to their supervised employees
    if user.is_supervisor and not user.is_admin:
        supervised_employees = user.supervised_employees.all()
        assignments = assignments.filter(user__in=supervised_employees)
    
    # Apply filters
    if user_id:
        assignments = assignments.filter(user_id=user_id)
    
    if shift_id:
        assignments = assignments.filter(shift_id=shift_id)
    
    if status_filter:
        assignments = assignments.filter(status=status_filter)
    
    assignments = assignments.order_by('user', 'start_time')
    
    serializer = TaskAssignmentSerializer(assignments, many=True)
    
    return Response({
        'date': assignment_date,
        'assignments': serializer.data,
        'total_count': assignments.count()
    }, status=status.HTTP_200_OK)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_daily_assignments(request):
    """Create task assignments for a shift on a specific date (admin only)"""
    user = request.user
    
    if not user.is_admin:
        return Response({
            'message': 'Only admins can create daily assignments'
        }, status=status.HTTP_403_FORBIDDEN)
    
    date_str = request.data.get('date')
    shift_id = request.data.get('shift_id')
    
    if not date_str or not shift_id:
        return Response({
            'message': 'date and shift_id are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        assignment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        shift = Shift.objects.get(id=shift_id)
        
        # Check if assignments already exist
        existing = TaskAssignment.objects.filter(
            assignment_date=assignment_date,
            shift=shift
        ).exists()
        
        if existing:
            return Response({
                'message': 'Assignments already exist for this date and shift',
                'suggestion': 'Delete existing assignments first or modify them individually'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create assignments
        assignments = TaskAssignmentService.create_daily_assignments(
            date=assignment_date,
            shift=shift,
            assigned_by=user
        )
        
        return Response({
            'message': f'Successfully created {len(assignments)} assignments',
            'date': assignment_date,
            'shift': shift.name,
            'count': len(assignments)
        }, status=status.HTTP_201_CREATED)
        
    except ValueError:
        return Response({
            'message': 'Invalid date format. Use YYYY-MM-DD'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Shift.DoesNotExist:
        return Response({
            'message': 'Shift not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'message': f'Error creating assignments: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def modify_assignment(request):
    """Modify a task assignment (admin/supervisor only)"""
    user = request.user
    
    if not (user.is_admin or user.is_supervisor):
        return Response({
            'message': 'You do not have permission to modify assignments'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = TaskAssignmentModifySerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'message': 'Invalid data',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        assignment = TaskAssignmentService.modify_assignment(
            assignment_id=serializer.validated_data['assignment_id'],
            modified_by=user,
            new_task_id=serializer.validated_data.get('new_task_id'),
            new_start_time=serializer.validated_data.get('new_start_time'),
            new_end_time=serializer.validated_data.get('new_end_time'),
            reason=serializer.validated_data.get('reason')
        )
        
        result_serializer = TaskAssignmentSerializer(assignment)
        
        return Response({
            'message': 'Assignment modified successfully',
            'assignment': result_serializer.data
        }, status=status.HTTP_200_OK)
        
    except PermissionError as e:
        return Response({
            'message': str(e)
        }, status=status.HTTP_403_FORBIDDEN)
    except ValueError as e:
        return Response({
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'message': f'Error modifying assignment: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_assignment(request, assignment_id):
    """Delete a task assignment (admin only)"""
    user = request.user
    
    if not user.is_admin:
        return Response({
            'message': 'Only admins can delete assignments'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        assignment = TaskAssignment.objects.get(id=assignment_id)
        
        if assignment.status == 'active':
            return Response({
                'message': 'Cannot delete an active assignment'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        assignment_info = {
            'user': assignment.user.names,
            'task': assignment.task.name,
            'date': assignment.assignment_date
        }
        
        assignment.delete()
        
        return Response({
            'message': 'Assignment deleted successfully',
            'deleted_assignment': assignment_info
        }, status=status.HTTP_200_OK)
        
    except TaskAssignment.DoesNotExist:
        return Response({
            'message': 'Assignment not found'
        }, status=status.HTTP_404_NOT_FOUND)


# ==================== SHIFT TASK ROTATION VIEWS ====================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def manage_shift_rotations(request):
    """Get all or create shift task rotation (admin only)"""
    user = request.user
    
    if not user.is_admin:
        return Response({
            'message': 'Only admins can manage shift rotations'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        rotations = ShiftTaskRotation.objects.all()
        serializer = ShiftTaskRotationSerializer(rotations, many=True)
        
        return Response({
            'rotations': serializer.data,
            'count': rotations.count()
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = ShiftTaskRotationSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(created_by=user)
            
            return Response({
                'message': 'Shift rotation created successfully',
                'rotation': serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'message': 'Invalid data',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def manage_shift_rotation_detail(request, rotation_id):
    """Get, update, or delete a specific shift rotation (admin only)"""

    print (f"[REQUEST] Method: {request.method}, Rotation ID: {rotation_id}, User: {request.user.names if hasattr(request.user, 'names') else request.user.username}")
    print (f"[REQUEST DATA] {request.data}")
    user = request.user
    
    if not user.is_admin:
        return Response({
            'message': 'Only admins can manage shift rotations'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        rotation = ShiftTaskRotation.objects.get(id=rotation_id)
        
        if request.method == 'GET':
            try:
                serializer = ShiftTaskRotationSerializer(rotation)
                return Response({
                    'rotation': serializer.data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                error_message = f'Error retrieving shift rotation: {str(e)}'
                print(f"[GET ERROR] {error_message}")
                print(f"[GET ERROR] Rotation ID: {rotation_id}")
                print(f"[GET ERROR] Exception type: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                
                return Response({
                    'message': error_message,
                    'error_type': type(e).__name__
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        elif request.method in ['PUT', 'PATCH']:
            try:
                serializer = ShiftTaskRotationSerializer(
                    rotation,
                    data=request.data,
                    partial=(request.method == 'PATCH')
                )
                
                if serializer.is_valid():
                    serializer.save()
                    
                    return Response({
                        'message': 'Shift rotation updated successfully',
                        'rotation': serializer.data
                    }, status=status.HTTP_200_OK)
                
                # Log validation errors
                print(f"[{request.method} VALIDATION ERROR] Rotation ID: {rotation_id}")
                print(f"[{request.method} VALIDATION ERROR] Errors: {serializer.errors}")
                print(f"[{request.method} VALIDATION ERROR] Request data: {request.data}")
                
                return Response({
                    'message': 'Invalid data',
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
                
            except Exception as e:
                error_message = f'Error updating shift rotation: {str(e)}'
                print(f"[{request.method} ERROR] {error_message}")
                print(f"[{request.method} ERROR] Rotation ID: {rotation_id}")
                print(f"[{request.method} ERROR] Request data: {request.data}")
                print(f"[{request.method} ERROR] Exception type: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                
                return Response({
                    'message': error_message,
                    'error_type': type(e).__name__
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        elif request.method == 'DELETE':
            try:
                rotation_info = {
                    'id': rotation.id,
                    'shift': rotation.shift.name,
                    'task_count': rotation.task_count
                }
                
                rotation.delete()
                
                print(f"[DELETE SUCCESS] Rotation deleted: {rotation_info}")
                
                return Response({
                    'message': 'Shift rotation deleted successfully',
                    'deleted_rotation': rotation_info
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                error_message = f'Error deleting shift rotation: {str(e)}'
                print(f"[DELETE ERROR] {error_message}")
                print(f"[DELETE ERROR] Rotation ID: {rotation_id}")
                print(f"[DELETE ERROR] Exception type: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                
                return Response({
                    'message': error_message,
                    'error_type': type(e).__name__
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except ShiftTaskRotation.DoesNotExist:
        error_message = f'Shift rotation with ID {rotation_id} not found'
        print(f"[NOT FOUND ERROR] {error_message}")
        print(f"[NOT FOUND ERROR] User: {user.names if hasattr(user, 'names') else user.username}")
        
        return Response({
            'message': 'Shift rotation not found',
            'rotation_id': rotation_id
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        error_message = f'Unexpected error in manage_shift_rotation_detail: {str(e)}'
        print(f"[UNEXPECTED ERROR] {error_message}")
        print(f"[UNEXPECTED ERROR] Method: {request.method}")
        print(f"[UNEXPECTED ERROR] Rotation ID: {rotation_id}")
        print(f"[UNEXPECTED ERROR] User: {user.names if hasattr(user, 'names') else user.username}")
        print(f"[UNEXPECTED ERROR] Exception type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        
        return Response({
            'message': 'An unexpected error occurred',
            'error': str(e),
            'error_type': type(e).__name__
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

# ==================== TASK OVERLOAD VIEWS ====================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def manage_task_overloads(request):
    """Get all or create task overload (admin/supervisor)"""
    
    print(f"[MANAGE TASK OVERLOADS] Method: {request.method}, User: {request.user.names if hasattr(request.user, 'names') else request.user.username}")
    print(f"[MANAGE TASK OVERLOADS] Request data: {request.data}")
    
    user = request.user
    
    # Permission check
    if not (user.is_admin or user.is_supervisor):
        print(f"[MANAGE TASK OVERLOADS] Permission denied for user: {user.names if hasattr(user, 'names') else user.username}, Role: {user.role if hasattr(user, 'role') else 'Unknown'}")
        return Response({
            'message': 'You do not have permission to manage task overloads'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        try:
            print("[GET TASK OVERLOADS] Fetching task overloads...")
            
            # Get all unresolved overloads
            overloads = TaskOverload.objects.filter(is_resolved=False)
            print(f"[GET TASK OVERLOADS] Found {overloads.count()} unresolved overloads")
            
            # For supervisors, might want to filter by their shifts
            if user.is_supervisor and not user.is_admin:
                print(f"[GET TASK OVERLOADS] User is supervisor, applying additional filters if needed")
                # Implement filtering logic if needed
                # Example: overloads = overloads.filter(shift__in=user.managed_shifts.all())
                pass
            
            # Serialize the data
            serializer = TaskOverloadSerializer(overloads, many=True)
            print(f"[GET TASK OVERLOADS] Successfully serialized {len(serializer.data)} overloads")
            
            return Response({
                'overloads': serializer.data,
                'count': overloads.count()
            }, status=status.HTTP_200_OK)
            
        except TaskOverload.DoesNotExist:
            error_message = 'No task overloads found'
            print(f"[GET TASK OVERLOADS ERROR] {error_message}")
            return Response({
                'message': error_message,
                'overloads': [],
                'count': 0
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_message = f'Error fetching task overloads: {str(e)}'
            print(f"[GET TASK OVERLOADS ERROR] {error_message}")
            print(f"[GET TASK OVERLOADS ERROR] Exception type: {type(e).__name__}")
            traceback.print_exc()
            
            return Response({
                'message': 'Failed to fetch task overloads',
                'error': str(e),
                'error_type': type(e).__name__
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'POST':
        try:
            print("[CREATE TASK OVERLOAD] Creating new task overload...")
            print(f"[CREATE TASK OVERLOAD] Request data: {request.data}")
            
            # Normalize the request data to match serializer field names
            normalized_data = dict(request.data)
            
            # Handle task_id -> task conversion
            if 'task_id' in normalized_data and 'task' not in normalized_data:
                normalized_data['task'] = normalized_data.pop('task_id')
                print(f"[CREATE TASK OVERLOAD] Converted task_id to task: {normalized_data['task']}")
            
            # Handle shift_id -> shift conversion
            if 'shift_id' in normalized_data and 'shift' not in normalized_data:
                normalized_data['shift'] = normalized_data.pop('shift_id')
                print(f"[CREATE TASK OVERLOAD] Converted shift_id to shift: {normalized_data['shift']}")
            
            # Handle empty time fields - convert empty strings to None
            if 'time_slot_start' in normalized_data and normalized_data['time_slot_start'] == '':
                normalized_data['time_slot_start'] = None
                print("[CREATE TASK OVERLOAD] Converted empty time_slot_start to None")
            
            if 'time_slot_end' in normalized_data and normalized_data['time_slot_end'] == '':
                normalized_data['time_slot_end'] = None
                print("[CREATE TASK OVERLOAD] Converted empty time_slot_end to None")
            
            print(f"[CREATE TASK OVERLOAD] Normalized data: {normalized_data}")
            
            # Validate and create overload
            serializer = TaskOverloadSerializer(data=normalized_data)
            
            if serializer.is_valid():
                print("[CREATE TASK OVERLOAD] Data is valid, saving...")
                
                # Save with the user who created it
                overload = serializer.save(created_by=user)
                print(f"[CREATE TASK OVERLOAD] Successfully created overload with ID: {overload.id}")
                
                # Serialize the created overload for response
                response_serializer = TaskOverloadSerializer(overload)
                
                return Response({
                    'message': 'Task overload created successfully',
                    'overload': response_serializer.data
                }, status=status.HTTP_201_CREATED)
            
            # Validation failed
            print(f"[CREATE TASK OVERLOAD] Validation failed")
            print(f"[CREATE TASK OVERLOAD] Validation errors: {serializer.errors}")
            
            return Response({
                'message': 'Invalid data',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except KeyError as e:
            error_message = f'Missing required field: {str(e)}'
            print(f"[CREATE TASK OVERLOAD ERROR] {error_message}")
            print(f"[CREATE TASK OVERLOAD ERROR] Request data: {request.data}")
            traceback.print_exc()
            
            return Response({
                'message': 'Missing required field',
                'error': str(e),
                'error_type': 'KeyError'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except ValueError as e:
            error_message = f'Invalid value: {str(e)}'
            print(f"[CREATE TASK OVERLOAD ERROR] {error_message}")
            print(f"[CREATE TASK OVERLOAD ERROR] Request data: {request.data}")
            traceback.print_exc()
            
            return Response({
                'message': 'Invalid data value',
                'error': str(e),
                'error_type': 'ValueError'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Task.DoesNotExist:
            error_message = 'Task not found'
            print(f"[CREATE TASK OVERLOAD ERROR] {error_message}")
            print(f"[CREATE TASK OVERLOAD ERROR] Task ID from request: {request.data.get('task') or request.data.get('task_id')}")
            
            return Response({
                'message': 'Task not found',
                'error': 'The specified task does not exist',
                'error_type': 'TaskNotFound'
            }, status=status.HTTP_404_NOT_FOUND)
            
        except Shift.DoesNotExist:
            error_message = 'Shift not found'
            print(f"[CREATE TASK OVERLOAD ERROR] {error_message}")
            print(f"[CREATE TASK OVERLOAD ERROR] Shift ID from request: {request.data.get('shift') or request.data.get('shift_id')}")
            
            return Response({
                'message': 'Shift not found',
                'error': 'The specified shift does not exist',
                'error_type': 'ShiftNotFound'
            }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            error_message = f'Unexpected error creating task overload: {str(e)}'
            print(f"[CREATE TASK OVERLOAD ERROR] {error_message}")
            print(f"[CREATE TASK OVERLOAD ERROR] Exception type: {type(e).__name__}")
            print(f"[CREATE TASK OVERLOAD ERROR] Request data: {request.data}")
            traceback.print_exc()
            
            return Response({
                'message': 'Failed to create task overload',
                'error': str(e),
                'error_type': type(e).__name__
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resolve_task_overload(request, overload_id):
    """Mark task overload as resolved (admin/supervisor)"""
    
    print(f"[RESOLVE TASK OVERLOAD] Overload ID: {overload_id}, User: {request.user.names if hasattr(request.user, 'names') else request.user.username}")
    
    user = request.user
    
    # Permission check
    if not (user.is_admin or user.is_supervisor):
        print(f"[RESOLVE TASK OVERLOAD] Permission denied for user: {user.names if hasattr(user, 'names') else user.username}, Role: {user.role if hasattr(user, 'role') else 'Unknown'}")
        return Response({
            'message': 'You do not have permission to resolve task overloads'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        print(f"[RESOLVE TASK OVERLOAD] Fetching overload with ID: {overload_id}")
        
        # Get the overload
        overload = TaskOverload.objects.get(id=overload_id)
        print(f"[RESOLVE TASK OVERLOAD] Found overload: Task={overload.task.name}, Shift={overload.shift.name}")
        
        # Check if already resolved
        if overload.is_resolved:
            print(f"[RESOLVE TASK OVERLOAD] Warning: Overload {overload_id} is already resolved")
            return Response({
                'message': 'Task overload is already resolved',
                'overload': TaskOverloadSerializer(overload).data
            }, status=status.HTTP_200_OK)
        
        # Mark as resolved
        overload.is_resolved = True
        overload.resolved_at = timezone.now()
        overload.save()
        print(f"[RESOLVE TASK OVERLOAD] Successfully resolved overload {overload_id} at {overload.resolved_at}")
        
        # Serialize the response
        serializer = TaskOverloadSerializer(overload)
        
        return Response({
            'message': 'Task overload resolved successfully',
            'overload': serializer.data
        }, status=status.HTTP_200_OK)
        
    except TaskOverload.DoesNotExist:
        error_message = f'Task overload with ID {overload_id} not found'
        print(f"[RESOLVE TASK OVERLOAD ERROR] {error_message}")
        
        return Response({
            'message': 'Task overload not found',
            'error': error_message,
            'overload_id': overload_id
        }, status=status.HTTP_404_NOT_FOUND)
        
    except ValueError as e:
        error_message = f'Invalid overload ID: {str(e)}'
        print(f"[RESOLVE TASK OVERLOAD ERROR] {error_message}")
        print(f"[RESOLVE TASK OVERLOAD ERROR] Overload ID: {overload_id}")
        traceback.print_exc()
        
        return Response({
            'message': 'Invalid overload ID',
            'error': str(e),
            'error_type': 'ValueError'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        error_message = f'Unexpected error resolving task overload: {str(e)}'
        print(f"[RESOLVE TASK OVERLOAD ERROR] {error_message}")
        print(f"[RESOLVE TASK OVERLOAD ERROR] Exception type: {type(e).__name__}")
        print(f"[RESOLVE TASK OVERLOAD ERROR] Overload ID: {overload_id}")
        traceback.print_exc()
        
        return Response({
            'message': 'Failed to resolve task overload',
            'error': str(e),
            'error_type': type(e).__name__,
            'overload_id': overload_id
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# BONUS: Add a view to get resolved overloads as well
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_task_overloads(request):
    """Get all task overloads (both resolved and unresolved) with filtering options"""
    
    print(f"[GET ALL TASK OVERLOADS] User: {request.user.names if hasattr(request.user, 'names') else request.user.username}")
    
    user = request.user
    
    # Permission check
    if not (user.is_admin or user.is_supervisor):
        print(f"[GET ALL TASK OVERLOADS] Permission denied for user: {user.names if hasattr(user, 'names') else user.username}")
        return Response({
            'message': 'You do not have permission to view task overloads'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Get query parameters for filtering
        is_resolved = request.query_params.get('is_resolved', None)
        task_id = request.query_params.get('task_id', None)
        shift_id = request.query_params.get('shift_id', None)
        date = request.query_params.get('date', None)
        
        print(f"[GET ALL TASK OVERLOADS] Filters - is_resolved: {is_resolved}, task_id: {task_id}, shift_id: {shift_id}, date: {date}")
        
        # Start with all overloads
        overloads = TaskOverload.objects.all()
        
        # Apply filters
        if is_resolved is not None:
            is_resolved_bool = is_resolved.lower() in ['true', '1', 'yes']
            overloads = overloads.filter(is_resolved=is_resolved_bool)
            print(f"[GET ALL TASK OVERLOADS] Filtered by is_resolved={is_resolved_bool}")
        
        if task_id:
            overloads = overloads.filter(task_id=task_id)
            print(f"[GET ALL TASK OVERLOADS] Filtered by task_id={task_id}")
        
        if shift_id:
            overloads = overloads.filter(shift_id=shift_id)
            print(f"[GET ALL TASK OVERLOADS] Filtered by shift_id={shift_id}")
        
        if date:
            overloads = overloads.filter(overload_date=date)
            print(f"[GET ALL TASK OVERLOADS] Filtered by date={date}")
        
        # Order by most recent first
        overloads = overloads.order_by('-created_at')
        
        print(f"[GET ALL TASK OVERLOADS] Found {overloads.count()} overloads")
        
        # Serialize
        serializer = TaskOverloadSerializer(overloads, many=True)
        
        return Response({
            'overloads': serializer.data,
            'count': overloads.count(),
            'filters': {
                'is_resolved': is_resolved,
                'task_id': task_id,
                'shift_id': shift_id,
                'date': date
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        error_message = f'Error fetching task overloads: {str(e)}'
        print(f"[GET ALL TASK OVERLOADS ERROR] {error_message}")
        print(f"[GET ALL TASK OVERLOADS ERROR] Exception type: {type(e).__name__}")
        traceback.print_exc()
        
        return Response({
            'message': 'Failed to fetch task overloads',
            'error': str(e),
            'error_type': type(e).__name__
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# BONUS: Add bulk resolve functionality
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_resolve_task_overloads(request):
    """Bulk resolve multiple task overloads at once"""
    
    print(f"[BULK RESOLVE OVERLOADS] User: {request.user.names if hasattr(request.user, 'names') else request.user.username}")
    print(f"[BULK RESOLVE OVERLOADS] Request data: {request.data}")
    
    user = request.user
    
    # Permission check
    if not (user.is_admin or user.is_supervisor):
        print(f"[BULK RESOLVE OVERLOADS] Permission denied for user: {user.names if hasattr(user, 'names') else user.username}")
        return Response({
            'message': 'You do not have permission to resolve task overloads'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Get overload IDs from request
        overload_ids = request.data.get('overload_ids', [])
        
        if not overload_ids:
            print("[BULK RESOLVE OVERLOADS] No overload IDs provided")
            return Response({
                'message': 'No overload IDs provided',
                'error': 'overload_ids field is required and must be a non-empty array'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"[BULK RESOLVE OVERLOADS] Resolving {len(overload_ids)} overloads: {overload_ids}")
        
        # Get all overloads
        overloads = TaskOverload.objects.filter(id__in=overload_ids)
        
        if overloads.count() == 0:
            print(f"[BULK RESOLVE OVERLOADS] No overloads found for IDs: {overload_ids}")
            return Response({
                'message': 'No overloads found with the provided IDs',
                'provided_ids': overload_ids
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Track results
        resolved_count = 0
        already_resolved_count = 0
        failed_ids = []
        
        # Resolve each overload
        for overload in overloads:
            try:
                if not overload.is_resolved:
                    overload.is_resolved = True
                    overload.resolved_at = timezone.now()
                    overload.save()
                    resolved_count += 1
                    print(f"[BULK RESOLVE OVERLOADS] Resolved overload {overload.id}")
                else:
                    already_resolved_count += 1
                    print(f"[BULK RESOLVE OVERLOADS] Overload {overload.id} was already resolved")
            except Exception as e:
                failed_ids.append(overload.id)
                print(f"[BULK RESOLVE OVERLOADS] Failed to resolve overload {overload.id}: {str(e)}")
        
        # Prepare response
        response_data = {
            'message': f'Successfully resolved {resolved_count} overload(s)',
            'resolved_count': resolved_count,
            'already_resolved_count': already_resolved_count,
            'total_processed': overloads.count(),
            'requested_count': len(overload_ids)
        }
        
        if failed_ids:
            response_data['failed_ids'] = failed_ids
            response_data['failed_count'] = len(failed_ids)
        
        print(f"[BULK RESOLVE OVERLOADS] Results: {response_data}")
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        error_message = f'Unexpected error during bulk resolve: {str(e)}'
        print(f"[BULK RESOLVE OVERLOADS ERROR] {error_message}")
        print(f"[BULK RESOLVE OVERLOADS ERROR] Exception type: {type(e).__name__}")
        traceback.print_exc()
        
        return Response({
            'message': 'Failed to bulk resolve task overloads',
            'error': str(e),
            'error_type': type(e).__name__
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



    
# userApp/views.py
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_supervised_employees(request):
    """Get employees supervised by the current supervisor"""
    user = request.user
    
    if not user.is_supervisor:
        return Response({
            'message': 'Only supervisors can view supervised employees'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get employees supervised by this supervisor
    supervised_employees = user.supervised_employees.all()
    
    serializer = CustomUserSerializer(supervised_employees, many=True)
    
    return Response({
        'users': serializer.data,
        'count': supervised_employees.count()
    }, status=status.HTTP_200_OK)