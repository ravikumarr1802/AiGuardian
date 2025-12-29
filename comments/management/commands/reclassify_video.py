from django.core.management.base import BaseCommand
from comments.models import Comment
import os


class Command(BaseCommand):
    help = 'Re-run ML classifier on all comments for a video and update moderation_status in DB'

    def add_arguments(self, parser):
        parser.add_argument('video_id', type=str, help='YouTube video id to reclassify')
        parser.add_argument('--apply-youtube', action='store_true', help='If set, attempt to apply deletions via YouTube API when non-neutral')

    def handle(self, *args, **options):
        video_id = options['video_id']
        apply_youtube = options['apply_youtube']

        base_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        models_dir = os.path.join(base_dir, 'toxicity_models', 'models')
        vec_path = os.path.join(models_dir, 'tfidf_vectorizer.joblib')
        clf_path = os.path.join(models_dir, 'toxicity_classifier.joblib')
        le_path = os.path.join(models_dir, 'label_encoder.joblib')

        # Use transformer model exclusively
        try:
            from toxicity_models.transformers.bert_infer import predict_label1_prob as bert_predict
            self.stdout.write(self.style.NOTICE('Using transformer-based toxicity model (textdetox/bert-multilingual-toxicity-classifier)'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Transformer model unavailable: {e}'))
            return

        youtube = None
        if apply_youtube:
            try:
                from comments.youtube_service import get_youtube_service
                youtube = get_youtube_service()
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'YouTube service unavailable: {e}'))
                youtube = None

        qs = Comment.objects.filter(video_id=video_id)
        if not qs.exists():
            self.stdout.write(self.style.WARNING(f'No comments found for video {video_id}'))
            return

        updated = 0
        for c in qs:
            try:
                prob_label1 = float(bert_predict([c.text or ''])[0])
                if prob_label1 > 0.45:
                    new_status = 'deleted' if (youtube and apply_youtube) else 'review'
                elif 0.30 <= prob_label1 <= 0.45:
                    new_status = 'review'
                else:
                    new_status = 'neutral'

                old_status = c.moderation_status
                if new_status != old_status:
                    c.moderation_status = new_status
                    c.save()
                    updated += 1
                    self.stdout.write(self.style.NOTICE(f'Updated {c.comment_id}: {old_status} -> {new_status}'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Failed to reclassify {c.comment_id}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Finished reclassification for {video_id}. Updated {updated} comments.'))
