from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from .models import Task
from .serializers import TaskSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_task(request):
    """
    Create a new task
    """
    try:
        serializer = TaskSerializer(data=request.data)
        
        if serializer.is_valid():
            # Set created_by to current user if not provided
            serializer.save(created_by=request.user)
            
            print(f"Task created successfully: {serializer.data['name']}")
            return Response({
                'success': True,
                'message': 'Task created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            print(f"Task creation validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        print(f"Error creating task: {str(e)}")
        return Response({
            'success': False,
            'message': 'An error occurred while creating the task',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_tasks(request):
    """
    Retrieve all tasks without filters
    """
    try:
        tasks = Task.objects.all()
        serializer = TaskSerializer(tasks, many=True)
        
        print(f"Retrieved {tasks.count()} tasks")
        return Response({
            'success': True,
            'message': 'Tasks retrieved successfully',
            'count': tasks.count(),
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"Error retrieving tasks: {str(e)}")
        return Response({
            'success': False,
            'message': 'An error occurred while retrieving tasks',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_task_by_id(request, task_id):
    """
    Retrieve a specific task by ID
    """
    try:
        if not task_id:
            print("Task ID not provided")
            return Response({
                'success': False,
                'message': 'Task ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            print(f"Task with ID {task_id} not found")
            return Response({
                'success': False,
                'message': f'Task with ID {task_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = TaskSerializer(task)
        
        print(f"Task retrieved successfully: {task.name}")
        return Response({
            'success': True,
            'message': 'Task retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except ValueError:
        print(f"Invalid task ID format: {task_id}")
        return Response({
            'success': False,
            'message': 'Invalid task ID format'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        print(f"Error retrieving task by ID: {str(e)}")
        return Response({
            'success': False,
            'message': 'An error occurred while retrieving the task',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_task_by_name(request, task_name):
    """
    Retrieve tasks by name (exact match)
    """
    try:
        if not task_name or not task_name.strip():
            print("Task name not provided")
            return Response({
                'success': False,
                'message': 'Task name is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tasks = Task.objects.filter(name__iexact=task_name.strip())
        
        if not tasks.exists():
            print(f"No tasks found with name: {task_name}")
            return Response({
                'success': False,
                'message': f'No tasks found with name: {task_name}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = TaskSerializer(tasks, many=True)
        
        print(f"Found {tasks.count()} task(s) with name: {task_name}")
        return Response({
            'success': True,
            'message': 'Tasks retrieved successfully',
            'count': tasks.count(),
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"Error retrieving task by name: {str(e)}")
        return Response({
            'success': False,
            'message': 'An error occurred while retrieving tasks by name',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_task(request, task_id):
    """
    Update a task by ID
    """
    try:
        if not task_id:
            print("Task ID not provided")
            return Response({
                'success': False,
                'message': 'Task ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            print(f"Task with ID {task_id} not found")
            return Response({
                'success': False,
                'message': f'Task with ID {task_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Use partial=True for PATCH requests to allow partial updates
        partial = request.method == 'PATCH'
        serializer = TaskSerializer(task, data=request.data, partial=partial)
        
        if serializer.is_valid():
            serializer.save()
            
            print(f"Task updated successfully: {task.name}")
            return Response({
                'success': True,
                'message': 'Task updated successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        else:
            print(f"Task update validation failed: {serializer.errors}")
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except ValueError:
        print(f"Invalid task ID format: {task_id}")
        return Response({
            'success': False,
            'message': 'Invalid task ID format'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        print(f"Error updating task: {str(e)}")
        return Response({
            'success': False,
            'message': 'An error occurred while updating the task',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_task(request, task_id):
    """
    Delete a task by ID
    """
    try:
        if not task_id:
            print("Task ID not provided")
            return Response({
                'success': False,
                'message': 'Task ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            print(f"Task with ID {task_id} not found")
            return Response({
                'success': False,
                'message': f'Task with ID {task_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        task_name = task.name
        task.delete()
        
        print(f"Task deleted successfully: {task_name}")
        return Response({
            'success': True,
            'message': f'Task "{task_name}" deleted successfully'
        }, status=status.HTTP_200_OK)
        
    except ValueError:
        print(f"Invalid task ID format: {task_id}")
        return Response({
            'success': False,
            'message': 'Invalid task ID format'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        print(f"Error deleting task: {str(e)}")
        return Response({
            'success': False,
            'message': 'An error occurred while deleting the task',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)