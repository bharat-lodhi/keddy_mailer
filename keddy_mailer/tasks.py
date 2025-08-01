from celery import shared_task
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import re
import time
from urllib.parse import quote
from django.utils import timezone
from django.db.models import F
from datetime import timedelta
from premailer import transform

@shared_task (bind=True, max_retries=10)
def send_bulk_emails_task(self,smtp_data,reply_to,from_email, subject, body_template, recipients, preheader, attachment_path,sender_name,campaign_id):

    from smtplib import SMTP, SMTP_SSL
    from django.db.models import Sum
    import ssl
    from .utils import get_hourly_email_count
    from .models import EmailTracking ,UnsubscribedEmail,Campaign,CustomUser,CampaignAttachment,SMTPServer,SMTPUsageLog

    # attachment_files = CampaignAttachment.objects.filter(campaign_id=campaign_id)

    # Set up SMTP connection properly based on security
    if smtp_data['security'].lower() == 'ssl':
        context = ssl.create_default_context()
        server = SMTP_SSL(smtp_data['host'], smtp_data['port'], context=context)
        server.ehlo()
    elif smtp_data['security'].lower() == 'tls':
        server = SMTP(smtp_data['host'], smtp_data['port'])
        server.ehlo()
        server.starttls()
        server.ehlo()
    else:
        server = SMTP(smtp_data['host'], smtp_data['port'])  
        

    server.login(smtp_data['username'], smtp_data['password'])  
    

    # ✅ Hourly Limit Check (Before Loop)
    smtp_obj = SMTPServer.objects.filter(username=smtp_data['username']).first()
    if smtp_obj:
        hourly_limit = smtp_obj.emails_per_hour

        current_hour_count = get_hourly_email_count(smtp_obj)

        if current_hour_count >= hourly_limit:
            print(f"⏳ Hourly limit reached for SMTP: {smtp_obj.name}. Retrying in 1 hour.")
            raise self.retry(countdown=3650)  # Celery retry

  
    
    for recipient in recipients:
        email = recipient.get("email")
        name = recipient.get("name", "")  # blank if name is missing

        if UnsubscribedEmail.objects.filter(email=email).exists():
            print(f"Skipping unsubscribed email: {email}")
            continue

        hidden_preheader = f'<span style="display:none; max-height:0px; overflow:hidden;">{preheader}</span>'

        body = body_template.replace("{{email}}", email)\
                            .replace("{{name}}", name)\
                            .replace("{{preheader}}", preheader)\
                            .replace("{{campaign_id}}", str(campaign_id))
                    
        # body = hidden_preheader + body    
        body = hidden_preheader + transform(body)

        msg = MIMEMultipart()
        msg['From'] = f"{sender_name} <{from_email}>"
        msg['To'] = email
        msg['Subject'] = subject
        msg['Reply-To'] = reply_to
        
        msg.attach(MIMEText(body, 'html'))
        
        attachment_files = CampaignAttachment.objects.filter(campaign_id=campaign_id)

        
        for attach in attachment_files:
            with open(attach.file.path, 'rb') as f:
                part = MIMEApplication(f.read(), Name=attach.file.name)
                part['Content-Disposition'] = f'attachment; filename="{attach.file.name}"'
                msg.attach(part)
                
            


        try:
            server.sendmail(from_email, email, msg.as_string())

            
            obj = Campaign.objects.filter(id=campaign_id).first()   
            CustomUser.objects.filter(uid=obj.user_id).update(
                used_email_credit=F('used_email_credit') + 1
            )   
                
            
            EmailTracking.objects.create(
            campaign_id=campaign_id,
            recipient=email
            )
            
            smtp_obj = SMTPServer.objects.filter(username=smtp_data['username']).first()
            
            if smtp_obj:
                SMTPUsageLog.objects.create(
                    smtp_server=smtp_obj,
                    email_count=1
                )

            print(f"📨 Email sent to {email}")
        except Exception as e:
            print(f"❌ Failed to send email to {email}: {e}")
        
        time.sleep(1)  # every mail send after 2 seconds

    server.quit()
    
    # ✅ Mark campaign as sent
    try:
        campaign = Campaign.objects.get(id=campaign_id)
        campaign.is_sent = True
        campaign.scheduled_time = timezone.now()  # Optional
        campaign.save()
        print(f"✅ Campaign {campaign_id} marked as sent.")
    except Campaign.DoesNotExist:
        print(f"⚠️ Campaign with ID {campaign_id} not found.")
    
    return f"{len(recipients)} emails sent."






# from celery import shared_task
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# from email.mime.application import MIMEApplication
# import ssl

# @shared_task
# def send_bulk_emails_task(
#     smtp_data, reply_to, from_email, subject, body_template,
#     recipients, placeholder_text, attachment_path, sender_name,
#     is_html=False  # ✅ new flag to detect content type
# ):
#     from smtplib import SMTP, SMTP_SSL

#     # Set up SMTP server connection
#     if smtp_data['security'].lower() == 'ssl':
#         context = ssl.create_default_context()
#         server = SMTP_SSL(smtp_data['host'], smtp_data['port'], context=context)
#         server.ehlo()
#     elif smtp_data['security'].lower() == 'tls':
#         server = SMTP(smtp_data['host'], smtp_data['port'])
#         server.ehlo()
#         server.starttls()
#         server.ehlo()
#     else:
#         server = SMTP(smtp_data['host'], smtp_data['port'])

#     server.login(smtp_data['username'], smtp_data['password'])

#     for email in recipients:
#         # Replace placeholder with actual text
#         body = body_template.replace("{{placeholder}}", placeholder_text)

#         msg = MIMEMultipart()
#         msg['From'] = f"{sender_name} <{from_email}>"
#         msg['To'] = email
#         msg['Subject'] = subject
#         msg['Reply-To'] = reply_to

#         # ✅ Set body type based on is_html flag
#         content_type = 'html' if is_html else 'plain'
#         msg.attach(MIMEText(body, content_type))
        
        

#         # ✅ Attach file if provided
#         if attachment_path:
#             with open(attachment_path, 'rb') as f:
#                 part = MIMEApplication(f.read())
#                 part['Content-Disposition'] = f'attachment; filename="{attachment_path.split("/")[-1]}"'
#                 msg.attach(part)

#         server.sendmail(from_email, email, msg.as_string())
#         print(f"📨 Email sent to {email}")

#     server.quit()
#     return f"{len(recipients)} emails sent."
