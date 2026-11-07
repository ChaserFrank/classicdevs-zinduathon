# Decisions

Short ADR-style log. Newest at the bottom. Each entry: decision, why, trade-off.

## D-001 Django 5.2 LTS instead of 5.1 (Phase 1)

The brief names Django 5.1, which stopped receiving security fixes in December 2025. 5.2 is the
current LTS (supported to April 2028) with the same APIs we use. DRF moves to 3.18 (3.15 doesn't
support Django 5.2). Trade-off: none for our code; the brief's intent ("boring, well-known") holds.

## D-002 Custom User model created in Phase 1 (Phase 1)

Django cannot cleanly switch `AUTH_USER_MODEL` once auth migrations exist in a database. The
`accounts.User` model (email login, roles, phone, verification timestamps) is therefore created in
the first migration; profiles, JWT endpoints and OAuth follow in Phase 2 as planned.

## D-003 Email unique twice: `unique=True` and `UniqueConstraint(Lower("email"))` (Phase 1)

Django's auth check requires `unique=True` on `USERNAME_FIELD`. The lower-case expression constraint
from the brief stays as well: `save()` lowercases emails, but raw SQL or `bulk_create` bypass it.
Trade-off: two indexes on a small table.

## D-004 Local PostgreSQL on host port 5433 (Phase 1)

Developers often already run a Postgres on 5432 (this machine does). docker-compose maps
`${POSTGRES_HOST_PORT:-5433}` → 5432; `.env.example` points `DATABASE_URL` there. Inside Docker and
in CI the standard 5432 is used.

## D-005 JWT is the only authentication class (Phase 1)

No session authentication on the API: the client is a token-based SPA, so CSRF tokens aren't
needed, and unauthenticated calls get `401` with `WWW-Authenticate: Bearer` (the frontend's cue to
refresh) rather than `403`. Django admin keeps its own session login.

## D-006 Health checks ping Redis directly, not via the Django cache (Phase 1)

Tests use an in-memory cache, and what matters operationally is the Celery broker. The check
connects to `REDIS_URL` with a 2-second timeout.

## D-007 Small env helpers instead of django-environ (Phase 1)

Four functions in `config/settings/env.py` cover every setting; `python-dotenv` loads a local
`.env` without overriding real environment variables. One less dependency to explain.

## D-008 Validation `fields` keys are dotted paths (Phase 1)

Nested serializer errors are flattened to `{"contact.phoneNumber": ["..."]}` so the frontend can
map each message to an input without walking nested objects. Errors not tied to a field go under
`nonFieldErrors`.

## D-009 API docs are not throttled (Phase 1)

The 60/hour anonymous throttle would lock judges out of Swagger quickly at a shared venue IP.
`/schema/`, `/docs/`, `/redoc/` and `/health` are exempt; everything else is throttled.

## D-010 Pip timeout and retries in the Dockerfile (Phase 1)

Large wheel downloads timed out on a slow connection during the first build. `PIP_DEFAULT_TIMEOUT`
and `PIP_RETRIES` make builds survive venue Wi-Fi. CI also builds the image on every push.
