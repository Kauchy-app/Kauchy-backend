from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Notification
from .serializers import NotificationSerializer

def send_notification_to_user(user,title,message,notification_type,link=""):
    
    """
    Send a notification to a user via WebSocket.
    """
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link,
    )
    
    serializer= NotificationSerializer(notification)

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'notifications_{user.id}',
        {
            'type': 'notification_message',
            'notification': serializer.data
        }
    )
    return notification

def send_bulk_notifications(users,title,message,notification_type,link=""):
    """
    Send bulk notifications to multiple users.
    """
    notifications = []
    channel_layer = get_channel_layer()
    for user in users:
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link
        )
        notifications.append(notification)

        # Send to each user's WebSocket group
        serializer = NotificationSerializer(notification)
        async_to_sync(channel_layer.group_send)(
            f'notifications_{user.id}',
            {
                'type': 'notification_message',
                'notification': serializer.data
            }
        )
    
    return notifications


