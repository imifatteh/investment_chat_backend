import os
import threading
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from polygon_ai.polygon_websocket import PolygonWebSocketService
from polygon_ai.routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "investment_chat_project.settings")

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)


# Start the WebSocket service in a separate thread
def start_polygon_ws():
    service = PolygonWebSocketService()
    service.start(tickers=["AAPL", "TSLA", "MSFT"])


threading.Thread(target=start_polygon_ws, daemon=True).start()
