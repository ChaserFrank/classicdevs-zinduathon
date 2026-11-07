# SkillProof backend

Django + DRF API for **SkillProof** (Zinduathon 3.0, "Noise vs Signal"). It turns a developer's
public GitHub history into an explained skill card: proven skills, a Signal Score (0–100) built from
five rule-based sub-scores, and the evidence behind every number. Recruiters search, shortlist and
send feedback; job seekers receive it in-app, by email and by SMS (Thrivewave).

> Status: **Phases 1–3** complete (foundation; accounts and auth; analysis pipeline). See `docs/DECISIONS.md` and `../TESTING_LOG.md`.

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
tests/             mirrors apps/; fixtures/github/ for recorded GitHub API responses
docs/              AUTH.md, SCORING.md, DECISIONS.md, TESTING.md (more arrive with their phases)
scripts/           record_fixtures.py (record real GitHub responses for tests)
```

## API conventions

- Base path `/api/v1/`, JSON with **camelCase** keys (Python stays snake_case).
- `Authorization: Bearer <access token>` (JWT).
- Pagination `?page=&pageSize=` (max 100) → `{count, next, previous, results}`.
- Errors are always `{code, message, fields?}`; every response carries `X-Request-ID`.
