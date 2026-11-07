# Claude Code prompt: SkillProof backend (Django + DRF + PostgreSQL)

> How to use: put this file in the root of the repository as `BACKEND_PROMPT.md`, open Claude Code in the
> repository, and say: **"Read BACKEND_PROMPT.md and build the backend it describes, phase by phase. Stop at the
> end of each phase, show me the test results, and wait for me to say continue."**

---

## 0. Your role and how to work

You are a senior Django engineer building the backend for **SkillProof**, a hackathon project for
Zinduathon 3.0 (Zindua School, Nairobi), theme **"Noise vs Signal: proof of work, proof of skill in the AI era."**
The judges reward: a working product they can see, technical choices the team can explain, and evidence of
testing, iteration and impact. Build to that standard.

Rules for how you work:

1. **Work in the phases in section 14, in order.** At the end of each phase: run `ruff check .`, run
   `pytest`, run `python manage.py check --deploy` (from Phase 2 onward, with production settings), make one git
   commit with a clear message, and summarise what you built and what the tests show. Then stop and wait.
2. **Never invent the Thrivewave API format.** Its reference is not public. Implement the adapter exactly as
   described in section 9 with the request format in one replaceable function, and ask me for the docs when you
   reach it.
3. **Scoring rules are pure Python** (no Django imports, no network) and are the most tested code in the project.
4. **Every number shown to users must be traceable to a rule.** The AI model only writes summary text.
5. **Do not change the API contract in section 7** without telling me: a React frontend already depends on it.
6. Prefer boring, well-known libraries. If you replace a library named here, explain why in `docs/DECISIONS.md`.
7. Keep secrets out of git. Every setting comes from environment variables, documented in `.env.example`.
8. Write docstrings that explain *why*, not *what*. The team must be able to explain every module to judges.
9. When something is ambiguous, choose the simplest option that keeps the contract, write the choice in
   `docs/DECISIONS.md`, and mention it in your phase summary.

---

## 1. What the product does

A job seeker connects their GitHub account. SkillProof reads their **public** repositories, commits, file trees
and dependency manifests, and produces a **skill card**: proven skills with confidence labels, a **Signal Score
(0–100)** built from five explained sub-scores, the evidence (repos, commit counts, date ranges, tests, CI)
behind every skill, a check of the skills they *claim* on their CV, and "noise" flags (one-shot code dumps,
tutorial clones, unverified claims). An LLM writes a three-sentence summary of that evidence and never sets a
number.

**Recruiters** search job seekers by proven skill and score, view their cards, shortlist them against job
postings, and send them feedback. **Job seekers** receive every piece of feedback by **email and SMS**
(SMS through the **Thrivewave** API) and in an in-app inbox. An **admin** approves recruiters, manages users,
skills and content, and reads notification and audit logs.

---

## 2. Tech stack (use these)

| Concern | Choice |
| --- | --- |
| Language / framework | Python 3.12, Django 5.1, Django REST Framework 3.15 |
| Database | PostgreSQL 16 (via `psycopg[binary]` 3 and `dj-database-url`). No SQLite anywhere, including tests |
| Auth | `djangorestframework-simplejwt` (access + refresh, rotation, blacklist) |
| GitHub login | Custom OAuth 2.0 web flow for a single-page app (section 6.3), using `requests` |
| API docs | `drf-spectacular` + `drf-spectacular[sidecar]` (Swagger UI and ReDoc, served offline) |
| CORS | `django-cors-headers` |
| JSON casing | `djangorestframework-camel-case` (Python snake_case, JSON camelCase), with drf-spectacular camelize hook |
| Filtering | `django-filter` |
| Background jobs | Celery 5 + Redis (analyses and notifications). `CELERY_TASK_ALWAYS_EAGER=true` in local dev |
| Email | Django email framework; SMTP backend in production, console backend in dev; HTML + text templates |
| SMS | Thrivewave adapter (section 9) |
| Encryption of stored tokens | `cryptography` (Fernet), key from env |
| Phone numbers | `phonenumbers` (normalise to E.164, default region KE) |
| Rate limiting | DRF throttles (scoped) backed by Redis cache |
| Static files | WhiteNoise |
| Server | gunicorn |
| Logging | structured JSON logs (`python-json-logger`), request ID middleware |
| Error tracking (optional) | `sentry-sdk` if `SENTRY_DSN` is set |
| Tests | pytest, pytest-django, factory_boy, `responses` (mock HTTP), pytest-cov, freezegun |
| Lint / format | ruff (lint + format) |
| Containers | Dockerfile + docker-compose (postgres, redis, web, worker, beat, mailpit) |

---

## 3. Repository layout

Monorepo: the React (Next.js) frontend already lives in `frontend/`. Build everything below in `backend/`.

```
backend/
  manage.py
  pyproject.toml              # ruff + pytest config
  requirements/base.txt, dev.txt, prod.txt
  .env.example
  Dockerfile
  docker-compose.yml
  Makefile                    # make dev, make test, make lint, make schema, make seed
  config/
    settings/base.py, dev.py, test.py, prod.py
    urls.py, celery.py, wsgi.py, asgi.py
  apps/
    core/                     # base models (timestamps, UUID public ids), pagination, exceptions, health, audit
    accounts/                 # User, profiles, JWT, GitHub OAuth, email/phone verification, consent, privacy
    companies/                # Company, recruiter approval
    skills/                   # Skill catalogue + aliases (admin-managed)
    analysis/                 # GitHub fetch, scoring pipeline, analyses, skill cards
      services/               # github.py, skills.py, scores.py, flags.py, claims.py, summary.py, pipeline.py
    recruiting/               # job postings, candidate search, shortlists, feedback, match score
    notifications/            # in-app notifications, preferences, deliveries, email + Thrivewave SMS
      providers/              # email.py, thrivewave.py
      templates/notifications/ # email HTML + text, SMS text
    adminpanel/               # admin-only API: stats, approvals, user management, logs
  docs/
    ARCHITECTURE.md  DATABASE.md  API.md  AUTH.md  SCORING.md  NOTIFICATIONS.md
    FRONTEND_INTEGRATION.md  SECURITY_AND_PRIVACY.md  DEPLOYMENT.md  TESTING.md  DECISIONS.md
  tests/                      # mirrors apps/, plus fixtures/github/*.json
```

---

## 4. Roles and permissions

