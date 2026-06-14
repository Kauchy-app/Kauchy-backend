from django.contrib import admin
from .models import KauchModel, PostModel, PostLike, PostComment, KauchFollow

# Register your models here.


@admin.register(KauchModel)
class KauchAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'owner', 'followers_count', 'created_at')
    search_fields = ('name', 'owner__username', 'owner__email')


@admin.register(PostModel)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'kauch', 'media_type', 'likes_count', 'comments_count', 'created_at')
    list_filter = ('media_type',)
    search_fields = ('description', 'kauch__name')


@admin.register(PostComment)
class PostCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'user', 'created_at')
    search_fields = ('text',)


admin.site.register(PostLike)
admin.site.register(KauchFollow)
