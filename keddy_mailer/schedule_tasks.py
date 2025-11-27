#schedule_tasks.py
 
from celery import shared_task
from django.utils import timezone
from .utils import extract_recipients_from_file, extract_recipients_from_text, generate_tracking_block

@shared_task(name='keddy_mailer.schedule_tasks.schedule_email_sender')
def schedule_email_sender():
    from .tasks import send_bulk_emails_task
    from .models import Campaign, SubjectLineFile

    print("🕒 Running scheduled task...")
    now = timezone.now()
    print("Current time:", now)
    
    campaigns = Campaign.objects.filter(scheduled_time__lte=now, is_sent=False)
    
    print(f"Found {campaigns.count()} campaign(s) to send...")

    for campaign in campaigns:
        print(f"📌 {campaign.name} | CTA: '{campaign.cta_text}'")
        print("⏩ Sending campaign:", campaign.name)

        smtp = campaign.smtp_server

        # ✅ Use manual recipients if provided
        if campaign.manual_recipients:
            recipients = extract_recipients_from_text(campaign.manual_recipients)
        else:
            recipients = extract_recipients_from_file(campaign.email_list.file.path)

        # ✅ Use custom template if provided
        if campaign.custom_template:
            body_template = campaign.custom_template
        else:
            body_template = campaign.template.content

        # ✅ NEW: Get random subject line if subject line file exists
        final_subject = campaign.subject
        subject_line_file_id = None
        
        if campaign.subject_line_file:
            random_subject = campaign.subject_line_file.get_random_subject_line()
            if random_subject:
                final_subject = random_subject
                campaign.used_subject_line = random_subject
                campaign.save()
                print(f"🎯 Using random subject line: {final_subject}")
            subject_line_file_id = campaign.subject_line_file.id

        tracking_block = generate_tracking_block(campaign)
        final_body = body_template + tracking_block

        print("Recipients count:", len(recipients))
        print("Calling send_bulk_emails_task...")

        smtp_data = {
            'host': smtp.host,
            'port': smtp.port,
            'username': smtp.username,
            'password': smtp.password,
            'security': smtp.security,
        }

        send_bulk_emails_task.delay(
            smtp_data=smtp_data,
            reply_to=campaign.reply_to,
            from_email=smtp.from_email,
            subject=final_subject,  # Use final_subject (could be random)
            body_template=final_body,
            recipients=recipients,
            preheader=campaign.preheader,
            attachment_path=campaign.attachments.path if campaign.attachments else None,
            sender_name=campaign.sender_name,
            campaign_id=campaign.id,
            # subject_line_file_id=subject_line_file_id  # NEW
        )

        campaign.is_sent = True
        campaign.save()
        
        print(f"✅ Campaign '{campaign.name}' marked as sent.")


# @shared_task(name='keddy_mailer.schedule_tasks.schedule_email_sender')
# def schedule_email_sender():
#     from .tasks import send_bulk_emails_task
#     from .models import Campaign

#     print("🕒 Running scheduled task...")
#     now = timezone.now()
#     print("Current time:", now)
    
#     campaigns = Campaign.objects.filter(scheduled_time__lte=now, is_sent=False)
    
#     print(f"Found {campaigns.count()} campaign(s) to send...")

#     for campaign in campaigns:
#         print(f"📌 {campaign.name} | CTA: '{campaign.cta_text}' | Attach: {campaign.attachments}")
#         print("⏩ Sending campaign:", campaign.name)

#         smtp = campaign.smtp_server

#         # ✅ Use manual recipients if provided
#         if campaign.manual_recipients:
#             recipients = extract_recipients_from_text(campaign.manual_recipients)
#         else:
#             recipients = extract_recipients_from_file(campaign.email_list.file.path)

#         # ✅ Use custom template if provided
#         if campaign.custom_template:
#             body_template = campaign.custom_template
#         else:
#             body_template = campaign.template.content

#         tracking_block = generate_tracking_block(campaign)
#         final_body = body_template + tracking_block
#         print("📧 FINAL BODY FOR SCHEDULED EMAIL:\n", final_body)


#         print("Recipients count:", len(recipients))
#         print("Calling send_bulk_emails_task...")

#         smtp_data = {
#             'host': smtp.host,
#             'port': smtp.port,
#             'username': smtp.username,
#             'password': smtp.password,
#             'security': smtp.security,
#         }

#         send_bulk_emails_task.delay(
#             smtp_data=smtp_data,
#             reply_to=campaign.reply_to,
#             from_email=smtp.from_email,
#             subject=campaign.subject,
#             body_template=final_body,
#             recipients=recipients,
#             preheader=campaign.preheader,
#             attachment_path=campaign.attachments.path if campaign.attachments else None,
#             sender_name=campaign.sender_name,
#             campaign_id=campaign.id,
#         )

#         campaign.is_sent = True
#         campaign.save()
        
#         print("📌 Tracking Debug:")
#         print("CTA TEXT:", repr(campaign.cta_text))
#         print("ATTACHMENT:", repr(campaign.attachments))

#         print(f"✅ Campaign '{campaign.name}' marked as sent.")
