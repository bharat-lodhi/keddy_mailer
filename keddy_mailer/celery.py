from __future__ import absolute_import
import os
from celery import Celery


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'keddy_mailer.settings')

app = Celery('keddy_mailer')
app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

# 👇 Add this line to force task registration
import keddy_mailer.schedule_tasks

__all__ = ('celery_app',)