Three roles on one user model: `job_seeker`, `recruiter`, `admin`.

| Capability | Job seeker | Recruiter | Admin |
| --- | --- | --- | --- |
| Register with email + password | Yes | Yes (starts `pending`) | No (created with `createsuperuser` or by another admin) |
| Sign in with GitHub | Yes (creates or links account) | Yes (link only, for convenience) | Yes (link only) |
| Run an analysis | Own GitHub account only | No | Any GitHub login |
| View a skill card | Own; any public share link | Job seekers with `card_visible=true`; share links | All |
| Manage claimed skills | Own | — | All |
| Search candidates | — | Approved only | Yes |
| Job postings (create/edit/close) | — | Approved only, own company | All |
| Shortlist candidates | — | Approved only | Yes |
| Send feedback to a job seeker | — | Approved only | Yes |
| Receive feedback (in-app, email, SMS) | Yes | — | — |
| Notification preferences | Yes | Yes | Yes |
| Export own data / delete account | Yes | Yes | — |
| Approve or reject recruiters, suspend users | — | — | Yes |
| Manage skill catalogue and aliases | — | — | Yes |
| Read notification deliveries and audit log | Own notifications only | Own notifications only | All |

Implement as DRF permission classes in `apps/accounts/permissions.py`: `IsJobSeeker`, `IsApprovedRecruiter`,
`IsAdminRole`, `IsApprovedRecruiterOrAdmin`, `IsOwnerOrAdmin`, plus object-level checks. A recruiter whose
status is `pending` or `rejected` can sign in and see their status, but every recruiter-only endpoint answers
`403` with code `recruiter_not_approved`.

---

## 5. Database (PostgreSQL, normalised to 3NF)

Rules:

- Every table has `id` (BigAutoField, internal) and, where exposed in URLs, `public_id` (UUID, unique, indexed).
  APIs expose `public_id` or natural keys (GitHub login), never internal ids.
- `created_at` / `updated_at` on every table (abstract `TimeStampedModel` in `core`).
- Enumerations are `TextChoices` enforced by `CheckConstraint`.
- Add the unique constraints, foreign key `on_delete` rules and indexes listed below. Add a
  `CheckConstraint` for every numeric range (scores 0–20 and 0–100, evidence ≥ 0).
- No JSON blobs for data that is queried or filtered. JSONB is allowed only for raw provider responses,
  audit metadata and cached raw GitHub payloads.
- Write `docs/DATABASE.md` with a Mermaid ER diagram and one line per table explaining why it exists.

### 5.1 Accounts and organisations

| Table | Columns | Constraints and notes |
| --- | --- | --- |
| `accounts_user` | email, password, role, full_name, phone (E.164, nullable), email_verified_at, phone_verified_at, is_active, is_staff, is_superuser, last_login, date_joined | email unique (case-insensitive: store lowercase + `UniqueConstraint(Lower("email"))`); phone unique when not null; custom manager; `USERNAME_FIELD="email"`, no username |
| `accounts_jobseekerprofile` | user (1:1), headline, location, card_visible (default true), open_to_work (default true) | One per job seeker |
| `accounts_githubaccount` | user (1:1), github_id (unique), login (unique, lowercase), avatar_url, access_token_encrypted, token_scopes, connected_at, last_synced_at | Created by GitHub sign-in. Token encrypted with Fernet. A job seeker's analysed GitHub login comes from here, which proves ownership |
| `companies_company` | name (unique, case-insensitive), website, location, is_verified | Recruiters belong to one company |
| `companies_recruiterprofile` | user (1:1), company (FK), job_title, approval_status (`pending`/`approved`/`rejected`/`suspended`), reviewed_by (FK user, null), reviewed_at, review_note | Status changes are audited and notify the recruiter by email |
| `accounts_consentrecord` | user, consent_type (`terms`, `privacy`, `sms_feedback`, `email_feedback`), granted (bool), policy_version, ip_address, created_at | Append-only. Kenya Data Protection Act 2019: we must be able to show when consent was given or withdrawn |
| `accounts_verificationcode` | user, purpose (`verify_email`, `verify_phone`, `reset_password`), code_hash, expires_at, used_at, attempts | Store only a hash. 6-digit codes for phone (sent by SMS), signed tokens for email links. Max 5 attempts, 10-minute expiry |

### 5.2 Skills catalogue

| Table | Columns | Constraints and notes |
| --- | --- | --- |
| `skills_skill` | name (unique), slug (unique), category (`language`, `framework`, `practice`, `tool`) | Seeded by a data migration from the mapping table in section 8.2; admin can add more |
| `skills_skillalias` | skill (FK), alias (unique, lowercase) | "js" → JavaScript, "drf" → Django REST Framework, dependency names → skill |
| `skills_dependencymapping` | ecosystem (`npm`, `pypi`, `go`, `maven`), package_name, skill (FK) | unique (ecosystem, package_name). Lets admins extend detection without code changes |

### 5.3 Analyses and evidence

| Table | Columns | Constraints and notes |
| --- | --- | --- |
| `analysis_repository` | github_id (unique), owner_login, name, html_url, is_fork, default_branch, pushed_at | Shared across analyses |
| `analysis_analysis` | public_id, job_seeker (FK JobSeekerProfile, null for admin-run analyses), github_login, triggered_by (FK user), status (`queued`, `running`, `completed`, `failed`), error_code, signal_score (0–100, null until done), ai_summary, summary_source (`llm`, `template`), repos_analysed, commits_analysed, started_at, completed_at | index (github_login, -created_at); index (status) |
| `analysis_subscore` | analysis (FK), key (`consistency`, `iteration`, `quality`, `breadth`, `ownership`), value (0–20), reason | unique (analysis, key) |
| `analysis_analysisrepository` | analysis (FK), repository (FK), user_commits, total_commits, first_commit_at, last_commit_at, has_tests, has_ci, readme_length, sampled_additions, sampled_deletions | unique (analysis, repository). The evidence row the UI shows |
| `analysis_analysisskill` | analysis (FK), skill (FK), evidence (Decimal 5,2), label (`strong`, `moderate`, `emerging`) | unique (analysis, skill) |
| `analysis_skillevidence` | analysis_skill (FK), analysis_repository (FK) | unique pair. Through table: which repos prove which skill |
| `analysis_claimedskill` | job_seeker (FK), raw_text, skill (FK, null if no match), position | unique (job_seeker, Lower(raw_text)). What the user says on their CV, max 12 |
| `analysis_claimresult` | analysis (FK), claimed_skill (FK), status (`verified`, `partly`, `unverified`) | unique (analysis, claimed_skill) |
| `analysis_flag` | analysis (FK), type (`one_shot_dump`, `unexplained_bulk`, `tutorial_clone`, `unverified_claim`), analysis_repository (FK, null), claimed_skill (FK, null), reason | |
| `analysis_githubcache` | url (unique), etag, payload (JSONB), fetched_at | Conditional requests (`If-None-Match`) save rate limit; 24 h TTL |

