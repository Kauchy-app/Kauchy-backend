from channels.generic.websocket import AsyncWebsocketConsumer
import json
from channels.db import database_sync_to_async
from .models import Notification
from .serializers import NotificationSerializer


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user =  self.scope['user']

        if  not self.user.is_authenticated:
            await self.close()
            return
        
        self.notification_group_name = f'notifications_{self.user.id}'
        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name
        )
        await self.accept()

        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type':'unread_count',
            'count':unread_count
        }))

    async def disconnect(self,close_code):
        if hasattr(self,'notification_group_name'):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name
                
            )

    async def receive(self, text_data ):
        data = json.loads(text_data)
        action = data.get("action")

        if action =="mark_read":
            notification_id=data.get('notification_id')
            await self.mark_notification_read(notification_id)
        elif action == 'mark_all_read':
            await self.mark_all_read()
        elif action == 'get_notification':
            await self.send_notification()
        elif action == 'delete':
            notification_id = data.get('notification_id')
            await self.delete_notification(notification_id)

    async def notification_message(self, event):
        """Receive notification from group and send to WebSocket"""
        # Send the new notification
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': event['notification']
        }))
        
        # Also send updated unread count
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count
        }))

    async def send_notification(self):
        """Send all notifications to client"""
        notification = await self.get_notifications()
        await self.send(text_data=json.dumps({
            'type': 'notifications',
            'notifications': notification
        }))
        
        # Send unread count
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count
        }))

    @database_sync_to_async
    def get_notifications(self):
        notification = Notification.objects.filter(user=self.user)[:5]
        serializer = NotificationSerializer(notification,many=True)
        return serializer.data
    
    @database_sync_to_async
    def get_unread_count(self):
        return Notification.objects.filter(user=self.user,is_read=False).count()
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        try:
            notification = Notification.objects.get(id= notification_id,user=self.user)
            notification.is_read = True
            notification.save()
            return True
        except Notification.DoesNotExist:  
            return False
        
    @database_sync_to_async
    def mark_all_read(self):
        Notification.objects.filter(user=self.user, is_read=False).update(is_read= True)

    @database_sync_to_async
    def delete_notification(self,notification_id):
        try:
            notification= Notification.objects.get(user=self.user, id=notification_id)
            notification.delete()
            return True
        except Notification.DoesNotExist:
            return  False


