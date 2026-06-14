from rest_framework import serializers
from .models import ConversationModel, MessageModel


class ConversationSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    last_message_time = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = ConversationModel
        fields = [
            'id',
            'other_user',
            'last_message',
            'last_message_time',
            'unread_count',
        ]
        read_only_fields = ['id']


    def get_other_user(self, obj):
        request_user = self.context.get('request_user')

        other_user = obj.buyer if obj.vendor == request_user else obj.vendor

        return {
            "id": other_user.id,
            "username": other_user.username,
            "profile_picture": other_user.profile_url,
            "status": other_user.online,
            "last_seen": other_user.last_seen
        }

    def get_last_message(self, obj):
        last_msg = obj.messages.last()

        if last_msg:
            return {
                'text': last_msg.text,
                'file': last_msg.file.url if last_msg.file else None,
                'sender': last_msg.sender.id,
                'is_mine': last_msg.sender == self.context.get('request_user'),
                'is_read': last_msg.is_read
            }
        return None
    
    def get_last_message_time(self, obj):
        # Use annotated value if available
        if hasattr(obj, 'last_message_time_db'):
            return obj.last_message_time_db.isoformat() if obj.last_message_time_db else None
        
        # Fallback
        last_msg = obj.messages.first()
        if last_msg:
            return last_msg.timestamp.isoformat()
        return obj.created_at.isoformat() if obj.created_at else None
    
    def get_unread_count(self, obj):
        # Use annotated value if available
        if hasattr(obj, 'unread_count_db'):
            return obj.unread_count_db
        
        # Fallback
        request_user = self.context.get('request_user')
        return obj.messages.filter(
            is_read=False
        ).exclude(sender=request_user).count()

class MessageSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="sender.username", read_only=True)
    reply_to_details = serializers.SerializerMethodField()

    class Meta:
        model = MessageModel
        fields = '__all__'

    def get_reply_to_details(self, obj):
        if obj.reply_to:
            return {
                "id": obj.reply_to.id,
                "text": obj.reply_to.text,
                "file": obj.reply_to.file.url if obj.reply_to.file else None,
                "sender_name": obj.reply_to.sender.username,
                "sender_id": obj.reply_to.sender.id,
            }
        return None