### 5.4 Recruiting

| Table | Columns | Constraints and notes |
| --- | --- | --- |
| `recruiting_jobposting` | public_id, company (FK), created_by (FK recruiter user), title, description, location, employment_type (`full_time`, `part_time`, `contract`, `internship`), remote_policy (`onsite`, `hybrid`, `remote`), status (`draft`, `open`, `closed`), closes_at | |
| `recruiting_jobrequiredskill` | job_posting (FK), skill (FK), minimum_label (`emerging`/`moderate`/`strong`), weight (1–3) | unique (job_posting, skill) |
| `recruiting_shortlistentry` | recruiter (FK user), job_seeker (FK JobSeekerProfile), job_posting (FK, null), stage (`saved`, `contacted`, `interview`, `offer`, `rejected`), note | unique (recruiter, job_seeker, job_posting) |
| `recruiting_feedback` | public_id, recruiter (FK user), job_seeker (FK JobSeekerProfile), analysis (FK, null), job_posting (FK, null), status (`shortlisted`, `interview`, `not_a_fit`, `general`), message (max 1,000 chars), read_at | index (job_seeker, -created_at) |
| `recruiting_profileview` | recruiter (FK user), job_seeker (FK), viewed_at | Lets job seekers see "3 recruiters viewed your card this week" (counts only, no names unless the recruiter sent feedback) |

### 5.5 Notifications and audit

| Table | Columns | Constraints and notes |
| --- | --- | --- |
| `notifications_notification` | public_id, user (FK), kind (`analysis_completed`, `analysis_failed`, `recruiter_feedback`, `recruiter_approved`, `recruiter_rejected`, `shortlisted`, `profile_viewed_digest`), title, body, link_path, feedback (FK, null), analysis (FK, null), read_at | The in-app inbox |
| `notifications_preference` | user (FK), kind, channel (`in_app`, `email`, `sms`), enabled | unique (user, kind, channel). Defaults created on sign-up from consent choices |
| `notifications_delivery` | notification (FK), channel (`email`, `sms`), recipient, status (`queued`, `sent`, `delivered`, `failed`, `skipped`, `dry_run`), provider (`smtp`, `thrivewave`), provider_message_id, provider_response (JSONB), attempts, last_error, sent_at, delivered_at | index (status), index (provider_message_id) |
| `core_auditlog` | actor (FK user, null), action, target_type, target_id, metadata (JSONB), ip_address, user_agent | Append-only. Log: sign-in, failed sign-in, role/approval changes, feedback sent, analysis run, data export, account deletion, admin actions |

---

## 6. Authentication

### 6.1 JWT (simplejwt)

- Access token lifetime 15 minutes, refresh token 7 days, `ROTATE_REFRESH_TOKENS=True`,
  `BLACKLIST_AFTER_ROTATION=True`, `UPDATE_LAST_LOGIN=True`.
- Custom claims in the access token: `role`, `approvalStatus` (recruiters), `githubLogin` (if linked).
- Responses from sign-in, register and GitHub callback all return the same shape:
  `{ "access": "...", "refresh": "...", "user": <MeSerializer> }`.
- Logout blacklists the refresh token.
- The React frontend keeps the access token in memory and the refresh token in `localStorage` (hackathon
  trade-off; document the httpOnly-cookie alternative in `docs/AUTH.md` and implement it behind a setting
  `JWT_REFRESH_IN_COOKIE=false` if time allows).

### 6.2 Email + password

- Register: email, password (Django validators), role (`job_seeker` or `recruiter` only), fullName, phone
  (optional for recruiters, required for job seekers who opt into SMS), company name (recruiters; create or reuse
  the `Company`), consents (`terms` required; `emailFeedback`, `smsFeedback` optional).
- Send an email verification link on register. Unverified users can sign in, but job seekers cannot run an
  analysis and recruiters cannot be approved until the email is verified.
- Password reset by email link (signed token, 1 hour).
- Phone verification: `POST /auth/phone/send-code` sends a 6-digit code by SMS through Thrivewave;
  `POST /auth/phone/verify` checks it. SMS feedback is sent only to verified phones.

### 6.3 Sign in with GitHub (OAuth web flow for a single-page app)

1. `GET /api/v1/auth/github/authorize` → returns `{ "authorizeUrl": "...", "state": "..." }`. Build the URL
   for `https://github.com/login/oauth/authorize` with `client_id`, `redirect_uri` = `FRONTEND_URL/auth/github/callback`,
   `scope=read:user user:email`, and a `state` value that is signed (Django `signing.dumps`, 10-minute max age)
   and carries the intended role and an optional `link` flag.
2. The frontend redirects the browser to `authorizeUrl`. GitHub redirects back to the frontend callback page
   with `code` and `state`.
3. The frontend calls `POST /api/v1/auth/github/callback` with `{ code, state, role? }`. The backend verifies
   `state`, exchanges `code` at `https://github.com/login/oauth/access_token`, calls `GET /user` and
   `GET /user/emails`, then:
   - If a `GithubAccount` with that `github_id` exists → sign that user in.
   - Else if the request carries a valid JWT (linking from settings) → link GitHub to the current user.
   - Else if a user exists with the same **verified primary** GitHub email → link and sign in.
   - Else create a new user with the role from `state` (default `job_seeker`), mark email verified (GitHub
     verified it), and create the profile.
   - Store the GitHub access token encrypted; it raises the analysis rate limit from 60 to 5,000 requests/hour.
4. Return the JWT pair and user. Audit-log the sign-in.
5. `DELETE /api/v1/auth/github` unlinks (refused if the user has no password set, to avoid locking them out).

Document the GitHub OAuth app setup (callback URL for local and production) in `docs/AUTH.md`.

