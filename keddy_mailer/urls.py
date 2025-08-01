"""
URL configuration for keddy_mailer project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from . import views

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    
    path('',views.home ,),
    path('login/',views.login,name="login"),
    path('register/',views.register,name="register"),
    path('logout/',views.logout),
    
    #  ----------------User URLS----------------------
    path('userhome/',views.userhome),
    path('add_server/',views.add_server),
    path('add_list/',views.add_list),
    path('add_template/',views.add_template),
    path('create_campaign/',views.create_campaign),
    path('campaign_success/',views.campaign_success),

    path('track_open/<int:campaign_id>/<str:email>/', views.track_open),
    path('track_click/<int:campaign_id>/<path:email>/', views.track_click),
    path('track_attachment/<int:campaign_id>/<str:email>/', views.track_attachment),
    path("analytics/", views.campaign_analytics),
    
    path('smtp_list/', views.smtp_server_list, name='smtp_list'),
    path('delete_smtp/<int:id>/', views.delete_smtp, name='delete_smtp'),
    path('edit_smtp_server/<int:server_id>/', views.edit_smtp_server, name='edit_smtp_server'),

    path('email_lists/', views.email_list_view),
    path("delete_list_user/<int:list_id>/", views.delete_list_user, name="delete_list_user"),
    path('edit_email_list/<int:list_id>', views.edit_email_list),
    
    path("template_list/", views.template_list, name="template_list"),
    path("edit_template/<int:id>", views.edit_template, name="edit_template"),
    path("delete_template/<int:id>", views.delete_template, name="delete_template"),
    
    path('campaign_list/', views.campaign_list ,name='campaign_list'),
    path('delete_campaign/<int:campaign_id>/', views.delete_campaign),

    path("subscription/<str:email>/", views.toggle_subscription, name="toggle_subscription"),
    
    path("user_profile/", views.user_profile, name="user_profile"),
    path("edit_user_profile/", views.edit_user_profile, name="edit_user_profile"),
    path("change_user_password/", views.change_user_password, name="change_user_password"),
    

    path("chat/", views.chat_page, name="chat_page"),
    path("send_message/", views.send_message, name="send_message"),
    path("fetch_messages/", views.fetch_messages, name="fetch_messages"),

    # # ---------------------- ADMIN URLS ---------------------------------------
    
    path("admin/chat/", views.admin_chat_panel, name="admin_chat_panel"),
    path("admin/send_message/", views.admin_send_message, name="admin_send_message"),
    path("admin/fetch_messages/", views.admin_fetch_messages, name="admin_fetch_messages"),


    path('adminhome/',views.adminhome),
    path('user_list/',views.user_list),
    path("toggle_user_status/<str:uid>/", views.toggle_user_status, name="toggle_user_status"),
    path("delete_user/<str:uid>/", views.delete_user_permanent, name="delete_user_permanent"),
    path('edit_user/<str:uid>/', views.edit_user, name='edit_user'),
    path("add_user/", views.add_user, name="add_user"),
    path("all_email_lists/", views.all_email_lists, name="all_email_lists"),
    path("download_email_list/<int:list_id>/", views.download_email_list, name="download_email_list"),
    path('delete_email_list/<int:list_id>', views.delete_email_list,name= "delete_email_list"),
    path("all_templates/", views.all_templates, name="all_templates"),
    path("delete_template_admin/<int:tid>/", views.delete_template_admin, name="delete_template_admin"),
    path("edit_template_admin/<int:tid>/", views.edit_template_admin, name="edit_template_admin"),
    path('add_template_admin/', views.add_template_admin, name='add_template_admin'),
    path("all_campaign_admin/", views.all_campaign_admin, name="all_campaign_admin"),
    path("delete_campaign_admin/<int:campaign_id>/", views.delete_campaign_admin, name="delete_campaign_admin"),
    path("all_server_admin/", views.all_server_admin, name="all_server_admin"),
    path('delete_server_admin/<int:smtp_id>/', views.delete_server_admin, name='delete_server_admin'),
    path('toggle_smtp_status/<int:smtp_id>/', views.toggle_smtp_status, name='toggle_smtp_status'),
    path('edit_smtp_admin/<int:smtp_id>/', views.edit_smtp_admin, name='edit_smtp_admin'),
    path('add_server_admin/', views.add_server_admin, name='add_server_admin'),
    path("user_credits_admin/", views.user_credits_admin, name="user_credits_admin"),
    path("edit_user_credit/<int:user_id>/", views.edit_user_credit, name="edit_user_credit"),
    
    path("admin_profile/", views.admin_profile, name="admin_profile"),
    path("edit_admin_profile/", views.edit_admin_profile, name="edit_admin_profile"),
    path("change_admin_password/", views.change_admin_password, name="change_admin_password"),

    
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    
handler404 = 'keddy_mailer.views.custom_page_not_found'
