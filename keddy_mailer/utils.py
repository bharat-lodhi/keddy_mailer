import csv

import pandas as pd
import os
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta


# def get_hourly_email_count(smtp_server):
#     now = timezone.now()
#     one_hour_ago = now - timedelta(hours=1)

#     return SMTPUsageLog.objects.filter(
#         smtp_server=smtp_server,
#         timestamp__gte=one_hour_ago
#     ).aggregate(total=Sum('email_count'))['total'] or 0
    
    
def get_hourly_email_count(smtp_obj):
    from .models import SMTPUsageLog
    now = timezone.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    hour_end = hour_start + timedelta(hours=1)

    return SMTPUsageLog.objects.filter(
        smtp_server=smtp_obj,
        timestamp__range=(hour_start, hour_end)
    ).aggregate(total=Sum('email_count'))['total'] or 0
    

def extract_recipients_from_file(file_path):
    recipients = []

    # Use pandas to read both .csv and .xlsx
    try:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_path.endswith((".xls", ".xlsx")):
            df = pd.read_excel(file_path)
        else:
            raise ValueError("Unsupported file format")

        # Ensure 'email' and optional 'name' columns
        df.fillna("", inplace=True)

        for _, row in df.iterrows():
            email = row.get('email', '').strip()
            name = row.get('name', '').strip() if 'name' in row else ""
            print(f"name={name}, email = {email}","*"*50)
            if email:  # Ensure email exists
                recipients.append({"email": email, "name": name})
    except Exception as e:
        print("❌ Error reading file:", e)

    return recipients

import re

def extract_recipients_from_text(text):
    if not text:
        return []
    return [{"email": email.strip(), "name": ""} for email in re.split(r'[\n,]+', text) if email.strip()]


from urllib.parse import quote
from django.conf import settings

def generate_tracking_block(campaign):
    """
    Returns a tracking HTML block for open pixel, CTA button, unified download link, and unsubscribe link.
    """
    cta_text = campaign.cta_text.strip() if campaign.cta_text else ""
    cta_url = campaign.cta_url


    tracking_block = f"""
    <!-- 👁️ Invisible Pixel -->
    <img src="{settings.BASE_URL}/track_open/{campaign.id}/{{{{email}}}}" width="1" height="1" style="display:none;" />
    """

    # CTA Button
    if cta_text:
        tracking_block += f"""
        <p>
          <a href="{settings.BASE_URL}/track_click/{campaign.id}/{{{{email}}}}?url={ cta_url }"
             style="background-color:#28a745; color:#fff; padding:10px 20px; border-radius:6px; text-decoration:none;">
             {cta_text}
          </a>
        </p>
        """

    # 📦 Single unified download link
    if campaign.attachment_files.exists():
        download_link = f"{settings.BASE_URL}/track_attachment/{campaign.id}/{{{{email}}}}"
        tracking_block += f"""
        <p>
        <a href="{download_link}"
            style="text-decoration:underline; color:#1a73e8;" target="_blank">
            📎 Click here to download your file(s)
        </a>
        </p>
        """

    # Unsubscribe link
    tracking_block += f"""
    <p style="font-size:12px; color:#888;">
        <a href="{settings.BASE_URL}/subscription/{{{{email}}}}" style="color: #888; text-decoration: underline;">
          Unsubscribe
        </a>
    </p>
    """

    return tracking_block