---

## 7. API contract (for the React frontend)

General rules:

- Base path `/api/v1/`. JSON in and out, camelCase keys.
- Pagination: `PageNumberPagination`, `?page=&pageSize=` (max 100). Shape
  `{ "count", "next", "previous", "results": [] }`.
- Errors: always `{ "code": "<machine_code>", "message": "<human sentence>", "fields": { "<field>": ["..."] } }`
  (`fields` only for validation errors). Implement a custom exception handler. Codes include:
  `validation_error`, `not_authenticated`, `token_invalid`, `permission_denied`, `recruiter_not_approved`,
  `email_not_verified`, `not_found`, `no_public_repos`, `github_not_linked`, `rate_limited`, `github_rate_limited`,
  `analysis_in_progress`, `server_error`.
- Every endpoint has `@extend_schema` with summary, description, request and response serializers, error
  responses, examples, and a tag (`Auth`, `Profile`, `Analyses`, `Skills`, `Candidates`, `Jobs`, `Shortlists`,
  `Feedback`, `Notifications`, `Admin`, `System`).

### 7.1 The skill card shape (must stay exactly compatible)

The frontend's `lib/types.ts` defines this. `GET /api/v1/cards/{githubLogin}` and a completed analysis return it:

```ts
interface Analysis {
  username: string;                 // GitHub login
  profile: { username: string; name: string | null; avatarUrl: string; verifiedOwner: boolean };
  signalScore: number;              // 0–100
  subScores: Record<"consistency"|"iteration"|"quality"|"breadth"|"ownership", { value: number; reason: string }>;
  skills: {
    name: string;
    category: "Language" | "Framework" | "Practice" | "Tool";
    label: "Strong" | "Moderate" | "Emerging" | "Unverified";
    evidence: number;
    repos: { name: string; url: string; commits: number; firstCommit: string; lastCommit: string; hasTests: boolean; hasCI: boolean }[];
  }[];
  claims: { skill: string; status: "Verified" | "Partly" | "Unverified" }[];
  flags: { type: "one_shot_dump"|"unexplained_bulk"|"tutorial_clone"|"unverified_claim"; repo?: string; reason: string }[];
  aiSummary: string;
  reposAnalysed: number;
  commitsAnalysed: number;
  analysedAt: string;               // ISO 8601
}
```

Note the display casing: category and label values are Title Case in the API even though the database stores
lowercase. `verifiedOwner` is true when the analysed login belongs to a linked `GithubAccount`. `hasCI` must keep
that exact casing; add a serializer field override so camel-casing doesn't produce `hasCi`.

### 7.2 Endpoints

| Method | Path | Who | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | Anyone | DB + Redis check, version, commit SHA |
| POST | `/auth/register` | Anyone | Email sign-up → tokens + user |
| POST | `/auth/login` | Anyone | Email + password → tokens + user (throttled 5/min per IP+email) |
| POST | `/auth/token/refresh` | Anyone with refresh token | New access (+ rotated refresh) |
| POST | `/auth/logout` | Signed in | Blacklist refresh token |
| GET | `/auth/github/authorize` | Anyone | Authorize URL + state |
| POST | `/auth/github/callback` | Anyone | Exchange code → tokens + user |
| DELETE | `/auth/github` | Signed in | Unlink GitHub |
| POST | `/auth/email/verify` | Anyone with link token | Verify email |
| POST | `/auth/email/resend` | Signed in | Resend verification |
| POST | `/auth/password/reset` | Anyone | Send reset email (always 204, no account enumeration) |
| POST | `/auth/password/reset/confirm` | Anyone with token | Set new password |
| POST | `/auth/password/change` | Signed in | Change password |
| POST | `/auth/phone/send-code` | Signed in | SMS a 6-digit code (throttled 3/hour) |
| POST | `/auth/phone/verify` | Signed in | Verify phone |
| GET, PATCH | `/me` | Signed in | Current user + role profile; update name, phone, headline, `cardVisible`, `openToWork` |
| GET, PUT | `/me/claimed-skills` | Job seeker | Read or replace claimed skills (max 12) |
| GET, PUT | `/me/notification-preferences` | Signed in | Matrix of kind × channel |
| GET | `/me/export` | Signed in | JSON export of all the user's data (DPA right of access) |
| DELETE | `/me` | Signed in | Delete account: anonymise feedback authored, delete personal data, revoke tokens; requires password or recent GitHub sign-in |
| GET | `/me/profile-views` | Job seeker | Count of recruiter views by week |
| POST | `/analyses` | Job seeker (own linked GitHub), admin (`githubLogin` in body) | Start an analysis → `202 { id, status }`. Reuse a completed analysis under 24 h old unless `force=true` or claimed skills changed (then `200` with the card). One running analysis per login (`409 analysis_in_progress`) |
| GET | `/analyses/{id}` | Owner, admin | Status (`queued`/`running`/`completed`/`failed`), progress step (1–4) and, when complete, the card |
| GET | `/analyses` | Job seeker (own), admin (all, filterable) | History with scores over time (iteration evidence) |
| GET | `/cards/{githubLogin}` | Anyone (public share link) | Latest completed card, or `404`. Records a `ProfileView` when the caller is a recruiter |
| GET | `/skills` | Anyone | Skill catalogue for autocomplete (`?search=`) |
| GET | `/candidates` | Approved recruiter, admin | Search job seekers with `cardVisible`: `?skills=react,django&minLabel=moderate&minScore=60&openToWork=true&search=&ordering=-signalScore&page=` |
| GET | `/candidates/{githubLogin}` | Approved recruiter, admin | Card + shortlist state + feedback this recruiter already sent |
| POST | `/candidates/{githubLogin}/feedback` | Approved recruiter, admin | `{ status, message, jobPostingId? }` → creates feedback, in-app notification, email + SMS |
| GET | `/feedback` | Job seeker (received), recruiter (sent) | Paginated, newest first |
| POST | `/feedback/{id}/read` | Job seeker | Mark read |
| GET, POST | `/jobs` | Approved recruiter (own company), admin; job seekers can list `open` jobs | Job postings with required skills |
| GET, PATCH, DELETE | `/jobs/{id}` | Owner recruiter, admin | |
| GET | `/jobs/{id}/matches` | Owner recruiter, admin | Ranked candidates with match score (section 8.7) |
| GET | `/jobs/{id}/match/me` | Job seeker | "How well do my proven skills match this job?" and which skills are missing |
| GET, POST | `/shortlists` | Approved recruiter | Saved candidates by stage |
| PATCH, DELETE | `/shortlists/{id}` | Owner recruiter | Move stage, edit note. Moving to `interview` can optionally send feedback |
| GET | `/notifications` | Signed in | In-app inbox, `?unread=true` |
| POST | `/notifications/{id}/read`, `/notifications/read-all` | Signed in | |
| POST | `/webhooks/thrivewave/delivery` | Thrivewave | Delivery reports; verified by shared secret header or HMAC (section 9) |
| GET | `/admin/stats` | Admin | Users by role, pending recruiters, analyses per day, average score, feedback sent, SMS/email delivery rates |
| GET | `/admin/recruiters?status=pending` | Admin | Approval queue |
| POST | `/admin/recruiters/{id}/approve`, `/reject` | Admin | With note; notifies by email (+ SMS if opted in) |
| GET, PATCH | `/admin/users`, `/admin/users/{id}` | Admin | Search, suspend/reactivate, change role |
| GET | `/admin/notification-deliveries` | Admin | Filter by status, channel, provider |
| POST | `/admin/notification-deliveries/{id}/retry` | Admin | Retry a failed delivery |
| GET | `/admin/audit-log` | Admin | Filter by actor, action, date |
| GET, POST, PATCH | `/admin/skills`, `/admin/dependency-mappings` | Admin | Manage detection without code changes |

