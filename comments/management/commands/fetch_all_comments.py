from django.core.management.base import BaseCommand
from comments.models import Comment, ChannelVideo
from comments import video_config
import os


class Command(BaseCommand):
    help = "Fetch comments for all configured videos and auto-moderate using ML model"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100, help="Max comments per video to fetch")

    def handle(self, *args, **kwargs):
        limit = kwargs.get("limit", 100)

        # Determine videos to process (DB first, fallback to config)
        try:
            db_vids = list(ChannelVideo.objects.order_by('-created_at').values_list('video_id', flat=True))
            video_list = db_vids if db_vids else getattr(video_config, 'CHANNEL_VIDEOS', [])
        except Exception:
            video_list = getattr(video_config, 'CHANNEL_VIDEOS', [])

        if not video_list:
            self.stdout.write(self.style.WARNING("No videos configured to fetch."))
            return

        # Resolve model paths relative to project layout
        base_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        models_dir = os.path.join(base_dir, 'toxicity_models', 'models')
        vec_path = os.path.join(models_dir, 'tfidf_vectorizer.joblib')
        clf_path = os.path.join(models_dir, 'toxicity_classifier.joblib')
        le_path = os.path.join(models_dir, 'label_encoder.joblib')

        # Use transformer-based model exclusively
        try:
            from toxicity_models.transformers.bert_infer import predict_label1_prob as bert_predict
            self.stdout.write(self.style.NOTICE("Using transformer-based toxicity model (textdetox/bert-multilingual-toxicity-classifier)"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Transformer model unavailable: {e}. Please install transformers/torch and the model."))
            return

        # Import YouTube service at runtime to avoid import-time failures
        try:
            from comments.youtube_service import get_youtube_service
            youtube = get_youtube_service()
        except Exception as e:
            youtube = None
            self.stdout.write(self.style.WARNING(f"YouTube service unavailable, will only store comments locally: {e}"))

        total_new = 0
        for video_id in video_list:
            self.stdout.write(self.style.NOTICE(f"Processing video: {video_id}"))
            try:
                if youtube:
                    request = youtube.commentThreads().list(
                        part="snippet",
                        videoId=video_id,
                        textFormat="plainText",
                        maxResults=limit,
                    )
                    response = request.execute()
                else:
                    response = {"items": []}

                new_count = 0
                for item in response.get("items", []):
                    # item is a commentThread resource — the actual top-level comment id is under snippet.topLevelComment.id
                    tlc = item.get("snippet", {}).get("topLevelComment", {})
                    snippet = tlc.get("snippet", {})
                    comment_id = tlc.get("id") or item.get("id")
                    text = snippet.get("textDisplay", "")
                    author = snippet.get("authorDisplayName", "")
                    like_count = snippet.get("likeCount", 0)
                    published_at_str = snippet.get("publishedAt")
                    published_at = None
                    if published_at_str:
                        try:
                            import datetime as _dt
                            published_at = _dt.datetime.strptime(published_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
                        except Exception:
                            published_at = None

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
                        try:
                            # Predict LABEL_1 probability using transformer
                            prob_label1 = float(bert_predict([text])[0])
                            # Apply thresholds
                            if prob_label1 > 0.45:
                                decision = 'toxic'
                            elif 0.30 <= prob_label1 <= 0.45:
                                decision = 'review'
                            else:
                                decision = 'neutral'

                            self.stdout.write(self.style.NOTICE(f"Transformer LABEL_1 score for {comment_id}: {prob_label1} -> {decision}"))

                            if decision == 'toxic':
                                if youtube:
                                    try:
                                        youtube.comments().setModerationStatus(id=comment_id, moderationStatus='rejected').execute()
                                        obj.moderation_status = 'deleted'
                                    except Exception as e:
                                        obj.moderation_status = 'review'
                                        self.stdout.write(self.style.WARNING(f"YouTube API delete failed for {comment_id}: {e}"))
                                else:
                                    obj.moderation_status = 'review'
                            elif decision == 'review':
                                obj.moderation_status = 'review'
                            else:
                                obj.moderation_status = 'neutral'

                            obj.save()
                            # If we set to review, add to retrain queue so it can be labeled by a human
                            if obj.moderation_status == 'review':
                                try:
                                    import csv as _csv
                                    queue_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'retrain_queue.csv'))
                                    with open(queue_path, 'a', newline='', encoding='utf-8') as csvfile:
                                        writer = _csv.writer(csvfile)
                                        # Write minimal retrain row: comment_id, language_type (NULL), toxic_word (NULL), context (text), category (Neutral)
                                        writer.writerow([comment_id, 'NULL', 'NULL', text, 'Neutral'])
                                except Exception as e:
                                    self.stdout.write(self.style.WARNING(f"Failed to append to retrain queue for {comment_id}: {e}"))
                            new_count += 1
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f"Failed to classify comment {comment_id}: {e}"))
                total_new += new_count
                self.stdout.write(self.style.SUCCESS(f"  → {new_count} new comments added for {video_id}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed processing {video_id}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Finished. Total new comments added: {total_new}"))
