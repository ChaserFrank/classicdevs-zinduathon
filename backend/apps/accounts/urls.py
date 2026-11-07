from django.urls import path

from . import dev_views, views

urlpatterns = [
    path("auth/register", views.RegisterView.as_view(), name="auth-register"),
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
    path("auth/token/refresh", views.RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", views.LogoutView.as_view(), name="auth-logout"),
    path(
        "auth/github/authorize", views.GithubAuthorizeView.as_view(), name="auth-github-authorize"
    ),
    path("auth/github/callback", views.GithubCallbackView.as_view(), name="auth-github-callback"),
    path("auth/github", views.GithubUnlinkView.as_view(), name="auth-github-unlink"),
    path("auth/github/dev-login", dev_views.dev_login, name="auth-github-dev-login"),
    path("auth/github/dev-callback", dev_views.dev_callback, name="auth-github-dev-callback"),
    path("auth/email/verify", views.EmailVerifyView.as_view(), name="auth-email-verify"),
    path("auth/email/resend", views.EmailResendView.as_view(), name="auth-email-resend"),
    path("auth/password/reset", views.PasswordResetView.as_view(), name="auth-password-reset"),
    path(
        "auth/password/reset/confirm",
        views.PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("auth/password/change", views.PasswordChangeView.as_view(), name="auth-password-change"),
    path("auth/phone/send-code", views.PhoneSendCodeView.as_view(), name="auth-phone-send-code"),
    path("auth/phone/verify", views.PhoneVerifyView.as_view(), name="auth-phone-verify"),
    path("me", views.MeView.as_view(), name="me"),
    path("me/export", views.MeExportView.as_view(), name="me-export"),
]