Also register every model in the **Django admin** (`/django-admin/`) with list filters, search and read-only
audit fields, and an admin action to approve recruiters in bulk.

### 7.3 API documentation (drf-spectacular)

- `GET /api/v1/schema/` (OpenAPI 3 YAML/JSON), `GET /api/v1/docs/` (Swagger UI with JWT "Authorize" button),
  `GET /api/v1/redoc/`. Use the sidecar so docs work offline at a venue with poor Wi-Fi.
- `SPECTACULAR_SETTINGS`: title "SkillProof API", description from `docs/API.md` intro, version,
  `COMPONENT_SPLIT_REQUEST=True`, camelize postprocessing hook, enum name overrides so generated TypeScript enums
  have clean names, JWT security scheme.
- `make schema` writes `backend/openapi.yaml`, committed. CI fails if the committed schema is out of date.
- In `docs/FRONTEND_INTEGRATION.md`, show how the frontend generates types from it:
  `npx openapi-typescript ../backend/openapi.yaml -o lib/api-schema.ts`.

---

## 8. The analysis pipeline (implement exactly)

Runs as a Celery task `run_analysis(analysis_id)`. It updates `status` and a `progress_step` (1 reading repos,
2 reading commits, 3 finding skills, 4 scoring) so the frontend can show progress.

### 8.1 Step 1: collect evidence (`services/github.py`, the only module that calls GitHub)

Use the job seeker's own GitHub token when linked, else `GITHUB_TOKEN` from env. Send
`X-GitHub-Api-Version: 2022-11-28`. Use ETag caching (`analysis_githubcache`). Fetch up to **5 repos in
parallel** (ThreadPoolExecutor). Raise typed errors: `UserNotFound`, `NoPublicRepos`, `GitHubRateLimited`
(read `X-RateLimit-Remaining` / `Reset`).

For the 15 most recently pushed, **non-fork, non-empty** public repos owned by the user:

