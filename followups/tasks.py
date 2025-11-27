# followups/tasks.py (COMPLETE FIXED VERSION)
from celery import shared_task
from django.utils import timezone
from django.db.models import Count, Q, F
from datetime import timedelta
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import requests
from django.conf import settings
from django.urls import reverse

from .models import FollowUpCampaign, FollowUpSequence, FollowUpTracking, FollowUpAnalytics
from keddy_mailer.models import EmailTracking, CustomUser, SMTPUsageLog

logger = logging.getLogger(__name__)

@shared_task(name='followups.process_followup_campaigns')
def process_followup_campaigns():
    """
    Main task that runs regularly to process all active follow-up campaigns
    """
    try:
        logger.info("🔄 Starting follow-up campaigns processing...")
        
        # Get all active follow-up campaigns
        active_campaigns = FollowUpCampaign.objects.filter(status='active')
        logger.info(f"Found {active_campaigns.count()} active follow-up campaigns")
        
        for campaign in active_campaigns:
            try:
                process_single_followup_campaign(campaign)
            except Exception as e:
                logger.error(f"Error processing follow-up campaign {campaign.id}: {str(e)}")
                continue
        
        logger.info("✅ Follow-up campaigns processing completed")
        
    except Exception as e:
        logger.error(f"Error in process_followup_campaigns: {str(e)}")

def process_single_followup_campaign(campaign):
    """
    Process a single follow-up campaign
    """
    logger.info(f"Processing follow-up campaign: {campaign.name} (ID: {campaign.id})")
    
    # Check if campaign is completed
    if campaign.current_sequence >= campaign.max_followups:
        campaign.status = 'completed'
        campaign.completed_at = timezone.now()
        campaign.save()
        logger.info(f"Campaign {campaign.name} completed all sequences")
        return
    
    # Determine next sequence to send
    next_sequence_number = campaign.current_sequence + 1
    
    try:
        next_sequence = FollowUpSequence.objects.get(
            followup_campaign=campaign,
            sequence_number=next_sequence_number
        )
    except FollowUpSequence.DoesNotExist:
        logger.error(f"Sequence #{next_sequence_number} not found for campaign {campaign.name}")
        return
    
    # Check timing for this sequence
    if not should_send_sequence(campaign, next_sequence):
        logger.info(f"Sequence #{next_sequence_number} not ready to send for campaign {campaign.name}")
        return
    
    # Get recipients for this sequence
    recipients = get_recipients_for_sequence(campaign, next_sequence_number)
    
    if not recipients:
        logger.info(f"No recipients found for sequence #{next_sequence_number} in campaign {campaign.name}")
        
        # If no recipients, move to next sequence or complete campaign
        if next_sequence_number >= campaign.max_followups:
            campaign.status = 'completed'
            campaign.completed_at = timezone.now()
            campaign.save()
        else:
            campaign.current_sequence = next_sequence_number
            campaign.save()
        return
    
    # Send follow-up emails
    logger.info(f"Sending sequence #{next_sequence_number} to {len(recipients)} recipients")
    send_followup_sequence.delay(campaign.id, next_sequence.id, [r['email'] for r in recipients])

def should_send_sequence(campaign, sequence):
    """
    Check if a sequence should be sent based on timing
    """
    now = timezone.now()
    
    if sequence.sequence_number == 1:
        # First follow-up - check days after original campaign
        original_sent_time = campaign.original_campaign.created_at
        required_time = original_sent_time + timedelta(days=campaign.days_between)
        
        # Also check time of day
        required_datetime = timezone.make_aware(
            timezone.datetime.combine(required_time.date(), campaign.trigger_time)
        )
        
        return now >= required_datetime
    
    else:
        # Subsequent follow-ups - check previous sequence sent time
        try:
            prev_sequence = FollowUpSequence.objects.get(
                followup_campaign=campaign,
                sequence_number=sequence.sequence_number - 1
            )
            
            if not prev_sequence.is_sent:
                return False
            
            required_time = prev_sequence.sent_at + timedelta(days=sequence.days_after_previous)
            
            # Check time of day
            required_datetime = timezone.make_aware(
                timezone.datetime.combine(required_time.date(), campaign.trigger_time)
            )
            
            return now >= required_datetime
            
        except FollowUpSequence.DoesNotExist:
            return False

def get_recipients_for_sequence(campaign, sequence_number):
    """
    Get list of recipients who should receive this follow-up sequence
    """
    recipients = []
    
    # Get original campaign trackings
    original_trackings = EmailTracking.objects.filter(
        campaign=campaign.original_campaign,
        is_failed=False
    )
    
    for tracking in original_trackings:
        recipient_email = tracking.recipient
        
        # Check if recipient already received this sequence
        existing_followup = FollowUpTracking.objects.filter(
            followup_campaign=campaign,
            recipient=recipient_email,
            sequence_number=sequence_number
        ).exists()
        
        if existing_followup:
            continue
        
        # Check stop conditions based on previous follow-ups
        if should_stop_followups(campaign, recipient_email):
            continue
        
        # Check if recipient should be excluded based on original campaign response
        if should_exclude_recipient(campaign, tracking):
            continue
        
        recipients.append({
            'email': recipient_email,
            'name': ''  # Name can be extracted if available
        })
    
    return recipients

