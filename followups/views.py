# followups/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse 
from django.utils import timezone
from django.db.models import Count, Q, F
from django.contrib.auth.decorators import login_required

from keddy_mailer.models import Campaign, CustomUser, template, SMTPServer, EmailTracking
from .models import FollowUpCampaign, FollowUpSequence, FollowUpTracking, FollowUpAnalytics


import logging  # ✅ Logger import karo

# ✅ Logger setup
logger = logging.getLogger(__name__)


# Helper function to get user context
def get_user_context(request):
    user_id = request.session.get("user_id")
    user = get_object_or_404(CustomUser, uid=user_id)
    
    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0
    
    return {
        "company_name": user.company,
        "uname": user.name,
        "user": user,
        "credit_limit": credit_limit,
        "credit_percent": credit_percent,
        "credits_left": credits_left,
    }

def followup_dashboard(request):
    """Follow-up campaigns dashboard"""
    context = get_user_context(request)
    user_id = request.session.get("user_id")
    
    # Get all follow-up campaigns for user
    followup_campaigns = FollowUpCampaign.objects.filter(user_id=user_id).order_by('-created_at')
    
    # Calculate stats
    active_campaigns = followup_campaigns.filter(status='active').count()
    completed_campaigns = followup_campaigns.filter(status='completed').count()
    total_followups_sent = sum(campaign.total_emails_sent for campaign in followup_campaigns)
    
    context.update({
        'followup_campaigns': followup_campaigns,
        'active_campaigns': active_campaigns,
        'completed_campaigns': completed_campaigns,
        'total_followups_sent': total_followups_sent,
    })
    
    return render(request, 'followups/dashboard.html', context)

def create_followup_campaign(request, campaign_id):
    """Create follow-up campaign from existing campaign"""
    context = get_user_context(request)
    user_id = request.session.get("user_id")
    
    # Get original campaign
    original_campaign = get_object_or_404(Campaign, id=campaign_id, user_id=user_id)
    
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            max_followups = int(request.POST.get('max_followups', 3))
            days_between = int(request.POST.get('days_between', 2))
            trigger_time = request.POST.get('trigger_time', '11:00')
            stop_on_open = 'stop_on_open' in request.POST
            stop_on_click = 'stop_on_click' in request.POST
            
            # Create follow-up campaign
            followup_campaign = FollowUpCampaign.objects.create(
                original_campaign=original_campaign,
                name=name,
                user_id=user_id,
                max_followups=max_followups,
                days_between=days_between,
                trigger_time=trigger_time,
                stop_on_open=stop_on_open,
                stop_on_click=stop_on_click,
                status='draft'
            )
            
            # Create sequences
            for i in range(1, max_followups + 1):
                subject = request.POST.get(f'subject_{i}')
                body = request.POST.get(f'body_{i}')
                
                if subject and body:
                    FollowUpSequence.objects.create(
                        followup_campaign=followup_campaign,
                        sequence_number=i,
                        subject=subject,
                        body=body,
                        days_after_previous=days_between
                    )
            
            messages.success(request, f"Follow-up campaign '{name}' created successfully!")
            return redirect('followup_campaign_detail', followup_id=followup_campaign.id)
            
        except Exception as e:
            messages.error(request, f"Error creating follow-up campaign: {str(e)}")
    
    # Get non-responsive recipients for preview
    original_trackings = EmailTracking.objects.filter(campaign=original_campaign, is_failed=False)
    non_openers = original_trackings.filter(is_opened=False).count()
    non_clickers = original_trackings.filter(is_clicked=False).count()
    
    context.update({
        'original_campaign': original_campaign,
        'non_openers': non_openers,
        'non_clickers': non_clickers,
        'total_recipients': original_trackings.count(),
        'time_options': ['09:00', '11:00', '14:00', '16:00'],  # 9AM, 11AM, 2PM, 4PM
    })
    
    return render(request, 'followups/create_followup.html', context)

