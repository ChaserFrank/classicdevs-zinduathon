"""Login throttle. Other scopes (phone_code, password_reset) use DRF's ScopedRateThrottle with
`throttle_scope` on the view. Rates live in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]."""

from rest_framework.throttling import SimpleRateThrottle


class LoginThrottle(SimpleRateThrottle):
    """5/minute per (IP, email): slows password guessing against one account without letting one
    noisy IP (a whole venue on shared Wi-Fi) lock everyone else out."""

    scope = "login"

    def get_cache_key(self, request, view):
        email = str(request.data.get("email", "")).strip().lower()[:254]
        ident = f"{self.get_ident(request)}:{email}"
        return self.cache_format % {"scope": self.scope, "ident": ident}
