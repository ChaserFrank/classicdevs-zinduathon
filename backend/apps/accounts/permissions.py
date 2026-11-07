"""Role permissions. Object-level checks live in `IsOwnerOrAdmin`.

A recruiter who is pending/rejected/suspended can sign in and read `/me` (to see their status),
but every recruiter-only endpoint answers 403 `recruiter_not_approved`.
"""

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.companies.models import ApprovalStatus

from .models import Role


def _signed_in(request) -> bool:
    return bool(request.user and request.user.is_authenticated)


def is_admin(user) -> bool:
    return bool(user and user.is_authenticated and user.role == Role.ADMIN)


def is_approved_recruiter(user) -> bool:
    if not (user and user.is_authenticated and user.role == Role.RECRUITER):
        return False
    profile = getattr(user, "recruiter_profile", None)
    return bool(profile and profile.approval_status == ApprovalStatus.APPROVED)


class IsJobSeeker(BasePermission):
    message = "Only job seekers can do this."

    def has_permission(self, request, view):
        return _signed_in(request) and request.user.role == Role.JOB_SEEKER


class IsAdminRole(BasePermission):
    message = "Only admins can do this."

    def has_permission(self, request, view):
        return is_admin(request.user)


class IsApprovedRecruiter(BasePermission):
    message = "Only approved recruiters can do this."

    def has_permission(self, request, view):
        if not _signed_in(request) or request.user.role != Role.RECRUITER:
            return False
        if not is_approved_recruiter(request.user):
            raise PermissionDenied(
                "Your recruiter account is not approved yet.", code="recruiter_not_approved"
            )
        return True


class IsApprovedRecruiterOrAdmin(BasePermission):
    message = "Only approved recruiters and admins can do this."

    def has_permission(self, request, view):
        if is_admin(request.user):
            return True
        return IsApprovedRecruiter().has_permission(request, view)


class IsOwnerOrAdmin(BasePermission):
    """Object-level: the view's object must belong to the user (via `owner_field`, default
    "user"), unless the user is an admin."""

    message = "You can only access your own records."

    def has_permission(self, request, view):
        return _signed_in(request)

    def has_object_permission(self, request, view, obj):
        if is_admin(request.user):
            return True
        owner = obj
        for part in getattr(view, "owner_field", "user").split("__"):
            owner = getattr(owner, part, None)
        return owner == request.user
