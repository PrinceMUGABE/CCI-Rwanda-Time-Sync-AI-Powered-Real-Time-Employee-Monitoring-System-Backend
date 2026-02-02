# userApp/views.py
from linecache import cache
import logging
import base64
import re
from django.conf import settings
import numpy as np
import cv2
import traceback
from requests import Request
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from django.db.models import Q
import face_recognition
import string
import random
from django.core.mail import send_mail
from django.utils import timezone

from .utils.logging_utils import calculate_login_status, create_user_log

from .utils.utils import generate_otp, store_otp, verify_otp, send_login_otp_to_email, send_otp_email
from .models import CustomUser
from .serializers import (
    CustomUserSerializer,
    LoginOTPRequestSerializer,
    LoginOTPVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer, 
    UserListSerializer, 
    ChangePasswordSerializer,
    UserProfileSerializer,
    FaceLoginSerializer
)
from shiftApp.models import Shift

# Configure logging
logger = logging.getLogger(__name__)

# Pre-trained face detector from OpenCV
face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')


def is_high_quality(image):
    """Check if the image is of high enough resolution."""
    try:
        height, width = image.shape[:2]
        min_resolution = (200, 200)
        return width >= min_resolution[0] and height >= min_resolution[1]
    except Exception as e:
        print(f"Error checking image quality: {str(e)}")
        return False


def get_image_from_file(image):
    """Load an image from a bytes-like object and perform basic checks."""
    try:
        # Convert the uploaded image bytes to a numpy array
        image.seek(0)
        file_array = np.frombuffer(image.read(), np.uint8)
        loaded_image = cv2.imdecode(file_array, cv2.IMREAD_COLOR)

        if loaded_image is None:
            logging.error("Image could not be loaded.")
            return None, "Failed to load image. Please upload a valid image file."

        if not is_high_quality(loaded_image):
            logging.error("Image is too low quality.")
            return None, "Image resolution is too low. Please upload a higher quality image (minimum 200x200 pixels)."

        faces = face_detector.detectMultiScale(loaded_image, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) > 1:
            logging.error("More than one person is found in the image.")
            return None, "More than one person detected in the image. Please submit a picture with only one person."
        
        if len(faces) == 0:
            logging.error("No faces detected in the submitted image.")
            return None, "No face detected in the image. Please submit a clear face photo."

        logging.info("Successfully loaded and validated image.")
        return loaded_image, None

    except Exception as e:
        logging.error(f"Failed to process image: {str(e)}")
        print(f"Error in get_image_from_file: {str(e)}")
        return None, "Failed to process the submitted image."


def compare_images_content(submitted_picture, existing_picture):
    """Compare the content of two images and return match score (0-100)."""
    try:
        submitted_picture_rgb = cv2.cvtColor(submitted_picture, cv2.COLOR_BGR2RGB)
        existing_picture_rgb = cv2.cvtColor(existing_picture, cv2.COLOR_BGR2RGB)

        submitted_encodings = face_recognition.face_encodings(submitted_picture_rgb)
        existing_encodings = face_recognition.face_encodings(existing_picture_rgb)

        if not submitted_encodings or not existing_encodings:
            logging.error("Failed to encode faces in one or both pictures.")
            print("Failed to encode faces")
            return 0.0

        distances = face_recognition.face_distance(existing_encodings, submitted_encodings[0])
        
        if len(distances) == 0:
            return 0.0

        # Calculate match score (0-100%)
        best_match_distance = min(distances)
        match_score = (1 - best_match_distance) * 100
        
        logging.info(f"Match score: {match_score:.2f}%")
        print(f"Face comparison match score: {match_score:.2f}%")
        return match_score

    except Exception as e:
        logging.error(f"Error comparing images: {str(e)}")
        print(f"Error in compare_images_content: {str(e)}")
        traceback.print_exc()
        return 0.0


def is_valid_password(password):
    """Validate password complexity."""
    try:
        if len(password) < 8:
            return "Password must be at least 8 characters long."
        if not any(char.isdigit() for char in password):
            return "Password must include at least one number."
        if not any(char.isupper() for char in password):
            return "Password must include at least one uppercase letter."
        if not any(char.islower() for char in password):
            return "Password must include at least one lowercase letter."
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return "Password must include at least one special character (!@#$%^&* etc.)."
        return None
    except Exception as e:
        error_msg = f"Error validating password: {str(e)}"
        print(error_msg)
        return "Error validating password format."

def is_valid_email(email):
    """Validate email format and domain."""
    try:
        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        
        # Check format
        if not re.match(email_regex, email):
            return "Invalid email format."
        
        # Check if it's a Gmail for personal email
        if not email.endswith("@gmail.com"):
            return "Only Gmail addresses are allowed for personal email."
        
        return None
    except Exception as e:
        error_msg = f"Error validating email: {str(e)}"
        print(error_msg)
        return "Error validating email format."

