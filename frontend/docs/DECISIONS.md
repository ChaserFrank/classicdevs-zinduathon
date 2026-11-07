# Decisions (frontend)

## F-001 New app beside, not on top of, the teammate's prototype (Phase 1)

`frontend/myskill` (a React 19 JSX prototype) moved to `frontend-legacy/myskill` unchanged, as the
guidelines direct; the new TypeScript app lives at `frontend/`. Nothing was deleted.

## F-002 Stack versions follow the guidelines (Phase 1)

Vite 5, React 18, React Router 6 (data router, v7 future flags on), TanStack Query 5, Tailwind 3,
React Three Fiber 8 / drei 9 (the React 18 line). Pinned in `package-lock.json`.

## F-003 Generated types treat defaults as optional (Phase 1)

`openapi-typescript --default-non-nullable false`: otherwise request fields with a server default
(e.g. `consents.emailFeedback`) become required in TypeScript although the API doesn't need them.

## F-004 Paths keep the `/api/v1` prefix (Phase 1)

The OpenAPI paths include `/api/v1`, so the client's base URL is the API origin and calls read
`api.GET("/api/v1/me")`, which matches the backend docs and Swagger exactly.

## F-005 Static planet derived from the real scene (Phase 1)

The fallback image is a capture of the actual 3D scene, converted to transparent WebP by mapping
brightness to alpha (post-processing renders to an opaque buffer, so a direct transparent capture
isn't possible).

## F-006 Scrim glass for surfaces over the planet (Phase 1)

Default glass over the brightest rim fails AA for secondary text (2.4:1). Surfaces that can sit
over the rim use `GlassPanel scrim` (84% dark), tested in `src/lib/contrast.test.ts`.

## F-007 Backend fixes found by the frontend (Phase 1)

- `/health` didn't send CORS headers: the health middleware answered before `CorsMiddleware`.
  Moved after it (still before the Host check); regression test added.
- Backend tests read the developer's `backend/.env` for `FRONTEND_URL`/`CORS_ALLOWED_ORIGINS`;
  the test settings now pin them.
- Backend defaults now allow the Vite origin `http://localhost:5173`.
