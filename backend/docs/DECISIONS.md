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

## D-011 Dev-only GitHub sign-in pages (Phase 2)

There is no frontend yet, and GitHub must redirect the browser somewhere. `/auth/github/dev-login`
and `/auth/github/dev-callback` act as the frontend's callback page so OAuth can be tested from a
browser and Swagger. They are excluded from the schema and return 404 unless
`GITHUB_DEV_CALLBACK_ENABLED` (dev settings only). Production settings never enable them.

## D-012 Phone codes echoed as `devCode` in local development (Phase 2)

Until Thrivewave is wired up, SMS is dry-run and codes go nowhere. Dev settings set
`SMS_DEV_ECHO_CODES` so the send-code response includes the code. Codes are still never logged, and
the flag is off in test and production settings.

## D-013 Email links use signed tokens; only SMS codes use the VerificationCode table (Phase 2)

Email verification links are signed (Django `signing`, 3 days, bound to the address). Password reset
signs Django's own token generator output, which is single-use because it hashes the password. Both
are stateless, so nothing needs cleaning up. SMS codes are short and guessable, so they need stored
state (HMAC, expiry, attempt counter).

## D-014 New error codes (Phase 2)

Added to the brief's list: `invalid_credentials`, `state_invalid`, `github_oauth_failed`,
`github_email_unverified`, `github_already_linked`, `github_not_configured`, `password_required`,
`terms_required`, `recruiter_signup_requires_email`, `phone_missing`, `code_invalid`,
`code_attempts_exceeded`. Each is documented on its endpoint in Swagger.

## D-015 GitHub sign-up creates job seekers only (Phase 2)

The brief says recruiters "link only" via GitHub. A recruiter needs a company and admin approval,
which the GitHub flow can't collect, so recruiter sign-up stays email-based.

## D-016 Pre-registered email accounts are reclaimed on GitHub sign-in (Phase 2)

If someone registered an address they don't own (never verified), and the real owner later signs in
with GitHub (whose verified primary email matches), we link GitHub and remove the squatter's
password, then sign everyone out of that account. Without this, the squatter could keep access.

## D-017 Consent: one "terms" checkbox records both terms and privacy (Phase 2)

The register form has one required checkbox for the terms and privacy policy, stored as two
`ConsentRecord` rows. Feedback-by-email and feedback-by-SMS consents default to false (opt-in).

## D-018 Synthetic GitHub fixtures until a token is available (Phase 3)

The brief asks for recorded responses from three real accounts. Recording needs a `GITHUB_TOKEN`
(60 unauthenticated requests/hour is not enough for one account). Until then, pipeline tests run on
three persona fixtures in `tests/fixtures/github/personas/`, expanded into GitHub's exact response
shapes (pagination and `Link` headers included). `scripts/record_fixtures.py` records real
accounts into `recordings/` in replayable form once a token is set.

## D-019 Commit sampling is per repo; user commits capped at 300 per repo (Phase 3)

`ANALYSIS_COMMIT_SAMPLE=20` is read per repo, because the iteration and flag rules are per repo.
That is up to 300 detail requests for 15 repos (within the 5,000/hour token limit, cached by ETag).
User commits are paged up to 3 × 100; total counts use the `per_page=1` + `rel="last"` trick.

## D-020 Manifests one directory deep (Phase 3)

Monorepos keep `package.json` in `frontend/` or `backend/`. We read manifests at the root and one
level down (max 5 per repo, skipping `node_modules/`, `vendor/`, `dist/`, `build/`, virtualenvs).

## D-021 Rounding is half-up everywhere (Phase 3)

Sub-scores and evidence round half up (10.5 → 11, 0.015 → 0.02). Python's `round()` rounds halves
to even and suffers float representation, which gave 0.01 for 0.015.

## D-022 Analysis stores a profile snapshot and tips (Phase 3)

`Analysis.github_name` and `avatar_url` snapshot the GitHub profile shown on the card. `tips` is a
small JSON list of display text, derived on each run and never queried, so a JSON column is within
the brief's rule (JSON only for data that is not queried or filtered).

## D-023 One active analysis per login, enforced by the database (Phase 3)

A partial unique constraint on `(github_login)` where status is queued/running backs up the 409
check against double clicks and races. An analysis untouched for 15 minutes is marked failed
(`timeout`) so a crashed worker can't block a login forever.

## D-024 Public cards prefer job-seeker analyses (Phase 3)

`/cards/{login}` returns the latest completed analysis owned by a job seeker if one exists, else
the latest admin-run one (used for demo warm-up). Admin-run analyses only read public GitHub data.

## D-025 Anthropic SDK for the summary, Claude Opus 5.5 by default (Phase 3)

The official `anthropic` SDK (not raw HTTP) with model `claude-opus-5-5` unless `LLM_MODEL` says
otherwise, effort `low` (a short, well-specified writing task), a 15 s timeout, one retry, and
server-side refusal fallback (`fallbacks: "default"`). Only the Anthropic provider is implemented;
the `SummaryProvider` protocol leaves room for another.
