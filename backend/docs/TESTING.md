# Testing

## Running

```bash
make services      # PostgreSQL + Redis in Docker (tests never use SQLite)
make test          # pytest
make cov           # with coverage report
```

`pytest` uses `config.settings.test`: PostgreSQL from `DATABASE_URL`, fast MD5 password hashing,
in-memory email and cache, Celery tasks run inline. The health tests also ping the real Redis.

## Coverage targets

- Pure scoring code (`apps/analysis/services/`, from Phase 3): **≥ 95% line coverage**.
- Overall: **≥ 80%**.

## What each test file covers

| File | Covers |
| --- | --- |
| `tests/core/test_health.py` | `/health` healthy, Redis down, DB down, ignores bad tokens |
| `tests/core/test_middleware.py` | Request ID generation, reuse of safe ids, rejection of unsafe ids, log filter |
| `tests/core/test_exceptions.py` | Error shape for validation (camelCase, nested), 401, 403 with specific codes, 404, 429, 500 without leaking details, domain errors |
| `tests/core/test_api_basics.py` | JSON 404 for unknown URLs, docs are public, schema tags, CORS allow/deny, pagination (size, cap, camelCase param, shape) |
| `tests/core/test_audit.py` | Audit entries: actor/target/IP/user agent, anonymous actor, append-only, survives user deletion |
| `tests/accounts/test_register_login.py` | Register (job seeker, recruiter, consents, email sent, validation), login (success, audit of failures, suspended, throttle per IP+email, claims) |
| `tests/accounts/test_tokens.py` | Refresh rotation + blacklist, claims reloaded, suspended users, logout and its permissions |
| `tests/accounts/test_email_password.py` | Email verification (expiry, address binding, idempotent), password reset (single use, 1 hour, no enumeration, throttle), password change |
| `tests/accounts/test_phone.py` | Kenyan number formats, send/verify, codes hashed and never logged, 5 attempts, expiry, newest code only, throttle |
| `tests/accounts/test_github_oauth.py` | Authorize URL, callback: new user, existing github_id, link by verified email, link while signed in, conflicts, bad/expired state, bad code, GitHub down, unverified email, terms, recruiter refusal, unlink |
| `tests/accounts/test_me.py` | `/me` shape per role, PATCH per role, phone rules, read-only fields |
| `tests/accounts/test_permissions.py` | Role × permission matrix, `recruiter_not_approved` for pending/rejected/suspended, owner-or-admin |
| `tests/accounts/test_dev_callback.py` | Dev pages hidden by default, redirect + state cookie, escaping, not in schema, missing config |
| `tests/companies/test_approval.py` | Approve/reject/suspend with audit, email must be verified, company reuse, Django admin bulk action |
| `tests/core/test_crypto.py` | Fernet round trip, wrong/missing key, deploy check |
| `tests/accounts/test_user_model.py` | Lowercase email, case-insensitive uniqueness (ORM and raw SQL), phone uniqueness with NULLs, role constraint, superuser rules |

## Adding tests

- Put factories in `tests/factories.py` (one per model).
- Mock every outbound HTTP call with `responses`; tests never hit GitHub, the LLM or Thrivewave.
- Recorded GitHub API responses go under `tests/fixtures/github/<login>/` (script arrives in
  Phase 3).
- Any change to a scoring rule or threshold gets a line in `../TESTING_LOG.md`.
