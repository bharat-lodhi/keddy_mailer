from django.shortcuts import render,redirect
from django.http import HttpResponse, FileResponse, Http404
from django.contrib.auth.hashers import make_password
from django.conf import settings

from django.utils.timezone import now

# -----------------file upload or view--------------------
from django.core.files.storage import FileSystemStorage
# -------------------------------------
from . import emailapi

# -----------------------Campaign---------------------------------------
import os
import csv
import xlrd
from django.conf import settings
from .models import Campaign, SMTPServer, email_list, template,CustomUser,UnsubscribedEmail,CampaignAttachment,SMTPUsageLog

from django.utils.timezone import make_aware
from datetime import datetime
from django.utils.dateparse import parse_datetime
from django.contrib import messages
from django.utils import timezone
from .utils import generate_tracking_block

# ----------------------------------------------------------------

def logout(request):
    request.session.flush()  
    return redirect('/')

def custom_page_not_found(request, exception):
    return render(request, '404.html', status=404)



def home(request):
    return render(request,"home.html")



def register(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        number = request.POST.get("number")
        password = request.POST.get("password")
        dob = request.POST.get("dob")
        address = request.POST.get("address")
        company = request.POST.get("company")

        if CustomUser.objects.filter(email=email).exists():
            return render(request, "register.html", {"msg": 2})  # Email already exists

        # Hash the password before saving
        hashed_password = make_password(password)

        obj = CustomUser(
            name=name,
            email=email,
            number=number,
            password=hashed_password,
            dob=dob,
            address=address,
            company=company,
            email_credit_limit = 200,
        )

        try:
            obj.save()
            return render(request, "register.html", {"msg": 1})  # Success
        except Exception as e:
            print(e)
            return render(request, "register.html")

    return render(request, "register.html")

from django.contrib.auth.hashers import check_password
from .models import CustomUser  # Make sure your CustomUser is correctly imported

def login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user = CustomUser.objects.get(email=email, is_active=True)
            if check_password(password, user.password):
                # Login successful
                request.session["email"] = user.email
                request.session["name"] = user.name
                request.session["user_id"] = user.uid
                request.session["role"] = user.role

                if user.role == "user":
                    return redirect("/userhome/")
                else:
                    return redirect("/adminhome/")
            else:
                # Wrong password
                return render(request, "login.html", {"msg": "Invalid Email or Password!"})
        except CustomUser.DoesNotExist:
            return render(request, "login.html", {"msg": "Invalid Email or Password!"})
    else:
        return render(request, "login.html")




from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils.timezone import now
from django.shortcuts import render
from .models import Campaign, EmailTracking, CustomUser
import json
from datetime import timedelta
from django.db.models import Count, Q, F
from django.db.models.functions import Coalesce

def userhome(request):
    try:
        user_id = request.session.get("user_id")
        user_name = request.session.get("name")

        # user = CustomUser.objects.get(uid=user_id)
        user = get_object_or_404(CustomUser, uid=user_id)
        # 📌 Credit Info
        used_credit = user.used_email_credit
        credit_limit = user.email_credit_limit
        credits_left = max(0, credit_limit - used_credit)
        try:
            credit_percent = int((credits_left / credit_limit) * 100)
        except ZeroDivisionError:
            credit_percent = 0
        
        # credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0
        
        
        user_campaigns = Campaign.objects.filter(user_id=user_id)
        # 📌 Lifetime Email Sent
        lifetime_sent = EmailTracking.objects.filter(campaign__in=user_campaigns).count()
        
        # 📌 Time Ranges
        today = now().date()
        start_of_month = today.replace(day=1)
        start_of_last_month = (start_of_month - timedelta(days=1)).replace(day=1)
        end_of_last_month = start_of_month - timedelta(days=1)

        # 📊 Last Month Stats
        last_month_campaigns = user_campaigns.filter(created_at__date__range=(start_of_last_month, end_of_last_month)).count()
        last_month_sent = EmailTracking.objects.filter(
            campaign__in=user_campaigns,
            sent_at__date__range=(start_of_last_month, end_of_last_month)
        ).count()
        last_month_clicks = EmailTracking.objects.filter(
            campaign__in=user_campaigns,
            sent_at__date__range=(start_of_last_month, end_of_last_month),
            is_clicked=True
        ).count()

        # 📊 Current Month Stats
        current_month_campaigns = user_campaigns.filter(created_at__date__gte=start_of_month).count()
        current_month_sent = EmailTracking.objects.filter(
            campaign__in=user_campaigns,
            sent_at__date__gte=start_of_month
        ).count()
        current_month_clicks = EmailTracking.objects.filter(
            campaign__in=user_campaigns,
            sent_at__date__gte=start_of_month,
            is_clicked=True
        ).count()

        # 📊 Today Stats
        today_campaigns = user_campaigns.filter(created_at__date=today).count()
        today_sent = EmailTracking.objects.filter(
            campaign__in=user_campaigns,
            sent_at__date=today
        ).count()
        today_clicks = EmailTracking.objects.filter(
            campaign__in=user_campaigns,
            sent_at__date=today,
            is_clicked=True
        ).count()

        # 📈 ChartJS Data
        labels = ["Last Month", "This Month", "Today"]
        campaigns_data = [last_month_campaigns, current_month_campaigns, today_campaigns]
        emails_data = [last_month_sent, current_month_sent, today_sent]
        clicks_data = [last_month_clicks, current_month_clicks, today_clicks]
        
        user_campaigns = Campaign.objects.filter(user_id=user_id)
        from django.db.models.functions import NullIf

        campaign_stats = (
            Campaign.objects
            .filter(user_id=user_id, is_sent=True)
            .annotate(
                total_sent=Count('emailtracking'),
                total_clicked=Count('emailtracking', filter=Q(emailtracking__is_clicked=True)),
            )

            .annotate(
                # click_rate=Coalesce(F('total_clicked') * 100.0 / F('total_sent'), 0.0)

                click_rate=Coalesce(
                    F('total_clicked') * 100.0 / NullIf(F('total_sent'), 0),
                    0.0
                ),

            )
            .order_by('-click_rate')[:5]
        )
        try:
            click_rate = f"{(current_month_clicks / current_month_sent * 100):.1f}%"
        except ZeroDivisionError:
            click_rate = "0%"

        # user = get_object_or_404(CustomUser, uid=user_id)
        context = {
            "uname": user_name,
            "user":user,
            "company_name": user.company,   
            "credit_limit": credit_limit,
            "credit_percent": credit_percent,
            "credits_left": credits_left,
            "click_rate": click_rate,
            # "click_rate": f"{(current_month_clicks / current_month_sent * 100):.1f}%" if current_month_sent else "0%",
            "total_sent": lifetime_sent,
            "monthly_sent": current_month_sent,
            "monthly_clicked": current_month_clicks,
            "labels": json.dumps(labels),
            "campaigns_data": json.dumps(campaigns_data),
            "emails_data": json.dumps(emails_data),
            "clicks_data": json.dumps(clicks_data),
            "top_campaigns":campaign_stats,

        }

        return render(request, "userhome.html", context)
    except Exception as e:
        print("Error in userhome view:", e)
        return render(request, "userhome.html",context)


# def add_server(request):
#     user_id = request.session.get("user_id")
#     uname = request.session.get("name")
    
#     email = request.session.get("email")

#     user = get_object_or_404(CustomUser, uid=user_id)
#     # 📌 Credit Info
#     used_credit = user.used_email_credit
#     credit_limit = user.email_credit_limit
#     credits_left = max(0, credit_limit - used_credit)
#     credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0
    
#     # obj = CustomUser.objects.get(uid=user_id)
#     company_name = user.company
#     context={
#         "company_name":company_name,
#         "uname":uname,
#         "user":user,
#         "company_name": user.company,  
#         "credit_limit": credit_limit,
#         "credit_percent": credit_percent,
#         "credits_left": credits_left,

#     }
    
#     if request.method=="POST":
    
#         name= request.POST.get("name")
#         host = request.POST.get("host")
#         port = request.POST.get("port")
#         username = request.POST.get("username")
#         smtp_server = request.POST.get("smtp_server")
#         password = request.POST.get("password")
#         from_email = request.POST.get("from_email")
#         emails_per_hour = request.POST.get("emails_per_hour")
#         security = request.POST.get("security")
#         user_id = user_id
        
#         try: 
#             obj = SMTPServer(user_id = user_id,name=name , host = host , port = port , username = username,smtp_server = smtp_server , password = password , from_email = from_email , emails_per_hour = emails_per_hour, security = security)
#             obj.save()
#             print("*"*70)
#             emailapi.sendEmail(username,password)
#             print("Mail send successfully ")
            
#             messages.success(request, "SMTP server added. A verification email has been sent. Please check your inbox and click the link to verify.")
#             return render(request,"add_server.html",context)
#         except Exception as e:
#             print(e)
#             messages.error(request, f"Failed to verify server: {str(e)}")
#             return render(request,"add_server.html",context)
#     else:   
#         return render(request,"add_server.html",context)


import smtplib
from email.mime.text import MIMEText
from django.shortcuts import get_object_or_404


def add_server(request):
    user_id = request.session.get("user_id")
    uname = request.session.get("name")
    email = request.session.get("email")

    user = get_object_or_404(CustomUser, uid=user_id)

    used_credit = user.used_email_credit
    credit_limit = user.email_credit_limit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0

    context = {
        "company_name": user.company,
        "uname": uname,
        "user": user,
        "credit_limit": credit_limit,
        "credit_percent": credit_percent,
        "credits_left": credits_left,
    }

    if request.method == "POST":
        name = request.POST.get("name")
        host = request.POST.get("host")
        port = int(request.POST.get("port"))
        username = request.POST.get("username")
        smtp_server = request.POST.get("smtp_server")
        password = request.POST.get("password")
        from_email = request.POST.get("from_email")
        emails_per_hour = request.POST.get("emails_per_hour")
        security = request.POST.get("security")

        # Create test email
        test_msg = MIMEText(f"""
        Hello {uname},

        This is a test email sent from your SMTP server via the Keddy Mailer platform.
        It was sent to verify that your SMTP settings (host, port, username, password, etc.) are correct.

        If you're seeing this, it means the connection was successful.

        Thank you,  
        Keddy Mailer Team
        """)
        test_msg["Subject"] = "SMTP Server Verification - Keddy Mailer"

        test_msg["From"] = "Keddy Mailer"
        test_msg["To"] = email

        try:
            if security == "SSL":
                server = smtplib.SMTP_SSL(host, port)
            else:
                server = smtplib.SMTP(host, port)
                if security == "TLS":
                    server.starttls()
            
            server.login(username, password)
            server.send_message(test_msg)
            server.quit()

            # ✅ Save only after successful test
            obj = SMTPServer(
                user_id=user_id,
                name=name,
                host=host,
                port=port,
                username=username,
                smtp_server=smtp_server,
                password=password,
                from_email=from_email,
                emails_per_hour=emails_per_hour,
                is_active = 1,
                security=security,
            )
            obj.save()

            messages.success(request, "SMTP server added and verified successfully. Test email sent.")
            return render(request, "add_server.html", context)

        except Exception as e:
            print("SMTP Test Error:", e)
            messages.error(request, f"SMTP verification failed: {str(e)}")
            return render(request, "add_server.html", context)

    else:
        return render(request, "add_server.html", context)






# def verify_server(request):
#     user_id = request.session.get("user_id")
#     vemail = request.GET.get('vemail')

#     if not user_id:
#         messages.error(request, "Session expired. Please log in again.")
#         return redirect('/login/')  # or wherever your login page is

#     try:
#         updated = SMTPServer.objects.filter(username=vemail).update(is_active=1)
#         if updated:
#             messages.success(request, "SMTP server added and verified successfully.")
#         else:
#             messages.error(request, "No matching server found or already verified.")
#     except Exception as e:
#         messages.error(request, f"Failed to verify server: {str(e)}")

#     return redirect("/add_server/")


# def smtp_server_list(request):
#     user_id = request.session.get("user_id")
#     smtp_servers = SMTPServer.objects.filter(user_id=user_id).order_by('-created_at')
#     user = get_object_or_404(CustomUser, uid=user_id)

#     credit_limit = user.email_credit_limit
#     used_credit = user.used_email_credit
#     credits_left = max(0, credit_limit - used_credit)
#     credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0
    
#     uname = request.session.get("name")
#     obj = CustomUser.objects.get(uid=user_id)
#     company_name = obj.company
#     context={
#         "company_name":company_name,
#         "uname":uname,
#         "credits_left":credits_left,
#         'smtp_servers': smtp_servers,
#         "user":user,
#         "credit_limit":credit_limit,
#         "credit_percent":credit_percent,
#     }
#     return render(request, 'smtp_list.html',context)


from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count
from django.db.models.functions import TruncHour


def smtp_server_list(request):
    user_id = request.session.get("user_id")
    smtp_servers = SMTPServer.objects.filter(user_id=user_id).order_by('-created_at')
    user = get_object_or_404(CustomUser, uid=user_id)

    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0

    # Time range for last hour
    one_hour_ago = timezone.now() - timedelta(hours=1)

    # Prepare SMTP stats
    smtp_data = []
    for smtp in smtp_servers:
        total_sent = SMTPUsageLog.objects.filter(smtp_server=smtp).aggregate(total=Sum('email_count'))['total'] or 0
        last_hour_sent = SMTPUsageLog.objects.filter(
            smtp_server=smtp,
            timestamp__gte=one_hour_ago
        ).aggregate(total=Sum('email_count'))['total'] or 0

        smtp_data.append({
            'smtp': smtp,
            'total_sent': total_sent,
            'last_hour_sent': last_hour_sent,
        })

    uname = request.session.get("name")
    company_name = user.company

    context = {
        "company_name": company_name,
        "uname": uname,
        "credits_left": credits_left,
        "user": user,
        "credit_limit": credit_limit,
        "credit_percent": credit_percent,
        "smtp_data": smtp_data,
    }
    return render(request, 'smtp_list.html', context)



from django.shortcuts import get_object_or_404

def delete_smtp(request, id):
    user_id = request.session.get("user_id")
    try:
        server = get_object_or_404(SMTPServer, id=id, user_id=user_id)
        server.delete()
        messages.success(request, "SMTP server deleted successfully.")
    except Exception as e:
        messages.error(request, f"SMTP server deletion Failed: {str(e)}")
        
    return redirect('/smtp_list/')

from django.shortcuts import render, get_object_or_404, redirect




def edit_smtp_server(request, server_id):
    server = get_object_or_404(SMTPServer, id=server_id)

    if request.method == 'POST':
        server.name = request.POST.get('name')
        server.from_email = request.POST.get('from_email')
        server.host = request.POST.get('host')
        server.emails_per_hour = request.POST.get('emails_per_hour')
        server.smtp_server = request.POST.get('smtp_server')
        server.port = request.POST.get('port')
        server.security = request.POST.get('security')

        server.save()
        messages.success(request, 'Server updated successfully!')
        return redirect('/smtp_list/')  
    
    user_id = request.session.get("user_id")
    user = get_object_or_404(CustomUser, uid=user_id)

    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0
    
    context = {
        "company_name": user.company,
        "uname": user.name,
        "edit": True,
        "server": server,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
    }

    return render(request, 'edit_smtp_server.html', context)




def add_list(request):

    # -------------session--------------
    user_id = request.session.get("user_id")
    uname = request.session.get("name")
    email = request.session.get("email")    
    # ----------------------------------
    obj = CustomUser.objects.get(uid=user_id)
    company_name = obj.company
    
    user = get_object_or_404(CustomUser, uid=user_id)

    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0
    context={
        "company_name":company_name,
        "uname":uname,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
    }
    if request.method == "POST":
                
        list_name= request.POST.get("list_name")
        uploaded_file = request.FILES['file']
        fs = FileSystemStorage()
        # Save the file
        file = fs.save(uploaded_file.name, uploaded_file)
        
        try:
            # create datbase record
            obj = email_list(user_id = user_id,file=file , list_name = list_name)
            obj.save()
            messages.success(request, "Email list added successfully.")
            return render(request,"add_list.html",context)
        except Exception as e:
            messages.error(request, f"Failed to add email list: {str(e)}")
            return render(request,"add_list.html",context)
        
    return render(request,"add_list.html" , context)



def email_list_view(request):
    user_id = request.session.get("user_id")
    lists = email_list.objects.filter(user_id=user_id).order_by('-uploaded_at')
    uname = request.session.get("name")
    obj = CustomUser.objects.get(uid=user_id)
    company_name = obj.company
    
    user = get_object_or_404(CustomUser, uid=user_id)

    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0
    context={
        "company_name":company_name,
        "uname":uname,
        "lists": lists,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
    }
    return render(request, "email_lists.html", context)

def delete_list_user(request, list_id):
    user_id = request.session.get("user_id")
    email_obj = get_object_or_404(email_list, id=list_id, user_id=user_id)
    email_obj.file.delete()  # deletes file from storage
    email_obj.delete()
    messages.success(request, "Email list deleted successfully.")
    return redirect("/email_lists/")


def edit_email_list(request, list_id):
    user_id = request.session.get("user_id")
    email_obj = get_object_or_404(email_list, id=list_id, user_id=user_id)
    
    user = get_object_or_404(CustomUser, uid=user_id)

    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0
    context={
        "company_name":user.company,
        "uname":user.name,
        "email_obj": email_obj,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
    }
    if request.method == "POST":
        new_name = request.POST.get("list_name")
        if new_name:
            email_obj.list_name = new_name
            email_obj.save()
            messages.success(request, "List name updated successfully.")
        return redirect("/email_lists/")
    
    return render(request, "edit_email_list.html", context)




def add_template(request):
    # -------------session--------------
    user_id = request.session.get("user_id")
    uname = request.session.get("name")
    email = request.session.get("email")    
    # ----------------------------------
    
    user = get_object_or_404(CustomUser, uid=user_id)

    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0
    context={
        "company_name":user.company,
        "uname":uname,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
        
    }

    if request.method == "POST":
                
        template_name = request.POST.get("template_name")
        content = request.POST.get("content")
        try:
            obj = template(user_id = user_id,template_name = template_name , content = content)
            obj.save()
            messages.success(request, "Template added successfully.")
            return render(request,"add_template.html",context)
        except Exception as e:
            print(e)
            messages.error(request, f"Failed to add template: {str(e)}")
            return render(request,"add_template.html",context)
    
    return render(request ,"add_template.html",context)


# Show list of templates

from django.db.models import Q

def template_list(request):
    user_id = request.session.get("user_id")
    templates = template.objects.filter(Q(user_id=user_id) | Q(user_id__isnull=True)).order_by('-uploaded_at')
    uname = request.session.get("name")
    user = get_object_or_404(CustomUser, uid=user_id)

    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0
    
    context={
        "company_name":user.company,
        "uname":uname,
        "templates": templates,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
    }
    return render(request, "template_list.html", context)

# Edit template
def edit_template(request, id):
    user_id = request.session.get("user_id")
    
    try:
        temp = get_object_or_404(template, id=id, user_id=user_id)
    except:
        messages.error(request, "You are not authorized to edit this template.")    
        return redirect("/template_list/")

    if request.method == "POST":
        try:
            temp.template_name = request.POST.get("template_name")
            temp.content = request.POST.get("content")
            temp.save()
            messages.success(request, "Template updated successfully.")
            return redirect("/template_list/")
        except:
            messages.error(request, "You are not authorized to edit this template !!!.")
            return redirect("/template_list/")  
    
    user = get_object_or_404(CustomUser, uid=user_id)

    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0
    
    context={
        "company_name":user.company,
        "uname":user.name,
        "template": temp,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
    }
             
    return render(request, "edit_template.html", context)
    

# Delete template
def delete_template(request, id):
    user_id = request.session.get("user_id")
    try:
        temp = get_object_or_404(template, id=id, user_id=user_id)
    except:
        messages.error(request, "You are not authorized to delete this template.")    
        return redirect("/template_list/")
    temp.delete()
    messages.success(request, "Template deleted successfully.")
    return redirect("/template_list/")


def campaign_success(request):
    # -------------session--------------
    user_id = request.session.get("user_id")
    
    user = get_object_or_404(CustomUser, uid=user_id)

    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0  
    # ----------------------------------
    
    obj = CustomUser.objects.get(uid=user_id)
    company_name = obj.company
    context={
        "company_name":company_name,
        "uname":user.name,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
        
    }
    return render(request,"campaign_success.html",context)



import pandas as pd
import os

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



def create_campaign(request):
    from .tasks import send_bulk_emails_task
    user_id = request.session.get("user_id")
    obj = CustomUser.objects.get(uid=user_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')  # 'send_now' or 'schedule'
        name = request.POST.get('name')
        reply_to = request.POST.get('reply_to')
        subject = request.POST.get('subject')
        preheader = request.POST.get('placeholder_text')
        sender_name = request.POST.get('sender_name')
        scheduled_time_raw = request.POST.get('scheduled_time')
        cta_text = request.POST.get("cta_text", "").strip()
        cta_url = request.POST.get("cta_url")
        

        
        attachments = request.FILES.getlist('attachments[]')
        print(attachments , "*"*30)
        print(len(attachments) , "*"*30)
        print("FILES:", request.FILES)
        print("ATTACHMENTS:", request.FILES.getlist('attachments[]'))
        
        scheduled_time = None
        if scheduled_time_raw:
            dt = datetime.strptime(scheduled_time_raw, "%Y-%m-%dT%H:%M")
            scheduled_time = make_aware(dt)

        email_list_id = request.POST.get('email_list')
        template_id = request.POST.get('template')
        smtp_id = request.POST.get('smtp_server')
        
       

        email_list_obj = email_list.objects.get(id=email_list_id) if email_list_id else None
        template_obj = template.objects.get(id=template_id) if template_id else None
        smtp = SMTPServer.objects.get(id=smtp_id)

        custom_recipients_text = request.POST.get('customRecipients')
        custom_template_content = request.POST.get('customTemplate')

        if custom_recipients_text:
            recipients = extract_recipients_from_text(custom_recipients_text)
        else:
            file_path = email_list_obj.file.path
            recipients = extract_recipients_from_file(file_path)

        if custom_template_content:
            template1 = custom_template_content
        else:
            template1 = template_obj.content

        # ✅ Get current user object
        user = CustomUser.objects.get(uid=user_id)
        
        start_of_month = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_sent = EmailTracking.objects.filter(
            campaign__user_id=user_id,
            sent_at__gte=start_of_month
        ).count()
        
        if user.used_email_credit >= user.email_credit_limit:
            messages.error(request,"Email credit limit reached")
            return redirect("/create_campaign/")
        else:
            # ✅ Step 1: Create campaign FIRST
            campaign = Campaign.objects.create(
                name=name,
                reply_to=reply_to,
                email_list=email_list_obj,
                subject=subject,
                template=template_obj,
                preheader=preheader,
                smtp_server=smtp,
                sender_name=sender_name,
                user_id=user_id,
                scheduled_time=scheduled_time if action == 'schedule' else None,
                is_sent=False,
                manual_recipients=custom_recipients_text or None,
                custom_template=custom_template_content or None,
                cta_text=cta_text,
                cta_url = cta_url,
            )
            
            for file in attachments:
                CampaignAttachment.objects.create(campaign=campaign, file=file)

            # ✅ Step 2: Now tracking_html with campaign.id
            from urllib.parse import quote  # at top of views.py
            
            # file_name = campaign.attachments.name.split("/")[-1] if campaign.attachments else ""
            # file_name = quote(campaign.attachments.name.split("/")[-1]) if campaign.attachments else ""

            tracking_block = generate_tracking_block(campaign)
            template1 += tracking_block


            smtp_data = {
                'host': smtp.host,
                'port': smtp.port,
                'username': smtp.username,
                'password': smtp.password,
                'security': smtp.security,
            }

            attachment_paths = [
                attachment.file.path
                for attachment in campaign.attachment_files.all()
            ]
            
            
            
            if action == 'send_now':
                send_bulk_emails_task.delay(
                    smtp_data=smtp_data,
                    reply_to=reply_to,
                    from_email=smtp.from_email,
                    subject=subject,
                    body_template=template1,
                    recipients=recipients,
                    preheader=preheader,
                    attachment_path=attachment_paths,
                    sender_name=sender_name,
                    campaign_id=campaign.id  # ✅ Required for EmailTracking
                )
                messages.success(request, "Campaign sent successfully.")
            else:
                messages.success(request, f"Campaign scheduled for {scheduled_time}.")
                
            return redirect('/campaign_success/')
        
    user = get_object_or_404(CustomUser, uid=user_id)

    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0  
    
    

          
    context = {
        'email_lists': email_list.objects.filter(user_id=user_id).order_by('-uploaded_at'),
        'templates': template.objects.filter(Q(user_id=user_id) | Q(user_id__isnull=True)).order_by('-uploaded_at'),
        'smtps': SMTPServer.objects.filter(user_id=user_id,is_active=1).order_by('-created_at'),
        'uname': user.name,
        "company_name":user.company,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
    }
    return render(request, 'create_campaign.html', context)


def campaign_list(request):
    user_id = request.session.get("user_id")

    # Only show campaigns that are NOT deleted
    campaigns = Campaign.objects.filter(user_id=user_id, is_deleted=False).order_by('-created_at')

    user = get_object_or_404(CustomUser, uid=user_id)

    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0  


    context={
        "company_name":user.company,
        "uname":user.name,
        'campaigns': campaigns,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
    }
    for campaign in campaigns:
        tracking = EmailTracking.objects.filter(campaign=campaign)
        campaign.sent_count = tracking.count()
        campaign.click_count = tracking.filter(is_clicked=True).count()
        
    return render(request, 'campaign_list.html', context)


def delete_campaign(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id)

    # Soft delete: mark as deleted instead of actual delete
    campaign.is_deleted = True
    campaign.save()

    messages.success(request, "Campaign deleted successfully.")
    return redirect('campaign_list')



# --------------------------------------------------------------------



# ================================OTP==========================

import random
import string

def generate_OTP(length=6):
    """Generate a numeric OTP of given length (default 6 digits)"""
    return ''.join(random.choices(string.digits, k=length))

# Usage
# otp = generate_numeric_otp()  # e.g. "429731"

# =====================================================================

from django.http import FileResponse, Http404
from django.utils.timezone import now
from .models import EmailTracking

def track_open(request, campaign_id, email):
    EmailTracking.objects.filter(campaign_id=campaign_id, recipient=email).update(
        is_opened=True,
        open_timestamp=now()
    )
    return HttpResponse(b"")  # invisible image response

def track_click(request, campaign_id, email):
    EmailTracking.objects.filter(campaign_id=campaign_id, recipient=email).update(
        is_clicked=True,
        click_timestamp=now(),
        is_opened=True,  # if clicked, we can assume opened
        open_timestamp=now()
    )
    return redirect(request.GET.get("url", "https://google.com"))




from django.http import FileResponse, Http404
from django.utils.timezone import now
from .models import EmailTracking
import os
from django.conf import settings
from urllib.parse import unquote




from django.http import FileResponse, HttpResponse, Http404
from django.shortcuts import get_object_or_404
from .models import Campaign
from zipfile import ZipFile
from io import BytesIO
import os

def track_attachment(request, campaign_id, email):
    campaign = get_object_or_404(Campaign, id=campaign_id)
    attachments = campaign.attachment_files.all()

    if not attachments:
        raise Http404("No attachments found.")

    # 🧠 Optional: Save tracking info to DB or log (you can create a DownloadLog model)

    if attachments.count() == 1:
        # Single file
        attachment = attachments.first()
        return FileResponse(
            attachment.file.open('rb'),
            as_attachment=True,
            filename=os.path.basename(attachment.file.name)
        )

    # 📦 Create a zip of all files
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        for attachment in attachments:
            file_name = os.path.basename(attachment.file.name)
            with attachment.file.open('rb') as f:
                zip_file.writestr(file_name, f.read())

    zip_buffer.seek(0)
    return FileResponse(
        zip_buffer,
        as_attachment=True,
        filename='attachments.zip'
    )




# from django.db.models import Count, Q
from .models import Campaign, EmailTracking

def campaign_analytics(request):
    user_id = request.session.get("user_id")
    campaigns = Campaign.objects.filter(user_id=user_id).order_by("-created_at")

    data = []
    for camp in campaigns:
        total_sent = EmailTracking.objects.filter(campaign=camp).count()
        opened = EmailTracking.objects.filter(campaign=camp, is_opened=True).count()
        clicked = EmailTracking.objects.filter(campaign=camp, is_clicked=True).count()

        data.append({
            "name": camp.name,
            "sent": total_sent,
            "opened": opened,
            "clicked": clicked,
        })

    return render(request, "analytics.html", {"data": data})

    
    
def toggle_subscription(request, email):
    if UnsubscribedEmail.objects.filter(email=email).exists():
        UnsubscribedEmail.objects.filter(email=email).delete()
        print(f"✅ Resubscribed: {email}")
    else:
        UnsubscribedEmail.objects.create(email=email)
        print(f"🚫 Unsubscribed: {email}")

    # blank pixel to avoid redirect
    pixel = (
        b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
        b'\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00'
        b'\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02L\x01\x00;'
    )
    return HttpResponse(pixel, content_type='image/gif')


def user_profile(request):
    user_id = request.session.get("user_id")
    user = get_object_or_404(CustomUser, uid=user_id)

    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0  


    context={
        "company_name":user.company,
        "uname":user.name,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
    }
    return render(request, "user_profile.html", context)

def edit_user_profile(request):
    user_id = request.session.get("user_id")
    user = get_object_or_404(CustomUser, uid=user_id)
    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0  


    context={
        "company_name":user.company,
        "uname":user.name,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
    }

    if request.method == "POST":
        user.name = request.POST.get("name")
        user.email = request.POST.get("email")
        user.number = request.POST.get("number")
        user.dob = request.POST.get("dob")
        user.address = request.POST.get("address")
        user.company = request.POST.get("company")
        if request.FILES.get("profile_image"):
            user.profile_image = request.FILES["profile_image"]
        user.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("user_profile")

    return render(request, "edit_user_profile.html", context)


def change_user_password(request):
    user_id = request.session.get("user_id")
    user = get_object_or_404(CustomUser, uid=user_id)
    
    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0  


    context={
        "company_name":user.company,
        "uname":user.name,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
    }

    if request.method == "POST":
        current = request.POST.get("current_password")
        new = request.POST.get("new_password")
        confirm = request.POST.get("confirm_password")

        if not check_password(current, user.password):
            messages.error(request, "Current password is incorrect.")
        elif new != confirm:
            messages.error(request, "New password and confirm password do not match.")
        else:
            user.password = make_password(new)
            user.save()
            messages.success(request, "Password changed successfully.")
            return redirect("/change_user_password/")

    return render(request, "user_change_password.html",context)


# --------------------------------usern----------------------------------


def chat_page(request):
    user_id = request.session.get("user_id")
    user = get_object_or_404(CustomUser, uid=user_id)
    request.session["email"] = user.email
    
    credit_limit = user.email_credit_limit
    used_credit = user.used_email_credit
    credits_left = max(0, credit_limit - used_credit)
    credit_percent = int((credits_left / credit_limit) * 100) if credit_limit > 0 else 0  
    context={
        "company_name":user.company,
        "uname":user.name,
        "user":user,
        "credit_limit":credit_limit,
        "credit_percent":credit_percent,
        "credits_left":credits_left,
    }
    return render(request, "chat.html", context)

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ChatMessage
from django.utils import timezone
import json

@csrf_exempt
def send_message(request):
    if request.method == "POST":
        data = json.loads(request.body)
        sender = request.session.get("email")
        receiver = data.get("receiver_email")
        message = data.get("message")

        if not sender or not receiver or not message:
            return JsonResponse({"status": "error", "msg": "Missing fields"})

        ChatMessage.objects.create(
            sender_email=sender,
            receiver_email="admin@gmail.com",
            message=message,
            timestamp=timezone.now()
        )
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error", "msg": "Invalid method"})


def fetch_messages(request):
    if request.method == "GET":
        user_email = request.session.get("email")
        if not user_email:
            return JsonResponse({"status": "error", "msg": "User not logged in"})

        obj = CustomUser.objects.filter(role = "admin").first()
        admin_email = obj.email
        messages = ChatMessage.objects.filter(
            sender_email__in=[user_email, admin_email],
            receiver_email__in=[user_email, admin_email]
        ).order_by("timestamp")

        data = [
            {
                "sender": m.sender_email,
                "message": m.message,
                "time": m.timestamp.strftime("%H:%M")
            }
            for m in messages
        ]
        return JsonResponse({"status": "success", "messages": data})
    return JsonResponse({"status": "error", "msg": "Invalid method"})


# ----------------------- For admin support -----------------------------

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
from .models import CustomUser, ChatMessage


def admin_chat_panel(request):
    if not request.session.get("email"):
        return JsonResponse({"error": "Admin not logged in"}, status=403)
    
    user_id = request.session.get("user_id")
    admin = CustomUser.objects.filter(uid = user_id).first()
    users = CustomUser.objects.filter(role="user")
    context={
        "users":users,
        "admin" :admin,
        "uname":admin.name,
        "company_name" : admin.company,
    }
    return render(request, "admin_chat.html", context)


@csrf_exempt
def admin_send_message(request):
    if request.method == "POST":
        data = json.loads(request.body)
        sender = request.session.get("email", "admin@example.com")
        receiver = data.get("receiver_email")
        message = data.get("message")

        if not receiver or not message:
            return JsonResponse({"status": "error", "msg": "Missing fields"})

        ChatMessage.objects.create(
            sender_email=sender,
            receiver_email=receiver,
            message=message,
            timestamp=timezone.now()
        )
        return JsonResponse({"status": "success"})


def admin_fetch_messages(request):
    if request.method == "GET":
        admin_email = request.session.get("email", "admin@example.com")
        user_email = request.GET.get("user_email")
        if not user_email:
            return JsonResponse({"status": "error", "msg": "User not selected"})

        messages = ChatMessage.objects.filter(
            sender_email__in=[admin_email, user_email],
            receiver_email__in=[admin_email, user_email]
        ).order_by("timestamp")

        data = [
            {
                "sender": "Admin" if m.sender_email == admin_email else get_user_name(m.sender_email),
                "message": m.message,
                "time": m.timestamp.strftime("%H:%M")
            }
            for m in messages
        ]
        return JsonResponse({"status": "success", "messages": data})


def get_user_name(email):
    user = CustomUser.objects.filter(email=email).first()
    return user.name if user else email

# from django.shortcuts import render
# from django.http import JsonResponse
# from .models import CustomUser, ChatMessage
# from django.views.decorators.csrf import csrf_exempt
# from django.utils import timezone
# import json

# def admin_chat_panel(request):
#     users = CustomUser.objects.filter(role="user")
#     return render(request, "admin_chat.html", {"users": users})


# @csrf_exempt
# def admin_send_message(request):
#     if request.method == "POST":
#         # admin_email = request.session.get("email")
#         data = json.loads(request.body)
#         sender = "admin@example.com"  # static admin email
#         receiver = data.get("receiver_email")
#         message = data.get("message")

#         if not receiver or not message:
#             return JsonResponse({"status": "error", "msg": "Missing fields"})

#         ChatMessage.objects.create(
#             sender_email=sender,
#             receiver_email=receiver,
#             message=message,
#             timestamp=timezone.now()
#         )
#         return JsonResponse({"status": "success"})


# def admin_fetch_messages(request):
#     if request.method == "GET":
#         admin_email = "admin@example.com"
#         user_email = request.GET.get("user_email")
#         if not user_email:
#             return JsonResponse({"status": "error", "msg": "User not selected"})

#         messages = ChatMessage.objects.filter(
#             sender_email__in=[admin_email, user_email],
#             receiver_email__in=[admin_email, user_email]
#         ).order_by("timestamp")

#         data = [
#             {
#                 "sender": m.sender_email,
#                 "message": m.message,
#                 "time": m.timestamp.strftime("%H:%M")
#             }
#             for m in messages
#         ]
#         return JsonResponse({"status": "success", "messages": data})

# ================================ ADMIN DESHBOARD LOGIC  =================================================================================================
from django.db.models.functions import TruncMonth
from django.db.models import Count
from django.utils.timezone import now
import calendar
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q, F, FloatField, ExpressionWrapper

def adminhome(request):
    user_id = request.session.get("user_id")
    obj = CustomUser.objects.filter(uid = user_id)
    
    today = timezone.now().date()
    
    start_of_month = today.replace(day=1)
    start_of_last_month = (start_of_month - timedelta(days=1)).replace(day=1)
    end_of_last_month = start_of_month - timedelta(days=1)
    
    # ---- USERS ----
    users_today = CustomUser.objects.filter(created_at__date=today,role="user").count()
    users_this_month = CustomUser.objects.filter(created_at__date__gte=start_of_month,role="user").count()
    users_last_month = CustomUser.objects.filter(created_at__date__gte=start_of_last_month, created_at__date__lte=end_of_last_month,role="user").count()

    # ---- CAMPAIGNS ----
    campaigns_today = Campaign.objects.filter(created_at__date=today).count()
    campaigns_this_month = Campaign.objects.filter(created_at__date__gte=start_of_month).count()
    campaigns_last_month = Campaign.objects.filter(created_at__date__gte=start_of_last_month, created_at__date__lte=end_of_last_month).count()

    # ---- SMTPs ----
    smtps_today = SMTPServer.objects.filter(created_at__date=today,is_active = 1).count()
    smtps_this_month = SMTPServer.objects.filter(created_at__date__gte=start_of_month,is_active = 1).count()
    smtps_last_month = SMTPServer.objects.filter(created_at__date__gte=start_of_last_month, created_at__date__lte=end_of_last_month,is_active = 1).count()

    user_counts = [users_last_month, users_this_month, users_today]
    campaign_counts = [campaigns_last_month, campaigns_this_month, campaigns_today]
    smtp_counts = [smtps_last_month, smtps_this_month, smtps_today]
    labels = ['Last Month', 'This Month', 'Today']

    top_campaigns = (
        Campaign.objects.annotate(
            total_sent=Count('emailtracking'),
            total_clicked=Count('emailtracking', filter=Q(emailtracking__is_clicked=True)),
            click_rate=ExpressionWrapper(
                100 * F('total_clicked') / F('total_sent'),
                output_field=FloatField()
            )
        )
        .filter(total_sent__gt=0, is_deleted=False)  # Exclude empty or deleted ones
        .order_by('-click_rate')[:5]
    )
   
    admin = get_object_or_404(CustomUser, role='admin', uid=request.session.get('user_id'))
    context = {
        "total_users": CustomUser.objects.filter(role="user").count(),
        "total_campaigns": Campaign.objects.count(),
        "total_smtp" : SMTPServer.objects.filter(is_active = 1).count(),
        "uname":request.session.get("name"),
        "company_name":obj[0].company,
        "admin":admin,

        # "labels": all_months,
        # "user_counts": get_monthly_series(user_data, all_months),
        # "campaign_counts": get_monthly_series(campaign_data, all_months),
        # "smtp_counts": get_monthly_series(smtp_data, all_months),
        
        "labels": labels,
        "user_counts": user_counts,
        "campaign_counts": campaign_counts,
        "smtp_counts": smtp_counts,
        "top_campaigns": top_campaigns,
        "all_users": CustomUser.objects.filter(role="user")
    }
    return render(request, "adminhome.html", context)




def user_list(request):
    user_id = request.session.get("user_id")
    obj = CustomUser.objects.filter(uid = user_id)
    
    users = CustomUser.objects.filter(role="user").order_by('-created_at')
    admin = get_object_or_404(CustomUser, role='admin', uid=request.session.get('user_id'))
    context = {
        "uname":request.session.get("name"),
        "company_name":obj[0].company,
        "users": users,
        "admin":admin
    }
    return render(request,"all_user.html",context)


def toggle_user_status(request, uid):
    user = get_object_or_404(CustomUser, uid=uid)
    user.is_active = not user.is_active  # Toggle status
    user.save()
    return redirect("/user_list/")

def delete_user_permanent(request, uid):
    try:
        user = CustomUser.objects.get(uid=uid)
        user.delete()
        messages.success(request, "User deleted successfully.")
    except CustomUser.DoesNotExist:
        messages.error(request, "User not found.")
    except Exception as e:
        messages.error(request, "Failed to delete user. Please try again.")
    return redirect("/user_list/")





def edit_user(request, uid):
    user = get_object_or_404(CustomUser, uid=uid)

    if request.method == 'POST':
        try:
            user.name = request.POST.get('name')
            user.email = request.POST.get('email')
            user.company = request.POST.get('company')

            new_password = request.POST.get('password')
            if new_password:  # Only update if password is given
                user.password = make_password(new_password)

            user.save()
            messages.success(request, "User updated successfully!")
        except Exception as e:
            messages.error(request, "Something went wrong. Please try again.")
        return redirect('/user_list/')

    admin = get_object_or_404(CustomUser, role='admin', uid=request.session.get('user_id'))
    context = {
        "uname": request.session.get("name"),
        "company_name": admin.company,
        "user": user,
        "admin": admin
    }
    return render(request, "edit_user.html", context)



def add_user(request):
    user_id = request.session.get("user_id")
    obj = CustomUser.objects.filter(uid=user_id).first()

    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        number = request.POST.get("number")
        password = request.POST.get("password")
        dob = request.POST.get("dob")
        address = request.POST.get("address")
        company = request.POST.get("company")
        role = request.POST.get("role")
        email_credit_limit = request.POST.get("email_credit_limit")

        # Duplicate email check
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("/add_user/")

        hashed_password = make_password(password)

        CustomUser.objects.create(
            name=name,
            email=email,
            number=number,
            password=hashed_password,
            dob=dob,
            address=address,
            company=company,
            role=role,
            email_credit_limit=email_credit_limit,
            created_at=timezone.now(),
            is_active=True
        )

        messages.success(request, "User created successfully.")
        return redirect("/add_user/")

    admin = get_object_or_404(CustomUser, role='admin', uid=user_id)
    context = {
        "uname": request.session.get("name"),
        "company_name": obj.company,
        "admin": admin
    }
    return render(request, "add_user.html", context)

from django.core.files.storage import default_storage


def all_email_lists(request):
    user_id = request.session.get("user_id")
    user_obj = CustomUser.objects.filter(uid=user_id).first()

    all_lists = email_list.objects.all().order_by("-uploaded_at")

    email_lists = []
    for e in all_lists:
        user = CustomUser.objects.filter(uid=e.user_id).first()

        # Count emails from uploaded file
        total_emails = 0
        if e.file and default_storage.exists(e.file.name):
            try:
                with default_storage.open(e.file.name, 'r') as f:
                    reader = csv.reader(f)
                    # skip header
                    next(reader, None)
                    for row in reader:
                        if row and row[0].strip():  # check if not empty
                            total_emails += 1
            except Exception as ex:
                print(f"Error reading {e.file.name}: {ex}")

        email_lists.append({
            'id': e.id,
            'name': e.list_name,
            'user': user.name if user else "Unknown",
            'total_emails': total_emails,
            'created_at': e.uploaded_at,
        })
    admin = get_object_or_404(CustomUser, role='admin', uid=request.session.get('user_id'))
    context = {
        "uname": request.session.get("name"),
        "company_name": user_obj.company if user_obj else "",
        "email_lists": email_lists,
        "admin":admin
    }
    return render(request, "all_email_lists.html", context)



def download_email_list(request, list_id):
    email_list_obj = get_object_or_404(email_list, id=list_id)
    if not email_list_obj.file:
        return HttpResponse("No file found for this email list.", status=404)

    file_path = email_list_obj.file.name
    if not default_storage.exists(file_path):
        return HttpResponse("File does not exist.", status=404)

    # Open file
    with default_storage.open(file_path, 'r') as f:
        lines = f.readlines()

    # Prepare CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{email_list_obj.list_name}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Email'])

    for line in lines:
        email = line.strip()
        if email:
            writer.writerow([email])

    return response

def delete_email_list(request, list_id):
    email_list_obj = get_object_or_404(email_list, id=list_id)
    email_list_obj.delete()
    messages.success(request, "Email list deleted successfully.")
    return redirect("all_email_lists")



def all_templates(request):
    templates = template.objects.all().order_by("-uploaded_at")
    users = CustomUser.objects.all()

    user_map = {u.uid: u.name for u in users}

    for t in templates:
        t.user_name = user_map.get(t.user_id, "Admin")
        t.display_name = t.template_name or "Admin"
        
    user_id = request.session.get('user_id')
    obj = CustomUser.objects.filter(uid=user_id).first()
    admin = get_object_or_404(CustomUser, role='admin', uid=request.session.get('user_id'))
    context = {
        "templates": templates,
        "uname":obj.name,
        "company_name":obj.company,
        "admin":admin
        }
    return render(request, "all_templates.html",context) 
    


def delete_template_admin(request, tid):
    temp = get_object_or_404(template, id=tid)
    temp.delete()
    messages.success(request, "Template deleted successfully.")
    return redirect("all_templates")

def edit_template_admin(request, tid):
    temp = get_object_or_404(template, id=tid)
    user_id = request.session.get('user_id')
    obj = CustomUser.objects.filter(uid=user_id).first()
    context = {
        "template": temp,
        "uname":obj.name,
        "company_name":obj.company,
        "admin":obj
        }

    if request.method == "POST":
        temp.template_name = request.POST.get("template_name")
        temp.content = request.POST.get("content")
        temp.save()
        messages.success(request, "Template updated successfully.")
        return redirect("all_templates")

    return render(request, "edit_template_admin.html", context)


def add_template_admin(request):
    all_users = CustomUser.objects.all()
    
    user_id = request.session.get('user_id')
    obj = CustomUser.objects.filter(uid=user_id).first()
    context = {
        "all_users": all_users,
        "uname":obj.name,
        "company_name":obj.company,
        'admin':obj
        }

    if request.method == "POST":
        name = request.POST.get("template_name")
        content = request.POST.get("content")
        user_id = request.POST.get("user_id") or None  # None = global

        template.objects.create(
            template_name=name,
            content=content,
            user_id=user_id
        )
        messages.success(request, "Template added successfully.")
        return redirect("/all_templates/")

    return render(request, "add_template_admin.html", context)


def all_campaign_admin(request):
    campaigns = Campaign.objects.filter(is_deleted=False).order_by('-created_at')
    users = CustomUser.objects.all()
    user_map = {str(user.uid): user.name for user in users}

    # Attach user name to each campaign (no need for template filter)
    for c in campaigns:
        c.user_name = user_map.get(str(c.user_id), "Unknown")

    user_id = request.session.get('user_id')
    obj = CustomUser.objects.filter(uid=user_id).first()
    context = {
        "campaigns": campaigns,
        "uname":obj.name,
        "company_name":obj.company,
        "admin":obj
        }
    return render(request, "all_campaign_admin.html",context)


def delete_campaign_admin(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id)
    campaign.is_deleted = True
    campaign.save()
    messages.success(request, "Campaign deleted successfully.")
    return redirect("all_campaign_admin")


def all_server_admin(request):
    servers = SMTPServer.objects.all().order_by('-created_at')
    users = CustomUser.objects.all()
    
    user_id = request.session.get('user_id')
    obj = CustomUser.objects.filter(uid=user_id).first()
    context = {
        "servers": servers,
        "users": users,
        "uname":obj.name,
        "company_name":obj.company,
        "admin":obj
        }
    return render(request, "all_server_admin.html", context)
    
def toggle_smtp_status(request, smtp_id):
    smtp = get_object_or_404(SMTPServer, id=smtp_id)
    smtp.is_active = 0 if smtp.is_active == 1 else 1
    smtp.save()
    messages.success(request, "SMTP status updated.")
    return redirect('all_server_admin')

def edit_smtp_admin(request, smtp_id):
    smtp = get_object_or_404(SMTPServer, id=smtp_id)
    if request.method == 'POST':
        smtp.name = request.POST.get('name')
        smtp.host = request.POST.get('host')
        smtp.port = request.POST.get('port')
        smtp.username = request.POST.get('username')
        smtp.password = request.POST.get('password')
        smtp.from_email = request.POST.get('from_email')
        smtp.smtp_server = request.POST.get('smtp_server')
        smtp.emails_per_hour = request.POST.get('emails_per_hour')
        smtp.security = request.POST.get('security')
        smtp.save()
        messages.success(request, "SMTP updated successfully.")
        return redirect('all_server_admin')
    
    user_id = request.session.get('user_id')
    obj = CustomUser.objects.filter(uid=user_id).first()
    context = {
        "smtp": smtp,
        "uname":obj.name,
        "company_name":obj.company,
        "admin":obj
        }
    return render(request, 'edit_smtp_admin.html', context)

def delete_server_admin(request, smtp_id):
    smtp = get_object_or_404(SMTPServer, id=smtp_id)
    smtp.delete()
    messages.success(request, "SMTP deleted.")
    return redirect('all_server_admin')


def add_server_admin(request):
    users = CustomUser.objects.all()
    user_id = request.session.get('user_id')
    obj = CustomUser.objects.filter(uid=user_id).first()
    context = {
        "users": users,
        "uname":obj.name,
        "company_name":obj.company,
        "admin":obj
        }
    
    if request.method == "POST":
        user_id = request.POST.get("user_id")
        smtp = SMTPServer(
            user_id=user_id,
            name=request.POST.get("name"),
            host=request.POST.get("host"),
            port=request.POST.get("port"),
            username=request.POST.get("username"),
            password=request.POST.get("password"),
            from_email=request.POST.get("from_email"),
            smtp_server=request.POST.get("smtp_server"),
            emails_per_hour=request.POST.get("emails_per_hour"),
            security=request.POST.get("security"),
        )
        smtp.save()
        messages.success(request, "SMTP server added successfully.")
        return redirect("all_server_admin")
    
    return render(request, "add_server_admin.html",context)




def user_credits_admin(request):
    users = CustomUser.objects.all().order_by('-created_at')
    user_stats = []

    for user in users:
        credit_left = max(user.email_credit_limit - user.used_email_credit, 0)

        user_stats.append({
            "id": user.id,
            "uid": user.uid,
            "name": user.name,
            "email": user.email,
            "email_credit_limit": user.email_credit_limit,
            "used_credit": user.used_email_credit,
            "credit_left": credit_left,
        })
        
    user_id = request.session.get('user_id')
    obj = CustomUser.objects.filter(uid=user_id).first()
    context = {
        "users": user_stats,
        "uname":obj.name,
        "company_name":obj.company,
        "admin":obj
        }
    
    return render(request, "user_credits_admin.html", context)


def edit_user_credit(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)

    if request.method == 'POST':
        credit_limit = request.POST.get('email_credit_limit')
        credit_left = request.POST.get('credit_left')

        if credit_limit.isdigit() and credit_left.isdigit():
            credit_limit = int(credit_limit)
            credit_left = int(credit_left)
            used_credit = max(credit_limit - credit_left, 0)

            user.email_credit_limit = credit_limit
            user.used_email_credit = used_credit
            user.save()

            messages.success(request, "User credit updated successfully.")
        else:
            messages.error(request, "Invalid input. Please enter valid numbers.")

        return redirect('user_credits_admin')

    credit_left = max(user.email_credit_limit - user.used_email_credit, 0)
    user_id = request.session.get('user_id')
    obj = CustomUser.objects.filter(uid=user_id).first()
    context = {
        "user": user,
        "used_credit": user.used_email_credit,
        "credit_left": credit_left,
        "uname":obj.name,
        "company_name":obj.company,
        "admin":obj
        }
    
    return render(request, "edit_user_credit.html",context)



def admin_profile(request):
    admin = get_object_or_404(CustomUser, role='admin', uid=request.session.get('user_id'))
    user_id = request.session.get('user_id')
    obj = CustomUser.objects.filter(uid=user_id).first()
    context = {
        "uname":obj.name,
        "company_name":obj.company,
        "admin":admin
        }
    return render(request, 'admin_profile.html', context)

def edit_admin_profile(request):
    user_id = request.session.get("user_id")
    admin = get_object_or_404(CustomUser, uid=user_id, role="admin")


    if request.method == 'POST':
        admin.name = request.POST.get("name")
        admin.email = request.POST.get("email")
        admin.number = request.POST.get("number")
        admin.dob = request.POST.get("dob")
        admin.address = request.POST.get("address")
        admin.company = request.POST.get("company")

        if 'profile_image' in request.FILES:
            admin.profile_image = request.FILES['profile_image']

        admin.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("admin_profile")
    
    obj = CustomUser.objects.filter(uid=user_id).first()
    context = {
        "uname":obj.name,
        "company_name":obj.company,
        "admin":admin
        }
    return render(request, "edit_admin_profile.html", context)




def change_admin_password(request):
    user_id = request.session.get("user_id")
    admin = get_object_or_404(CustomUser, uid=user_id, role="admin")
    obj = CustomUser.objects.filter(uid=user_id).first()
    context = {
        "uname": obj.name,
        "company_name": obj.company,
        "admin": admin
    }

    if request.method == "POST":
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        if new_password != confirm_password:
            messages.error(request, "New password and confirmation do not match.")
            return redirect("/change_admin_password/")

        admin.password = make_password(new_password)
        admin.save()
        messages.success(request, "Password updated successfully.")
        return redirect("/change_admin_password/")

    return render(request, "admin_change_password.html", context)
