# Frontend integration

For whoever builds the SkillProof web app. The skill card shape matches the earlier prototype's
`lib/types.ts`.

## Environment

| Frontend env var | Value |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` locally; the deployed API URL in production |

Backend side: put the frontend origin in `CORS_ALLOWED_ORIGINS` and `FRONTEND_URL` (email/SMS links
and the GitHub OAuth redirect use it). `Content-Disposition` and `X-Request-ID` are exposed to
browsers.

## Types from the schema

```bash
npx openapi-typescript ../backend/openapi.yaml -o lib/api-schema.ts
```

```ts
import type { components } from "./api-schema";
type Card = components["schemas"]["Card"];
type Candidate = components["schemas"]["Candidate"];
```

## A typed fetch wrapper with refresh-on-401

```ts
let accessToken: string | null = null; // memory only
const REFRESH_KEY = "sp_refresh";      // localStorage (see AUTH.md for the cookie alternative)

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string,
              public fields?: Record<string, string[]>) { super(message); }
}

export function setTokens(t: { access: string; refresh: string }) {
  accessToken = t.access;
  localStorage.setItem(REFRESH_KEY, t.refresh);
}

async function refresh(): Promise<boolean> {
  const token = localStorage.getItem(REFRESH_KEY);
  if (!token) return false;
  const res = await fetch(`${BASE}/auth/token/refresh`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: token }),
  });
  if (!res.ok) { localStorage.removeItem(REFRESH_KEY); return false; }
  setTokens(await res.json()); // rotation: always store the new refresh token
  return true;
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json",
               ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
               ...init.headers },
  });
  if (res.status === 401 && retry && (await refresh())) return api<T>(path, init, false);
  if (res.status === 204) return undefined as T;
  const body = await res.json();
  if (!res.ok) throw new ApiError(res.status, body.code, body.message, body.fields);
  return body as T;
}
```

Call `refresh()` once on app load to restore a session from the stored refresh token.

## Sign-in flows

- **Email:** `POST /auth/register` or `/auth/login` → `{access, refresh, user}` → `setTokens`.
- **GitHub:** `GET /auth/github/authorize?acceptTerms=true` → store `state` in `sessionStorage`
  → `window.location = authorizeUrl`. On `/auth/github/callback` (frontend page): check `state`
  matches, then `POST /auth/github/callback {code, state}` (with the Bearer header when linking
  from settings) → `{access, refresh, user, created}`.
- **Email verification / password reset links** land on `/verify-email?token=` and
  `/reset-password?token=`; post the token to the matching endpoint.

Route on `user.role` and, for recruiters, `user.recruiterProfile.approvalStatus` (pending
recruiters see a "waiting for approval" page).

## Running an analysis

```ts
const start = await api<{ id: string; status: string; card?: Card }>("/analyses", { method: "POST", body: "{}" });
if (start.card) return start.card; // a result under 24 h old was reused (HTTP 200)
let a;
do {
  await new Promise(r => setTimeout(r, 2500));
  a = await api<AnalysisDetail>(`/analyses/${start.id}`);
  setProgress(a.progressStep);     // 1 reading repos · 2 commits · 3 skills · 4 scoring
} while (a.status === "queued" || a.status === "running");
if (a.status === "failed") showError(a.errorCode, a.errorMessage);
```

## Error codes → UI

| Code | Show |
| --- | --- |
| `validation_error` | `fields` next to inputs (keys are camelCase, nested as `consents.terms`) |
| `not_authenticated`, `token_invalid` | Try refresh; if it fails, go to sign-in |
| `recruiter_not_approved` | "Your account is waiting for approval" |
| `email_not_verified` | "Check your inbox" + resend button |
| `github_not_linked` | "Connect GitHub" button (authorize with `link=true`) |
| `analysis_in_progress` | Resume polling the running analysis |
| `no_public_repos` | "We need at least one public, non-fork repo with code" |
| `github_rate_limited` | "GitHub is busy, try again in an hour" |
| `rate_limited` | `message` already says when to retry |
| `server_error` | Generic error + the `X-Request-ID` for support |
