"""Settings shared by every environment.

Everything that differs between machines comes from environment variables (see `.env.example`), so
the same code runs on a laptop, in CI and on Render/Railway. Environment-specific files (dev, test,
prod) only override what they must.
"""

from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

from .env import env_bool, env_int, env_list, env_str

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# A local `.env` is convenient for development; real environment variables always win.
load_dotenv(BASE_DIR / ".env", override=False)

SECRET_KEY = env_str("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

APP_VERSION = env_str("APP_VERSION", "0.1.0")
GIT_COMMIT_SHA = env_str("GIT_COMMIT_SHA", "")
FRONTEND_URL = env_str("FRONTEND_URL", "http://localhost:3000").rstrip("/")

# --- Applications ---------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "drf_spectacular_sidecar",
]
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "apps.core.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Turns ?pageSize=&minScore= into page_size/min_score so Python code stays snake_case.
    "djangorestframework_camel_case.middleware.CamelCaseMiddleWare",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database (PostgreSQL only; no SQLite anywhere so tests see real constraints) -----------------
DATABASES = {
    "default": dj_database_url.parse(
        env_str("DATABASE_URL", "postgres://skillproof:skillproof@localhost:5433/skillproof"),
        conn_max_age=env_int("DB_CONN_MAX_AGE", 60),
        conn_health_checks=True,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth -----------------------------------------------------------------------------------------
# Custom user model from day one: swapping it after the first migration is painful in Django.
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalisation -------------------------------------------------------------------------
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# --- Static files (WhiteNoise serves admin + API docs assets without a separate web server) -------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# --- Redis: cache (throttles) and Celery broker ---------------------------------------------------
REDIS_URL = env_str("REDIS_URL", "redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "skillproof",
    }
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = None  # results live in PostgreSQL (Analysis/Delivery rows), not Redis
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE: dict = {}

# --- CORS / CSRF ----------------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
CORS_EXPOSE_HEADERS = ["Content-Disposition", "X-Request-ID"]
CORS_ALLOW_HEADERS = (
    "accept",
    "authorization",
    "content-type",
    "x-request-id",
)
JWT_REFRESH_IN_COOKIE = env_bool("JWT_REFRESH_IN_COOKIE", False)
CORS_ALLOW_CREDENTIALS = JWT_REFRESH_IN_COOKIE

# --- Django REST Framework ------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": (
        "djangorestframework_camel_case.render.CamelCaseJSONRenderer",
        "djangorestframework_camel_case.render.CamelCaseBrowsableAPIRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "djangorestframework_camel_case.parser.CamelCaseJSONParser",
        "djangorestframework_camel_case.parser.CamelCaseFormParser",
        "djangorestframework_camel_case.parser.CamelCaseMultiPartParser",
    ),
    # JWT only (no session auth): the API is stateless and needs no CSRF tokens. Anonymous
    # requests get 401 + WWW-Authenticate: Bearer, which tells the frontend to refresh.
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/hour",
        "user": "600/hour",
        "login": "5/minute",
        "analysis": "10/hour",
        "feedback": "30/hour",
        "phone_code": "3/hour",
        "password_reset": "5/hour",
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# --- OpenAPI docs ---------------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "SkillProof API",
    "DESCRIPTION": (
        "SkillProof turns a developer's public GitHub history into an explained skill card: "
        "proven skills, a Signal Score built from five rule-based sub-scores, and the evidence "
        "behind each number. Recruiters search and give feedback; job seekers receive it "
        "in-app, by email and by SMS.\n\nConventions: JSON with camelCase keys, "
        "`Authorization: Bearer <access token>`, "
        "page-number pagination (`?page=&pageSize=`), errors shaped "
        "`{code, message, fields?}`."
    ),
    "VERSION": APP_VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True, "displayRequestDuration": True},
    "CAMELIZE_NAMES": False,
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.contrib.djangorestframework_camel_case.camelize_serializer_fields",
        "drf_spectacular.hooks.postprocess_schema_enums",
    ],
    # Clean, stable enum names in generated TypeScript (instead of e.g. "RedisEnum").
    "ENUM_NAME_OVERRIDES": {
        "DependencyStatusEnum": ["ok", "down"],
        "HealthStatusEnum": ["ok", "degraded"],
    },
    "TAGS": [
        {"name": "System", "description": "Health and version"},
        {"name": "Auth", "description": "Registration, sign-in, tokens, GitHub OAuth"},
        {"name": "Profile", "description": "The signed-in user's own data"},
        {"name": "Analyses", "description": "Run and read GitHub analyses and skill cards"},
        {"name": "Skills", "description": "Skill catalogue"},
        {"name": "Candidates", "description": "Recruiter search over job seekers"},
        {"name": "Jobs", "description": "Job postings and match scores"},
        {"name": "Shortlists", "description": "Recruiter shortlists"},
        {"name": "Feedback", "description": "Recruiter feedback to job seekers"},
        {"name": "Notifications", "description": "In-app inbox and preferences"},
        {"name": "Admin", "description": "Admin-only management API"},
    ],
}

# --- Logging (JSON lines with a request id, so one request can be followed across services) -------
LOG_FORMAT = env_str("LOG_FORMAT", "json")
LOG_LEVEL = env_str("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "apps.core.logging.RequestIdFilter"}},
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
            "rename_fields": {"asctime": "time", "levelname": "level", "name": "logger"},
        },
        "text": {"format": "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": LOG_FORMAT if LOG_FORMAT in {"json", "text"} else "json",
            "filters": ["request_id"],
        }
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "django.db.backends": {"level": "WARNING"},
    },
}

# --- Error tracking (optional) --------------------------------------------------------------------
SENTRY_DSN = env_str("SENTRY_DSN")
if SENTRY_DSN:  # pragma: no cover - only in deployed environments
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        release=GIT_COMMIT_SHA or APP_VERSION,
        traces_sample_rate=0.1,
        send_default_pii=False,  # never ship emails/phones/tokens to a third party
    )
