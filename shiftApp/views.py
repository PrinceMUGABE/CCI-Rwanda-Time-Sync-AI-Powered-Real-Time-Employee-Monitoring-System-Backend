# shiftApp/views.py

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import datetime, timedelta

from .models import BreakTemplate, Shift
from .serializers import (
    BreakTemplateSerializer,
    ShiftSerializer, 
    ShiftListSerializer
)
from userApp.models import CustomUser


class ShiftPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_shift(request):
    """Create a new shift template"""
    if not request.user.is_admin:
        return Response({
            'message': 'Only admins can create shifts'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = ShiftSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        serializer.save()
        return Response({
            'message': 'Shift created successfully',
            'shift': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'message': 'Shift creation failed',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_shifts(request):
    """List all shift templates with pagination and filtering"""
    # Get query parameters
    status_filter = request.query_params.get('status', None)
    
    # Base queryset
    queryset = Shift.objects.all()
    
    # Apply filters
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    # Pagination
    paginator = ShiftPagination()
    paginated_shifts = paginator.paginate_queryset(queryset, request)
    
    serializer = ShiftListSerializer(paginated_shifts, many=True, context={'request': request})
    
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_shift(request, shift_id):
    """Get single shift template details"""
    shift = get_object_or_404(Shift, id=shift_id)
    serializer = ShiftSerializer(shift, context={'request': request})
    
    return Response({
        'message': 'Shift retrieved successfully',
        'shift': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_shift(request, shift_id):
    """Update shift template details"""
    if not request.user.is_admin:
        return Response({
            'message': 'Only admins can update shifts'
        }, status=status.HTTP_403_FORBIDDEN)
    
    shift = get_object_or_404(Shift, id=shift_id)
    serializer = ShiftSerializer(shift, data=request.data, partial=True, context={'request': request})
    
    if serializer.is_valid():
        serializer.save()
        print(f"Shift updated successfully: {serializer.data}")
        return Response({
            'message': 'Shift updated successfully',
            'shift': serializer.data
        }, status=status.HTTP_200_OK)
    
    return Response({
        'message': 'Shift update failed',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_shift(request, shift_id):
    """Delete a shift template"""
    if not request.user.is_admin:
        return Response({
            'message': 'Only admins can delete shifts'
        }, status=status.HTTP_403_FORBIDDEN)
    
    shift = get_object_or_404(Shift, id=shift_id)

    shift.delete()
    
    return Response({
        'message': 'Shift deleted successfully'
    }, status=status.HTTP_200_OK)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_break_template(request):
    """Create a new break template for a shift"""
    if not request.user.is_admin:
        return Response({
            'message': 'Only admins can create break templates'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = BreakTemplateSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        serializer.save()
        print(f"Break template created successfully: {serializer.data}")
        return Response({
            'message': 'Break template created successfully',
            'break_template': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'message': 'Break template creation failed',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_shift_breaks(request, shift_id):
    """Get all breaks for a specific shift"""
    shift = get_object_or_404(Shift, id=shift_id)
    breaks = shift.breaks.all()
    
    serializer = BreakTemplateSerializer(breaks, many=True, context={'request': request})
    
    return Response({
        'message': 'Breaks retrieved successfully',
        'breaks': serializer.data
    }, status=status.HTTP_200_OK)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_break_template(request, break_id):
    """Update a break template"""
    if not request.user.is_admin:
        return Response({
            'message': 'Only admins can update break templates'
        }, status=status.HTTP_403_FORBIDDEN)
    
    break_template = get_object_or_404(BreakTemplate, id=break_id)
    serializer = BreakTemplateSerializer(break_template, data=request.data, partial=True, context={'request': request})
    
    if serializer.is_valid():
        serializer.save()
        print(f"Break template updated successfully: {serializer.data}")
        return Response({
            'message': 'Break template updated successfully',
            'break_template': serializer.data
        }, status=status.HTTP_200_OK)
    
    return Response({
        'message': 'Break template update failed',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_break_template(request, break_id):
    """Delete a break template"""
    if not request.user.is_admin:
        return Response({
            'message': 'Only admins can delete break templates'
        }, status=status.HTTP_403_FORBIDDEN)
    
    break_template = get_object_or_404(BreakTemplate, id=break_id)
    
    
    break_template.delete()
    
    return Response({
        'message': 'Break template deleted successfully'
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_break_templates(request):
    """List all break templates with optional filtering by shift"""
    shift_id = request.query_params.get('shift_id', None)
    
    queryset = BreakTemplate.objects.all()
    
    if shift_id:
        queryset = queryset.filter(shift__id=shift_id)
    
    serializer = BreakTemplateSerializer(queryset, many=True, context={'request': request})
    
    return Response({
        'message': 'Break templates retrieved successfully',
        'break_templates': serializer.data
    }, status=status.HTTP_200_OK)

