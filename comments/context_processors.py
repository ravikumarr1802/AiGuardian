from . import video_config
from .models import ChannelVideo


def channel_videos(request):
    """Make channel_videos_info available to all templates.

    Prefers DB-backed ChannelVideo entries, falls back to video_config constants.
    Returns list of (video_id, link) pairs as `channel_videos_info`.
    """
    try:
        videos = list(ChannelVideo.objects.order_by('-created_at').values_list('video_id', 'link'))
        if videos:
            return {"channel_videos_info": videos}
    except Exception:
        pass
    return {"channel_videos_info": list(zip(video_config.CHANNEL_VIDEOS, video_config.CHANNEL_VIDEO_LINKS))}
