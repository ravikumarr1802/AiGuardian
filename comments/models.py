from django.db import models

class Comment(models.Model):
    comment_id = models.CharField(max_length=100, primary_key=True)
    video_id = models.CharField(max_length=50)
    author = models.CharField(max_length=255)
    text = models.TextField()
    like_count = models.IntegerField(default=0)
    published_at = models.DateTimeField()
    moderation_status = models.CharField(
        max_length=20,
        choices=[("unclassified", "Unclassified"),
                 ("neutral", "Neutral"),
                 ("toxic", "Toxic"),
                 ("review", "Review"),
                 ("deleted", "Deleted")],
        default="unclassified"
    )

    def __str__(self):
        return f"{self.comment_id} - {self.text[:30]}"


class ChannelVideo(models.Model):
    """Represents a YouTube channel video to monitor."""
    video_id = models.CharField(max_length=64, unique=True)
    link = models.URLField(max_length=500, blank=True)
    name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name or self.video_id}"
