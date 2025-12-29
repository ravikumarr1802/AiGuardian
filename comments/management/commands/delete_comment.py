from django.core.management.base import BaseCommand
from comments.youtube_service import get_youtube_service
from comments.models import Comment

class Command(BaseCommand):
    help = "Delete a comment from YouTube by comment ID"

    def add_arguments(self, parser):
        parser.add_argument("comment_id", type=str, help="YouTube comment ID")

    def handle(self, *args, **options):
        comment_id = options["comment_id"]
        youtube = get_youtube_service()

        youtube.comments().setModerationStatus(
            id=comment_id,
            moderationStatus="rejected"
        ).execute()

        # Update in DB
        Comment.objects.filter(comment_id=comment_id).update(moderation_status="deleted")

        self.stdout.write(self.style.SUCCESS(f"Comment {comment_id} deleted."))
