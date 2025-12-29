from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from .models import Comment, ChannelVideo
from .video_config import CHANNEL_VIDEOS, CHANNEL_VIDEO_LINKS
import os
import csv


def log_analytics(request):
	from datetime import timedelta
	# Accept optional video_id to scope analytics to a single video
	video_id = request.GET.get('video_id') or request.POST.get('video_id')
	base_qs = Comment.objects.all()
	if video_id:
		base_qs = base_qs.filter(video_id=video_id)

	# Build logs and group by date (YYYY-MM-DD)
	logs_by_date = {}
	for c in base_qs.order_by('-published_at'):
		if c.published_at:
			published_at_ist = c.published_at + timedelta(hours=5, minutes=30)
			date_key = published_at_ist.date().isoformat()
			published_str = published_at_ist.strftime('%Y-%m-%d %H:%M:%S')
		else:
			published_at_ist = None
			date_key = 'unknown'
			published_str = ''

		entry = {
			'comment_id': c.comment_id,
			'author': c.author,
			'published_at_ist': published_str,
			'operation': c.moderation_status.capitalize(),
			'text': c.text,
		}
		logs_by_date.setdefault(date_key, []).append(entry)

	# Sort dates descending
	sorted_dates = sorted(logs_by_date.keys(), reverse=True)

	# Determine video display name
	if video_id:
		video_name = ChannelVideo.objects.filter(video_id=video_id).values_list('name', flat=True).first() or video_id
	else:
		# don't show 'All Videos' label when not scoped to a specific video
		video_name = ''

	import json
	return render(request, 'comments/log_analytics.html', {
		'timeline_logs_by_date': logs_by_date,
		'timeline_logs_by_date_json': json.dumps(logs_by_date),
		'sorted_dates': sorted_dates,
		'current_video_id': video_id,
		'current_video_name': video_name,
	})


@csrf_exempt
def neutral_and_queue(request):
	if request.method == 'POST':
		comment_id = request.POST.get('comment_id')
		language_type = request.POST.get('language_type')
		toxic_word = request.POST.get('toxic_word')  # Should be 'NULL'
		context = request.POST.get('context')
		toxicity_category = request.POST.get('toxicity_category')  # Should be 'Neutral'
		# Queue for retraining: append to CSV file
		queue_path = os.path.join(os.path.dirname(__file__), 'retrain_queue.csv')
		with open(queue_path, 'a', newline='', encoding='utf-8') as csvfile:
			writer = csv.writer(csvfile)
			writer.writerow([
				comment_id,
				language_type,
				toxic_word,
				context,
				toxicity_category
			])
		# Mark comment as neutral and update status
		try:
			comment = Comment.objects.get(comment_id=comment_id)
			comment.moderation_status = 'neutral'
			comment.save()
			return JsonResponse({'success': True})
		except Comment.DoesNotExist:
			return JsonResponse({'error': 'Comment not found'}, status=404)
	return HttpResponse(status=405)


@csrf_exempt
def fetch_comments(request):
	if request.method == 'POST':
		# Prefer provided video_id; otherwise use the most recently-added ChannelVideo; fall back to first constant
		video_id = request.POST.get('video_id')
		if not video_id:
			try:
				recent = ChannelVideo.objects.order_by('-created_at').values_list('video_id', flat=True).first()
				if recent:
					video_id = recent
				else:
					video_id = CHANNEL_VIDEOS[0] if CHANNEL_VIDEOS else None
			except Exception:
				video_id = CHANNEL_VIDEOS[0] if CHANNEL_VIDEOS else None
		from django.core.management import call_command
		import subprocess
		flag_path = os.path.join(os.path.dirname(__file__), 'retrain_flag.txt')
		queue_path = os.path.join(os.path.dirname(__file__), 'retrain_queue.csv')
		# Get current queue length
		try:
			with open(queue_path, 'r', encoding='utf-8') as f:
				queue_len = sum(1 for _ in f)
		except FileNotFoundError:
			queue_len = 0
		# Get last flag value
		try:
			with open(flag_path, 'r') as f:
				last_flag = int(f.read().strip())
		except (FileNotFoundError, ValueError):
			# If no flag exists, assume 0 processed items
			last_flag = 0

		# Retrain only after 20 or more new queued comments
		new_items = queue_len - last_flag
		if new_items >= 20 or (last_flag == 0 and queue_len >= 20):
			retrain_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'toxicity_models', 'retrain_model.py')
			subprocess.run(['python', retrain_script])  # Wait for retraining to finish
		# Now fetch and classify comments using updated model
		call_command('fetch_comments', video_id)
		# Redirect to the per-video dashboard where possible
		if video_id:
			return redirect('dashboard_video', video_id=video_id)
		return redirect('dashboard')
	return HttpResponse(status=405)


