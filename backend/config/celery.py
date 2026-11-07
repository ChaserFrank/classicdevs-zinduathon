"""Celery app. Analyses and notification deliveries run here so slow GitHub/SMTP/SMS calls never
hold an HTTP request open. Configuration comes from Django settings prefixed CELERY_."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("skillproof")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
