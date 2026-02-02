# backend/asgi.py
import os
from django.core.asgi import get_asgi_application

# Set Django settings module FIRST
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Initialize Django ASGI application early to ensure AppRegistry is populated
django_asgi_app = get_asgi_application()

# NOW import Channels components (after Django is initialized)
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

print("=" * 50)
print("INITIALIZING ASGI APPLICATION")
print("=" * 50)

# Import routing modules
websocket_urlpatterns = []

try:
    from chatApp import routing as chat_routing
    websocket_urlpatterns += chat_routing.websocket_urlpatterns
    print(f"✅ Added {len(chat_routing.websocket_urlpatterns)} chatApp WebSocket patterns")
except (ImportError, AttributeError) as e:
    print(f"⚠️  chatApp routing not available: {e}")

try:
    from assistanceApp import routing as assistance_routing
    websocket_urlpatterns += assistance_routing.websocket_urlpatterns
    print(f"✅ Added {len(assistance_routing.websocket_urlpatterns)} assistanceApp WebSocket patterns")
except (ImportError, AttributeError) as e:
    print(f"⚠️  assistanceApp routing not available: {e}")

print(f"\n📋 TOTAL WebSocket patterns: {len(websocket_urlpatterns)}")
for i, pattern in enumerate(websocket_urlpatterns, 1):
    print(f"  {i}. {pattern.pattern}")

print("=" * 50)

# Configure ASGI application
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})

print("✅ ASGI APPLICATION READY")
print("=" * 50)