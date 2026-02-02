# rulesApp/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Rule
from .serializers import RuleSerializer, RuleListSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_rules(request):
    """
    Get rules accessible to the logged-in user
    """
    try:
        print(f"\n=== Fetching rules for user: {request.user.names} ===")
        
        user = request.user
        user_role = user.role
        
        # Get all active rules
        rules = Rule.objects.filter(status='active')
        
        # Filter rules based on user's role
        accessible_rules = []
        for rule in rules:
            if rule.can_user_view(user_role):
                accessible_rules.append(rule)
        
        # Apply filters if provided
        rule_type = request.GET.get('type')
        if rule_type:
            accessible_rules = [r for r in accessible_rules if r.rule_type == rule_type]
        
        # Sort by creation date
        accessible_rules.sort(key=lambda x: x.created_at, reverse=True)
        
        serializer = RuleListSerializer(accessible_rules, many=True)
        
        print(f"✅ Found {len(accessible_rules)} rules for {user.names}")
        for rule in accessible_rules[:3]:  # Print first 3 rules
            print(f"  - {rule.title} ({rule.rule_type}) - Description: {rule.description}")
        
        return Response({
            'success': True,
            'count': len(accessible_rules),
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"❌ Error fetching user rules: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_rule(request):
    """
    Create a new rule (Admin only)
    """
    try:
        print(f"\n=== Creating new rule ===")
        print(f"Request user: {request.user.names}, Role: {request.user.role}")
        
        # Check if user is admin
        if not request.user.role == 'admin':
            print("❌ User is not admin")
            return Response({
                'success': False,
                'error': 'Only admins can create rules'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = RuleSerializer(data=request.data)
        
        if serializer.is_valid():
            rule = serializer.save()
            print(f"✅ Rule created: {rule.title}")
            print(f"   Type: {rule.rule_type}, User Type: {rule.user_type}")
            
            return Response({
                'success': True,
                'message': 'Rule created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            print(f"❌ Validation errors: {serializer.errors}")
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        print(f"❌ Error creating rule: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_rules(request):
    """
    Get all rules (Admin only)
    """
    try:
        print(f"\n=== Fetching all rules ===")
        
        # Check if user is admin
        if not request.user.role == 'admin':
            print("❌ User is not admin")
            return Response({
                'success': False,
                'error': 'Only admins can view all rules'
            }, status=status.HTTP_403_FORBIDDEN)
        
        rules = Rule.objects.all().order_by('-created_at')
        serializer = RuleListSerializer(rules, many=True)
        
        print(f"✅ Found {rules.count()} rules")
        
        return Response({
            'success': True,
            'count': rules.count(),
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"❌ Error fetching all rules: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_rule_detail(request, rule_id):
    """
    Get rule details by ID
    """
    try:
        print(f"\n=== Fetching rule details ID: {rule_id} ===")
        
        rule = get_object_or_404(Rule, id=rule_id)
        
        # Check if user can view this rule
        if not rule.can_user_view(request.user.role):
            print(f"❌ User cannot view this rule")
            return Response({
                'success': False,
                'error': 'You do not have permission to view this rule'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = RuleSerializer(rule)
        
        print(f"✅ Rule found: {rule.title}")
        print(f"   Description length: {len(rule.description)} chars")
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Rule.DoesNotExist:
        print(f"❌ Rule not found: ID {rule_id}")
        return Response({
            'success': False,
            'error': 'Rule not found'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        print(f"❌ Error fetching rule details: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_rules_by_type(request, rule_type):
    """
    Get rules by type
    """
    try:
        print(f"\n=== Fetching rules by type: {rule_type} ===")
        
        # Validate rule type
        valid_types = ['rule', 'regulation']
        if rule_type not in valid_types:
            print(f"❌ Invalid rule type: {rule_type}")
            return Response({
                'success': False,
                'error': f'Invalid rule type. Must be: {", ".join(valid_types)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        
        # Get rules by type
        if user.role == 'admin':
            rules = Rule.objects.filter(rule_type=rule_type)
        else:
            rules = Rule.objects.filter(rule_type=rule_type, status='active')
            # Filter by user access
            rules = [r for r in rules if r.can_user_view(user.role)]
        
        serializer = RuleListSerializer(rules, many=True)
        
        print(f"✅ Found {len(rules)} {rule_type}(s)")
        
        return Response({
            'success': True,
            'count': len(rules),
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"❌ Error fetching rules by type: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_rule(request, rule_id):
    """
    Update a rule (Admin only)
    """
    try:
        print(f"\n=== Updating rule ID: {rule_id} ===")
        
        # Check if user is admin
        if not request.user.role == 'admin':
            print("❌ User is not admin")
            return Response({
                'success': False,
                'error': 'Only admins can update rules'
            }, status=status.HTTP_403_FORBIDDEN)
        
        rule = get_object_or_404(Rule, id=rule_id)
        print(f"Rule found: {rule.title}")
        
        serializer = RuleSerializer(rule, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_rule = serializer.save()
            print(f"✅ Rule updated: {updated_rule.title}")
            print(f"   New status: {updated_rule.status}")
            
            return Response({
                'success': True,
                'message': 'Rule updated successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        else:
            print(f"❌ Validation errors: {serializer.errors}")
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Rule.DoesNotExist:
        print(f"❌ Rule not found: ID {rule_id}")
        return Response({
            'success': False,
            'error': 'Rule not found'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        print(f"❌ Error updating rule: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_rule(request, rule_id):
    """
    Delete a rule (Admin only)
    """
    try:
        print(f"\n=== Deleting rule ID: {rule_id} ===")
        
        # Check if user is admin
        if not request.user.role == 'admin':
            print("❌ User is not admin")
            return Response({
                'success': False,
                'error': 'Only admins can delete rules'
            }, status=status.HTTP_403_FORBIDDEN)
        
        rule = get_object_or_404(Rule, id=rule_id)
        rule_title = rule.title
        
        rule.delete()
        print(f"✅ Rule deleted: {rule_title}")
        
        return Response({
            'success': True,
            'message': 'Rule deleted successfully'
        }, status=status.HTTP_200_OK)
        
    except Rule.DoesNotExist:
        print(f"❌ Rule not found: ID {rule_id}")
        return Response({
            'success': False,
            'error': 'Rule not found'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        print(f"❌ Error deleting rule: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)