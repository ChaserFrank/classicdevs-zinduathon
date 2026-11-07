"""One function for writing audit entries, so every call site records the same fields."""

from typing import Any

from .models import AuditLog


def client_ip(request) -> str | None:
    """First address in X-Forwarded-For (set by the Render/Railway proxy), else REMOTE_ADDR."""
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def record(
    action: str,
    *,
    actor=None,
    target=None,
    request=None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Write an audit entry. `target` may be any model instance; its public id is preferred."""
    target_type, target_id = "", ""
    if target is not None:
        target_type = target._meta.label_lower
        target_id = str(getattr(target, "public_id", None) or target.pk)
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata or {},
        ip_address=client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:512] if request else ""),
    )
