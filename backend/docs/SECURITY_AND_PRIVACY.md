# Security and privacy

## Threats and controls

| Threat | Control |
| --- | --- |
| Password guessing | 5 attempts/min per IP+email; Django password validators; failed sign-ins audited |
| Stolen refresh token | 7-day lifetime, rotation with blacklist (each token works once), blacklisted on logout, password change/reset, suspension, deletion |
| Stolen access token | 15-minute lifetime; suspended users are refused on every request |
| Account pre-registration (squatting an email) | GitHub sign-in with the same verified email removes the squatter's password (D-016) |
| OAuth CSRF / replay | Signed `state` with 10-minute expiry; SPA compares it with sessionStorage; code exchanged server-side |
| Leaked database | GitHub tokens Fernet-encrypted (`FIELD_ENCRYPTION_KEY`); SMS codes stored as HMAC; passwords hashed |
| Enumeration | Password reset always 204; public ids are UUIDs; other users' analyses and notifications answer 404 |
| Recruiter abuse | Admin approval before any recruiter access; recruiters never see email/phone; feedback HTML stripped, https-only links, abusive messages held for review; 30 feedback/hour |
| Webhook spoofing | HMAC-SHA256 signature or shared secret; refused when no secret is configured |
| Injection in logs | Request ids accepted only from a safe character set; tokens, codes, passwords, SMS text never logged; phone numbers masked |
| Clickjacking, downgrade | `X-Frame-Options: DENY`, HSTS (1 year, preload), secure cookies, SSL redirect (`check --deploy` in CI) |
| Prompt injection via repo content | The LLM never sees repo text, only our computed JSON; its output is grounding-checked and never sets a number |
| Runaway costs / abuse | Analyses 10/hour per user, one active per login, GitHub ETag cache |

## Kenya Data Protection Act 2019

| Obligation | How SkillProof meets it |
| --- | --- |
| Lawful basis, consent | Terms + privacy consent required at sign-up; email and SMS feedback consents are separate opt-ins; append-only `ConsentRecord` with policy version, time and IP; changing notification preferences records consent changes; SMS "STOP" withdraws consent |
| Purpose limitation, minimisation | Only public GitHub data is read; no repo contents are stored except manifests' dependency names (derived) and evidence statistics |
| Right of access | `GET /me/export` returns everything as JSON (audited) |
| Right to erasure | `DELETE /me` (password or recent GitHub sign-in): deletes the user, profiles, analyses, consents, notifications; signs out everywhere; feedback a recruiter sent stays with its recipient, anonymised |
| Retention | Daily job: notification bodies and rendered messages older than 180 days are blanked; raw GitHub responses older than 7 days are deleted |
| Accountability | Audit log of sign-ins, failures, approvals, feedback, analyses, exports, deletions and admin actions; append-only, readable by admins (`/admin/audit-log`) |
| Transparency | Every number on a card has a written rule (`SCORING.md`) and a plain-language reason; job seekers see recruiter view counts |
| Third-party processors | GitHub (public data), Anthropic (computed skill summary only, no personal contact data), SMTP provider, Thrivewave (phone number + message) |