@csrf_exempt
def fetch_all_comments(request):
	"""
	Trigger fetching comments for all videos in CHANNEL_VIDEOS.
	"""
	if request.method == 'POST':
		from django.core.management import call_command
		import subprocess
		flag_path = os.path.join(os.path.dirname(__file__), 'retrain_flag.txt')
		queue_path = os.path.join(os.path.dirname(__file__), 'retrain_queue.csv')

		# Determine whether to retrain first (same logic as single fetch)
		try:
			with open(queue_path, 'r', encoding='utf-8') as f:
				queue_len = sum(1 for _ in f)
		except FileNotFoundError:
			queue_len = 0
		try:
			with open(flag_path, 'r') as f:
				last_flag = int(f.read().strip())
		except (FileNotFoundError, ValueError):
			last_flag = 0
		new_items = queue_len - last_flag
		if new_items >= 20 or (last_flag == 0 and queue_len >= 20):
			retrain_script = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'toxicity_models', 'retrain_model.py')
			subprocess.run(['python', retrain_script])

		# Prefer DB-backed ChannelVideo entries; fall back to constants
		try:
			db_vids = list(ChannelVideo.objects.order_by('-created_at').values_list('video_id', flat=True))
			if db_vids:
				video_list = db_vids
			else:
				video_list = CHANNEL_VIDEOS
		except Exception:
			video_list = CHANNEL_VIDEOS

		# Call centralized command that loads models once and processes all videos
		call_command('fetch_all_comments')

		# If the dashboard requested the fetch for a specific video, redirect back to that video's dashboard
		current_video_id = request.POST.get('current_video_id')
		if current_video_id:
			return redirect('dashboard_video', video_id=current_video_id)
		return redirect('dashboard')
	return HttpResponse(status=405)


@csrf_exempt
def move_to_neutral(request, comment_id):
	if request.method == 'POST':
		try:
			comment = Comment.objects.get(comment_id=comment_id)
			comment.moderation_status = 'neutral'
			comment.save()
		except Comment.DoesNotExist:
			pass
	return redirect('dashboard')


def dashboard(request, video_id=None):
	"""
	Dashboard view. If video_id is provided, show stats and comments for that video only.
	"""
	from datetime import timedelta, datetime
	from django.utils import timezone

	base_qs = Comment.objects.all()
	if video_id:
		base_qs = base_qs.filter(video_id=video_id)

	stats = {
		'total': base_qs.count(),
		'review': base_qs.filter(moderation_status__in=['review']).count(),
		'neutral': base_qs.filter(moderation_status='neutral').count(),
		'deleted': base_qs.filter(moderation_status='deleted').count(),
		'toxic': base_qs.filter(moderation_status='deleted').count(),  # All deleted are toxic
	}

	def convert_and_sort(queryset):
		comments = list(queryset)
		for c in comments:
			if c.published_at:
				# Add 5 hours 30 minutes to UTC to get IST
				c.published_at_ist = c.published_at + timedelta(hours=5, minutes=30)
			else:
				c.published_at_ist = None
		# Sort by IST datetime, newest first
		return sorted(comments, key=lambda x: x.published_at_ist or timezone.now(), reverse=True)

	review_comments = convert_and_sort(base_qs.filter(moderation_status__in=['review']))
	neutral_comments = convert_and_sort(base_qs.filter(moderation_status='neutral'))
	deleted_comments = convert_and_sort(base_qs.filter(moderation_status='deleted'))


	# Prepare paired video info for templates
	try:
		vids = list(ChannelVideo.objects.order_by('-created_at').values_list('video_id', 'link'))
		if vids:
			channel_videos_info = [(v[0], v[1]) for v in vids]
		else:
			channel_videos_info = list(zip(CHANNEL_VIDEOS, CHANNEL_VIDEO_LINKS))
	except Exception:
		channel_videos_info = list(zip(CHANNEL_VIDEOS, CHANNEL_VIDEO_LINKS))

	return render(request, 'comments/dashboard.html', {
		'stats': stats,
		'review_comments': review_comments,
		'neutral_comments': neutral_comments,
		'deleted_comments': deleted_comments,
		'channel_videos_info': channel_videos_info,
		'current_video_id': video_id,
		'current_video_name': (ChannelVideo.objects.filter(video_id=video_id).values_list('name', flat=True).first() if video_id else None) or video_id,
	})