def followup_campaign_detail(request, followup_id):
    """Follow-up campaign detail view"""
    context = get_user_context(request)
    user_id = request.session.get("user_id")
    
    followup_campaign = get_object_or_404(FollowUpCampaign, id=followup_id, user_id=user_id)
    sequences = followup_campaign.sequences.all()
    
    # Get analytics
    analytics, created = FollowUpAnalytics.objects.get_or_create(followup_campaign=followup_campaign)
    
    # Get tracking stats
    tracking_stats = FollowUpTracking.objects.filter(followup_campaign=followup_campaign).aggregate(
        total_sent=Count('id'),
        total_opens=Count('id', filter=Q(is_opened=True)),
        total_clicks=Count('id', filter=Q(is_clicked=True)),
        active_recipients=Count('id', filter=Q(is_active=True)),
    )
    
    context.update({
        'followup_campaign': followup_campaign,
        'sequences': sequences,
        'analytics': analytics,
        'tracking_stats': tracking_stats,
    })
    
    return render(request, 'followups/followup_detail.html', context)

def start_followup_campaign(request, followup_id):
    """Start a follow-up campaign"""
    user_id = request.session.get("user_id")
    followup_campaign = get_object_or_404(FollowUpCampaign, id=followup_id, user_id=user_id)
    
    if followup_campaign.status == 'draft':
        followup_campaign.status = 'active'
        followup_campaign.started_at = timezone.now()
        followup_campaign.save()
        
        messages.success(request, f"Follow-up campaign '{followup_campaign.name}' started successfully!")
    else:
        messages.warning(request, "Campaign is already active or completed.")
    
    # TEMPORARY FIX: Use direct URL instead of reverse
    return redirect(f'/followups/campaign/{followup_id}/')

def stop_followup_campaign(request, followup_id):
    """Stop a follow-up campaign"""
    user_id = request.session.get("user_id")
    followup_campaign = get_object_or_404(FollowUpCampaign, id=followup_id, user_id=user_id)
    
    if followup_campaign.status == 'active':
        followup_campaign.status = 'paused'
        followup_campaign.save()
        
        messages.success(request, f"Follow-up campaign '{followup_campaign.name}' paused successfully!")
    else:
        messages.warning(request, "Only active campaigns can be paused.")
    
    # TEMPORARY FIX: Use direct URL instead of reverse
    return redirect(f'/followups/campaign/{followup_id}/')


def followup_analytics(request, followup_id):
    """Detailed analytics for follow-up campaign"""
    context = get_user_context(request)
    user_id = request.session.get("user_id")
    
    followup_campaign = get_object_or_404(FollowUpCampaign, id=followup_id, user_id=user_id)
    analytics = get_object_or_404(FollowUpAnalytics, followup_campaign=followup_campaign)
    
    # Get sequence-wise data for charts
    sequences_data = []
    for seq in followup_campaign.sequences.all():
        seq_trackings = FollowUpTracking.objects.filter(
            followup_campaign=followup_campaign,
            sequence_number=seq.sequence_number
        )
        
        sequences_data.append({
            'sequence_number': seq.sequence_number,
            'subject': seq.subject,
            'sent_count': seq_trackings.count(),
            'open_count': seq_trackings.filter(is_opened=True).count(),
            'click_count': seq_trackings.filter(is_clicked=True).count(),
            'sent_at': seq.sent_at,
        })
    
    context.update({
        'followup_campaign': followup_campaign,
        'analytics': analytics,
        'sequences_data': sequences_data,
    })
    
    return render(request, 'followups/analytics.html', context)

