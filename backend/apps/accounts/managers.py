from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """Email is the login. It is stored lowercase so `Ann@x.com` and `ann@x.com` are one account."""

    use_in_migrations = True

    def normalize_email(self, email):
        return (email or "").strip().lower()

    def get_by_natural_key(self, username):
        return self.get(email__iexact=username)

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Users must have an email address.")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)  # None → unusable password (e.g. GitHub-only sign-up)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        from .models import Role

        extra.setdefault("role", Role.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra["role"] != Role.ADMIN or not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("A superuser must have role=admin, is_staff=True, is_superuser=True.")
        return self._create_user(email, password, **extra)
