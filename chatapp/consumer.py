from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .utils import get_all_conversations, store_message, mark_as_read, load_user_messages, change_online_status
import json
from django.utils import timezone

class UnifiedChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return
        

        self.subscribed_rooms = set()

        await self.accept()

        await change_online_status(self.user, True)

        conversations = await get_all_conversations(self.user)

        for conv in conversations:
            room_name = f"chat_{conv['id']}"
            self.subscribed_rooms.add(room_name)

            await self.channel_layer.group_add(
                room_name,
                self.channel_name
            )

        await self.send(text_data=json.dumps({
            "type":"conversation_list",
            "conversations": conversations
        }, default=str))


    async def disconnect(self, code):
        if hasattr(self, 'subscribed_rooms'):
            for room_name in self.subscribed_rooms:
                await self.channel_layer.group_discard(
                    room_name,
                    self.channel_name
                )
        
        if hasattr(self, 'user') and self.user.is_authenticated:
            await change_online_status(self.user, False)


    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')

        if action == "send_message":
            conversation_id = data["conversation_id"]
            message = data["message"]
            reply_to_id = data.get("reply_to_id")

            message_data = await store_message(self.user, conversation_id, message, reply_to_id=reply_to_id)

            await self.channel_layer.group_send(
                f"chat_{conversation_id}",
                {
                    'type':"chat_message",
                    "conversation_id":conversation_id,
                    "id": message_data.get("id"),
                    "message": message_data["text"],
                    "sender": message_data["sender"],
                    'timestamp': message_data["timestamp"],
                    "reply_to_details": message_data.get("reply_to_details")
                }
            )

        elif action == "mark_as_read":
            conversation_id = data["conversation_id"]
            await mark_as_read(conversation_id, self.user)

            await self.channel_layer.group_send(
                f"chat_{conversation_id}",
                {
                    "type":"mark_read",
                    "conversation_id":conversation_id,
                    "sender": getattr(self.user, "id", None)
                }
            )


        elif action == "get_message":
            conversation_id = data["conversation_id"]
            messages = await load_user_messages(conversation_id)
            # print(conversation_id)

            await self.send(text_data=json.dumps({
                "type":"my_messages",
                "messages": messages
            }, default=str))


    async def chat_message(self, event):
        conversations = await get_all_conversations(self.user)
        await self.send(text_data=json.dumps({
            "type":"conversation_list",
            "conversations": conversations
        }, default=str))

        await self.send(text_data=json.dumps({
            'type':'new_message',
            'conversation_id': event['conversation_id'],
            'id': event.get('id'),
            'message': event.get('message', ''),
            'file': event.get('file_url'),
            'sender': event['sender'],
            'timestamp': event['timestamp'],
            'reply_to_details': event.get('reply_to_details')
        }, default=str))
    
    
    async def mark_read(self, event):
        await self.send(text_data=json.dumps({
            'type':"mark_chat",
            "conversation_id":event["conversation_id"],
            "sender": event["sender"]
        }, default=str))