| Data | Endpoint |
| --- | --- |
| Repo list | `GET /users/{login}/repos?type=owner&sort=pushed&per_page=100` |
| Languages | `GET /repos/{owner}/{repo}/languages` |
| User's commits | `GET /repos/{owner}/{repo}/commits?author={login}&per_page=100` |
| All commits (count) | `GET /repos/{owner}/{repo}/commits?per_page=100` |
| Commit detail (sample of 20, deterministic seed = repo full name) | `GET /repos/{owner}/{repo}/commits/{sha}` → stats.additions / deletions |
| File tree | `GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1` |
| Manifests | `package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, `pom.xml` via contents API (base64) |
| README | `GET /repos/{owner}/{repo}/readme` (size) |

Convert everything into plain dataclasses (`Repo`, `Commit`) before passing to the next steps.

### 8.2 Step 2: detect skills (`services/skills.py`, pure)

- **Languages:** from language bytes; ignore a language under 5% of a repo.
- **Frameworks and tools:** from manifest dependencies, using `DependencyMapping` rows (load them once and
  pass them in as a dict so the function stays pure). Seed at least: react, next, vue, @angular/core, express,
  @nestjs/core, django, djangorestframework, flask, fastapi, pandas/numpy → "Data analysis",
  scikit-learn/torch/tensorflow → "Machine learning", pg/psycopg/psycopg2/prisma → PostgreSQL,
  mongoose/pymongo → MongoDB, tailwindcss, jest/vitest/pytest → Testing. Express or NestJS also implies Node.js.
- **Practices:** Testing (paths like `tests/`, `__tests__/`, `test_*.py`, `*_test.py`, `*.test.ts(x)`,
  `*.spec.ts`), CI/CD (`.github/workflows/`), Docker (`Dockerfile`, `docker-compose.yml`, `compose.yaml`).
- Forks never count.

### 8.3 Step 3: confidence per skill (pure)

```
span(repo)     = 1.0 if days between user's first and last commit ≥ 30; 0.6 if ≥ 7; else 0.3
evidence(repo) = min(1, user_commits / 20) × span(repo)
evidence(skill)= Σ evidence(repo) over repos showing that skill   (rounded to 2 dp)
label          = Strong ≥ 2.0 · Moderate ≥ 0.8 · Emerging > 0 · Unverified = 0
```

### 8.4 Step 4: Signal Score (pure, `services/scores.py`)

Five sub-scores, each an integer 0–20 with a plain-language reason; the Signal Score is their sum.

| Sub-score | Rule |
| --- | --- |
| Consistency | Distinct ISO weeks with user commits in the last 365 days: `20 × min(1, weeks / 26)`. Reason: "Active in N of the last 52 weeks" |
| Iteration | Median sampled commit size (additions + deletions): ≤ 200 → 8 pts, ≤ 500 → 5, else 2. Plus `12 × (repos with 10+ user commits / original repos)`. Minus `6 × (repos where one commit holds > 50% of sampled added lines / original repos)`. Clamp 0–20 |
| Quality practices | +8 if any repo has tests, +6 CI, +3 a README over 300 bytes, +3 a `Dockerfile` or `.env.example` |
| Breadth | 4 per Strong skill + 2 per Moderate, max 20 |
| Ownership | `20 × (original repos where the user wrote ≥ 70% of commits / original repos)` |

### 8.5 Step 5: flags (pure, `services/flags.py`)

- `one_shot_dump`: ≥ 200 sampled added lines and one commit holds > 80% of them.
- `unexplained_bulk`: a commit adding ≥ 2,000 lines with fewer than 3 commits after it.
- `tutorial_clone`: repo name matches common tutorial patterns (todo, calculator, weather, tic-tac-toe,
  hello-world, netflix/amazon clone…) **and** fewer than 5 user commits.
- `unverified_claim`: a claimed skill with no evidence.
- One flag per repo at most. Flags are worded as prompts to check, never accusations.

### 8.6 Claims (pure, `services/claims.py`)

Normalise claimed text through `SkillAlias`. `verified` = Strong or Moderate; `partly` = Emerging;
`unverified` = not detected.

### 8.7 Job match score (pure, `recruiting/services/match.py`) — new

For a job posting with required skills (each with `minimum_label` and `weight` 1–3):
`match = Σ weight × credit / Σ weight × 100`, where credit is 1.0 if the candidate's label meets the minimum,
0.5 if one level below, 0 otherwise. Return the score, the met skills and the missing skills. Used by
`/jobs/{id}/matches` and `/jobs/{id}/match/me`.

### 8.8 Step 6: AI summary (`services/summary.py`)

- Provider-agnostic interface `SummaryProvider.summarise(payload) -> str | None`; implement an Anthropic or
  OpenAI provider selected by `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL`. Timeout 15 s.
- Prompt: three sentences for a recruiter, using only the JSON (skills with labels and evidence, sub-scores,
  flags); strongest skills first; say plainly which are emerging; no numbers or skills that are not in the JSON.
- **Grounding check:** reject the summary if it names a known skill that was not detected. Fall back to a
  deterministic template summary. Store `summary_source`.
- Never let the summary step fail the analysis.

### 8.9 Improvement tips (pure) — new

`tips_for(analysis) -> list[str]` (max 3) derived from the lowest sub-scores and the flags, e.g.
"Add tests to shop-app", "Commit in smaller steps: 2 repos arrived mostly in one commit",
"Add a README to matatu-routes". Used in analysis feedback messages and shown on the card's owner view.

---

## 9. Notifications: email and Thrivewave SMS

### 9.1 Service

`notifications/services.py` exposes one entry point: `notify(user, kind, context, *, actor=None)`. It:

1. Creates the in-app `Notification`.
2. For `email` and `sms`, checks `NotificationPreference`, consent, and (for SMS) a verified phone; creates a
   `Delivery` row with status `queued` or `skipped` (and why).
3. Enqueues a Celery task per delivery, after the database transaction commits (`transaction.on_commit`).
4. Tasks retry with exponential backoff (max 3 attempts) on network errors and 5xx, not on 4xx.

Messages are Django templates in `templates/notifications/<kind>/{subject.txt, body.txt, body.html, sms.txt}`.
SMS bodies must fit **one GSM-7 part (160 characters)**: render, replace non-GSM characters (smart quotes, en
dashes), and truncate the message part (never the link or the opt-out text). Unit-test every SMS template's
maximum length with long names.

### 9.2 What triggers notifications

| Event | Recipient | In-app | Email | SMS |
| --- | --- | --- | --- | --- |
| Analysis completed | Job seeker | Yes | Score, top 3 skills, 3 tips, card link | "SkillProof: your Signal Score is 72. Top skill: TypeScript. Tip: add tests to shop-app. {link} Reply STOP to opt out" |
| Analysis failed | Job seeker | Yes | Reason + what to do | No |
| Recruiter feedback | Job seeker | Yes | Company, recruiter name, status, full message, link | "SkillProof: {Company} sent you feedback ({status}). Read it: {link}" |
| Shortlisted / interview stage | Job seeker | Yes | Yes | Yes |
| Recruiter approved / rejected | Recruiter | Yes | Yes | If opted in |
| Weekly profile-views digest (Celery beat, Monday 08:00 Africa/Nairobi) | Job seeker | Yes | Yes, if any views | No |
| Phone verification code | Any user | No | No | Yes (bypasses preferences, never logged in plain text) |

Links use `FRONTEND_URL` and a short path (`/u/{login}`, `/inbox`) to save SMS characters.

### 9.3 Email provider

Django `EmailMultiAlternatives` (text + HTML). Dev: Mailpit in docker-compose (SMTP on 1025, UI on 8025).
Production: any SMTP (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`,
`DEFAULT_FROM_EMAIL`). Thrivewave's public site lists SMS but not email; if the organisers supply a Thrivewave
email API, add a second provider class behind the same `EmailProvider` interface.

### 9.4 Thrivewave SMS adapter (`notifications/providers/thrivewave.py`)

Thrivewave Solutions (Kenya) offers bulk SMS through REST and SMPP APIs, but its API reference is **not**
published online. Build the adapter so only one function changes when we get the real docs:

```python
class ThrivewaveClient:
    def __init__(
        self,
        base_url,
        api_key,
        sender_id,
        *,
        username=None,
        sms_path="/sms/send",
        timeout=10,
        session=None,
    ): ...

    def build_payload(self, to_e164: str, message: str) -> tuple[dict, dict]:
        """Return (headers, json_body). THE ONLY PLACE THAT KNOWS THRIVEWAVE'S REQUEST FORMAT.
        Placeholder until the organisers' docs arrive: Bearer api_key header,
        body {"sender_id", "phone" (2547XXXXXXXX, no plus), "message"}."""

    def parse_response(self, status_code: int, body: dict | str) -> SmsResult:
        """SmsResult(ok, provider_message_id, raw). Treat 2xx as success unless the body says otherwise."""

    def send_sms(self, to_e164: str, message: str) -> SmsResult: ...
```

- Settings: `THRIVEWAVE_BASE_URL`, `THRIVEWAVE_API_KEY`, `THRIVEWAVE_USERNAME` (optional), `THRIVEWAVE_SENDER_ID`,
  `THRIVEWAVE_SMS_PATH`, `THRIVEWAVE_WEBHOOK_SECRET`, `SMS_DRY_RUN` (default **true**).
