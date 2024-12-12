import websocket
import json

from django.conf import settings

# Replace with your API key
api_key = settings.POLYGON_API_KEY

# WebSocket URL for stocks
url = "wss://socket.polygon.io/stocks"


# Define the message handler to print messages
def on_message(ws, message):
    print("Received Message:", message)


# Define the WebSocket connection open handler
def on_open(ws):
    print("Connection Opened")
    # Subscribe to a ticker, for example: T.AAPL (Apple)
    subscribe_message = {
        "action": "subscribe",
        "params": "T.AAPL",  # Real-time trades for Apple
    }
    ws.send(json.dumps(subscribe_message))


# Define the WebSocket connection close handler
def on_close(ws, close_status_code, close_msg):
    print("Connection Closed")


# Define the WebSocket error handler
def on_error(ws, error):
    print(f"Error: {error}")


# Create and run the WebSocket client
ws = websocket.WebSocketApp(
    url, on_message=on_message, on_open=on_open, on_error=on_error, on_close=on_close
)

# Run the WebSocket client
ws.run_forever()
