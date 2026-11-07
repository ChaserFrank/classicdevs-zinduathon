"""Scheduled housekeeping (Celery beat). See config/settings/base.py CELERY_BEAT_SCHEDULE."""

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

NOTIFICATION_BODY_DAYS = 180
GITHUB_CACHE_DAYS = 7


@shared_task(ignore_result=True)
def apply_retention() -> dict:
    """Data minimisation (Kenya DPA): message bodies older than 180 days are blanked (the fact a
    notification existed stays, for delivery statistics), raw GitHub responses older than 7 days
    are deleted."""
    from apps.analysis.models import GithubCache
    from apps.core import audit
    from apps.notifications.models import Delivery, Notification

    body_cutoff = timezone.now() - timedelta(days=NOTIFICATION_BODY_DAYS)
    old = Notification.objects.filter(created_at__lt=body_cutoff).exclude(body="")
    cleared = old.update(body="")
    Delivery.objects.filter(created_at__lt=body_cutoff, provider_response__has_key="render").update(
        provider_response={}
    )
    cache_deleted, _ = GithubCache.objects.filter(
        fetched_at__lt=timezone.now() - timedelta(days=GITHUB_CACHE_DAYS)
    ).delete()
    result = {"notification_bodies_cleared": cleared, "github_cache_deleted": cache_deleted}
    audit.record("system.retention", metadata=result)
    return result
