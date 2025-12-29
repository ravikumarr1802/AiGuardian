from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/<str:video_id>/', views.dashboard, name='dashboard_video'),
    path('home/', views.home, name='home'),
    path('delete_comment/<str:comment_id>/', views.delete_comment, name='delete_comment'),
    path('move_to_neutral/<str:comment_id>/', views.move_to_neutral, name='move_to_neutral'),
    path('fetch_comments/', views.fetch_comments, name='fetch_comments'),
    path('fetch_all_comments/', views.fetch_all_comments, name='fetch_all_comments'),
    path('reclassify_and_delete/', views.reclassify_and_delete, name='reclassify_and_delete'),
    path('neutral_and_queue/', views.neutral_and_queue, name='neutral_and_queue'),
    path('log_analytics/', views.log_analytics, name='log_analytics'),
    path('add_video/', views.add_video, name='add_video'),
    # path('model_performance/', views.model_performance, name='model_performance'),
]
