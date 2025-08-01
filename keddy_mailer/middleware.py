
# middleware.py

from django.shortcuts import redirect

def sessioncheckrole_middleware(get_response):
    def middleware(request):
        path = request.path
        session = request.session
        
        
        # --- Paths that require login for "user" role ---
        user_paths = [
            '/userhome/',
            '/add_server/',
            '/add_list/',
            '/add_template/',
            '/create_campaign/',
            '/campaign_success/',
            '/smtp_list/',
            '/delete_smtp/',
            '/edit_smtp_server/',
            '/email_lists/',
            '/delete_list_user/',
            '/edit_email_list/',
            '/template_list/',
            '/edit_template/',
            '/delete_template/',
            '/campaign_list/',
            '/delete_campaign/',
            '/subscription/',
            '/analytics/',
            '/user_profile/',
            '/edit_user_profile/',
            '/change_user_password/',
        ]

        # --- Paths that require login for "admin" role ---
        admin_paths = [
            '/adminhome/',
            '/user_list/',
            '/toggle_user_status/',
            '/delete_user/',
            '/edit_user/',
            '/add_user/',
            '/all_email_lists/',
            '/download_email_list/',
            '/delete_email_list/',
            '/all_templates/',
            '/delete_template_admin/',
            '/edit_template_admin/',
            '/add_template_admin/',
            '/all_campaign_admin/',
            '/delete_campaign_admin/',
            '/all_server_admin/',
            '/delete_server_admin/',
            '/toggle_smtp_status/',
            '/edit_smtp_admin/',
            '/add_server_admin/',
            '/user_credits_admin/',
            '/edit_user_credit/',
            '/admin_profile/',
            '/edit_admin_profile/',
            '/change_admin_password/',
        

        ]

        # --- Check login status ---
        if any(path.startswith(up) for up in user_paths):
            if session.get('role') != 'user':
                return redirect('/login/')

        elif any(path.startswith(ap) for ap in admin_paths):
            if session.get('role') != 'admin':
                return redirect('/login/')

        return get_response(request)
    return middleware
