# requestApp/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
import traceback

from .models import ShiftChangeRequest
from .serializers import (
    ShiftChangeRequestCreateSerializer,
    ShiftChangeRequestDetailSerializer,
    ShiftChangeRequestListSerializer,
    ShiftChangeRequestUpdateSerializer
)
from userApp.models import CustomUser

import json
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import traceback

from .models import ShiftChangeRequest
from .serializers import (
    ShiftChangeRequestListSerializer,
    ShiftChangeRequestDetailSerializer
)
from userApp.models import CustomUser


def print_data_to_terminal(data, title="DATA"):
    """Helper function to print data to terminal in a readable format"""
    print("\n" + "="*80)
    print(f"{title}")
    print("="*80)
    
    if isinstance(data, dict):
        # Remove profile_picture from nested data
        cleaned_data = remove_profile_pictures(data)
        print(json.dumps(cleaned_data, indent=2, default=str))
    elif isinstance(data, list):
        cleaned_data = [remove_profile_pictures(item) for item in data]
        print(json.dumps(cleaned_data, indent=2, default=str))
    else:
        print(data)
    
    print("="*80 + "\n")


def remove_profile_pictures(data):
    """Recursively remove profile_picture fields from data"""
    if isinstance(data, dict):
        return {
            key: remove_profile_pictures(value) 
            for key, value in data.items() 
            if key != 'profile_picture'
        }
    elif isinstance(data, list):
        return [remove_profile_pictures(item) for item in data]
    else:
        return data


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_requests(request):
    """
    Get all shift change requests (with filtering)
    
    Query parameters:
    - status: Filter by status (pending, accepted, cancelled)
    - change_type: Filter by change type
    """
    try:
        user = request.user
        
        # Base queryset
        if user.is_admin:
            # Admins see all requests
            queryset = ShiftChangeRequest.objects.all()
        elif user.role=='supervisor':
            # Supervisors see their own requests and their supervised employees' requests
            supervised_users = user.supervised_employees.all()
            queryset = ShiftChangeRequest.objects.filter(
                Q(user=user) | Q(user__in=supervised_users)
            )
        else:
            # Regular employees see only their own requests
            queryset = ShiftChangeRequest.objects.filter(user=user)
        
        # Apply filters
        request_status = request.GET.get('status', None)
        if request_status:
            queryset = queryset.filter(status=request_status)
        
        change_type = request.GET.get('change_type', None)
        if change_type:
            queryset = queryset.filter(change_type=change_type)
        
        # Serialize
        serializer = ShiftChangeRequestListSerializer(queryset, many=True)
        
        response_data = {
            'count': queryset.count(),
            'requests': serializer.data
        }
        
        # Print to terminal
        print_data_to_terminal(
            response_data, 
            f"GET ALL REQUESTS - User: {user.names} ({user.emp_number})"
        )
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in get_all_requests: {error_message}")
        print(traceback.format_exc())
        return Response(
            {
                'error': 'An error occurred while retrieving requests.',
                'detail': error_message
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_request_by_id(request, request_id):
    """
    Get a specific shift change request by ID
    """
    try:
        user = request.user
        
        # Get the request
        try:
            shift_request = ShiftChangeRequest.objects.get(id=request_id)
        except ShiftChangeRequest.DoesNotExist:
            return Response(
                {
                    'error': 'Request not found.',
                    'detail': f'No shift change request found with ID {request_id}.'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if not (user.is_admin or 
                shift_request.user == user or 
                (user.is_supervisor and user.can_supervise(shift_request.user))):
            return Response(
                {
                    'error': 'Permission denied.',
                    'detail': 'You do not have permission to view this request.'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Serialize and return
        serializer = ShiftChangeRequestDetailSerializer(shift_request)
        
        response_data = {
            'request': serializer.data
        }
        
        # Print to terminal
        print_data_to_terminal(
            response_data,
            f"GET REQUEST BY ID ({request_id}) - User: {user.names} ({user.emp_number})"
        )
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in get_request_by_id: {error_message}")
        print(traceback.format_exc())
        return Response(
            {
                'error': 'An error occurred while retrieving the request.',
                'detail': error_message
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_requests_for_employee(request, emp_number):
    """
    Get all shift change requests for a specific employee
    """
    try:
        current_user = request.user
        
        # Get the employee
        try:
            employee = CustomUser.objects.get(emp_number=emp_number)
        except CustomUser.DoesNotExist:
            return Response(
                {
                    'error': 'Employee not found.',
                    'detail': f'No employee found with employee number {emp_number}.'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if not (current_user.is_admin or 
                current_user == employee or 
                (current_user.is_supervisor and current_user.can_supervise(employee))):
            return Response(
                {
                    'error': 'Permission denied.',
                    'detail': 'You do not have permission to view this employee\'s requests.'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get requests
        queryset = ShiftChangeRequest.objects.filter(user=employee)
        
        # Apply filters
        request_status = request.GET.get('status', None)
        if request_status:
            queryset = queryset.filter(status=request_status)
        
        serializer = ShiftChangeRequestListSerializer(queryset, many=True)
        
        response_data = {
            'employee': {
                'emp_number': employee.emp_number,
                'names': employee.names,
                'email': employee.email
            },
            'count': queryset.count(),
            'requests': serializer.data
        }
        
        # Print to terminal
        print_data_to_terminal(
            response_data,
            f"GET REQUESTS FOR EMPLOYEE ({emp_number}) - Requested by: {current_user.names}"
        )
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in get_requests_for_employee: {error_message}")
        print(traceback.format_exc())
        return Response(
            {
                'error': 'An error occurred while retrieving employee requests.',
                'detail': error_message
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_requests_for_supervisor(request, emp_number):
    """
    Get all requests from employees supervised by a specific supervisor
    """
    try:
        current_user = request.user
        
        # Get the supervisor
        try:
            supervisor = CustomUser.objects.get(emp_number=emp_number)
        except CustomUser.DoesNotExist:
            return Response(
                {
                    'error': 'Supervisor not found.',
                    'detail': f'No supervisor found with employee number {emp_number}.'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if the user is actually a supervisor
        if not supervisor.is_supervisor and not supervisor.is_admin:
            return Response(
                {
                    'error': 'Invalid supervisor.',
                    'detail': 'The specified employee is not a supervisor or admin.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check permissions
        if not (current_user.is_admin or current_user == supervisor):
            return Response(
                {
                    'error': 'Permission denied.',
                    'detail': 'You do not have permission to view this supervisor\'s requests.'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get supervised employees
        supervised_employees = supervisor.supervised_employees.all()
        
        # Get requests from supervised employees
        queryset = ShiftChangeRequest.objects.filter(user__in=supervised_employees)
        
        # Apply filters
        request_status = request.GET.get('status', None)
        if request_status:
            queryset = queryset.filter(status=request_status)
        
        serializer = ShiftChangeRequestListSerializer(queryset, many=True)
        
        response_data = {
            'supervisor': {
                'emp_number': supervisor.emp_number,
                'names': supervisor.names,
                'email': supervisor.email
            },
            'supervised_employees_count': supervised_employees.count(),
            'requests_count': queryset.count(),
            'requests': serializer.data
        }
        
        # Print to terminal
        print_data_to_terminal(
            response_data,
            f"GET REQUESTS FOR SUPERVISOR ({emp_number}) - Requested by: {current_user.names}"
        )
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in get_requests_for_supervisor: {error_message}")
        print(traceback.format_exc())
        return Response(
            {
                'error': 'An error occurred while retrieving supervisor requests.',
                'detail': error_message
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_requests(request):
    """
    Get all requests for the currently logged-in user
    """
    try:
        user = request.user
        
        # Get user's requests
        queryset = ShiftChangeRequest.objects.filter(user=user)
        
        # Apply filters
        request_status = request.GET.get('status', None)
        if request_status:
            queryset = queryset.filter(status=request_status)
        
        serializer = ShiftChangeRequestListSerializer(queryset, many=True)
        
        response_data = {
            'count': queryset.count(),
            'requests': serializer.data
        }
        
        # Print to terminal
        print_data_to_terminal(
            response_data,
            f"GET MY REQUESTS - User: {user.names} ({user.emp_number})"
        )
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in get_my_requests: {error_message}")
        print(traceback.format_exc())
        return Response(
            {
                'error': 'An error occurred while retrieving your requests.',
                'detail': error_message
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_supervised_requests(request):
    """
    Get all requests from employees supervised by the logged-in supervisor
    """
    try:
        user = request.user
        
        # Check if user is a supervisor or admin
        if not (user.is_supervisor or user.is_admin):
            return Response(
                {
                    'error': 'Permission denied.',
                    'detail': 'Only supervisors and admins can access supervised employee requests.'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get supervised employees
        supervised_employees = user.supervised_employees.all()
        
        # Get requests from supervised employees
        queryset = ShiftChangeRequest.objects.filter(user__in=supervised_employees)
        
        # Apply filters
        request_status = request.GET.get('status', None)
        if request_status:
            queryset = queryset.filter(status=request_status)
        
        serializer = ShiftChangeRequestListSerializer(queryset, many=True)
        
        response_data = {
            'supervised_employees_count': supervised_employees.count(),
            'requests_count': queryset.count(),
            'requests': serializer.data
        }
        
        # Print to terminal
        print_data_to_terminal(
            response_data,
            f"GET SUPERVISED REQUESTS - Supervisor: {user.names} ({user.emp_number})"
        )
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in get_supervised_requests: {error_message}")
        print(traceback.format_exc())
        return Response(
            {
                'error': 'An error occurred while retrieving supervised requests.',
                'detail': error_message
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_shift_change_request(request):
    """
    Create a new shift change request
    
    Required fields:
    - change_type: 'shift_only', 'day_off_only', or 'both'
    - reason: Text explaining the reason for change
    - start_date: Date when change should take effect
    - new_shift: ID of new shift (required for 'shift_only' and 'both')
    - new_day_off: New day off (required for 'day_off_only' and 'both')
    """
    print("create_shift_change_request called")
    print("Request data:", request.data)
    try:
        user = request.user
        
        # Check if user can make requests (not admin)
        if user.role == 'admin':
            return Response(
                {
                    'error': 'Admins cannot create shift change requests.',
                    'detail': 'Admins can directly modify their shift and day off settings.'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create serializer with user context
        serializer = ShiftChangeRequestCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            # Save the request
            shift_request = serializer.save()
            
            # Return detailed response
            detail_serializer = ShiftChangeRequestDetailSerializer(shift_request)
            
            return Response(
                {
                    'message': 'Shift change request created successfully.',
                    'request': detail_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        
        print(f"Validation errors: {serializer.errors}")
        return Response(
            {
                'error': 'Invalid request data.',
                'details': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    except ValidationError as ve:
        error_message = str(ve)
        print(f"ValidationError in create_shift_change_request: {error_message}")
        print(traceback.format_exc())
        return Response(
            {
                'error': 'Validation error occurred.',
                'detail': error_message
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in create_shift_change_request: {error_message}")
        print(traceback.format_exc())
        return Response(
            {
                'error': 'An unexpected error occurred while creating the request.',
                'detail': error_message
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_request(request, request_id):
    """
    Accept a shift change request and apply the changes to the employee
    
    Only supervisors (who supervise the employee) and admins can accept requests
    """
    try:
        user = request.user
        
        # Get the request
        try:
            shift_request = ShiftChangeRequest.objects.get(id=request_id)
        except ShiftChangeRequest.DoesNotExist:
            return Response(
                {
                    'error': 'Request not found.',
                    'detail': f'No shift change request found with ID {request_id}.'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if request is pending
        if shift_request.status != 'pending':
            return Response(
                {
                    'error': 'Cannot accept request.',
                    'detail': f'Only pending requests can be accepted. Current status: {shift_request.status}.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check permissions
        if not (user.is_admin or 
                (user.is_supervisor and user.can_supervise(shift_request.user))):
            return Response(
                {
                    'error': 'Permission denied.',
                    'detail': 'You do not have permission to accept this request.'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Approve the request (this also updates the user's shift/day_off)
        try:
            shift_request.approve(user)
        except ValidationError as ve:
            print(f"ValidationError in accept_request: {str(ve)}")
            return Response(
                {
                    'error': 'Approval failed.',
                    'detail': str(ve)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Return updated request
        serializer = ShiftChangeRequestDetailSerializer(shift_request)
        
        return Response(
            {
                'message': 'Request accepted successfully. Employee shift/day off has been updated.',
                'request': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in accept_request: {error_message}")
        print(traceback.format_exc())
        return Response(
            {
                'error': 'An error occurred while accepting the request.',
                'detail': error_message
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_request(request, request_id):
    """
    Cancel a shift change request
    
    Request body (optional):
    - cancellation_reason: Reason for cancellation
    
    Users can cancel their own requests
    Supervisors and admins can cancel requests from their supervised employees
    """
    try:
        user = request.user
        
        # Get the request
        try:
            shift_request = ShiftChangeRequest.objects.get(id=request_id)
        except ShiftChangeRequest.DoesNotExist:
            return Response(
                {
                    'error': 'Request not found.',
                    'detail': f'No shift change request found with ID {request_id}.'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if request is pending
        if shift_request.status != 'pending':
            return Response(
                {
                    'error': 'Cannot cancel request.',
                    'detail': f'Only pending requests can be cancelled. Current status: {shift_request.status}.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check permissions
        if not (user == shift_request.user or 
                user.is_admin or 
                (user.is_supervisor and user.can_supervise(shift_request.user))):
            return Response(
                {
                    'error': 'Permission denied.',
                    'detail': 'You do not have permission to cancel this request.'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get cancellation reason
        cancellation_reason = request.data.get('cancellation_reason', None)
        
        # Cancel the request
        try:
            shift_request.cancel(user, cancellation_reason)
        except ValidationError as ve:
            print(f"ValidationError in cancel_request: {str(ve)}")
            return Response(
                {
                    'error': 'Cancellation failed.',
                    'detail': str(ve)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Return updated request
        serializer = ShiftChangeRequestDetailSerializer(shift_request)
        
        return Response(
            {
                'message': 'Request cancelled successfully.',
                'request': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in cancel_request: {error_message}")
        print(traceback.format_exc())
        return Response(
            {
                'error': 'An error occurred while cancelling the request.',
                'detail': error_message
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_request(request, request_id):
    """
    Delete a shift change request
    
    Only admins and the request owner can delete requests
    Can only delete pending or cancelled requests
    """
    try:
        user = request.user
        
        # Get the request
        try:
            shift_request = ShiftChangeRequest.objects.get(id=request_id)
        except ShiftChangeRequest.DoesNotExist:
            return Response(
                {
                    'error': 'Request not found.',
                    'detail': f'No shift change request found with ID {request_id}.'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if not (user.is_admin or user == shift_request.user):
            return Response(
                {
                    'error': 'Permission denied.',
                    'detail': 'Only admins and request owners can delete requests.'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Cannot delete accepted requests
        if shift_request.status == 'accepted':
            return Response(
                {
                    'error': 'Cannot delete accepted request.',
                    'detail': 'Accepted requests cannot be deleted as they have already been applied.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Store request data before deletion
        request_data = {
            'id': shift_request.id,
            'user': shift_request.user.names,
            'change_type': shift_request.change_type,
            'status': shift_request.status
        }
        
        # Delete the request
        shift_request.delete()
        
        return Response(
            {
                'message': 'Request deleted successfully.',
                'deleted_request': request_data
            },
            status=status.HTTP_200_OK
        )
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in delete_request: {error_message}")
        print(traceback.format_exc())
        return Response(
            {
                'error': 'An error occurred while deleting the request.',
                'detail': error_message
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def update_request(request, request_id):
    """
    Update a shift change request (only pending requests can be updated)
    
    Request body:
    - reason: Updated reason
    - new_shift: Updated shift ID
    - new_day_off: Updated day off
    - start_date: Updated start date
    """
    print("update_request called")
    print("Request data:", request.data)
    try:
        user = request.user
        
        # Get the request
        try:
            shift_request = ShiftChangeRequest.objects.get(id=request_id)
        except ShiftChangeRequest.DoesNotExist:
            return Response(
                {
                    'error': 'Request not found.',
                    'detail': f'No shift change request found with ID {request_id}.'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Only the request owner can update
        if user != shift_request.user:
            return Response(
                {
                    'error': 'Permission denied.',
                    'detail': 'Only the request owner can update the request.'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Can only update pending requests
        if shift_request.status != 'pending':
            return Response(
                {
                    'error': 'Cannot update request.',
                    'detail': f'Only pending requests can be updated. Current status: {shift_request.status}.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update the request
        serializer = ShiftChangeRequestUpdateSerializer(
            shift_request,
            data=request.data,
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            
            # Return detailed response
            detail_serializer = ShiftChangeRequestDetailSerializer(shift_request)
            
            return Response(
                {
                    'message': 'Request updated successfully.',
                    'request': detail_serializer.data
                },
                status=status.HTTP_200_OK
            )
        
        print(f"Validation errors: {serializer.errors}")
        return Response(
            {
                'error': 'Invalid request data.',
                'details': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in update_request: {error_message}")
        print(traceback.format_exc())
        return Response(
            {
                'error': 'An error occurred while updating the request.',
                'detail': error_message
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )





@api_view(['GET'])
@permission_classes([IsAuthenticated])
def supervisor_get_all_requests(request):
    """
    Get all shift change requests (with filtering)
    
    Query parameters:
    - status: Filter by status (pending, accepted, cancelled)
    - change_type: Filter by change type
    """
    try:
        user = request.user
        
        # Base queryset
        if user.role == 'admin':
            # Admins see all requests
            queryset = ShiftChangeRequest.objects.all()
        elif user.role == 'supervisor':
            # Supervisors see their own requests and their supervised employees' requests
            supervised_users = user.supervised_employees.all()
            queryset = ShiftChangeRequest.objects.filter(
                Q(user=user) | Q(user__in=supervised_users)
            )
        else:
            # Regular employees see only their own requests
            queryset = ShiftChangeRequest.objects.filter(user=user)
        
        # Apply filters
        request_status = request.GET.get('status', None)
        if request_status:
            queryset = queryset.filter(status=request_status)
        
        change_type = request.GET.get('change_type', None)
        if change_type:
            queryset = queryset.filter(change_type=change_type)
        
        # Serialize
        serializer = ShiftChangeRequestListSerializer(queryset, many=True)
        
        response_data = {
            'count': queryset.count(),
            'requests': serializer.data
        }
        
        # Print to terminal
        print_data_to_terminal(
            response_data, 
            f"GET ALL REQUESTS - User: {user.names} ({user.emp_number})"
        )
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in get_all_requests: {error_message}")
        print(traceback.format_exc())
        return Response(
            {
                'error': 'An error occurred while retrieving requests.',
                'detail': error_message
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