def get_campaigns_for_followup(request):
    """Get user's sent campaigns for follow-up creation"""
    user_id = request.session.get("user_id")
    
    campaigns = Campaign.objects.filter(
        user_id=user_id, 
        is_sent=True,
        is_deleted=False
    ).order_by('-created_at')
    
    campaigns_data = []
    for campaign in campaigns:
        trackings = EmailTracking.objects.filter(campaign=campaign, is_failed=False)
        non_openers = trackings.filter(is_opened=False).count()
        non_clickers = trackings.filter(is_clicked=False).count()
        
        campaigns_data.append({
            'id': campaign.id,
            'name': campaign.name,
            'sent_count': trackings.count(),
            'non_openers': non_openers,
            'non_clickers': non_clickers,
            'created_at': campaign.created_at.strftime('%Y-%m-%d'),
            'create_url': f'/followups/create/{campaign.id}/'  # ✅ YEH LINE ADD KARO
        })
    
    return JsonResponse({'campaigns': campaigns_data})

def check_followup_credit(request):
    """Check if user has enough credits for follow-up"""
    user_id = request.session.get("user_id")
    user = get_object_or_404(CustomUser, uid=user_id)
    
    # Estimate credits needed (non-responsive recipients)
    campaign_id = request.GET.get('campaign_id')
    if campaign_id:
        campaign = get_object_or_404(Campaign, id=campaign_id, user_id=user_id)
        trackings = EmailTracking.objects.filter(campaign=campaign, is_failed=False)
        
        if campaign.followup_campaigns.exists():
            # Already has follow-up, count only active non-responders
            existing_followup = campaign.followup_campaigns.first()
            active_trackings = FollowUpTracking.objects.filter(
                followup_campaign=existing_followup,
                is_active=True
            ).count()
            estimated_credits = active_trackings
        else:
            # New follow-up, count all non-responders based on settings
            stop_on_open = request.GET.get('stop_on_open') == 'true'
            stop_on_click = request.GET.get('stop_on_click') == 'true'
            
            if stop_on_open and stop_on_click:
                non_responders = trackings.filter(is_opened=False, is_clicked=False).count()
            elif stop_on_open:
                non_responders = trackings.filter(is_opened=False).count()
            elif stop_on_click:
                non_responders = trackings.filter(is_clicked=False).count()
            else:
                non_responders = trackings.count()
            
            estimated_credits = non_responders
    
    credits_left = max(0, user.email_credit_limit - user.used_email_credit)
    
    return JsonResponse({
        'credits_left': credits_left,
        'estimated_credits': estimated_credits,
        'has_sufficient_credits': credits_left >= estimated_credits,
    })
    
    



def track_followup_open(request, followup_id, email, sequence_number):
    """
    Track when a follow-up email is opened
    """
    try:
        FollowUpTracking.objects.filter(
            followup_campaign_id=followup_id,
            recipient=email,
            sequence_number=sequence_number
        ).update(
            is_opened=True,
            open_timestamp=timezone.now()
        )
        
        # Update campaign additional opens count
        campaign = FollowUpCampaign.objects.get(id=followup_id)
        campaign.additional_opens = F('additional_opens') + 1
        campaign.save()
        
        # Update analytics
        analytics, created = FollowUpAnalytics.objects.get_or_create(followup_campaign=campaign)
        analytics.update_analytics()
        
    except Exception as e:
        logger.error(f"Error tracking follow-up open: {str(e)}")
    
    return HttpResponse(b"", content_type='image/gif')

def track_followup_click(request, followup_id, email, sequence_number):
    """
    Track when a link in follow-up email is clicked
    """
    try:
        FollowUpTracking.objects.filter(
            followup_campaign_id=followup_id,
            recipient=email,
            sequence_number=sequence_number
        ).update(
            is_clicked=True,
            click_timestamp=timezone.now(),
            is_opened=True,  # Also mark as opened
            open_timestamp=timezone.now()
        )
        
        # Update campaign additional clicks count
        campaign = FollowUpCampaign.objects.get(id=followup_id)
        campaign.additional_clicks = F('additional_clicks') + 1
        campaign.save()
        
        # Update analytics
        analytics, created = FollowUpAnalytics.objects.get_or_create(followup_campaign=campaign)
        analytics.update_analytics()
        
    except Exception as e:
        logger.error(f"Error tracking follow-up click: {str(e)}")
    
    redirect_url = request.GET.get('url', '/')
    return redirect(redirect_url)