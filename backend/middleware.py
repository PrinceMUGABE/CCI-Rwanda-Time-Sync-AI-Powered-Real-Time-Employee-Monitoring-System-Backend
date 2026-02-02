# backend/middleware.py
import pytz
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

class TimezoneMiddleware(MiddlewareMixin):
    """Middleware to activate system timezone"""
    
    def process_request(self, request):
        try:
            # Use the system timezone from settings
            tz = pytz.timezone(settings.TIME_ZONE)
            timezone.activate(tz)
        except Exception as e:
            # Fallback if timezone is invalid
            print(f"Timezone activation error: {e}")
            timezone.activate(pytz.UTC)
    
    def process_response(self, request, response):
        timezone.deactivate()
        return response