"""Phone verification codes by SMS.

Uses the Thrivewave adapter directly: verification codes bypass notification preferences and are
not stored as Delivery rows, so the code never appears in the database or logs.
"""

from apps.notifications.providers import thrivewave


def send_sms(to_e164: str, message: str) -> str:
    """Send (or dry-run) an SMS. Returns "dry_run", "sent" or "failed"."""
    try:
        result = thrivewave.send(to_e164, message)
    except thrivewave.ThrivewaveTransientError:
        return "failed"
    if result.dry_run:
        return "dry_run"
    return "sent" if result.ok else "failed"
