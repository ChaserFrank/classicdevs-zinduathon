# Claude Code prompt: SkillProof frontend (React + Vite + TypeScript)

> How to use:
> 1. Put this file in the repository root as `FRONTEND_PROMPT.md` (next to `BACKEND_PROMPT.md`).
> 2. Save the reference images into `frontend/design-reference/`: the dark glowing-planet hero as
>    `01-landing-reference.png`, plus any login and registration screenshots from the Behance project
>    (https://www.behance.net/gallery/222041051/Landing-Page-Login-Page-Design) as `02-login.png`, `03-register.png`.
> 3. Make sure the backend from `BACKEND_PROMPT.md` runs and `backend/openapi.yaml` exists.
> 4. Open Claude Code in the repository and say: **"Read FRONTEND_PROMPT.md and build the frontend it describes,
>    phase by phase. Stop at the end of each phase, show me screenshots and test results, and wait for me to say
>    continue."**

---

## 0. Your role and how to work

You are a senior frontend engineer and product designer building the React frontend for **SkillProof**, a
hackathon project for Zinduathon 3.0 (Zindua School, Nairobi), theme **"Noise vs Signal: proof of work, proof of
skill in the AI era."** Judges reward a working product they can see, technical choices the team can explain, and
evidence of testing and iteration. The UI must look exceptional: a **glassy, transparent, floating** interface over
a dark space scene with a glowing planet, and it must work end to end against the real Django backend.

Rules:

1. **Work in the phases in section 13, in order.** At the end of each phase run `npm run typecheck`,
   `npm run lint`, `npm run test`, and (from Phase 3) the Playwright smoke test against the running backend. Take
   screenshots of every new screen at 1440 px and 390 px wide (Playwright `page.screenshot`), look at them, fix what
   looks wrong, commit, summarise, and **stop**.
2. **The backend is the source of truth.** Generate types from `backend/openapi.yaml` and call only endpoints that
   exist in it. If a screen needs data the API does not provide, **stop and tell me** which endpoint or field is
   missing. Never mock around it in production code.
3. **Ask before guessing** about anything in section 15.
4. TypeScript `strict: true`. No `any` except at clearly commented boundaries.
5. Every screen has four states designed and built: loading (skeletons), empty (with a clear next action),
   error (says what happened and what to do), and success.
6. Accessibility is part of "done": keyboard navigation, visible focus, labelled controls, WCAG AA contrast **on
   glass** (test it), `prefers-reduced-motion` respected.
7. Keep components small and named for what users see. Write short comments explaining *why* where it is not obvious.
8. Record significant choices in `frontend/docs/DECISIONS.md`.

---

## 1. Design direction

### 1.1 The reference: what to adapt

The reference images in `frontend/design-reference/` define the look. The main one
(`01-landing-reference.png`) is a dark hero: a **near-black page**, a **floating pill-shaped navigation bar**
centred at the top, a **small pill badge** above a **centred, bold sans-serif headline** in white, a short muted
sub-line, and a **huge glowing orange planet rising from the bottom edge**: its surface is a **dotted world map**
(white dots on dark violet), the rim burns orange with a soft bloom, and faint stars sit in the black around it.

Adapt the *aesthetic and motion*, never the brand: no Gcore logo, name, wording or product names. Write
`frontend/docs/DESIGN.md` first, containing: what each reference image does (layout, proportions, type, colour
sampled as hex, glow treatment, nav, badge, buttons, form fields), what we take, what we change for SkillProof and
why. If there are login/registration references, the auth screens follow their layout closely. If there are none,
use the auth layout in 1.6 and tell me so in the phase summary.

### 1.2 Concept: the Signal Planet

The theme is noise becoming signal. The planet is our signal: a sphere of evidence dots. On the landing page,
**scattered noise particles drift in from the edges and lock onto the planet's surface as dots**: raw data
resolving into a clear picture. The planet faces **Africa with Kenya near the centre**; Nairobi has a small amber
pulse. This is the one memorable element of the product. Everything around it stays quiet and disciplined.

### 1.3 Tokens

| Token | Value | Use |
| --- | --- | --- |
| `void` | `#050507` | Page background (near-black, very slightly cool) |
| `void-2` | `#0B0B10` | Raised surfaces behind glass |
| `planet` | `#1A0F2E` → `#2A1745` | The planet's dark violet body |
| `flare` | `#FF7A1A` | Primary accent: rim glow, primary buttons, focus, active nav, scores |
| `flare-hot` | `#FFB15C` | Highlights, hover, the brightest part of the rim |
| `ember` | `#C2410C` | Deep glow edges, gradients toward black |
| `ink` | `#F5F5F7` | Primary text |
| `mist` | `#8E8E9A` | Secondary text |
| `line` | `rgba(255,255,255,0.10)` | Hairlines, glass borders |
| `ok` | `#4ADE80` | Success, delivered, approved |
| `warn` | `#FBBF24` | Pending, partly verified |
| `bad` | `#F87171` | Errors, unverified claims, flags |

Check the sampled hex values from the reference and adjust `flare`/`ember` to match it; record the final values in
`DESIGN.md` and `src/styles/tokens.css`. Skill tiers: Strong = solid `flare`, Moderate = `flare` outline,
Emerging = `mist` outline, Unverified = dashed `bad`.

**Typography:** a geometric grotesk in the spirit of the reference, such as **Plus Jakarta Sans** (700 for
headlines, 400/500 for UI), self-hosted with `@fontsource`. Headlines are large, tight (`letter-spacing: -0.02em`,
line-height 1.05) and centred in heroes, left-aligned inside the app. Numbers (scores) use tabular figures.
Sentence case everywhere; no all-caps labels.

### 1.4 Glass system

Glass here is **dark smoked glass**, not white frost: it lets the orange glow and the dots bleed through.

- **`GlassPanel`:** `background: rgba(18,18,24,0.55)`, `backdrop-filter: blur(24px) saturate(160%)`, a 1px
  `line` border, an inner top highlight `rgba(255,255,255,0.08)`, radius 24px, and a deep drop shadow so it floats.
- **`GlassCard`:** radius 16px, `rgba(255,255,255,0.04)` fill, lighter blur.
- **`GlassPill`:** the reference's nav and badge: fully rounded, `rgba(20,20,26,0.7)`, hairline border, 8px
  blur. Used for the nav bar, badges, chips, segmented controls and filters.
- **`glow` prop:** an orange bloom behind one element per screen (the login card, the score, the active filter
  panel): a blurred radial `flare` gradient at 25–35% opacity plus a 1px gradient edge from `flare-hot` to transparent.
- **Primary button:** the reference's "Sign up" pill is white on black; ours is **white pill with black text** for
  the main call to action on dark heroes, and **`flare` pill with black text** inside the app. Secondary: glass pill.
- **Readability guard:** test AA contrast of `ink` and `mist` over the worst case (the brightest rim colour behind
  glass) and add a darker scrim where it fails.
- **Fallback** where `backdrop-filter` is unsupported: solid `void-2` at 92% opacity.

### 1.5 Animation and motion

Build the background and motion in `src/components/space/`:

1. **`SignalPlanet` (landing hero, auth screens, error pages):** Three.js via `@react-three/fiber` + `drei`.
   - Sphere of about 12–18k points on a Fibonacci lattice; keep only points over land using an equirectangular
     land mask (generate a 360×180 PNG once from Natural Earth 1:110m land, public domain, into
     `public/textures/land-mask.png`; document the script in `scripts/`). Dots are white at 85% opacity with slight
     size variation; ocean is the dark violet body.
   - Rim glow: a fresnel shader on a slightly larger sphere, `ember` → `flare` → `flare-hot`, plus an
     additive-blended bloom (postprocessing `Bloom`, low intensity) so the planet "burns" at the edge like the reference.
   - Position: centred horizontally, only the top 35–45% of the sphere visible above the bottom of the viewport.
   - Rotation: very slow (one turn per ~4 minutes), with Kenya facing the viewer at load. A small amber pulse ring
     repeats at Nairobi every 4 s.
   - **Noise → signal moment (once, on first load):** ~1,500 particles start scattered across the screen in `mist`
     and drift in over 2.4 s with easing, landing as planet dots and turning white. Then the headline and sub-line
     fade up (word stagger 40 ms). That is the page's single orchestrated sequence.
   - Stars: 300–500 tiny points with slow twinkle, parallax with pointer movement (max 6 px).
   - **Scroll:** on the landing page the planet rises and scales slightly as the user scrolls the first 600 px,
     then fades behind content (Framer Motion `useScroll`).
   - **Performance:** lazy-load the 3D chunk; pause when the tab is hidden or the planet is off-screen; cap device
     pixel ratio at 1.75; target 60 fps on a mid-range laptop and keep the main thread free (measure and record in
     `DESIGN.md`). On low-power devices (`navigator.hardwareConcurrency <= 4` or no WebGL2), render a pre-rendered
     static planet image (`public/images/planet-static.webp`, created by the same scene) with a CSS glow.
   - **Reduced motion:** static planet image, no particle sequence, no twinkle.
2. **`SpaceBackdrop` (inside the app):** no 3D. A near-black field with a faint, very large orange glow arc low
   at the top-right corner (a planet just out of frame), subtle star dust (CSS or a tiny canvas), and an optional
   film grain at 4% opacity. The glow strength reacts to progress: it brightens as an analysis runs (steps 1–4) and
   settles when the card appears.
3. **Micro-interactions (answer user actions only):** nav pill items get a sliding highlight under the cursor; buttons
   get a soft inner glow on press; the score dial fills with an orange arc and the number counts up; panels open with a
   short scale-and-fade; toasts slide from the top centre as glass pills; tabs and segmented controls slide their
   indicator. No looping hover animations on cards.
4. Use Framer Motion for these moments, CSS transitions for the rest. All durations 150–400 ms except the hero
   sequence.

### 1.6 Layouts

- **Public pages:** the floating glass **pill nav** centred at the top (logo glyph in an orange rounded square,
  links with small chevrons for menus, a white "Get your skill card" pill on the right; collapses to a pill with a
  menu button under 768 px). Hero content centred: badge pill → headline → sub-line → two CTAs → planet below.
- **Auth screens:** the same black space with the planet glowing low behind the content. A centred `GlassPanel`
  with `glow` (max width 440 px) holding the form; the brand glyph and a one-line promise above it. Registration
  step 1 shows two large glass choice cards side by side ("I'm looking for work" / "I'm hiring"). If the reference
  shows a split layout for login, follow it: form panel on the left, planet and a short value statement on the right.
- **App shell (all three roles):** `SpaceBackdrop`; a floating glass **sidebar** (icons + labels, collapsible,
  bottom bar on mobile) and a floating glass **top bar** (page title, search for recruiters/admin, notification
  bell, user pill with avatar and role). Content is an asymmetric grid of floating panels with clear hierarchy, not a
  wall of identical cards.
- Responsive from 360 px; test at 360, 390, 768, 1024, 1440.

## 2. Tech stack (use these)

| Concern | Choice |
| --- | --- |
| Build | Vite 5, React 18, TypeScript 5 (strict) |
| Routing | React Router 6.x data router (`createBrowserRouter`, loaders for guards, lazy routes per section) |
| Server state | TanStack Query 5 (devtools in dev) |
| API client | `openapi-fetch` with types from `openapi-typescript` (generated from `backend/openapi.yaml`) |
| Forms | React Hook Form + Zod (`@hookform/resolvers`) |
| UI primitives | Radix UI (Dialog, DropdownMenu, Popover, Select, Tabs, Tooltip, Switch, Checkbox, Slider, Toast via `sonner`) wrapped in our glass components, shadcn/ui-style (copy-in components, not a theme) |
| Styling | Tailwind CSS 3 + CSS variables in `tokens.css`; `clsx` + `tailwind-merge` |
| Charts | Recharts (radar for sub-scores, line for score history, bars for admin stats) |
| Icons | lucide-react |
| Motion | Framer Motion (see 1.5) |
| 3D | `three`, `@react-three/fiber`, `@react-three/drei`, `@react-three/postprocessing` (lazy-loaded, landing/auth only) |
| Drag and drop | `@dnd-kit/core` for the shortlist board |
| Dates | date-fns (display in the user's local time; Africa/Nairobi in seed data) |
| Phone input | `libphonenumber-js` (default region KE) |
| Tests | Vitest + Testing Library + MSW (unit/component), Playwright (e2e and screenshots), axe-core checks |
| Lint/format | ESLint (typescript-eslint, react-hooks, jsx-a11y) + Prettier |
| Container | Multi-stage Docker: Node build → nginx serving static files with SPA fallback |

---

## 3. Repository and folder layout

The repository currently has `frontend/` (an old Next.js 14 template) and `backend/` (Django + DRF). First:

1. Rename the old folder to `frontend-legacy/` (keep it for reference; delete it in Phase 7 if I agree).
2. Create the new Vite app in `frontend/`.
3. Reuse the *logic* of `frontend-legacy/` components (`results/score-dial.tsx`, `results/sub-scores.tsx`,
   `results/skills.tsx`, `results/claims-and-flags.tsx`, the claimed-skills chip input in `analyze-form.tsx`) and
   restyle them with the new tokens in section 1. The old indigo/amber look and its `signal-field` background are
   replaced by the Signal Planet. Remove Next-specific code (`next/link`, `next/font`, `"use client"`).

```
frontend/
  design-reference/              # reference images (provided by me)
  public/
  src/
    main.tsx, App.tsx
    app/
      router.tsx                 # all routes, guards, lazy loading
      providers.tsx              # QueryClient, AuthProvider, ProgressGlowProvider, Toaster, Tooltip
      layouts/                   # PublicLayout, AuthLayout, AppShell (sidebar + topbar), AdminShell
    lib/
      api/
        schema.d.ts              # GENERATED — never edit
        client.ts                # openapi-fetch client + auth/refresh middleware
        errors.ts                # ApiError, error-code → UI copy
        query-keys.ts
      auth/                      # token store, AuthProvider, useAuth, guards
      utils.ts, format.ts, phone.ts
    features/
      auth/                      # login, register, github callback, verify email, reset password, phone verify
      landing/
      card/                      # public skill card + all card components
      analysis/                  # run analysis, progress, history
      seeker/                    # job seeker dashboard, inbox, jobs, settings
      recruiter/                 # dashboard, candidates, candidate detail, jobs, matches, shortlists
      notifications/             # bell, inbox, preferences matrix
      admin/                     # stats, approvals, users, analyses, skills, deliveries, audit log
      settings/                  # shared account settings
    components/
      glass/                     # GlassPanel, GlassCard, GlassChip, LitEdge
      ui/                        # Button, Input, Field, Select, Combobox, Dialog, Tabs, Badge, Skeleton, EmptyState, ErrorState, Pagination, DataTable, StatTile
      space/                     # SignalPlanet (3D), SpaceBackdrop, Stars, ProgressGlow provider
      brand/                     # Wordmark, Logo glyph
    styles/                      # tokens.css, globals.css, fonts.css
    test/                        # msw handlers, test utils
  e2e/                           # Playwright specs + screenshot spec
  docs/                          # see section 12
  Dockerfile, nginx.conf, .dockerignore
  .env.example
```

---

## 4. Connecting to the backend

### 4.1 Environment

```
# frontend/.env.example
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_URL=http://localhost:5173
VITE_DJANGO_ADMIN_URL=http://localhost:8000/django-admin/
VITE_API_DOCS_URL=http://localhost:8000/api/v1/docs/
```

The backend's `CORS_ALLOWED_ORIGINS` and `FRONTEND_URL` must include `http://localhost:5173` (dev) and the
production frontend origin. **Check this in Phase 1** by calling `/health` from the browser; if CORS fails, tell me
the exact backend setting to change.

### 4.2 Generated types

- `npm run api:types` → `openapi-typescript ../backend/openapi.yaml -o src/lib/api/schema.d.ts`.
- Run it in `predev` and `prebuild`; CI fails if the generated file differs from the committed one.
- Derive all domain types from the schema (`components["schemas"]["Analysis"]`), never hand-write duplicates.

### 4.3 The client (`src/lib/api/client.ts`)

- `openapi-fetch` client with `baseUrl = import.meta.env.VITE_API_BASE_URL`.
- Middleware:
  1. Adds `Authorization: Bearer <access>` when signed in, and an `X-Request-ID` (uuid) for tracing.
  2. On `401` with code `token_invalid` or `not_authenticated`: **single-flight refresh** (one refresh call shared
     by all concurrent requests) via `POST /auth/token/refresh`, store the rotated refresh token, retry the
     original request **once**. If refresh fails: clear tokens, keep the current path, redirect to
     `/login?next=<path>` with a toast "Your session ended. Sign in again."
  3. Normalises every error into `ApiError { status, code, message, fields? }` from the backend shape
     `{ code, message, fields }`.
- `errors.ts` maps codes to UI copy (plain, specific, no apologies), for example:

| Code | UI message |
| --- | --- |
| `validation_error` | Show `fields` under each input; summary "Check the highlighted fields." |
| `not_authenticated`, `token_invalid` | (handled by refresh) |
| `permission_denied` | "Your account can't do this." |
| `recruiter_not_approved` | Redirect to `/recruiter/pending` |
| `email_not_verified` | "Verify your email first." + Resend button |
| `not_found` | Context-specific empty state |
| `no_public_repos` | "This GitHub account has no public repositories yet. Push a project and analyse again." |
| `github_not_linked` | "Connect your GitHub account to run an analysis." + Connect button |
| `rate_limited`, `github_rate_limited` | "Too many requests. Try again in a minute." (show retry time if provided) |
| `analysis_in_progress` | Resume polling the running analysis |
| `server_error` / network | "Something went wrong on our side. Try again." + Retry |

### 4.4 Tokens and session

Follow `backend/docs/AUTH.md` exactly. Default (matching the backend prompt): **access token in memory**,
**refresh token in `localStorage`** (`skillproof.refresh`), wrapped in try/catch. On app start, if a refresh token
exists, refresh, then load `GET /me` before rendering protected routes (show the glass splash while loading). If the
backend enables `JWT_REFRESH_IN_COOKIE`, switch to `credentials: "include"` and drop localStorage. Note both in
`docs/API_INTEGRATION.md`.

### 4.5 Query conventions

- Keys in `query-keys.ts` (`["me"]`, `["analyses", id]`, `["candidates", filters]`, …).
- `staleTime` 30 s by default; `["me"]` 5 min; invalidate precisely after mutations.
- Optimistic updates for: mark notification/feedback read, shortlist stage moves, preference toggles.
- URL is the source of truth for filters, search, sort and page on list screens (`useSearchParams`), so links can
  be shared and the back button works.

### 4.6 Analysis polling

`POST /analyses` → `202 { id, status }` (or `200` with a fresh cached card). Then poll `GET /analyses/{id}` every
1.5 s with TanStack Query `refetchInterval` until `completed` or `failed`; stop when the tab is hidden and resume on
focus. Show progress steps 1–4 from `progressStep` and brighten the `SpaceBackdrop` glow per step. On `completed`, show the
card with the one orchestrated reveal (score dial fills, panels float in). On `failed`, show the error copy and Retry.

---

## 5. Authentication screens (follow the reference layout, or section 1.6)

| Route | Screen | Endpoints |
| --- | --- | --- |
| `/login` | Email + password, "Continue with GitHub", "Forgot password?", link to register. `next` param respected | `POST /auth/login`, `GET /auth/github/authorize` |
| `/register` | **Step 1:** choose role with two large glass choice cards: "I'm looking for work" (job seeker) and "I'm hiring" (recruiter). **Step 2:** the form. Job seeker: full name, email, password (strength meter), phone (Kenyan format, optional unless SMS is ticked), consents. Recruiter: full name, work email, password, phone, company (combobox: existing or new), job title. Consents: Terms + Privacy (required, links), "Send me feedback by email" (default on), "Send me feedback by SMS" (default off; shows the phone field as required and a note that standard SMS opt-out applies). "Continue with GitHub" also offered, carrying the chosen role | `POST /auth/register`, `GET /auth/github/authorize?role=` |
| `/auth/github/callback` | Reads `code` + `state`, calls the backend, stores tokens, redirects by role (or to `next`). Shows progress and a clear error if `state` is invalid or the user cancelled | `POST /auth/github/callback` |
| `/verify-email?token=` | Verifies, then routes to the dashboard | `POST /auth/email/verify` |
| `/forgot-password`, `/reset-password?token=` | Request and set new password; always says "If an account exists, we've sent a link" | `POST /auth/password/reset`, `/confirm` |
| Phone verify (dialog, from settings or after register when SMS is ticked) | 6 separate OTP inputs with paste support, resend timer (60 s), attempt errors | `POST /auth/phone/send-code`, `/verify` |
| `/recruiter/pending` | Status of approval (pending / rejected with note / suspended), what happens next, sign out | `GET /me` |

After sign-in redirect: job seeker → `/app`, recruiter → `/recruiter` (or `/recruiter/pending`), admin → `/admin`.
Show a dismissible glass banner app-wide while `emailVerifiedAt` is null, with Resend.

---

## 6. Public screens

| Route | Screen | Endpoints |
| --- | --- | --- |
| `/` | Landing. Hero (section 1.6): badge pill "Proof of skill for the AI era", headline "Your commits already tell the story.", sub-line "SkillProof reads your public GitHub work and shows recruiters the evidence behind every skill.", white pill CTA "Get your skill card" (→ register as job seeker), glass pill "I'm hiring" (→ register as recruiter), and the Signal Planet with the noise-to-signal sequence. Below the fold: a floating demo panel contrasting the CV claim "Expert in React" (struck through) with a SkillProof evidence card. Sections: how it works (connect GitHub → we read the evidence → share the card), the five scoring rules ("Rules set every score. AI only writes the summary."), for recruiters (search by proven skill, send feedback by email and SMS), privacy note (public repos only, you control visibility, Kenya DPA), footer with links to API docs. Follow the reference's landing structure: generous black space, centred type, the planet as the visual | `GET /health` (status dot in footer, dev only) |
| `/u/:login` | Public skill card (shareable): profile, score dial, sub-scores radar + reasons, AI summary (labelled as AI-written), proven skills with evidence panel, claims checked, flags ("worth a closer look"). Owner sees tips and a "Run again" button; recruiters see "Shortlist" and "Send feedback"; anonymous visitors see "Get your own card". Set `<title>` and meta description | `GET /cards/{login}` |
| `*` | 404 in the product voice with a way back | — |
| Error boundary | Route-level boundary with Retry and a request ID for support | — |

---

## 7. Job seeker screens (`/app`)

| Route | Screen | Endpoints |
| --- | --- | --- |
| `/app` | Dashboard: latest Signal Score (lit panel), change since last analysis, top skills, up to 3 improvement tips, recent feedback (unread first), profile views this week (small bar chart), "Run analysis" CTA. Empty state if no GitHub linked or no analysis yet | `GET /me`, `GET /analyses?page=1`, `GET /feedback?pageSize=3`, `GET /me/profile-views` |
| `/app/analyse` | Claimed skills editor (chip input with autocomplete from the skill catalogue, max 12), "Analyse my GitHub" button, progress view (section 4.6), then the result card. If GitHub isn't linked: a Connect GitHub panel | `GET/PUT /me/claimed-skills`, `GET /skills?search=`, `POST /analyses`, `GET /analyses/{id}` |
| `/app/card` | My card (same components as `/u/:login`) + share panel: copy link, card visibility toggle ("Recruiters can find my card"), "Open to work" toggle | `GET /cards/{login}`, `PATCH /me` |
| `/app/history` | Score over time (line chart) and a list of past analyses with sub-score deltas; click to view that card | `GET /analyses` |
| `/app/inbox` | Recruiter feedback: list (company, status chip, first line, time, unread dot) + detail pane; mark read on open; filter by status | `GET /feedback`, `POST /feedback/{id}/read` |
| `/app/jobs` | Open job postings with "How well do I match?" (match %, met skills, missing skills with suggestions) | `GET /jobs?status=open`, `GET /jobs/{id}/match/me` |
| `/app/notifications` | Full in-app notification list, mark all read | `GET /notifications`, `POST /notifications/read-all` |
| `/app/settings` | Tabs: Profile (name, headline, location), Contact (email status, phone + verify), GitHub (linked account with avatar, link/unlink), Notifications (matrix of kinds × channels: in-app, email, SMS; SMS disabled until phone verified), Privacy (card visibility, data export download as JSON, delete account with typed confirmation), Password | `GET/PATCH /me`, `GET/PUT /me/notification-preferences`, `DELETE /auth/github`, `GET /me/export`, `DELETE /me`, `POST /auth/password/change` |

---

## 8. Recruiter screens (`/recruiter`)

All routes except `/recruiter/pending` require `approvalStatus === "approved"`.

| Route | Screen | Endpoints |
| --- | --- | --- |
| `/recruiter` | Dashboard: open jobs with top match counts, shortlist by stage, feedback sent this week, recent candidates viewed | `GET /jobs`, `GET /shortlists`, `GET /feedback` |
| `/recruiter/candidates` | Search: glass filter panel (lit) with skill multi-select (catalogue autocomplete), minimum label (Emerging / Moderate / Strong), minimum score slider, open to work, free-text search, sort (score, recent). Results as floating candidate rows: avatar, name/login, score, top 3 skill badges, last analysed. URL-synced filters, pagination, empty state that suggests loosening filters | `GET /candidates`, `GET /skills` |
| `/recruiter/candidates/:login` | Candidate detail: the full card + side panel with shortlist control (stage select, optional job), **feedback composer** (status select: Shortlisted / Interview / Not a fit / General; message with 1,000-char counter; optional job; preview of what the job seeker receives by email and SMS; send confirmation toast "Feedback sent. They'll get it by email and SMS." — or the channels actually used), and the history of feedback you already sent | `GET /candidates/{login}`, `POST /candidates/{login}/feedback`, `POST/PATCH /shortlists` |
| `/recruiter/jobs` | Job postings list with status filter | `GET /jobs` |
| `/recruiter/jobs/new`, `/recruiter/jobs/:id/edit` | Form: title, description, location, employment type, remote policy, closes at, required skills (skill + minimum label + weight 1–3), save as draft or publish | `POST /jobs`, `PATCH /jobs/{id}` |
| `/recruiter/jobs/:id` | Job detail + ranked matches (match %, met/missing skill chips, open card, shortlist, send feedback) | `GET /jobs/{id}`, `GET /jobs/{id}/matches` |
| `/recruiter/shortlists` | Board with columns per stage (Saved, Contacted, Interview, Offer, Rejected), drag cards between columns (dnd-kit, keyboard accessible) with a "Move to" menu fallback; moving to Interview offers to send feedback | `GET /shortlists`, `PATCH /shortlists/{id}`, `DELETE /shortlists/{id}` |
| `/recruiter/feedback` | Feedback sent, with delivery status per channel if the API provides it | `GET /feedback` |
| `/recruiter/notifications`, `/recruiter/settings` | As for job seekers, without the job-seeker-only tabs; company shown read-only | shared |

---

## 9. Admin screens (`/admin`)

| Route | Screen | Endpoints |
| --- | --- | --- |
| `/admin` | Overview: stat tiles (users by role, pending recruiters, analyses today, average score, feedback sent, SMS and email delivery rates) + charts (analyses per day, deliveries by status). Links to Django admin and API docs | `GET /admin/stats` |
| `/admin/recruiters` | Approval queue (tabs: Pending, Approved, Rejected, Suspended): company, name, email verified, requested at; approve or reject with a note (dialog) | `GET /admin/recruiters`, `POST /admin/recruiters/{id}/approve`, `/reject` |
| `/admin/users` | Data table: search, filter by role/status, suspend/reactivate, change role (confirm dialog) | `GET /admin/users`, `PATCH /admin/users/{id}` |
| `/admin/analyses` | All analyses with status, score, login, duration; open card | `GET /analyses` (admin scope) |
| `/admin/skills` | Skill catalogue and dependency mappings CRUD (inline edit) | `/admin/skills`, `/admin/dependency-mappings` |
| `/admin/deliveries` | Notification deliveries: filter by channel, status (queued, sent, delivered, failed, skipped, dry run), provider; row detail shows recipient (masked), body, provider response JSON; Retry for failed | `GET /admin/notification-deliveries`, `POST …/{id}/retry` |
| `/admin/audit-log` | Filter by actor, action, date range; metadata JSON viewer | `GET /admin/audit-log` |

---

## 10. Shared app shell and components

- **Sidebar** (role-specific items, active state with a soft amber glow, collapsible), **top bar** (page title,
  global search for recruiters/admin, notification bell with unread count polled every 60 s and a popover list,
  user menu with role badge, settings, API docs link for admin, sign out).
- **Components:** `ScoreDial`, `SubScoreRadar`, `SubScoreList`, `SkillList` + `EvidencePanel`, `TierBadge`
  (Strong / Moderate / Emerging / Unverified, Verified / Partly), `ClaimsTable`, `FlagList`, `AiSummary`,
  `CandidateRow`, `MatchBar`, `StatTile`, `DataTable` (sortable, paginated, keyboard accessible), `EmptyState`,
  `ErrorState`, `Skeleton`, `ConfirmDialog`, `ChipInput`, `PhoneInput`, `OtpInput`, `PasswordStrength`,
  `CopyButton`, `StatusChip`, `Pagination`.
- **Copy:** plain, sentence case, active verbs. A button says exactly what happens ("Send feedback", "Approve
  recruiter"), and its toast uses the same verb ("Feedback sent", "Recruiter approved"). Errors never apologise.

---

## 11. Testing

- **Unit/component (Vitest + Testing Library + MSW):** the refresh middleware (single-flight, retry once, logout on
  failure), error mapping, route guards for each role and approval state, the registration form (role step, consent
  rules, phone required when SMS ticked, backend field errors shown on fields), the feedback composer (counter,
  validation, success), analysis polling (progress steps, completed, failed), the notification preference matrix,
  and the chip input. MSW handlers return payloads matching the generated schema types.
- **Accessibility:** axe checks on every page in Playwright; zero serious violations.
- **E2E (Playwright) against the real backend** started with docker-compose and `python manage.py seed_demo`:
  1. Job seeker: register → verify email (read the link from Mailpit's API) → link GitHub is skipped in e2e by using
     a seeded job seeker with a linked account → run analysis (backend in eager mode with fixtures) → see card →
     share link works logged out.
  2. Recruiter: sign in as the seeded approved recruiter → search by skill → open candidate → send feedback → job
     seeker sees it in the inbox; the admin deliveries page shows email + SMS (dry run) rows.
  3. Pending recruiter is blocked and sees the pending screen; admin approves; recruiter can now search.
  4. Session refresh: expire the access token and confirm the request is retried transparently.
- **Screenshots:** `e2e/screenshots.spec.ts` captures every route at 390 and 1440 px into `e2e/__screenshots__/`
  for review (not as failing snapshots).
- CI (`.github/workflows/frontend.yml`): install, api types check, typecheck, lint, unit tests, build; e2e job with
  backend + Postgres + Redis services on pushes to `main`.

---

## 12. Docker, deployment and documentation

**Docker:**

- `frontend/Dockerfile`: stage 1 `node:20-alpine` installs with `npm ci`, generates types, builds with
  `VITE_API_BASE_URL` as a build argument; stage 2 `nginx:alpine` serves `dist/` as a non-root user with
  `nginx.conf` (SPA fallback to `index.html`, long cache for hashed assets, no cache for `index.html`, gzip,
  security headers).
- `.dockerignore` (node_modules, dist, .env*, design-reference not needed in the image).
- Add a `frontend` service to the repository's root `docker-compose.yml`: dev profile runs `vite --host` with the
  source mounted on port 5173; prod profile runs the nginx image on 8080. `docker compose up` must start the whole
  system (frontend, backend, worker, Postgres, Redis, Mailpit).

**Documentation (`frontend/docs/` + `frontend/README.md`):**

| File | Contents |
| --- | --- |
| `README.md` | Quick start (with and without Docker), env vars, demo accounts from `seed_demo`, scripts |
| `DESIGN.md` | Reference analysis, final tokens, glass tiers, Signal Planet spec and fallbacks, motion rules, performance measurement, screenshots of key screens |
| `ARCHITECTURE.md` | Folder structure, providers, routing and guards, data flow diagram (Mermaid) |
| `API_INTEGRATION.md` | Base URL, CORS, generated types, client middleware, token storage and refresh (sequence diagram), GitHub OAuth flow (sequence diagram), polling, error codes → UI copy, how to add a new endpoint |
| `ROUTES.md` | Every route → role → screen → endpoints (the tables in sections 5–9, kept up to date) |
| `TESTING.md` | How to run each test type, MSW, e2e prerequisites, screenshot review |
| `DEPLOYMENT.md` | Docker image; or Vercel/Netlify static hosting with SPA rewrite; production env vars; backend CORS and GitHub OAuth callback URL (`<frontend>/auth/github/callback`) |
| `DECISIONS.md` | Short log of choices and trade-offs |

---

## 13. Build phases (stop after each one)

| Phase | Deliverable | Done when |
| --- | --- | --- |
| 1. Foundation | Rename legacy folder, Vite + TS + Tailwind + tokens + fonts, glass components, space backdrop, `/dev/ui` page, router skeleton with layouts, API types generation, client with middleware, CORS check against `/health`, ESLint/Prettier/Vitest, Dockerfile + compose service, `DESIGN.md` from the reference images, `SignalPlanet` with fallbacks | `/dev/ui` shows every glass component; `/health` call succeeds from the browser; screenshots reviewed |
| 2. Auth | Landing page, login, register (two steps), GitHub OAuth callback, verify email, password reset, phone verify dialog, session bootstrap and refresh, guards by role, pending recruiter screen, email-unverified banner | Sign in/out/refresh works against the real backend for all three seeded roles; tests pass |
| 3. Skill card and analysis | Public card `/u/:login`, card components, job seeker dashboard, analyse flow with polling, my card + share/visibility, history | A seeded job seeker runs an analysis and sees the card; e2e flow 1 passes |
| 4. Notifications and inbox | Bell + popover, notifications page, feedback inbox, preferences matrix, settings tabs, data export, delete account | Preferences and inbox work against the API; tests pass |
| 5. Recruiter | Dashboard, candidate search, candidate detail with shortlist + feedback composer, jobs CRUD, matches, shortlist board, feedback sent | e2e flow 2 passes |
| 6. Admin | Overview stats, recruiter approvals, users, analyses, skills + mappings, deliveries with retry, audit log | e2e flow 3 passes |
| 7. Polish | Accessibility pass (axe clean), responsive pass at all widths, performance (Lighthouse ≥ 90 on landing and card), reduced motion, empty/error states audit, all docs, screenshot set, remove legacy folder if approved | Acceptance checklist complete |

---

## 14. Acceptance checklist

- [ ] Login and registration follow the reference layout (or 1.6 if none), styled with the glass system
- [ ] The landing hero matches the reference's look: pill nav, badge, centred headline, glowing dotted planet with the noise-to-signal sequence
- [ ] Dark glass panels float over the space backdrop; text meets AA contrast on every surface
- [ ] 3D runs at ~60 fps on a mid-range laptop, falls back to a static planet on low-power devices and for reduced motion
- [ ] All three roles have complete, guarded areas; pending/rejected recruiters see their status screen
- [ ] JWT refresh is transparent; GitHub sign-in works for new and existing users; email/phone verification work
- [ ] Every API call is typed from `openapi.yaml`; no hand-written duplicate types; no endpoints invented
- [ ] Analysis runs with live progress and the background resolves as it runs
- [ ] Recruiter feedback reaches the job seeker inbox, and email + SMS deliveries appear in the admin log
- [ ] Every screen has loading, empty, error and success states
- [ ] Responsive from 360 px to 1440 px; keyboard accessible; reduced motion respected
- [ ] Unit, component and e2e tests pass in CI; screenshots of every route reviewed
- [ ] `docker compose up` runs the full system; docs complete

---

## 15. Ask me before you build these (do not guess)

1. **Design screenshots** if `frontend/design-reference/` is empty, or if a screenshot is too small to read.
2. Login/registration reference screenshots, if none are in `design-reference/` (otherwise use section 1.6).
3. The **production backend URL** and the production frontend domain.
4. Whether the **GitHub OAuth app** callback URL is registered for `http://localhost:5173/auth/github/callback`
   and production.
5. **Terms and Privacy text** (or permission to write placeholder pages clearly marked as drafts).
6. The **SMS sender name** to show in the SMS consent text (from the Thrivewave account).
7. Any endpoint or field that a screen in sections 5–9 needs but `openapi.yaml` does not have.
