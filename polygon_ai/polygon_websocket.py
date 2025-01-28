from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from polygon.websocket import WebSocketClient

from django.conf import settings


class PolygonWebSocketService:
    def __init__(self):
        self.client = WebSocketClient(
            api_key=settings.POLYGON_API_KEY,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

    def start(self, tickers):
        # Initialize the WebSocket client with the correct callback for messages
        self.client = WebSocketClient(
            api_key=self.client.api_key, on_message=self.on_message
        )

        # Subscribe to the specified tickers
        for ticker in tickers:
            print(f"Subscribing to: T.{ticker}")
            self.client.subscribe("T." + ticker)

        # Run the WebSocket client (blocking)
        print("Starting WebSocket client...")
        print(self.on_message)
        self.client.run(handle_msg=self.on_message)

    def on_message(self, message):
        # Broadcast message to WebSocket group
        print(message)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "stocks_group", {"type": "stock_update", "message": message}
        )

    def on_error(self, error):
        print(f"WebSocket Error: {error}")

    def on_close(self, code, reason):
        print(f"WebSocket closed with code {code} and reason {reason}")
