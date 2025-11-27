# followups/urls.py
from django.urls import path
from . import views

app_name = 'followups'

urlpatterns = [
    # Dashboard & List Views
    path('', views.followup_dashboard, name='followup_dashboard'),
    
    # Creation & Management
    path('create/<int:campaign_id>/', views.create_followup_campaign, name='create_followup_campaign'),
    path('campaign/<int:followup_id>/', views.followup_campaign_detail, name='followup_campaign_detail'),
    path('campaign/<int:followup_id>/start/', views.start_followup_campaign, name='start_followup_campaign'),
    path('campaign/<int:followup_id>/stop/', views.stop_followup_campaign, name='stop_followup_campaign'),
    path('campaign/<int:followup_id>/analytics/', views.followup_analytics, name='followup_analytics'),
    
    # AJAX APIs
    path('api/campaigns/', views.get_campaigns_for_followup, name='get_campaigns_for_followup'),
    path('api/check-credit/', views.check_followup_credit, name='check_followup_credit'),
    
     # Tracking URLs
    path('track/open/<int:followup_id>/<str:email>/<int:sequence_number>/', 
         views.track_followup_open, name='track_followup_open'),
    path('track/click/<int:followup_id>/<str:email>/<int:sequence_number>/', 
         views.track_followup_click, name='track_followup_click'),
]