- **Dry run:** when true or when credentials are missing, do not call the network; store status `dry_run` and log
  the message. The demo must never break because of a missing key.
- Kenyan numbers: accept `07…`, `01…`, `+254…`, `254…`; store E.164; send in the format the payload needs.
- Delivery reports: `POST /api/v1/webhooks/thrivewave/delivery` updates `Delivery.status` to `delivered` or
  `failed` by `provider_message_id`. Verify `X-Thrivewave-Signature` (HMAC-SHA256 of the body with the secret) or
  a shared-secret header; make the check a function so it can be swapped. Return 200 quickly; idempotent.
- Opt-out: provide `POST /api/v1/webhooks/thrivewave/inbound` that turns "STOP" from a number into disabling SMS
  preferences for that user (only if Thrivewave supports inbound; otherwise document the manual path).
- Tests use `responses` to mock Thrivewave: success, 4xx (no retry), 5xx (retry), timeout, dry run, invalid
  phone, webhook signature valid/invalid, duplicate webhook.

---

## 10. Security, privacy and reliability

- CORS: `CORS_ALLOWED_ORIGINS` from env (default `http://localhost:3000`), `CORS_ALLOW_CREDENTIALS=True` only if
  cookie refresh is enabled, expose `Content-Disposition` for exports. Set `CSRF_TRUSTED_ORIGINS` to the same.
- Production settings: `SECURE_SSL_REDIRECT`, HSTS, secure cookies, `SECURE_PROXY_SSL_HEADER`,
  `X_FRAME_OPTIONS=DENY`, strict `ALLOWED_HOSTS`. `manage.py check --deploy` must pass.
- Throttles (Redis): anon 60/hour, user 600/hour, `login` 5/minute, `analysis` 10/hour per user,
  `feedback` 30/hour per recruiter, `phone_code` 3/hour, `password_reset` 5/hour.
- Feedback messages: strip HTML, max 1,000 chars, block links to non-https URLs, basic profanity/abuse check
  (word list) that holds the message for admin review instead of sending.
- Recruiters only see cards of job seekers with `card_visible=true` (share links stay public by the job seeker's
  choice). Recruiters never see phone numbers or emails through the API.
- Encrypt GitHub tokens at rest (Fernet, `FIELD_ENCRYPTION_KEY`). Never log tokens, codes or passwords.
- Data protection (Kenya DPA 2019): consent records, data export, account deletion, a retention job that deletes
  notification bodies older than 180 days and raw GitHub cache older than 7 days. Document in
  `docs/SECURITY_AND_PRIVACY.md`.
- Request ID middleware (`X-Request-ID`), JSON logs, Sentry if configured.
- Health endpoint used by Render/Railway health checks.

---

## 11. Additional features to include (beyond the original brief)

These make the product credible and the demo stronger. Build them in Phase 6 unless noted:

1. **Async analyses with progress** (Celery) so long GitHub fetches don't time out the request. (Phase 3)
2. **Analysis history** per job seeker: score over time, proof of iteration.
3. **Job postings + match score** for recruiters, and "how well do I match this job" for job seekers.
4. **Shortlists** with stages for recruiters.
5. **Profile-view counts** and a weekly digest for job seekers.
6. **Email and phone verification**, password reset.
7. **Data export and account deletion** (DPA rights).
8. **Admin dashboard API** with stats, approval queue, delivery logs and retry.
9. **Audit log** of sensitive actions.
10. **Skill catalogue and dependency mappings editable by admins.**
11. **Seed command** `python manage.py seed_demo` creating: 1 admin, 2 companies, 3 recruiters (1 pending),
    6 job seekers with realistic completed analyses built from saved fixtures, 2 job postings, feedback and
    notifications. Print the demo credentials. Must be idempotent.
12. **Warm-cache command** `python manage.py warm_demo --logins a,b,c` to pre-run demo analyses before judging.
13. **Health check** and version endpoint.
14. **OpenAPI-generated TypeScript types** for the frontend.

---

## 12. Testing requirements

- pytest + pytest-django against PostgreSQL (docker-compose or CI service container). factory_boy factories for
  every model.
- **Pure scoring code: ≥ 95% line coverage**, one test per rule and edge case (forks, empty repos, no commits,
  one-week repos, exactly-on-threshold values). Overall coverage ≥ 80%.
- Save real GitHub API JSON for 3 public accounts under `tests/fixtures/github/` (record once with a script
  `scripts/record_fixtures.py`, then mock with `responses`). Pipeline tests run on these fixtures.
- API tests for every endpoint: success, permission denied for each wrong role, validation errors, pagination,
  throttling (one representative test), and the exact skill card shape in section 7.1 (snapshot test).
- Auth tests: register, login, refresh rotation, blacklist on logout, GitHub callback (new user, existing
  github_id, link by verified email, link while signed in, bad state), recruiter approval gating.
- Notification tests: preferences respected, consent respected, SMS length ≤ 160, dry run, retries, webhooks.
- `TESTING.md` explains how to run tests and how to add a fixture. Keep `../TESTING_LOG.md` (repo root) updated
  with one line for every rule or threshold change you make and why.

CI (`.github/workflows/backend.yml`): Postgres + Redis services, install, `ruff check`, `ruff format --check`,
`python manage.py makemigrations --check --dry-run`, `python manage.py check --deploy` with prod settings and
dummy env, `pytest --cov`, and the schema-up-to-date check.

---

## 13. Documentation to write (`backend/docs/` + `backend/README.md`)

