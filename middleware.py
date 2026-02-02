# middleware.py
import pytz
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

class TimezoneMiddleware(MiddlewareMixin):
    """Middleware to set timezone to local timezone"""
    
    def process_request(self, request):
        # Force Django to use Africa/Kigali timezone
        timezone.activate(pytz.timezone('Africa/Kigali'))
    
    def process_response(self, request, response):
        # Deactivate timezone after response
        timezone.deactivate()
        return response