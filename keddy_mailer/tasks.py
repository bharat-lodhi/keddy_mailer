#tasks.py

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


@shared_task(bind=True, max_retries=10)
def send_bulk_emails_task(self, smtp_data, reply_to, from_email, subject, body_template, recipients,
                          preheader, attachment_path, sender_name, campaign_id):

    from smtplib import SMTP, SMTP_SSL
    import ssl, time, random
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.application import MIMEApplication
    from django.db.models import F
    from django.utils import timezone
    from .models import (
        EmailTracking, UnsubscribedEmail, Campaign,
        CustomUser, CampaignAttachment, SMTPServer, SMTPUsageLog, SubjectLineFile
    )
    from .utils import get_hourly_email_count
    from premailer import transform  # for inline CSS if used

    # ✅ NEW: Load subject lines if campaign has subject_line_file
    all_subject_lines = []
    try:
        campaign_obj = Campaign.objects.get(id=campaign_id)
        if campaign_obj.subject_line_file:
            subject_line_file = campaign_obj.subject_line_file
            all_subject_lines = subject_line_file.get_all_subject_lines()
            print(f"📝 Loaded {len(all_subject_lines)} subject lines from file: {[s[:30] + '...' if len(s) > 30 else s for s in all_subject_lines]}")
    except Exception as e:
        print(f"⚠️ Error loading subject lines: {e}")

    # ✅ Setup SMTP Connection
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
        server.ehlo()

    server.login(smtp_data['username'], smtp_data['password'])

    # ✅ Check SMTP hourly limit
    smtp_obj = SMTPServer.objects.filter(username=smtp_data['username']).first()
    if smtp_obj:
        hourly_limit = smtp_obj.emails_per_hour
        current_hour_count = get_hourly_email_count(smtp_obj)
        if current_hour_count >= hourly_limit:
            print(f"⏳ Hourly limit reached for {smtp_obj.name}. Retrying in 1 hour.")
            raise self.retry(countdown=3600)

    # ✅ Track used subject lines for analytics
    used_subjects_info = []

    # ✅ Send Loop - WITH PER-EMAIL RANDOM SUBJECT
    for index, recipient in enumerate(recipients):
        email = recipient.get("email")
        name = recipient.get("name", "")

        # Skip unsubscribed users
        if UnsubscribedEmail.objects.filter(email=email).exists():
            print(f"⚠️ Skipping unsubscribed email: {email}")
            continue

        # ✅ NEW: Select random subject line for EACH email if available
        final_subject = subject  # Default to original subject
        if all_subject_lines:
            random_subject = random.choice(all_subject_lines)
            final_subject = random_subject
            used_subjects_info.append(f"{email}: {random_subject}")
            print(f"🎯 Email {index+1}/{len(recipients)}: Using random subject '{final_subject}' for {email}")

        hidden_preheader = f'<span style="display:none; max-height:0px; overflow:hidden;">{preheader}</span>'
        body = body_template.replace("{{email}}", email)\
                            .replace("{{name}}", name)\
                            .replace("{{preheader}}", preheader)\
                            .replace("{{campaign_id}}", str(campaign_id))
        body = hidden_preheader + transform(body)

        msg = MIMEMultipart()
        msg['From'] = f"{sender_name} <{from_email}>"
        msg['To'] = email
        msg['Subject'] = final_subject  # Different subject for each email if random
        msg['Reply-To'] = reply_to
        msg.attach(MIMEText(body, 'html'))

        # ✅ Attach files if any
        attachment_files = CampaignAttachment.objects.filter(campaign_id=campaign_id)
        for attach in attachment_files:
            with open(attach.file.path, 'rb') as f:
                part = MIMEApplication(f.read(), Name=attach.file.name)
                part['Content-Disposition'] = f'attachment; filename="{attach.file.name}"'
                msg.attach(part)

        # ✅ Try sending email
        try:
            server.sendmail(from_email, email, msg.as_string())

            # Track as SENT (no failure)
            EmailTracking.objects.create(
                campaign_id=campaign_id,
                recipient=email,
                is_opened=False,
                is_clicked=False,
                is_failed=False
            )

            # Update usage log and credit
            if smtp_obj:
                SMTPUsageLog.objects.create(smtp_server=smtp_obj, email_count=1)
            campaign = Campaign.objects.filter(id=campaign_id).first()
            if campaign:
                CustomUser.objects.filter(uid=campaign.user_id).update(
                    used_email_credit=F('used_email_credit') + 1
                )

            print(f"✅ Sent successfully → {email} with subject: '{final_subject}'")

        except Exception as e:
            # Track as FAILED
            EmailTracking.objects.create(
                campaign_id=campaign_id,
                recipient=email,
                is_failed=True,
                is_opened=False,
                is_clicked=False
            )
            print(f"❌ Failed to send email → {email}: {e}")

        # Sleep between emails to avoid spam trigger
        time.sleep(1)

    server.quit()

    # ✅ Mark campaign as sent and save used subject lines info
    try:
        campaign = Campaign.objects.get(id=campaign_id)
        campaign.is_sent = True
        campaign.scheduled_time = timezone.now()
        
        # ✅ NEW: Save used subject lines information
        if used_subjects_info:
            import json
            campaign.used_subject_line = json.dumps(used_subjects_info)
            print(f"📊 Saved {len(used_subjects_info)} email-subject mappings")
        
        campaign.save()
        print(f"📦 Campaign {campaign_id} marked as sent.")
        
        # ✅ NEW: Print summary of subject line usage
        if used_subjects_info:
            print("🎯 SUBJECT LINE USAGE SUMMARY:")
            for info in used_subjects_info[:5]:  # Show first 5
                print(f"   - {info}")
            if len(used_subjects_info) > 5:
                print(f"   ... and {len(used_subjects_info) - 5} more")
                
    except Campaign.DoesNotExist:
        print(f"⚠️ Campaign with ID {campaign_id} not found.")

    return f"{len(recipients)} emails processed."



