
# followups/apps.py
from django.apps import AppConfig

class FollowupsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'followups'
    verbose_name = 'Follow Up Campaigns'
    
    def ready(self):
        # Import signals and tasks
        try:
            import followups.signals
            import followups.tasks
        except ImportError:
            pass