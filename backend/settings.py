from pathlib import Path
import os
import pytz
import tzlocal


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-*b^p3kh7jlfq=zl%(_b!(8u*fr6be$&gypdd*ycdups-(lu@6+'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'localhost:5173',
]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'channels',
    'django_celery_beat',
    'userApp',
    'shiftApp',
    'performanceApp.apps.PerformanceAppConfig',
    'notificationApp',
    'taskApp',
    'taskAssignmentApp',
    'requestApp',
    'reportApp',
    'rulesApp',

    
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'backend.middleware.TimezoneMiddleware',
]



ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'
ASGI_APPLICATION = 'backend.asgi.application'


LANGUAGE_CODE = 'en-us'





# Auto-detect and use system timezone
try:
    system_timezone = tzlocal.get_localzone_name()
    TIME_ZONE = system_timezone
    print(f"✓ Using system timezone: {TIME_ZONE}")
    
    # Get the UTC offset for MySQL
    tz = pytz.timezone(system_timezone)
    from datetime import datetime
    offset = tz.utcoffset(datetime.now())
    offset_hours = int(offset.total_seconds() / 3600)
    offset_str = f"{'+' if offset_hours >= 0 else ''}{offset_hours:02d}:00"
    
except Exception as e:
    print(f"⚠ Could not detect system timezone: {e}")
    TIME_ZONE = 'Africa/Kigali'  # Fallback
    offset_str = '+00:00'

USE_TZ = True

# Database Configuration with system timezone
DATABASES = {
    'default': {
        'ENGINE': 'mysql.connector.django',
        'NAME': 'natasha',
        'USER': 'root',
        'PASSWORD': '07288',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': f"SET sql_mode='STRICT_TRANS_TABLES', time_zone='{offset_str}'",
        },
    },
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/




# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'




# Simple JWT settings (optional, you can adjust expiration, etc.)
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=2),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=2),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}




# In settings.py
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True  # Extend session on each request
SESSION_COOKIE_SAMESITE = 'Lax'  # Allow cross-site session
SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS


JWT_SECRET_KEY = SECRET_KEY




AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # Default Django backend
]



CORS_ALLOW_ALL_ORIGINS = True


# settings.py

# Add media configurations
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'princemugabe567@gmail.com'
EMAIL_HOST_PASSWORD = 'qdzu gzbd bnjl qamv'
DEFAULT_FROM_EMAIL = 'Digital Mentorship  <princemugabe567@gmail.com>'



AUTH_USER_MODEL = 'userApp.CustomUser'




# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Allowed file extensions for template uploads
ALLOWED_TEMPLATE_EXTENSIONS = ['.pdf', '.docx', '.doc']
MAX_TEMPLATE_FILE_SIZE = 5 * 1024 * 1024  # 5MB



# Add to settings.py
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# OTP Settings
OTP_EXPIRY_SECONDS = 30
OTP_LENGTH = 6


MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')



CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
        # For production, use Redis:
        # 'BACKEND': 'channels_redis.core.RedisChannelLayer',
        # 'CONFIG': {
        #     "hosts": [('127.0.0.1', 6379)],
        # },
    },
}




USE_FREE_AI = True

# Frontend URL for email templates
FRONTEND_URL = 'http://localhost:5173'  # frontend URL

# Cache settings for FAQ (extend existing CACHES)
CACHES["assistance"] = {
    "BACKEND": "django_redis.cache.RedisCache",
    "LOCATION": "redis://127.0.0.1:6379/2",  # Use database 2 for assistance
    "OPTIONS": {
        "CLIENT_CLASS": "django_redis.client.DefaultClient",
    }
}

# Merge all REST_FRAMEWORK settings into one
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '50000/day',
        'user': '50000/day',
        'assistance_anon': '1000/hour',
        'assistance_user': '50000/hour',
    }
}

# Email for assistance responses (extend existing EMAIL settings)
ASSISTANCE_FROM_EMAIL = 'ai-assistance@CCIRwanda.com'  # Different from regular emails

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
        'colored': {
            'format': '\033[1;34m[{levelname}]\033[0m {asctime} - \033[1;32m{name}\033[0m - {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'debug.log'),
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'error.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'INFO',  # Set to DEBUG to see SQL queries
            'propagate': False,
        },
        # Your app loggers
        'userApp': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'notificationApp': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # Add other apps as needed
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Create logs directory if it doesn't exist
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

CORS_EXPOSE_HEADERS = ['Content-Type', 'Authorization']




# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB

# Media settings
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Allowed file types
ALLOWED_FILE_TYPES = {
    'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],
    'video': ['mp4', 'mov', 'avi', 'mkv', 'webm'],
    'audio': ['mp3', 'wav', 'ogg', 'm4a'],
    'document': ['pdf', 'doc', 'docx', 'txt', 'ppt', 'pptx', 'xls', 'xlsx']
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file


# settings.py
# Celery Configuration
CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# Update CELERY_BEAT_SCHEDULE (replace existing one)
from celery.schedules import crontab

CELERY_WORKER_POOL = 'solo' # Use solo pool for Windows/debugging


CELERY_BEAT_SCHEDULE = {
    # ===== TASK ASSIGNMENT - FIXED TIMING =====
    'auto-create-assignments-before-shifts': {
        'task': 'taskAssignmentApp.tasks.auto_create_assignments_before_shifts',
        'schedule': crontab(minute='*'),  # Every minute to catch 10-min window
        'options': {'queue': 'assignments'}
    },
    
    'send-task-reminders-multi-interval': {
        'task': 'taskAssignmentApp.tasks.send_task_reminders',
        'schedule': 120.0,  # Every 2 minutes to catch 30, 15, 10, 5 min windows
        'options': {'queue': 'notifications'}
    },
    
    'check-missed-assignments': {
        'task': 'taskAssignmentApp.tasks.check_missed_assignments',
        'schedule': crontab(minute='*'),  # Every minute
    },
    
    'generate-assignments-for-tomorrow-backup': {
        'task': 'taskAssignmentApp.tasks.generate_assignments_for_tomorrow',
        'schedule': crontab(minute='*'),  # Every minute
    },
    
    # ===== BREAK MANAGEMENT TASKS =====
    'monitor-and-create-breaks': {
        'task': 'performanceApp.tasks.monitor_and_create_breaks',
        'schedule': crontab(minute='*'),  # Every minute
        'options': {'queue': 'breaks'}
    },
    
    'create-daily-breaks': {
        'task': 'performanceApp.tasks.create_daily_breaks',
        'schedule': crontab(minute='*'),  # Every minute
    },
    
    'create-upcoming-breaks': {
        'task': 'performanceApp.tasks.create_upcoming_breaks',
        'schedule': crontab(minute='*'),  # Every minute
        'options': {'queue': 'breaks'}
    },
    
    'check-missed-breaks-new': {
        'task': 'performanceApp.tasks.check_missed_breaks',
        'schedule': crontab(minute='*'),  # Every minutes
    },
    
    'check-extended-breaks': {
        'task': 'performanceApp.tasks.check_extended_breaks',
        'schedule': crontab(minute='*'),  # Every minute
    },
    
    # ===== EXISTING TASKS =====
    'auto-record-breaks': {
        'task': 'performanceApp.tasks.auto_record_scheduled_breaks',
        'schedule': crontab(minute='*'),  # Every 5 minutes
    },
    'monitor-breaks': {
        'task': 'notificationApp.tasks.monitor_breaks',
        'schedule': 120.0,  # Every 2 minutes
    },
    'cleanup-notifications': {
        'task': 'notificationApp.tasks.cleanup_expired_notifications',
        'schedule': crontab(minute='*'),  # Every minute
    },
    'check-missed-breaks-old': {
        'task': 'notificationApp.tasks.check_missed_breaks',
        'schedule': crontab(minute='*'),  # Every minute
    },
    'shift-start-reminders': {
        'task': 'notificationApp.tasks.send_shift_start_reminders',
        'schedule': crontab(minute='*'),  # Every minute
    },
    'shift-end-reminders': {
        'task': 'notificationApp.tasks.send_shift_end_reminders',
        'schedule': crontab(minute='*'),  # Every minute
    },

     'check-task-end-reminders': {
        'task': 'notificationApp.tasks.check_task_end_reminders',
        'schedule': crontab(minute='*'),  # Every minute
        'options': {'queue': 'notifications'}
    },
    
    'check-missed-tasks': {
        'task': 'notificationApp.tasks.check_missed_tasks',
        'schedule': crontab(minute='*/5'),  # Every 10 minutes
        'options': {'queue': 'notifications'}
    },

    'send-shift-reminders': {
        'task': 'notificationApp.tasks.send_shift_reminders',
        'schedule': crontab(minute='*'),  # Every minute (combines start and end reminders)
        'options': {'queue': 'notifications'}
    },
}