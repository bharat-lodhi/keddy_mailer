# followups/models.py

from django.db import models
from django.utils import timezone
from keddy_mailer.models import Campaign, EmailTracking, CustomUser, template, SMTPServer

class FollowUpCampaign(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'), 
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    )
    
    id = models.AutoField(primary_key=True)
    original_campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='followup_campaigns')
    name = models.CharField(max_length=200)
    user_id = models.CharField(max_length=100)
    
    # Follow-up settings (User input)
    max_followups = models.IntegerField(default=3)  # Kitne follow-up jaye (1-11)
    days_between = models.IntegerField(default=2)   # Kitne din ka gap
    trigger_time = models.TimeField(default='11:00')  # Konsi time pe bhejna (11:00 AM default)
    stop_on_open = models.BooleanField(default=True)
    stop_on_click = models.BooleanField(default=True)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    current_sequence = models.IntegerField(default=0)  # Kaunsa follow-up chalu hai
    
    # Analytics
    total_emails_sent = models.IntegerField(default=0)
    total_credits_used = models.IntegerField(default=0)
    additional_opens = models.IntegerField(default=0)
    additional_clicks = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"FollowUp: {self.name}"
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    @property
    def progress_percentage(self):
        if self.max_followups == 0:
            return 0
        return (self.current_sequence / self.max_followups) * 100

class FollowUpSequence(models.Model):
    id = models.AutoField(primary_key=True)
    followup_campaign = models.ForeignKey(FollowUpCampaign, on_delete=models.CASCADE, related_name='sequences')
    sequence_number = models.IntegerField()  # 1, 2, 3, ... (max 11)
    
    # Email content
    subject = models.CharField(max_length=255)
    body = models.TextField()
    template = models.ForeignKey(template, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Timing
    days_after_previous = models.IntegerField(default=2)
    
    # Tracking
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    total_sent = models.IntegerField(default=0)
    credits_used = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['sequence_number']
        unique_together = ['followup_campaign', 'sequence_number']
    
    def __str__(self):
        return f"FollowUp #{self.sequence_number} - {self.followup_campaign.name}"

class FollowUpTracking(models.Model):
    id = models.AutoField(primary_key=True)
    followup_campaign = models.ForeignKey(FollowUpCampaign, on_delete=models.CASCADE)
    original_tracking = models.ForeignKey(EmailTracking, on_delete=models.CASCADE)
    recipient = models.EmailField()
    sequence_number = models.IntegerField()
    
    # Email sending tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    is_failed = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)
    credit_deducted = models.BooleanField(default=False)
    
    # Response tracking
    is_opened = models.BooleanField(default=False)
    open_timestamp = models.DateTimeField(null=True, blank=True)
    is_clicked = models.BooleanField(default=False)
    click_timestamp = models.DateTimeField(null=True, blank=True)
    
    # Stop condition tracking
    is_active = models.BooleanField(default=True)  # False if user opened/clicked and stop condition is on
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['followup_campaign', 'recipient', 'sequence_number']
        indexes = [
            models.Index(fields=['followup_campaign', 'recipient']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.recipient} - FollowUp #{self.sequence_number}"

class FollowUpAnalytics(models.Model):
    id = models.AutoField(primary_key=True)
    followup_campaign = models.OneToOneField(FollowUpCampaign, on_delete=models.CASCADE, related_name='analytics')
    
    # Overall stats
    total_recipients = models.IntegerField(default=0)
    total_followups_sent = models.IntegerField(default=0)
    total_credits_used = models.IntegerField(default=0)
    
    # Performance metrics
    overall_open_rate = models.FloatField(default=0.0)
    overall_click_rate = models.FloatField(default=0.0)
    additional_conversions = models.IntegerField(default=0)
    
    # Sequence-wise performance
    sequence_1_sent = models.IntegerField(default=0)
    sequence_1_opens = models.IntegerField(default=0)
    sequence_1_clicks = models.IntegerField(default=0)
    
    sequence_2_sent = models.IntegerField(default=0)
    sequence_2_opens = models.IntegerField(default=0)
    sequence_2_clicks = models.IntegerField(default=0)
    
    sequence_3_sent = models.IntegerField(default=0)
    sequence_3_opens = models.IntegerField(default=0)
    sequence_3_clicks = models.IntegerField(default=0)
    
    # Add more sequences as needed up to 11
    
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Analytics - {self.followup_campaign.name}"
    
    def update_analytics(self):
        """Update analytics data from tracking records"""
        from django.db.models import Count, Q
        
        # Calculate overall stats
        trackings = FollowUpTracking.objects.filter(followup_campaign=self.followup_campaign)
        
        self.total_followups_sent = trackings.count()
        self.total_opens = trackings.filter(is_opened=True).count()
        self.total_clicks = trackings.filter(is_clicked=True).count()
        
        # Calculate rates
        if self.total_followups_sent > 0:
            self.overall_open_rate = (self.total_opens / self.total_followups_sent) * 100
            self.overall_click_rate = (self.total_clicks / self.total_followups_sent) * 100
        
        self.save()