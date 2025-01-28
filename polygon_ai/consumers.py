import json
from channels.generic.websocket import AsyncWebsocketConsumer


class StockConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Group name for stock updates
        self.group_name = "stocks_group"

        # Add this connection to the group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Remove this connection from the group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "stock_update", "message": data.get("message", "")},
        )

    async def stock_update(self, event):
        # Send stock update to WebSocket client
        await self.send(text_data=json.dumps(event))
