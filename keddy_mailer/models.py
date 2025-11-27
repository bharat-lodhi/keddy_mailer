import random
import string
from django.db import models
from django.utils import timezone

def generate_alphanumeric_id():
    chars = string.ascii_uppercase + string.digits
    while True:
        uid = ''.join(random.choices(chars, k=10))
        # यह सुनिश्चित करे कि ID यूनिक हो
        if not CustomUser.objects.filter(uid=uid).exists():
            return uid

class CustomUser(models.Model):
    
    id = models.AutoField(primary_key=True)
    uid = models.CharField(
        max_length=10,
        default=generate_alphanumeric_id,
        editable=False,
        unique=True
    )
    
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    number = models.CharField(max_length=20)
    password = models.CharField(max_length=128)  # Plain text (NOT RECOMMENDED)
    dob = models.DateField()
    address = models.TextField()
    date = models.DateField(auto_now_add=True)
    time = models.TimeField(auto_now_add=True)
    role = models.CharField(max_length=20, default="user")
    company = models.CharField(max_length=100)
    email_credit_limit = models.BigIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    used_email_credit = models.BigIntegerField(default=0)
    profile_image = models.ImageField(
        upload_to='profile_pics/',
        default='profile_pics/default.jpg',
        null=True,
        blank=True
    )
    
    def __str__(self):
        return f"{self.uid}"    
    

class SMTPServer(models.Model):
    
    id = models.AutoField(primary_key=True)  # Auto-incrementing primary key
    user_id = models.CharField(max_length=100)
    
    name = models.CharField(max_length=100)
    host = models.CharField(max_length=255)
    port = models.IntegerField()
    username = models.CharField(max_length=130,unique=True)
    password = models.CharField(max_length=255)
    from_email = models.CharField(max_length=120)
    smtp_server = models.CharField(max_length=120)
    emails_per_hour = models.IntegerField()
    security = models.CharField(max_length=20)
    is_active = models.IntegerField(default=0) # 0=Inactive, 1=Active
    created_at = models.DateTimeField(auto_now_add=True)  # Auto-set on creation
    updated_at = models.DateTimeField(auto_now=True)      # Auto-updated on save
    show = models.IntegerField(default=0)

 
    def __str__(self):
        return f"SMTP: {self.host}"

class SMTPUsageLog(models.Model):
    smtp_server = models.ForeignKey(SMTPServer, on_delete=models.CASCADE, related_name='usage_logs')
    timestamp = models.DateTimeField(auto_now_add=True)  # Email sent time
    email_count = models.IntegerField(default=1)  # Number of emails sent in this event (default 1)

    def __str__(self):
        return f"{self.smtp_server.name} - {self.email_count} @ {self.timestamp}"


    

class email_list(models.Model):
    id = models.AutoField(primary_key=True)  # Auto-incrementing primary key
    
    user_id = models.CharField(max_length=100)
    list_name = models.CharField(max_length=255)  # Original file name
    
    file = models.FileField(upload_to='email_lists/')  # Actual file storage
    uploaded_at = models.DateTimeField(auto_now_add=True)  # Auto date/time


class template(models.Model):
    id = models.AutoField(primary_key=True)
    user_id = models.CharField(max_length=100, null=True, blank=True)
    template_name = models.CharField(max_length=100)
    content = models.TextField()
    uploaded_at = models.DateTimeField(auto_now_add=True)  # Auto date/time
    

class SubjectLineFile(models.Model):
    id = models.AutoField(primary_key=True)
    user_id = models.CharField(max_length=100)
    file_name = models.CharField(max_length=255)
    file = models.FileField(upload_to='subject_lines/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_name} - {self.user_id}"

    def get_all_subject_lines(self):
        """
        Extract all subject lines from file
        """
        try:
            file_extension = self.file.name.split('.')[-1].lower()
            subject_lines = []
            
            if file_extension in ['xlsx', 'xls']:
                # Excel file processing
                df = pd.read_excel(self.file.path)
                # Assuming first column contains subject lines
                subject_lines = df.iloc[:, 0].dropna().tolist()
            elif file_extension in ['txt']:
                # Text file processing
                with open(self.file.path, 'r', encoding='utf-8') as file:
                    subject_lines = [line.strip() for line in file if line.strip()]
            elif file_extension in ['csv']:
                # CSV file processing
                with open(self.file.path, 'r', encoding='utf-8') as file:
                    subject_lines = [line.strip().split(',')[0] for line in file if line.strip()]
            else:
                return []
                
            return subject_lines
            
        except Exception as e:
            print(f"Error reading subject line file: {e}")
            return []

    def get_random_subject_line(self):
        """
        Get one random subject line from all available
        """
        subject_lines = self.get_all_subject_lines()
        return random.choice(subject_lines) if subject_lines else None



class Campaign(models.Model):
    name = models.CharField(max_length=100)
    reply_to = models.EmailField()
    email_list = models.ForeignKey(email_list,on_delete=models.SET_NULL, null=True, blank=True)
    subject = models.CharField(max_length=255)
    template = models.ForeignKey(template, on_delete=models.SET_NULL, null=True, blank=True)
    preheader = models.CharField(max_length=255, blank=True)
    smtp_server = models.ForeignKey(SMTPServer, on_delete=models.SET_NULL, null=True, blank=True)
    sender_name = models.CharField(max_length=100)
    attachments = models.FileField(upload_to='attachments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user_id = models.CharField(max_length=100)
    scheduled_time = models.DateTimeField(null=True, blank=True)
    is_sent = models.BooleanField(default=False)  # To avoid duplicate send
    manual_recipients = models.TextField(null=True, blank=True)  # to store comma/newline separated emails
    custom_template = models.TextField(null=True, blank=True)    # to store manually written template
    cta_text = models.CharField(max_length=200, blank=True, null=True) 
    cta_url = models.URLField(max_length=500, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    
    # ----------------------------------
    subject_line_file = models.ForeignKey(
        SubjectLineFile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='campaigns'
    )
    
    # NEW FIELD: Track which subject was used for tracking
    used_subject_line = models.TextField(null=True, blank=True)
    # ------------------------------------
    
    @property
    def status(self):
        now = timezone.now()
        if self.is_sent:
            return "Sent"
        elif self.scheduled_time:
            return "Scheduled" if self.scheduled_time > now else "Pending"
        else:
            return "Pending"

    def __str__(self):
        return f"{self.name} ({self.status})"


class CampaignAttachment(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='attachment_files')
    file = models.FileField(upload_to="attachments/")


class EmailTracking(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    recipient = models.EmailField()
    sent_at = models.DateTimeField(auto_now_add=True)
    
    is_opened = models.BooleanField(default=False)
    open_timestamp = models.DateTimeField(null=True, blank=True)
    
    is_clicked = models.BooleanField(default=False)
    click_timestamp = models.DateTimeField(null=True, blank=True)
    
    is_failed = models.BooleanField(default=False)  # NEW FIELD
    error_message = models.TextField(null=True, blank=True)  # To store SMTP error if any

    def __str__(self):
        return f"{self.recipient} - {self.campaign.name}"

    
    
 
class UnsubscribedEmail(models.Model):
    email = models.EmailField(unique=True)
    unsubscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email
   

# =============================== for Chat ============================================

class ChatMessage(models.Model):
    sender_email = models.EmailField()
    receiver_email = models.EmailField()
    message = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.sender_email} → {self.receiver_email} : {self.message[:20]}"