def should_stop_followups(campaign, recipient_email):
    """
    Check if follow-ups should stop for a recipient based on previous responses
    """
    if not campaign.stop_on_open and not campaign.stop_on_click:
        return False
    
    # Check previous follow-up responses
    previous_followups = FollowUpTracking.objects.filter(
        followup_campaign=campaign,
        recipient=recipient_email,
        sequence_number__lt=campaign.current_sequence + 1
    )
    
    for followup in previous_followups:
        if campaign.stop_on_open and followup.is_opened:
            return True
        if campaign.stop_on_click and followup.is_clicked:
            return True
    
    return False

def should_exclude_recipient(campaign, original_tracking):
    """
    Check if recipient should be excluded based on original campaign response
    """
    # If original email was opened/clicked and stop conditions are set
    if campaign.stop_on_open and original_tracking.is_opened:
        return True
    if campaign.stop_on_click and original_tracking.is_clicked:
        return True
    
    return False

@shared_task(name='followups.send_followup_sequence')
def send_followup_sequence(campaign_id, sequence_id, recipient_emails):
    """
    Send a specific follow-up sequence to recipients
    """
    try:
        campaign = FollowUpCampaign.objects.get(id=campaign_id)
        sequence = FollowUpSequence.objects.get(id=sequence_id)
        
        logger.info(f"Sending follow-up sequence #{sequence.sequence_number} for campaign {campaign.name} to {len(recipient_emails)} recipients")
        
        # Get SMTP server details
        smtp_server = campaign.original_campaign.smtp_server
        
        successful_sends = 0
        
        # Send emails to each recipient
        for recipient_email in recipient_emails:
            try:
                # Send the actual email
                send_single_followup_email(
                    smtp_server=smtp_server,
                    recipient_email=recipient_email,
                    subject=sequence.subject,
                    body=sequence.body,
                    campaign=campaign,
                    sequence=sequence
                )
                
                successful_sends += 1
                
            except Exception as e:
                logger.error(f"Failed to send follow-up to {recipient_email}: {str(e)}")
                # Create failed tracking record
                FollowUpTracking.objects.create(
                    followup_campaign=campaign,
                    original_tracking=EmailTracking.objects.filter(
                        campaign=campaign.original_campaign,
                        recipient=recipient_email
                    ).first(),
                    recipient=recipient_email,
                    sequence_number=sequence.sequence_number,
                    is_failed=True,
                    error_message=str(e)
                )
        
        # Update sequence and campaign
        sequence.is_sent = True
        sequence.sent_at = timezone.now()
        sequence.total_sent = successful_sends
        sequence.credits_used = successful_sends
        sequence.save()
        
        campaign.current_sequence = sequence.sequence_number
        campaign.total_emails_sent += successful_sends
        campaign.total_credits_used += successful_sends
        campaign.save()
        
        # Update user credits
        user = CustomUser.objects.filter(uid=campaign.user_id).first()
        if user:
            user.used_email_credit = F('used_email_credit') + successful_sends
            user.save()
        
        # Update SMTP usage
        SMTPUsageLog.objects.create(
            smtp_server=smtp_server,
            email_count=successful_sends
        )
        
        # Update analytics
        update_followup_analytics(campaign)
        
        logger.info(f"✅ Successfully sent sequence #{sequence.sequence_number} to {successful_sends} recipients")
        
    except Exception as e:
        logger.error(f"Error in send_followup_sequence: {str(e)}")

