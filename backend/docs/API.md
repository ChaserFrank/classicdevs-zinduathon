# API

Interactive docs: **`/api/v1/docs/`** (Swagger UI, with an Authorize button for the JWT) and
**`/api/v1/redoc/`**. Both work offline. The OpenAPI schema is committed as `backend/openapi.yaml`
(`make schema`); CI fails if it's out of date.

## Conventions

| Topic | Rule |
| --- | --- |
| Versioning | Everything under `/api/v1/` |
| Casing | JSON keys and query params are camelCase (`pageSize`, `minScore`); Python stays snake_case |
| Auth | `Authorization: Bearer <access token>`; see `AUTH.md` |
| Pagination | `?page=&pageSize=` (default 20, max 100) → `{count, next, previous, results}` |
| Errors | `{code, message, fields?}`; `fields` maps each invalid field (dotted for nested) to messages |
| Ids | Public UUIDs or natural keys (GitHub login, skill slug); never database ids |
| Request id | Every response has `X-Request-ID`; send your own to correlate logs |
| Rate limits | anon 60/h, user 600/h, login 5/min per IP+email, analyses 10/h, feedback 30/h, phone codes 3/h, reset emails 5/h → `429 rate_limited` |

### Error codes

`validation_error`, `not_authenticated`, `token_invalid`, `permission_denied`,
`recruiter_not_approved`, `email_not_verified`, `not_found`, `rate_limited`, `server_error`,
`no_public_repos`, `github_not_linked`, `github_rate_limited`, `analysis_in_progress`,
`invalid_credentials`, `state_invalid`, `github_oauth_failed`, `github_email_unverified`,
`github_already_linked`, `github_not_configured`, `password_required`, `terms_required`,
`recruiter_signup_requires_email`, `phone_missing`, `code_invalid`, `code_attempts_exceeded`,
`already_shortlisted`. Analysis failures report `not_found`, `no_public_repos`,
`github_rate_limited`, `github_unavailable`, `timeout` or `server_error` in `errorCode`.

## Endpoints by role

| Area | Endpoint | Anyone | Job seeker | Recruiter (approved) | Admin |
| --- | --- | --- | --- | --- | --- |
| System | `GET /health` | ✓ | | | |
| Auth | `POST /auth/register`, `/auth/login`, `/auth/token/refresh`, `/auth/password/reset[/confirm]`, `/auth/email/verify`, `GET /auth/github/authorize`, `POST /auth/github/callback` | ✓ | | | |
| Auth | `POST /auth/logout`, `/auth/email/resend`, `/auth/password/change`, `/auth/phone/send-code`, `/auth/phone/verify`, `DELETE /auth/github` | | ✓ | ✓ | ✓ |
| Profile | `GET/PATCH/DELETE /me`, `GET /me/export`, `GET/PUT /me/notification-preferences` | | ✓ | ✓ | ✓ (no self-delete) |
| Profile | `GET/PUT /me/claimed-skills`, `GET /me/profile-views` | | ✓ | | |
| Analyses | `POST /analyses`, `GET /analyses`, `GET /analyses/{id}` | | own | | any |
| Analyses | `GET /cards/{githubLogin}` | ✓ | | | |
| Skills | `GET /skills?search=` | ✓ | | | |
| Candidates | `GET /candidates`, `GET /candidates/{login}`, `POST /candidates/{login}/feedback` | | | ✓ | ✓ |
| Feedback | `GET /feedback` | | received | sent | |
| Feedback | `POST /feedback/{id}/read` | | ✓ | | |
| Jobs | `GET /jobs`, `GET /jobs/{id}` | | open jobs | own company | all |
| Jobs | `POST /jobs`, `PATCH/DELETE /jobs/{id}`, `GET /jobs/{id}/matches` | | | own | all |
| Jobs | `GET /jobs/{id}/match/me` | | ✓ | | |
| Shortlists | `GET/POST /shortlists`, `PATCH/DELETE /shortlists/{id}` | | | own | own |
| Notifications | `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all` | | ✓ | ✓ | ✓ |
| Webhooks | `POST /webhooks/thrivewave/delivery`, `/inbound` | signed | | | |
| Admin | `/admin/stats`, `/admin/recruiters[/{id}/approve|reject]`, `/admin/users[/{id}]`, `/admin/notification-deliveries[/{id}/retry]`, `/admin/audit-log`, `/admin/feedback/held`, `/admin/feedback/{id}/release|reject`, `/admin/skills[/{slug}]`, `/admin/dependency-mappings[/{ecosystem}/{package}]` | | | | ✓ |

Pending, rejected or suspended recruiters can sign in and read `/me`; recruiter endpoints answer
`403 recruiter_not_approved`.

## curl walkthrough (after `python manage.py seed_demo`)

```bash
API=http://localhost:8000/api/v1
PW=SkillProof-demo-2026

# Sign in as a recruiter
TOKEN=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"grace@savanna.demo\",\"password\":\"$PW\"}" | jq -r .access)

# Find Python developers with at least moderate evidence, best first
curl -s "$API/candidates?skills=python&minLabel=moderate" -H "Authorization: Bearer $TOKEN" | jq '.results[] | {githubLogin, signalScore}'

# Read one card and send feedback
curl -s $API/candidates/amina-demo -H "Authorization: Bearer $TOKEN" | jq .card.subScores
curl -s -X POST $API/candidates/amina-demo/feedback -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"status":"interview","message":"Free for a call on Thursday?"}'

# As the job seeker: start a fresh analysis and poll it
JS=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"amina@jobseeker.demo\",\"password\":\"$PW\"}" | jq -r .access)
ID=$(curl -s -X POST $API/analyses -H "Authorization: Bearer $JS" -H 'Content-Type: application/json' -d '{"force":true}' | jq -r .id)
curl -s $API/analyses/$ID -H "Authorization: Bearer $JS" | jq '{status, progressStep, errorCode}'

# Public share link (no auth)
curl -s $API/cards/amina-demo | jq '{signalScore, aiSummary}'
```

(The demo personas exist only in the seed; a forced re-analysis of `amina-demo` calls the real
GitHub API and will fail with `not_found` unless such an account exists. Use
`warm_demo --logins <real login>` for live accounts.)
