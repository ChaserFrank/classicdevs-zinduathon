# SkillProof backend

Django + DRF API for **SkillProof** (Zinduathon 3.0, "Noise vs Signal"). It turns a developer's
public GitHub history into an explained skill card: proven skills, a Signal Score (0–100) built from
five rule-based sub-scores, and the evidence behind every number. Recruiters search, shortlist and
send feedback; job seekers receive it in-app, by email and by SMS (Thrivewave).

> Status: **Phases 1–6** complete. Phase 7 (hardening and deployment) is next. See `docs/DECISIONS.md` and `../TESTING_LOG.md`.

## Quick start (venv + Docker services) — recommended for development

```bash
cd backend
cp .env.example .env          # defaults work locally
make venv                     # .venv with dev requirements (Python 3.12)
make services                 # PostgreSQL (host port 5433), Redis (6379), Mailpit (1025 / UI 8025)
make migrate
make run                      # http://localhost:8000
```

## Quick start (everything in Docker)

```bash
cd backend && cp .env.example .env && make dev
```

Web on :8000 (with a Celery worker and beat), Mailpit UI at http://localhost:8025.

## Useful URLs

| URL | What |
| --- | --- |
| http://localhost:8000/api/v1/health | DB + Redis check, version, commit |
| http://localhost:8000/api/v1/docs/ | Swagger UI (works offline) |
| http://localhost:8000/api/v1/redoc/ | ReDoc |
| http://localhost:8000/api/v1/schema/ | OpenAPI 3 schema |
| http://localhost:8000/django-admin/ | Django admin (`python manage.py createsuperuser`) |
| http://localhost:8000/api/v1/auth/github/dev-login | Dev-only GitHub sign-in page (see `docs/AUTH.md`) |

## Everyday commands

| Command | Does |
| --- | --- |
| `make test` / `make cov` | Tests (against PostgreSQL) / with coverage |
| `make lint` / `make format` | ruff lint + format check / auto-fix |
| `make schema` | Regenerate the committed `openapi.yaml` |
| `make deploy-check` | `manage.py check --deploy` with production settings |

## Layout

```
config/            settings (base, dev, test, prod), urls, celery, wsgi/asgi
apps/core/         base models, audit log, error handler, pagination, request id, health
apps/accounts/     User, profiles, consents, JWT, email/phone verification, GitHub OAuth
apps/companies/    companies, recruiter profiles and approval
apps/skills/       skill catalogue, aliases, dependency mappings (seeded)
apps/analysis/     GitHub fetch, pure scoring rules, pipeline, analyses and cards
apps/notifications/ inbox, preferences, email + Thrivewave SMS deliveries, webhooks
apps/recruiting/   candidate search, jobs + match score, shortlists, feedback, profile views
apps/adminpanel/   admin API, seed_demo, warm_demo
tests/             mirrors apps/; fixtures/github/ for recorded GitHub API responses
docs/              see the table below; DECISIONS.md, TESTING.md (more arrive with their phases)
scripts/           record_fixtures.py (record real GitHub responses for tests)
```

## API conventions

- Base path `/api/v1/`, JSON with **camelCase** keys (Python stays snake_case).
- `Authorization: Bearer <access token>` (JWT).
- Pagination `?page=&pageSize=` (max 100) → `{count, next, previous, results}`.
- Errors are always `{code, message, fields?}`; every response carries `X-Request-ID`.

## Demo data

```bash
python manage.py seed_demo            # idempotent; prints the accounts below; sends no email/SMS
python manage.py warm_demo --logins octocat,another   # real GitHub analyses (needs GITHUB_TOKEN)
```

Password for every demo account: `SkillProof-demo-2026` (override with `DEMO_PASSWORD`).

| Role | Email |
| --- | --- |
| Admin | `admin@skillproof.demo` |
| Recruiter | `grace@savanna.demo`, `david@mawingu.demo` |
| Recruiter (pending approval) | `pending@mawingu.demo` |
| Job seekers | `amina@`, `brian@`, `chebet@`, `kipkorir@`, `njeri@`, `otieno@` + `jobseeker.demo` |

Their analyses come from six fictional GitHub personas run through the real scoring pipeline
(Signal Scores from 35 to 94), plus two open jobs, shortlists, feedback and profile views.

### Walkthrough for judges (Swagger at `/api/v1/docs/`)

1. `POST /auth/login` as `grace@savanna.demo`, then click **Authorize** and paste the `access` token.
2. `GET /candidates?skills=python&minLabel=moderate`: proven Python developers, best first.
3. `GET /candidates/amina-demo`: the skill card. Every number has a `reason`, every skill lists
   the repos that prove it, and flags show what to ask about.
4. `GET /jobs` then `GET /jobs/{id}/matches`: candidates ranked by match score.
5. `POST /candidates/chebet-demo/feedback`: the job seeker gets it in-app (and by email/SMS when
   configured). Try a rude message: it's held for admin review.
6. Sign in as `pending@mawingu.demo`: every recruiter endpoint answers `recruiter_not_approved`.
7. Sign in as `admin@skillproof.demo`: `GET /admin/stats`, approve the pending recruiter, read
   `/admin/audit-log`.

## Documentation

| Doc | What's in it |
| --- | --- |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Components, apps, request flows |
| [DATABASE](docs/DATABASE.md) | ER diagram, every table, constraints, normalisation |
| [API](docs/API.md) | Conventions, error codes, endpoints by role, curl walkthrough |
| [AUTH](docs/AUTH.md) | JWT, GitHub OAuth (setup + dev sign-in page), roles, approval |
| [SCORING](docs/SCORING.md) | Every rule with formulas and a worked example |
| [NOTIFICATIONS](docs/NOTIFICATIONS.md) | Events, templates, SMS length rule, Thrivewave adapter, webhooks |
| [FRONTEND_INTEGRATION](docs/FRONTEND_INTEGRATION.md) | Env, types, fetch wrapper, sign-in, polling, error codes |
| [SECURITY_AND_PRIVACY](docs/SECURITY_AND_PRIVACY.md) | Threats and controls, Kenya DPA |
| [TESTING](docs/TESTING.md) | How to run, coverage, fixtures, what each test covers |
| [DECISIONS](docs/DECISIONS.md) | Every significant choice and trade-off |
