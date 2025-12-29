from django.core.management.base import BaseCommand
from comments.models import Comment
from comments.youtube_service import get_youtube_service
from datetime import datetime
import datetime

class Command(BaseCommand):
    help = "Fetch comments from a YouTube video and auto-moderate using ML model"

    def add_arguments(self, parser):
        parser.add_argument("video_id", type=str, help="YouTube video ID")

    def handle(self, *args, **kwargs):
        video_id = kwargs["video_id"]
        youtube = get_youtube_service()

        # Use transformer-based model exclusively
        try:
            from toxicity_models.transformers.bert_infer import predict_label1_prob as bert_predict
            self.stdout.write(self.style.NOTICE("Using transformer-based toxicity model (textdetox/bert-multilingual-toxicity-classifier)"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Transformer model unavailable: {e}. Please install transformers/torch and the model."))
            return

        request = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            textFormat="plainText",
            maxResults=100,
        )
        response = request.execute()

        new_count = 0  # Track how many new comments were added

        for item in response.get("items", []):
            tlc = item.get("snippet", {}).get("topLevelComment", {})
            snippet = tlc.get("snippet", {})
            comment_id = tlc.get("id") or item.get("id")
            text = snippet["textDisplay"]
            author = snippet["authorDisplayName"]
            like_count = snippet.get("likeCount", 0)
            published_at = None
            try:
                published_at = datetime.datetime.strptime(snippet.get("publishedAt"), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
            except Exception:
                published_at = None

            # Only insert if not exists
            obj, created = Comment.objects.get_or_create(
                comment_id=comment_id,
                defaults={
                    "video_id": video_id,
                    "author": author,
                    "text": text,
                    "like_count": like_count,
                    "published_at": published_at,
                },
            )

            if created:
                # ML Moderation
                try:
                    prob_label1 = float(bert_predict([text])[0])
                    if prob_label1 > 0.45:
                        decision = 'toxic'
                    elif 0.30 <= prob_label1 <= 0.45:
                        decision = 'review'
                    else:
                        decision = 'neutral'

                    self.stdout.write(self.style.NOTICE(f"Transformer LABEL_1 score for {comment_id}: {prob_label1} -> {decision}"))

                    if decision == 'toxic':
                        try:
                            youtube.comments().setModerationStatus(id=comment_id, moderationStatus="rejected").execute()
                            obj.moderation_status = "deleted"
                        except Exception as e:
                            obj.moderation_status = "review"
                            self.stdout.write(self.style.WARNING(f"YouTube API delete failed for {comment_id}: {e}"))
                    elif decision == 'review':
                        obj.moderation_status = 'review'
                    else:
                        obj.moderation_status = 'neutral'

                    obj.save()
                    new_count += 1
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Transformer classification failed for {comment_id}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"✅ {new_count} new comments saved and auto-moderated (duplicates skipped)"))