| File | Contents |
| --- | --- |
| `README.md` | What it is, quick start with Docker (`make dev`) and without, demo credentials from `seed_demo`, links to all docs |
| `ARCHITECTURE.md` | Mermaid diagram: React → DRF → Celery → GitHub / LLM / SMTP / Thrivewave → PostgreSQL / Redis. Request flow for an analysis and for feedback. Why each component exists |
| `DATABASE.md` | Mermaid ER diagram, every table with purpose, constraints, indexes; normalisation notes (why sub-scores, skills, evidence are rows, not JSON) |
| `API.md` | Conventions (versioning, casing, pagination, errors, auth header), endpoint index by role, links to `/api/v1/docs/` and `/api/v1/redoc/`, curl examples for the main flows |
| `AUTH.md` | JWT lifetimes and refresh flow (sequence diagram), GitHub OAuth setup and flow (sequence diagram), roles and permission matrix, recruiter approval |
| `SCORING.md` | Every rule from section 8 with the formula, threshold and a worked example; how to change a threshold safely |
| `NOTIFICATIONS.md` | Event → channel table, templates, SMS length rule, Thrivewave adapter and how to plug in the real API format, dry run, webhooks, retries, how to test with Mailpit |
| `FRONTEND_INTEGRATION.md` | Base URL and env vars, CORS, auth flow for React (store tokens, refresh on 401, GitHub callback page), polling an analysis, error codes → UI messages, generating TypeScript types, a typed `fetch` wrapper example |
| `SECURITY_AND_PRIVACY.md` | Threat notes, throttles, token encryption, DPA consent, export, deletion, retention |
| `DEPLOYMENT.md` | Render or Railway: web, worker and beat services, managed Postgres and Redis, env vars table, build and start commands, GitHub OAuth production callback, Vercel frontend env |
| `TESTING.md` | How to run, coverage targets, fixtures, what each test file covers |
| `DECISIONS.md` | Short ADR-style log of every significant choice and trade-off |

Also produce `.env.example` with every variable, grouped and commented:

```
# Django
DJANGO_SETTINGS_MODULE=config.settings.dev
DJANGO_SECRET_KEY=
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
FRONTEND_URL=http://localhost:3000
CORS_ALLOWED_ORIGINS=http://localhost:3000
# Database / cache / queue
DATABASE_URL=postgres://skillproof:skillproof@localhost:5432/skillproof
REDIS_URL=redis://localhost:6379/0
CELERY_TASK_ALWAYS_EAGER=true
# Auth
JWT_ACCESS_MINUTES=15
JWT_REFRESH_DAYS=7
GITHUB_OAUTH_CLIENT_ID=
GITHUB_OAUTH_CLIENT_SECRET=
FIELD_ENCRYPTION_KEY=
# Analysis
GITHUB_TOKEN=
ANALYSIS_CACHE_HOURS=24
ANALYSIS_MAX_REPOS=15
ANALYSIS_COMMIT_SAMPLE=20
LLM_PROVIDER=anthropic
LLM_API_KEY=
LLM_MODEL=
# Email
EMAIL_HOST=localhost
EMAIL_PORT=1025
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=false
DEFAULT_FROM_EMAIL=SkillProof <no-reply@skillproof.app>
# Thrivewave SMS
SMS_DRY_RUN=true
THRIVEWAVE_BASE_URL=
THRIVEWAVE_API_KEY=
THRIVEWAVE_USERNAME=
THRIVEWAVE_SENDER_ID=
THRIVEWAVE_SMS_PATH=/sms/send
THRIVEWAVE_WEBHOOK_SECRET=
# Observability
SENTRY_DSN=
```

---

## 14. Build phases (stop after each one)

| Phase | Deliverable | Done when |
| --- | --- | --- |
| 1. Foundation | Project skeleton, split settings, PostgreSQL + Redis via docker-compose, core app (timestamps, public ids, error handler, pagination, request ID, health), CORS, drf-spectacular docs live, ruff, pytest, CI | `/api/v1/health` and `/api/v1/docs/` work; CI green |
| 2. Accounts and auth | User model with roles, profiles, companies, recruiter approval, consents, JWT (register, login, refresh, logout), email verification, password reset, phone verification (SMS dry run), GitHub OAuth, permissions, `/me` | Auth tests pass; Swagger "Authorize" works with a JWT |
| 3. Analysis | Skills catalogue + seed migration, GitHub client with ETag cache, pure scoring modules, claims, flags, tips, summary with grounding check, Celery task with progress, analyses and cards endpoints, card serializer matching section 7.1 | Pipeline tests on recorded fixtures pass; a real login produces a card; coverage targets met for pure code |
| 4. Notifications | Notification models, preferences, templates, email provider, Thrivewave adapter (dry run), Celery delivery tasks with retries, webhooks, analysis-completed notifications | Notification tests pass; Mailpit shows emails; dry-run SMS logged |
| 5. Recruiting | Candidate search with filters, candidate detail, feedback (with notifications), profile views, shortlists, job postings, match score | Recruiter flow works end to end in Swagger |
| 6. Admin and extras | Admin API (stats, approvals, users, deliveries, retry, audit log, skills), Django admin polish, data export, account deletion, retention task, weekly digest, `seed_demo`, `warm_demo` | Seeded demo works; all docs written |
| 7. Hardening | `check --deploy` clean, throttles, security headers, Dockerfile for production, Render/Railway deploy notes, final schema export, README demo walkthrough | Fresh clone → `make dev` → `seed_demo` → frontend can sign in and see cards |

At the end, give me: a summary of every endpoint, the test and coverage report, the list of decisions in
`DECISIONS.md`, and anything you could not finish or verify (especially the real Thrivewave request format).

---

## 15. Acceptance checklist

- [ ] Three roles work with correct permissions; pending recruiters are blocked from recruiter endpoints
- [ ] JWT access/refresh with rotation and blacklist; GitHub sign-in creates or links accounts
- [ ] PostgreSQL schema normalised as in section 5, with constraints and indexes; ER diagram documented
- [ ] Analysis runs async with progress; card JSON matches section 7.1 exactly
- [ ] Every scoring rule implemented as specified, pure, and unit-tested; thresholds documented
- [ ] AI summary grounded, with template fallback; never sets numbers
- [ ] Job seekers receive analysis and recruiter feedback in-app, by email and by SMS (Thrivewave adapter, dry run
      by default), respecting consent and preferences; every delivery logged
- [ ] Recruiters can search, view, shortlist, post jobs, see match scores and send feedback
- [ ] Admin can approve recruiters, manage users and skills, read stats, deliveries and audit log
- [ ] Swagger UI and ReDoc complete with examples; `openapi.yaml` committed; TS types can be generated
- [ ] CORS configured for the React frontend; `docs/FRONTEND_INTEGRATION.md` explains the full auth flow
- [ ] CI green: lint, format, migrations check, deploy check, tests with coverage, schema check
- [ ] `seed_demo` and `warm_demo` ready for judging; README walkthrough works from a fresh clone