def home(request):
	"""Home page showing channel videos as muted tiles."""
	# Prefer DB-backed ChannelVideo entries, fall back to config list
	try:
		videos = list(ChannelVideo.objects.order_by('-created_at').values_list('video_id', 'link', 'name'))
		if videos:
			channel_videos = [(v[0], v[1]) for v in videos]
		else:
			channel_videos = list(zip(CHANNEL_VIDEOS, CHANNEL_VIDEO_LINKS))
	except Exception:
		channel_videos = list(zip(CHANNEL_VIDEOS, CHANNEL_VIDEO_LINKS))

	# Build per-video stats synchronously from DB
	channel_videos_info = []
	for vid, link in channel_videos:
		qs = Comment.objects.filter(video_id=vid)
		stats = {
			'total': qs.count(),
			'review': qs.filter(moderation_status__in=['review']).count(),
			'neutral': qs.filter(moderation_status='neutral').count(),
			'deleted': qs.filter(moderation_status='deleted').count(),
			'toxic': qs.filter(moderation_status='deleted').count(),
		}
		channel_videos_info.append((vid, link, stats))

	return render(request, 'comments/home.html', {'channel_videos_info': channel_videos_info})


@csrf_exempt
def add_video(request):
	"""Accept POST to add a new ChannelVideo. Expects video_id, link, name.

	Returns JSON success/error.
	"""
	if request.method == 'POST':
		video_id = request.POST.get('video_id')
		link = request.POST.get('link')
		name = request.POST.get('name')
		if not video_id:
			return JsonResponse({'error': 'video_id required'}, status=400)
		try:
			obj, created = ChannelVideo.objects.get_or_create(video_id=video_id, defaults={'link': link or '', 'name': name or ''})
			if not created:
				# Update existing
				obj.link = link or obj.link
				obj.name = name or obj.name
				obj.save()
			return JsonResponse({'success': True, 'video_id': obj.video_id})
		except Exception as e:
			return JsonResponse({'error': str(e)}, status=500)
	return JsonResponse({'error': 'Invalid method'}, status=405)


def delete_comment(request, comment_id):
	comment = Comment.objects.get(comment_id=comment_id)
	# Call YouTube API to delete comment
	delete_comment_from_youtube(comment.comment_id)
	comment.moderation_status = 'deleted'
	comment.save()
	return redirect('dashboard')


def delete_comment_from_youtube(comment_id):
	try:
		# Import locally so Django management commands that don't need
		# YouTube API won't fail if google-auth-oauthlib isn't installed.
		from comments.youtube_service import get_youtube_service
	except Exception as e:
		raise RuntimeError(f"YouTube service unavailable: {e}")

	youtube = get_youtube_service()
	try:
		youtube.comments().setModerationStatus(id=comment_id, moderationStatus="rejected").execute()
	except Exception as e:
		# If the API reports a processingFailure, it's possible the stored id
		# is not the actual comment resource id but a thread id or otherwise
		# malformed. Attempt to look up the top-level comment id via
		# commentThreads.list and retry once.
		from googleapiclient.errors import HttpError
		try:
			if isinstance(e, HttpError) and e.resp.status == 400:
				err_content = getattr(e, 'error_details', None)
			# Try to lookup via commentThreads. Note: when a thread id was stored
			# the API can list the top-level comment resource using the thread id.
			try:
				resp = youtube.commentThreads().list(part='snippet', id=comment_id, maxResults=1).execute()
				items = resp.get('items', [])
				if items:
					tlc = items[0].get('snippet', {}).get('topLevelComment', {})
					real_id = tlc.get('id')
					if real_id and real_id != comment_id:
						# Retry with the real top-level comment id
						youtube.comments().setModerationStatus(id=real_id, moderationStatus='rejected').execute()
						return
			except Exception:
				pass
		finally:
			# Re-raise the original exception to be handled/logged by caller
			raise


@csrf_exempt
def reclassify_and_delete(request):
	if request.method == 'POST':
		comment_id = request.POST.get('comment_id')
		language_type = request.POST.get('language_type')
		toxic_word = request.POST.get('toxic_word')
		context = request.POST.get('context')
		toxicity_category = request.POST.get('toxicity_category')
		# Queue for retraining: append to CSV file
		queue_path = os.path.join(os.path.dirname(__file__), 'retrain_queue.csv')
		with open(queue_path, 'a', newline='', encoding='utf-8') as csvfile:
			writer = csv.writer(csvfile)
			writer.writerow([
				comment_id,
				language_type,
				toxic_word,
				context,
				toxicity_category
			])
		# Mark comment as deleted and update status
		try:
			comment = Comment.objects.get(comment_id=comment_id)
			delete_comment_from_youtube(comment_id)
			comment.moderation_status = 'deleted'
			comment.save()
			return JsonResponse({'success': True})
		except Comment.DoesNotExist:
			return JsonResponse({'error': 'Comment not found'}, status=404)
	return HttpResponse(status=405)
