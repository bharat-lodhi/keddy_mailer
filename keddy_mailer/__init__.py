from __future__ import absolute_import
from .celery import app as celery_app
import keddy_mailer.schedule_tasks 
__all__ = ('celery_app',)