def is_valid_phone(phone_number):
    """Validate phone number format."""
    try:
        # Remove spaces and check if it contains only digits and + sign
        cleaned_phone = phone_number.replace(" ", "").replace("-", "")
        if not cleaned_phone.startswith("+"):
            return "Phone number must start with country code (e.g., +250)"
        
        # Check if remaining characters are digits
        if not cleaned_phone[1:].isdigit():
            return "Phone number must contain only digits after the country code."
        
        # Check length (international format typically 10-15 digits)
        if len(cleaned_phone) < 10 or len(cleaned_phone) > 16:
            return "Phone number must be between 10 and 15 digits (including country code)."
        
        return None
    except Exception as e:
        error_msg = f"Error validating phone number: {str(e)}"
        print(error_msg)
        return "Error validating phone number format."

def generate_secure_password():
    """Generate a secure random password that meets complexity requirements."""
    try:
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special_chars = "!@#$%^&*(),.?\":{}|<>"
        
        password = [
            random.choice(lowercase),
            random.choice(uppercase),
            random.choice(digits),
            random.choice(special_chars)
        ]
        
        all_chars = lowercase + uppercase + digits + special_chars
        password.extend(random.choice(all_chars) for _ in range(4))
        
        random.shuffle(password)
        return ''.join(password)
    except Exception as e:
        error_msg = f"Error generating secure password: {str(e)}"
        print(error_msg)
        return None        


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_user(request):
    """Register a new user (Admin/Supervisor only)"""
    try:
        print(f"\n[REGISTER USER] Request from: {request.user.emp_number}")
        print(f"[REGISTER USER] Request data: {dict(request.data)}")
        
        # Check if user has permission to create users
        if not (request.user.is_admin or request.user.is_supervisor):
            error_msg = f"Permission denied: {request.user.emp_number} tried to register user"
            print(f"[REGISTER USER ERROR] {error_msg}")
            return Response({
                'message': 'Only admins and supervisors can register new users',
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Copy data to add creator info
        data = request.data.copy()
        
        # Validate email
        email = data.get('email')
        if email:
            email_validation_error = is_valid_email(email)
            if email_validation_error:
                print(f"[REGISTER USER ERROR] Email validation failed: {email_validation_error}")
                return Response({
                    'message': 'Email validation failed',
                    'error': email_validation_error
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if email already exists
            if CustomUser.objects.filter(email=email).exists():
                print(f"[REGISTER USER ERROR] Email already exists: {email}")
                return Response({
                    'message': 'Email already exists',
                    'error': 'This email is already registered.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate phone number
        phone_number = data.get('phone_number')
        if phone_number:
            phone_validation_error = is_valid_phone(phone_number)
            if phone_validation_error:
                print(f"[REGISTER USER ERROR] Phone validation failed: {phone_validation_error}")
                return Response({
                    'message': 'Phone number validation failed',
                    'error': phone_validation_error
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if phone number already exists
            if CustomUser.objects.filter(phone_number=phone_number).exists():
                print(f"[REGISTER USER ERROR] Phone number already exists: {phone_number}")
                return Response({
                    'message': 'Phone number already exists',
                    'error': 'This phone number is already registered.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate emp_number uniqueness
        emp_number = data.get('emp_number')
        if emp_number and CustomUser.objects.filter(emp_number=emp_number).exists():
            print(f"[REGISTER USER ERROR] Employee number already exists: {emp_number}")
            return Response({
                'message': 'Employee number already exists',
                'error': 'This employee number is already registered.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate profile picture if uploaded
        if 'profile_picture_upload' in request.FILES:
            profile_picture = request.FILES['profile_picture_upload']
            
            # Load and validate the image
            loaded_image, error = get_image_from_file(profile_picture)
            if error:
                print(f"[REGISTER USER ERROR] Profile picture validation failed: {error}")
                return Response({
                    'message': 'Profile picture validation failed',
                    'error': error
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Reset file pointer for serializer
            profile_picture.seek(0)
        
        # Set default send_credentials to True
        if 'send_credentials' not in data:
            data['send_credentials'] = 'true'
        
        print(f"[REGISTER USER] Creating serializer with data")
        serializer = CustomUserSerializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            print(f"[REGISTER USER] Serializer validation passed")
            user = serializer.save()
            
            # If profile picture was uploaded, log it
            if 'profile_picture_upload' in request.FILES:
                print(f"[REGISTER USER SUCCESS] User registered with profile picture: {user.emp_number}")
            else:
                print(f"[REGISTER USER SUCCESS] User registered without profile picture: {user.emp_number}")
            
            return Response({
                'message': 'User registered successfully',
                'user': {
                    'id': user.id,
                    'emp_number': user.emp_number,
                    'names': user.names,
                    'email': user.email,
                    'role': user.role,
                    'status': user.status,
                    'gender': user.get_gender_display(),
                    'created_by': request.user.names if request.user else None
                },
                'note': 'Login credentials have been sent to the user\'s email address.'
            }, status=status.HTTP_201_CREATED)
        
        # Log validation errors
        print(f"[REGISTER USER ERROR] Serializer validation failed")
        print(f"[REGISTER USER ERROR] Errors: {serializer.errors}")
        
        # Format errors for better display
        error_messages = []
        for field, errors in serializer.errors.items():
            if isinstance(errors, list):
                for error in errors:
                    error_messages.append(f"{field}: {error}")
            else:
                error_messages.append(f"{field}: {errors}")
        
        return Response({
            'message': 'Registration failed',
            'error': '; '.join(error_messages),
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        error_msg = f"[REGISTER USER EXCEPTION] {str(e)}"
        print(error_msg)
        print(f"[REGISTER USER EXCEPTION] Traceback: {traceback.format_exc()}")
        
        return Response({
            'message': 'An error occurred during registration',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def login_with_face(request):
    """Login using face recognition (requires profile picture)"""
    try:
        face_image = request.FILES.get('face_image')
        emp_number = request.data.get('emp_number')
        
        if not face_image:
            print("Face login failed: No face image provided")
            return Response({
                'message': 'Face image is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Load and validate submitted face image
        submitted_image, error = get_image_from_file(face_image)
        if error:
            print(f"Face login failed: {error}")
            return Response({
                'message': 'Face verification failed',
                'error': error
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # If emp_number is provided, verify specific user
        if emp_number:
            try:
                user = CustomUser.objects.get(emp_number=emp_number)
            except CustomUser.DoesNotExist:
                print(f"Face login failed: User {emp_number} not found")
                return Response({
                    'message': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            if not user.has_profile_picture():
                print(f"Face login failed: User {emp_number} has no profile picture")
                return Response({
                    'message': 'No profile picture on record. Please upload a profile picture first or login with credentials.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Convert binary to image
            try:
                if isinstance(user.profile_picture, bytes):
                    existing_picture_array = np.frombuffer(user.profile_picture, np.uint8)
                elif user.profile_picture:
                    existing_picture_array = np.frombuffer(user.profile_picture, np.uint8)
                else:
                    print(f"Face login failed: Profile picture is None for {emp_number}")
                    return Response({
                        'message': 'Profile picture not found'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                existing_picture = cv2.imdecode(existing_picture_array, cv2.IMREAD_COLOR)
                
                if existing_picture is None:
                    print(f"Face login failed: Could not decode profile picture for {emp_number}")
                    return Response({
                        'message': 'Error processing stored profile picture'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            except Exception as e:
                print(f"Error processing profile picture for {emp_number}: {str(e)}")
                return Response({
                    'message': 'Error processing stored profile picture'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Compare faces
            match_score = compare_images_content(submitted_image, existing_picture)
            
            print(f"Face match score for {emp_number}: {match_score:.2f}%")
            
            if match_score >= 70.0:
                if not user.is_active:
                    print(f"Face login failed: User {emp_number} is inactive")
                    return Response({
                        'message': 'Account is inactive. Please contact administrator.'
                    }, status=status.HTTP_403_FORBIDDEN)
                
                # Calculate login status based on shift
                login_time = timezone.now()
                login_status = calculate_login_status(user, login_time)
                
                # Create user log for face login
                try:
                    create_user_log(
                        user=user,
                        log_type='login',
                        activity='User logged into the system',
                        status=login_status,
                        scheduled_time=user.current_shift.get_datetime_range(login_time.date())[0] if user.current_shift else None,
                        shift=user.current_shift,
                        request=request,
                        is_auto=False,
                        notes=f"Login method: Face recognition (Match: {match_score:.2f}%)"
                    )
                    logger.info(f"Face login log created for user {emp_number}")
                except Exception as log_error:
                    logger.error(f"Failed to create face login log: {str(log_error)}")
                    # Don't fail login if log creation fails
                
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                serializer = CustomUserSerializer(user, context={'request': request})
                
                print(f"Face login successful for {emp_number} with {match_score:.2f}% match")
                return Response({
                    'message': 'Face login successful',
                    'match_score': round(match_score, 2),
                    'user': serializer.data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_200_OK)
            else:
                print(f"Face login failed: Match score {match_score:.2f}% below threshold for {emp_number}")
                return Response({
                    'message': 'Face verification failed. Match score too low.',
                    'match_score': round(match_score, 2),
                    'required_score': 70.0
                }, status=status.HTTP_401_UNAUTHORIZED)
        
        # If no emp_number, search all active users with profile pictures
        else:
            users_with_pictures = CustomUser.objects.filter(
                is_active=True
            ).exclude(profile_picture__isnull=True)
            
            # Further filter in Python to exclude empty binary data
            valid_users = []
            for user in users_with_pictures:
                if user.profile_picture and len(user.profile_picture) > 0:
                    valid_users.append(user)
            
            if not valid_users:
                print("Face login failed: No users with valid profile pictures found")
                return Response({
                    'message': 'No registered users with valid profile pictures found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            best_match_user = None
            best_match_score = 0
            
            for user in valid_users:
                try:
                    # Convert binary to image
                    if isinstance(user.profile_picture, bytes):
                        existing_picture_array = np.frombuffer(user.profile_picture, np.uint8)
                    else:
                        continue
                    
                    existing_picture = cv2.imdecode(existing_picture_array, cv2.IMREAD_COLOR)
                    
                    if existing_picture is None:
                        continue
                    
                    match_score = compare_images_content(submitted_image, existing_picture)
                    print(f"Checking {user.emp_number}: {match_score:.2f}%")
                    
                    if match_score > best_match_score:
                        best_match_score = match_score
                        best_match_user = user
                
                except Exception as e:
                    print(f"Error comparing with user {user.emp_number}: {str(e)}")
                    continue
            
            if best_match_user and best_match_score >= 70.0:
                # Calculate login status based on shift
                login_time = timezone.now()
                login_status = calculate_login_status(best_match_user, login_time)
                
                # Create user log for face login
                try:
                    create_user_log(
                        user=best_match_user,
                        log_type='login',
                        activity='User logged into the system',
                        status=login_status,
                        scheduled_time=best_match_user.current_shift.get_datetime_range(login_time.date())[0] if best_match_user.current_shift else None,
                        shift=best_match_user.current_shift,
                        request=request,
                        is_auto=False,
                        notes=f"Login method: Face recognition without emp_number (Match: {best_match_score:.2f}%)"
                    )
                    logger.info(f"Face login log created for user {best_match_user.emp_number}")
                except Exception as log_error:
                    logger.error(f"Failed to create face login log: {str(log_error)}")
                    # Don't fail login if log creation fails
                
                refresh = RefreshToken.for_user(best_match_user)
                serializer = CustomUserSerializer(best_match_user, context={'request': request})
                
                print(f"Face login successful for {best_match_user.emp_number} with {best_match_score:.2f}% match")
                return Response({
                    'message': 'Face login successful',
                    'match_score': round(best_match_score, 2),
                    'user': serializer.data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }, status=status.HTTP_200_OK)
            else:
                print(f"Face login failed: Best match score {best_match_score:.2f}% below threshold")
                return Response({
                    'message': 'No matching face found. Please try again or login with credentials.',
                    'best_match_score': round(best_match_score, 2) if best_match_score > 0 else 0,
                    'required_score': 70.0
                }, status=status.HTTP_401_UNAUTHORIZED)
    
    except Exception as e:
        print(f"Error during face login: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred during face login',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_users(request):
    """List all users without pagination"""
    try:
        role = request.query_params.get('role', None)
        status_filter = request.query_params.get('status', None)
        search = request.query_params.get('search', None)
        
        queryset = CustomUser.objects.all()
        
        if role:
            queryset = queryset.filter(role=role)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if search:
            queryset = queryset.filter(
                Q(names__icontains=search) |
                Q(emp_number__icontains=search) |
                Q(email__icontains=search) |
                Q(phone_number__icontains=search)
            )
        
        serializer = UserListSerializer(queryset, many=True, context={'request': request})
        
        
        return Response({
            'message': 'Users retrieved successfully',
            'count': len(serializer.data),
            'users': serializer.data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"❌ Error listing users: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred while retrieving users',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_supervised_employees(request):
    """List all users without pagination"""
    try:
        role = request.query_params.get('role', None)
        status_filter = request.query_params.get('status', None)
        search = request.query_params.get('search', None)
        
        queryset = CustomUser.objects.filter(supervisors=request.user)
        
        if role:
            queryset = queryset.filter(role=role)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if search:
            queryset = queryset.filter(
                Q(names__icontains=search) |
                Q(emp_number__icontains=search) |
                Q(email__icontains=search) |
                Q(phone_number__icontains=search)
            )
        
        serializer = UserListSerializer(queryset, many=True, context={'request': request})
        
        
        return Response({
            'message': 'Users retrieved successfully',
            'count': len(serializer.data),
            'users': serializer.data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"❌ Error listing users: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred while retrieving users',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user(request, user_id):
    """Get single user details"""
    try:
        user = get_object_or_404(CustomUser, id=user_id)
        serializer = CustomUserSerializer(user, context={'request': request})
        
        print(f"Retrieved user: {user.emp_number}")
        return Response({
            'message': 'User retrieved successfully',
            'user': serializer.data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"Error retrieving user: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred while retrieving user',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_profile(request):
    """Get logged-in user's profile"""
    try:
        user = request.user
        serializer = UserProfileSerializer(user, context={'request': request})
        
        print(f"Retrieved profile for: {user.emp_number}")
        return Response({
            'message': 'Profile retrieved successfully',
            'profile': serializer.data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"Error retrieving profile: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred while retrieving profile',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
# @parser_classes([MultiPartParser, FormParser])
def update_my_profile(request):
    """Update logged-in user's profile with validations"""
    try:
        user = request.user
        data = request.data.copy()
        
        print(f"Updating profile for user: {user.emp_number}")
        print(f"Request data: {dict(data)}")
        
        # Check if profile picture is required (user doesn't have one)
        if not user.has_profile_picture() and 'profile_picture_upload' not in data:
            return Response({
                'message': 'Profile picture is required. Please upload a profile picture.',
                'detail': 'You must upload a profile picture as you currently don\'t have one.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate profile picture if uploaded
        if 'profile_picture_upload' in request.FILES:
            profile_picture = request.FILES['profile_picture_upload']
            
            # Load and validate the image
            loaded_image, error = get_image_from_file(profile_picture)
            if error:
                return Response({
                    'message': 'Profile picture validation failed',
                    'error': error
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Reset file pointer for serializer
            profile_picture.seek(0)
            
            # Store validated image data for quality assurance
            data['_validated_profile_picture'] = loaded_image
        
        # Validate email if changed
        if 'email' in data and data['email'] != user.email:
            email_validation_error = is_valid_email(data['email'])
            if email_validation_error:
                return Response({
                    'message': 'Email validation failed',
                    'error': email_validation_error
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if email already exists (excluding current user)
            if CustomUser.objects.filter(email=data['email']).exclude(id=user.id).exists():
                return Response({
                    'message': 'Email already exists',
                    'error': 'This email is already registered by another user.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate phone number if changed
        if 'phone_number' in data and data['phone_number'] != user.phone_number:
            phone_validation_error = is_valid_phone(data['phone_number'])
            if phone_validation_error:
                return Response({
                    'message': 'Phone number validation failed',
                    'error': phone_validation_error
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if phone number already exists (excluding current user)
            if CustomUser.objects.filter(phone_number=data['phone_number']).exclude(id=user.id).exists():
                return Response({
                    'message': 'Phone number already exists',
                    'error': 'This phone number is already registered by another user.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Remove internal validation data before passing to serializer
        data.pop('_validated_profile_picture', None)
        
        serializer = UserProfileSerializer(user, data=data, partial=True, context={'request': request})
        
        if serializer.is_valid():
            # Additional validation before saving
            try:
                # If profile picture is being updated, ensure it meets quality standards
                if 'profile_picture_upload' in request.FILES:
                    print(f"Profile picture validated successfully for {user.emp_number}")
                    
                    # Additional face validation for profile picture
                    if not user.has_profile_picture():
                        # First-time profile picture upload - ensure it's a good quality face photo
                        profile_picture = request.FILES['profile_picture_upload']
                        loaded_image, error = get_image_from_file(profile_picture)
                        if error:
                            return Response({
                                'message': 'Profile picture quality check failed',
                                'error': error
                            }, status=status.HTTP_400_BAD_REQUEST)
                
                serializer.save()
                print(f"Profile updated successfully for: {user.emp_number}")
                
                return Response({
                    'message': 'Profile updated successfully',
                    'profile': serializer.data
                }, status=status.HTTP_200_OK)
                
            except Exception as save_error:
                print(f"Error saving profile update: {str(save_error)}")
                return Response({
                    'message': 'Failed to save profile update',
                    'error': str(save_error)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        print(f"Profile update validation failed: {serializer.errors}")
        return Response({
            'message': 'Profile update failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        print(f"Error updating profile: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred while updating profile',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_user(request, user_id):
    """Update user details (admin/supervisor only) with validations"""
    print(f"Updating user {user_id} by {request.data}")
    try:
        user = get_object_or_404(CustomUser, id=user_id)
        
        # Check permissions
        if not request.user.is_admin and not request.user.can_supervise(user):
            print(f"Permission denied: {request.user.emp_number} cannot update {user.emp_number}")
            return Response({
                'message': 'You do not have permission to update this user'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Handle both JSON and multipart data
        if hasattr(request.data, '_mutable'):
            # QueryDict (form data) - make it mutable
            data = request.data.copy()
        else:
            # Regular dict (JSON) - create a copy
            data = dict(request.data)
        
        # Validate profile picture if uploaded
        if 'profile_picture_upload' in request.FILES:
            profile_picture = request.FILES['profile_picture_upload']
            
            # Load and validate the image
            loaded_image, error = get_image_from_file(profile_picture)
            if error:
                return Response({
                    'message': 'Profile picture validation failed',
                    'error': error
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Reset file pointer for serializer
            profile_picture.seek(0)

        # Map current_shift_name to current_shift_field for serializer
        if 'current_shift_name' in data:
            shift_id = data['current_shift_name']
            try:
                shift = Shift.objects.get(id=shift_id)
                data['current_shift_field'] = shift.id
                del data['current_shift_name']  # Remove the old key
            except Shift.DoesNotExist:
                return Response({
                    'message': 'Invalid shift ID',
                    'error': f'Shift with ID {shift_id} does not exist.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate email if changed
        if 'email' in data and data['email'] != user.email:
            email_validation_error = is_valid_email(data['email'])
            if email_validation_error:
                return Response({
                    'message': 'Email validation failed',
                    'error': email_validation_error
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if email already exists (excluding current user)
            if CustomUser.objects.filter(email=data['email']).exclude(id=user.id).exists():
                return Response({
                    'message': 'Email already exists',
                    'error': 'This email is already registered by another user.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate phone number if changed
        if 'phone_number' in data and data['phone_number'] != user.phone_number:
            phone_validation_error = is_valid_phone(data['phone_number'])
            if phone_validation_error:
                return Response({
                    'message': 'Phone number validation failed',
                    'error': phone_validation_error
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if phone number already exists (excluding current user)
            if CustomUser.objects.filter(phone_number=data['phone_number']).exclude(id=user.id).exists():
                return Response({
                    'message': 'Phone number already exists',
                    'error': 'This phone number is already registered by another user.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle password fields - only include if provided
        if not data.get('password'):
            data.pop('password', None)
            data.pop('password_confirm', None)
        
        # Use partial=True for PATCH, but ensure required fields are present for PUT
        partial = request.method == 'PATCH'
        
        serializer = CustomUserSerializer(user, data=data, partial=partial, context={'request': request})
        
        if serializer.is_valid():
            updated_user = serializer.save()
            print(f"User updated: {updated_user.emp_number}")
            return Response({
                'message': 'User updated successfully',
                'user': serializer.data
            }, status=status.HTTP_200_OK)
        
        print(f"User update validation failed: {serializer.errors}")
        return Response({
            'message': 'Update failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        print(f"Error updating user: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred while updating user',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_user(request, user_id):
    """Delete a user (soft delete by setting inactive)"""
    try:
        if not request.user.is_admin:
            print(f"Permission denied: {request.user.emp_number} tried to delete user")
            return Response({
                'message': 'Only admins can delete users'
            }, status=status.HTTP_403_FORBIDDEN)
        
        user = get_object_or_404(CustomUser, id=user_id)
        
        if user.id == request.user.id:
            print(f"User {request.user.emp_number} tried to delete own account")
            return Response({
                'message': 'You cannot delete your own account'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user.is_active = False
        user.status = 'inactive'
        user.save()
        
        print(f"User deleted: {user.emp_number}")
        return Response({
            'message': 'User deleted successfully'
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"Error deleting user: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred while deleting user',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change user password"""
    try:
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            print(f"Password changed for: {request.user.emp_number}")
            return Response({
                'message': 'Password changed successfully'
            }, status=status.HTTP_200_OK)
        
        print(f"Password change validation failed: {serializer.errors}")
        return Response({
            'message': 'Password change failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        print(f"Error changing password: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred while changing password',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_supervisors(request):
    """Get all supervisors"""
    try:
        supervisors = CustomUser.objects.filter(role='supervisor', is_active=True)
        serializer = UserListSerializer(supervisors, many=True, context={'request': request})
        
        print(f"Retrieved {len(serializer.data)} supervisors")
        return Response({
            'message': 'Supervisors retrieved successfully',
            'count': len(serializer.data),
            'supervisors': serializer.data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"Error retrieving supervisors: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred while retrieving supervisors',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_supervised_employees(request, supervisor_id):
    """Get all employees supervised by a specific supervisor"""
    try:
        supervisor = get_object_or_404(CustomUser, id=supervisor_id, role='supervisor')
        employees = supervisor.supervised_employees.all()
        
        serializer = UserListSerializer(employees, many=True, context={'request': request})
        
        print(f"Retrieved {len(serializer.data)} employees for supervisor {supervisor.emp_number}")
        return Response({
            'message': 'Supervised employees retrieved successfully',
            'count': len(serializer.data),
            'employees': serializer.data,
            'supervisor': {
                'id': supervisor.id,
                'name': supervisor.names,
                'emp_number': supervisor.emp_number
            }
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"Error retrieving supervised employees: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred while retrieving supervised employees',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_supervisors(request, user_id):
    """Assign supervisors to an employee"""
    try:
        if not request.user.is_admin:
            print(f"Permission denied: {request.user.emp_number} tried to assign supervisors")
            return Response({
                'message': 'Only admins can assign supervisors'
            }, status=status.HTTP_403_FORBIDDEN)
        
        user = get_object_or_404(CustomUser, id=user_id)
        
        if user.role != 'employee':
            print(f"Invalid role: Cannot assign supervisors to {user.role}")
            return Response({
                'message': 'Only employees can be assigned supervisors'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        supervisor_ids = request.data.get('supervisor_ids', [])
        
        if not supervisor_ids:
            print("No supervisor IDs provided")
            return Response({
                'message': 'At least one supervisor must be provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        supervisors = CustomUser.objects.filter(id__in=supervisor_ids, role='supervisor')
        
        if supervisors.count() != len(supervisor_ids):
            print(f"Invalid supervisor IDs: {supervisor_ids}")
            return Response({
                'message': 'Some supervisor IDs are invalid'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user.supervisors.set(supervisors)
        
        serializer = CustomUserSerializer(user, context={'request': request})
        
        print(f"Supervisors assigned to {user.emp_number}")
        return Response({
            'message': 'Supervisors assigned successfully',
            'user': serializer.data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"Error assigning supervisors: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred while assigning supervisors',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_get_supervised_employees(request):
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




# userApp/views.py (add these views)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_with_otp_request(request):
    """
    Step 1: Request OTP for login
    User provides emp_number and password, system sends OTP to email
    """
    try:
        serializer = LoginOTPRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'message': 'Invalid request',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        emp_number = serializer.validated_data['emp_number']
        password = serializer.validated_data['password']
        
        try:
            user = CustomUser.objects.get(emp_number=emp_number, is_active=True)
        except CustomUser.DoesNotExist:
            logger.warning(f"Login OTP request: User {emp_number} not found or inactive")
            return Response({
                'message': 'Invalid credentials or account is inactive'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Verify password
        if not user.check_password(password):
            logger.warning(f"Login OTP request: Invalid password for {emp_number}")
            return Response({
                'message': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Generate and store OTP
        otp = generate_otp()
        store_otp(user.email, otp, expiry_seconds=300)  # 5 minutes expiry
        
        # Send OTP to email
        if send_login_otp_to_email(user, otp):
            logger.info(f"Login OTP sent to {user.email} for user {emp_number}")
            return Response({
                'message': 'OTP has been sent to your email',
                'email': user.email[:3] + '****' + user.email[user.email.find('@'):]  # Mask email
            }, status=status.HTTP_200_OK)
        else:
            logger.error(f"Failed to send OTP email to {user.email}")
            return Response({
                'message': 'Failed to send OTP. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        logger.error(f"Error in login OTP request: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred during login',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_with_otp_verify(request):
    """Step 2: Verify OTP and complete login"""
    try:
        serializer = LoginOTPVerifySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'message': 'Invalid request',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        emp_number = serializer.validated_data['emp_number']
        otp = serializer.validated_data['otp']
        
        try:
            user = CustomUser.objects.get(emp_number=emp_number, is_active=True)
        except CustomUser.DoesNotExist:
            logger.warning(f"Login OTP verify: User {emp_number} not found or inactive")
            return Response({
                'message': 'Invalid credentials or account is inactive'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Verify OTP
        is_valid, message = verify_otp(user.email, otp)
        
        if not is_valid:
            logger.warning(f"Login OTP verify failed for {emp_number}: {message}")
            return Response({
                'message': message
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Calculate login status based on shift
        login_time = timezone.now()
        login_status = calculate_login_status(user, login_time)
        
        # Create user log for login
        create_user_log(
            user=user,
            log_type='login',
            activity='User logged into the system',
            status=login_status,
            scheduled_time=user.current_shift.get_datetime_range(login_time.date())[0] if user.current_shift else None,
            shift=user.current_shift,
            request=request,
            is_auto=False,
            notes=f"Login method: OTP verification"
        )
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        serializer = CustomUserSerializer(user, context={'request': request})
        
        logger.info(f"OTP login successful for {emp_number}")
        return Response({
            'message': 'Login successful',
            'user': serializer.data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error in OTP verification: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred during login',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['POST'])
@permission_classes([IsAuthenticated])  # ← Requires valid access token
def logout(request):
    """Logout user by blacklisting refresh token"""
    try:
        refresh_token = request.data.get('refresh')
        
        if not refresh_token:
            return Response({
                'message': 'Refresh token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # With IsAuthenticated, request.user is the actual user object
        user = request.user
        
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            # Calculate logout status
            logout_time = timezone.now()
            logout_status = 'on_time'
            scheduled_time = None
            
            if user.current_shift:
                shift_start, shift_end = user.current_shift.get_datetime_range(logout_time.date())
                scheduled_time = shift_end
                diff_minutes = (logout_time - shift_end).total_seconds() / 60
                
                if diff_minutes < -15:
                    logout_status = 'early'
                elif -15 <= diff_minutes <= 5:
                    logout_status = 'on_time'
                elif 5 < diff_minutes <= 30:
                    logout_status = 'late'
                else:
                    logout_status = 'very_late'
            
            # Create user log
            try:
                create_user_log(
                    user=user,
                    log_type='logout',
                    activity='User logged out of the system',
                    status=logout_status,
                    scheduled_time=scheduled_time,
                    shift=user.current_shift,
                    request=request,
                    is_auto=False,
                    notes="Session ended manually"
                )
                logger.info(f"Logout log created for user {user.emp_number}")
            except Exception as log_error:
                logger.error(f"Failed to create logout log: {str(log_error)}")
            
            print(f"User {user.emp_number} logged out successfully")
            return Response({
                'message': 'Logged out successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Token blacklisting failed: {str(e)}")
            traceback.print_exc()
            return Response({
                'message': 'Invalid token'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        print(f"Error in logout: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred during logout',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    """
    Step 1: Request password reset OTP
    User provides email, system sends OTP
    """
    print("Password reset request received")
    print(f"Request data: {request.data}")
    try:
        serializer = PasswordResetRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            print(f"Password reset request validation failed: {serializer.errors}")
            return Response({
                'message': 'Invalid request',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        
        try:
            user = CustomUser.objects.get(email=email, is_active=True)
        except CustomUser.DoesNotExist:
            # Don't reveal if email exists for security
            print(f"Password reset request for non-existent email: {email}")
            return Response({
                'message': 'If your email is registered, you will receive a reset OTP'
            }, status=status.HTTP_200_OK)
        
        # Generate and store OTP
        otp = generate_otp()
        store_otp(email, otp, expiry_seconds=300)  # 5 minutes expiry
        
        # Send OTP to email
        if send_otp_email(user, otp):
            print(f"Password reset OTP sent to {email}")
            return Response({
                'message': 'If your email is registered, you will receive a reset OTP',
                'email': email[:3] + '****' + email[email.find('@'):]  # Mask email
            }, status=status.HTTP_200_OK)
        else:
            print(f"Failed to send password reset OTP to {email}")
            return Response({
                'message': 'Failed to send OTP. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        print(f"Error in password reset request: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred during password reset',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_verify(request):
    """
    Step 2: Verify password reset OTP
    User provides email and OTP
    """
    try:
        serializer = PasswordResetVerifySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'message': 'Invalid request',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        
        # Verify OTP
        is_valid, message = verify_otp(email, otp)
        
        if not is_valid:
            logger.warning(f"Password reset OTP verification failed for {email}: {message}")
            return Response({
                'message': message
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # OTP verified successfully
        logger.info(f"Password reset OTP verified for {email}")
        return Response({
            'message': 'OTP verified successfully. You can now reset your password.'
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error in password reset verification: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred during password reset',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    """
    Step 3: Reset password with verified OTP
    User provides email, OTP, and new password
    """
    print("Password reset confirmation received")
    print(f"Request data: {request.data}")
    try:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        
        if not serializer.is_valid():
            print(f"Password reset confirm validation failed: {serializer.errors}")
            return Response({
                'message': 'Invalid request',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']
        
        # Verify OTP again (for security)
        is_valid, message = verify_otp(email, otp)
        
        if not is_valid:
            print(f"Password reset confirmation OTP invalid for {email}: {message}")
            return Response({
                'message': message
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            user = CustomUser.objects.get(email=email, is_active=True)
        except CustomUser.DoesNotExist:
            print(f"Password reset: User with email {email} not found")
            return Response({
                'message': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        # Delete OTP from cache after successful reset
        cache_key = f"reset_otp_{email}"
        cache.clear(cache_key)
        
        # Send confirmation email (optional)
        try:
            subject = "Password Reset Successful - TimeSync System"
            message = f"""
Hello {user.names},

Your password has been successfully reset.

If you did not perform this action, please contact support immediately.

Best regards,
TimeSync System Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception as email_error:
            print(f"Failed to send password reset confirmation: {str(email_error)}")
        
        print(f"Password reset successful for {email}")
        return Response({
            'message': 'Password reset successful. You can now login with your new password.'
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"Error in password reset confirmation: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred during password reset',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


# userApp/views.py (replace the existing login_with_credentials function)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_with_credentials(request):
    """
    Login with employee number and password - Now redirects to OTP flow
    This is kept for backward compatibility but redirects to OTP flow
    """
    try:
        emp_number = request.data.get('emp_number')
        password = request.data.get('password')
        
        if not emp_number or not password:
            print("Login failed: Missing credentials")
            return Response({
                'message': 'Employee number and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Instead of direct login, initiate OTP flow
        data = {'emp_number': emp_number, 'password': password}
        return login_with_otp_request(Request(request._request, 'POST', data=data))
    
    except Exception as e:
        print(f"Error during login: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred during login',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_token(request):
    """Verify if the current access token is valid"""
    try:
        user = request.user
        serializer = CustomUserSerializer(user)
        
        return Response({
            "valid": True,
            "user": serializer.data
        }, status=200)
        
    except Exception as e:
        return Response({
            "valid": False,
            "error": str(e)
        }, status=401)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_reset_user_password(request, user_id):
    """Admin resets user password and sends email"""
    try:
        # Check if user has permission
        if not (request.user.is_admin or request.user.is_supervisor):
            print(f"Permission denied: {request.user.emp_number} tried to reset password")
            return Response({
                'message': 'Only admins and supervisors can reset passwords'
            }, status=status.HTTP_403_FORBIDDEN)
        
        user = get_object_or_404(CustomUser, id=user_id)
        
        # Admin cannot reset their own password this way
        if user.id == request.user.id:
            return Response({
                'message': 'To change your own password, please use the change password feature.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate new password
        new_password = generate_secure_password()
        user.set_password(new_password)
        user.save()
        
        # Send email to user
        try:
            subject = f"Your Password Has Been Reset - TimeSync System"
            
            message = f"""
Dear {user.names},

Your password has been reset by {request.user.names} ({request.user.role}).

Your new temporary password is: {new_password}

**Important:**
1. Please login and change your password immediately
2. This temporary password will expire in 24 hours
3. For security, change to a strong, memorable password

Login URL: {settings.FRONTEND_URL}/login

If you did not request this change, please contact your supervisor immediately.

Best regards,
TimeSync System Team
"""
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            
            print(f"Admin password reset email sent to {user.email}")
            
            # Send notification to admin
            admin_subject = f"Password Reset Completed: {user.emp_number}"
            admin_message = f"""
Hello {request.user.names},

You have successfully reset the password for:

User: {user.names}
Employee Number: {user.emp_number}
Email: {user.email}

The new temporary password has been sent to the user's email address.

Note: The temporary password will expire in 24 hours if not changed.

TimeSync System
"""
            
            send_mail(
                subject=admin_subject,
                message=admin_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[request.user.email],
                fail_silently=True,
            )
            
        except Exception as email_error:
            print(f"Error sending password reset email: {str(email_error)}")
            # Still return success but with warning
            return Response({
                'message': 'Password reset but email notification failed',
                'warning': 'Could not send email notification',
                'user': {
                    'id': user.id,
                    'emp_number': user.emp_number,
                    'names': user.names
                }
            }, status=status.HTTP_200_OK)
        
        return Response({
            'message': 'Password reset successful. Notification sent to user.',
            'user': {
                'id': user.id,
                'emp_number': user.emp_number,
                'names': user.names
            }
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"Error resetting password: {str(e)}")
        traceback.print_exc()
        return Response({
            'message': 'An error occurred while resetting password',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)