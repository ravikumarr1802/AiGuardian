from django.contrib import admin
from .models import Comment, ChannelVideo


class ChannelVideoAdmin(admin.ModelAdmin):
	list_display = ('video_id', 'name', 'link', 'created_at')
	search_fields = ('video_id', 'name')


admin.site.register(Comment)
admin.site.register(ChannelVideo, ChannelVideoAdmin)