# @shared_task(bind=True, max_retries=10)
# def send_bulk_emails_task(self, smtp_data, reply_to, from_email, subject, body_template, recipients,
#                           preheader, attachment_path, sender_name, campaign_id):

#     from smtplib import SMTP, SMTP_SSL
#     import ssl, time
#     from email.mime.multipart import MIMEMultipart
#     from email.mime.text import MIMEText
#     from email.mime.application import MIMEApplication
#     from django.db.models import F
#     from django.utils import timezone
#     from .models import (
#         EmailTracking, UnsubscribedEmail, Campaign,
#         CustomUser, CampaignAttachment, SMTPServer, SMTPUsageLog
#     )
#     from .utils import get_hourly_email_count
#     from premailer import transform  # for inline CSS if used

#     # ✅ Setup SMTP Connection
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
#         server.ehlo()

#     server.login(smtp_data['username'], smtp_data['password'])

#     # ✅ Check SMTP hourly limit
#     smtp_obj = SMTPServer.objects.filter(username=smtp_data['username']).first()
#     if smtp_obj:
#         hourly_limit = smtp_obj.emails_per_hour
#         current_hour_count = get_hourly_email_count(smtp_obj)
#         if current_hour_count >= hourly_limit:
#             print(f"⏳ Hourly limit reached for {smtp_obj.name}. Retrying in 1 hour.")
#             raise self.retry(countdown=3600)

#     # ✅ Send Loop
#     for recipient in recipients:
#         email = recipient.get("email")
#         name = recipient.get("name", "")

#         # Skip unsubscribed users
#         if UnsubscribedEmail.objects.filter(email=email).exists():
#             print(f"⚠️ Skipping unsubscribed email: {email}")
#             continue

#         hidden_preheader = f'<span style="display:none; max-height:0px; overflow:hidden;">{preheader}</span>'
#         body = body_template.replace("{{email}}", email)\
#                             .replace("{{name}}", name)\
#                             .replace("{{preheader}}", preheader)\
#                             .replace("{{campaign_id}}", str(campaign_id))
#         body = hidden_preheader + transform(body)

#         msg = MIMEMultipart()
#         msg['From'] = f"{sender_name} <{from_email}>"
#         msg['To'] = email
#         msg['Subject'] = subject
#         msg['Reply-To'] = reply_to
#         msg.attach(MIMEText(body, 'html'))

#         # ✅ Attach files if any
#         attachment_files = CampaignAttachment.objects.filter(campaign_id=campaign_id)
#         for attach in attachment_files:
#             with open(attach.file.path, 'rb') as f:
#                 part = MIMEApplication(f.read(), Name=attach.file.name)
#                 part['Content-Disposition'] = f'attachment; filename="{attach.file.name}"'
#                 msg.attach(part)

#         # ✅ Try sending email
#         try:
#             server.sendmail(from_email, email, msg.as_string())

#             # Track as SENT (no failure)
#             EmailTracking.objects.create(
#                 campaign_id=campaign_id,
#                 recipient=email,
#                 is_opened=False,
#                 is_clicked=False,
#                 is_failed=False
#             )

#             # Update usage log and credit
#             if smtp_obj:
#                 SMTPUsageLog.objects.create(smtp_server=smtp_obj, email_count=1)
#             campaign = Campaign.objects.filter(id=campaign_id).first()
#             if campaign:
#                 CustomUser.objects.filter(uid=campaign.user_id).update(
#                     used_email_credit=F('used_email_credit') + 1
#                 )

#             print(f"✅ Sent successfully → {email}")

#         except Exception as e:
#             # Track as FAILED
#             EmailTracking.objects.create(
#                 campaign_id=campaign_id,
#                 recipient=email,
#                 is_failed=True,
#                 is_opened=False,
#                 is_clicked=False
#             )
#             print(f"❌ Failed to send email → {email}: {e}")

#         # Sleep between emails to avoid spam trigger
#         time.sleep(1)

#     server.quit()

#     # ✅ Mark campaign as sent
#     try:
#         campaign = Campaign.objects.get(id=campaign_id)
#         campaign.is_sent = True
#         campaign.scheduled_time = timezone.now()
#         campaign.save()
#         print(f"📦 Campaign {campaign_id} marked as sent.")
#     except Campaign.DoesNotExist:
#         print(f"⚠️ Campaign with ID {campaign_id} not found.")

#     return f"{len(recipients)} emails processed."