def send_single_followup_email(smtp_server, recipient_email, subject, body, campaign, sequence):
    """
    Send a single follow-up email with proper tracking
    """
    try:
        # Add tracking to email body
        tracking_body = add_tracking_to_body(body, campaign, sequence, recipient_email)
        
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{campaign.original_campaign.sender_name} <{smtp_server.from_email}>"
        msg['To'] = recipient_email
        msg['Reply-To'] = campaign.original_campaign.reply_to
        
        # Generate tracking URLs
        tracking_pixel_url = generate_tracking_pixel_url(campaign, sequence, recipient_email)
        
        # Create HTML content with tracking
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{subject}</title>
        </head>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                {tracking_body}
                
                <!-- Tracking pixel -->
                <img src="{tracking_pixel_url}" 
                     width="1" height="1" style="display:none;" alt=""/>
                
                <!-- Unsubscribe link -->
                <div style="margin-top: 20px; padding: 10px; text-align: center; font-size: 12px; color: #666;">
                    <p>
                        <a href="{generate_unsubscribe_url(recipient_email)}" style="color: #666;">
                            Unsubscribe from these emails
                        </a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Attach HTML content
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send email using SMTP
        if smtp_server.security == 'tls':
            server = smtplib.SMTP(smtp_server.host, smtp_server.port)
            server.starttls()
        elif smtp_server.security == 'ssl':
            server = smtplib.SMTP_SSL(smtp_server.host, smtp_server.port)
        else:
            server = smtplib.SMTP(smtp_server.host, smtp_server.port)
        
        server.login(smtp_server.username, smtp_server.password)
        server.send_message(msg)
        server.quit()
        
        # Create successful tracking record
        original_tracking = EmailTracking.objects.filter(
            campaign=campaign.original_campaign,
            recipient=recipient_email
        ).first()
        
        FollowUpTracking.objects.create(
            followup_campaign=campaign,
            original_tracking=original_tracking,
            recipient=recipient_email,
            sequence_number=sequence.sequence_number,
            sent_at=timezone.now(),
            credit_deducted=True
        )
        
        logger.info(f"✅ Follow-up email sent to {recipient_email}")
        
    except Exception as e:
        logger.error(f"❌ Failed to send follow-up email to {recipient_email}: {str(e)}")
        raise e

def add_tracking_to_body(body, campaign, sequence, recipient_email):
    """
    Add tracking to links in email body and return modified body
    """
    import re
    
    # Convert line breaks to HTML
    body_html = body.replace('\n', '<br>')
    
    # Track all links in the body
    def add_tracking_to_link(match):
        url = match.group(1)
        tracking_url = generate_tracking_click_url(campaign, sequence, recipient_email, url)
        return f'href="{tracking_url}"'
    
    # Find all href attributes and add tracking
    body_with_tracking = re.sub(r'href="([^"]*)"', add_tracking_to_link, body_html)
    
    return body_with_tracking

def generate_tracking_pixel_url(campaign, sequence, recipient_email):
    """
    Generate tracking pixel URL for open tracking
    """
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    return f"{base_url}/followups/track/open/{campaign.id}/{recipient_email}/{sequence.sequence_number}/"

def generate_tracking_click_url(campaign, sequence, recipient_email, original_url):
    """
    Generate tracking URL for click tracking
    """
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    return f"{base_url}/followups/track/click/{campaign.id}/{recipient_email}/{sequence.sequence_number}/?url={original_url}"

def generate_unsubscribe_url(email):
    """
    Generate unsubscribe URL
    """
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    return f"{base_url}/unsubscribe/{email}/"

def update_followup_analytics(campaign):
    """
    Update analytics for a follow-up campaign
    """
    try:
        analytics, created = FollowUpAnalytics.objects.get_or_create(
            followup_campaign=campaign
        )
        
        # Get tracking statistics
        trackings = FollowUpTracking.objects.filter(followup_campaign=campaign)
        
        analytics.total_followups_sent = trackings.count()
        analytics.total_opens = trackings.filter(is_opened=True).count()
        analytics.total_clicks = trackings.filter(is_clicked=True).count()
        
        # Calculate rates
        if analytics.total_followups_sent > 0:
            analytics.overall_open_rate = (analytics.total_opens / analytics.total_followups_sent) * 100
            analytics.overall_click_rate = (analytics.total_clicks / analytics.total_followups_sent) * 100
        
        # Calculate additional conversions
        original_opens = EmailTracking.objects.filter(
            campaign=campaign.original_campaign,
            is_opened=True
        ).count()
        
        original_clicks = EmailTracking.objects.filter(
            campaign=campaign.original_campaign,
            is_clicked=True
        ).count()
        
        analytics.additional_conversions = max(0, analytics.total_opens - original_opens)
        
        analytics.save()
        
        logger.info(f"Updated analytics for campaign {campaign.name}")
        
    except Exception as e:
        logger.error(f"Error updating analytics for campaign {campaign.id}: {str(e)}")

@shared_task(name='followups.cleanup_old_followups')
def cleanup_old_followups():
    """
    Clean up old completed follow-up campaigns
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=90)
        old_campaigns = FollowUpCampaign.objects.filter(
            status='completed',
            completed_at__lt=cutoff_date
        )
        
        count = old_campaigns.count()
        old_campaigns.delete()
        
        logger.info(f"🧹 Cleaned up {count} old follow-up campaigns")
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_followups: {str(e)}")

# Manual trigger function for testing
def manually_trigger_followup(campaign_id):
    """
    Manually trigger a follow-up campaign for testing
    """
    try:
        campaign = FollowUpCampaign.objects.get(id=campaign_id)
        process_single_followup_campaign(campaign)
        return True
    except Exception as e:
        logger.error(f"Manual trigger failed: {str(e)}")
        return False