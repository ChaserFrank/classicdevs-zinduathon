# SkillProof frontend

React + TypeScript single-page app for SkillProof, over the Django API in `../backend`.

> Status: **Phase 1 (foundation)**. See `docs/DESIGN.md` and `docs/DECISIONS.md`.

## Quick start

```bash
cd frontend
cp .env.example .env        # VITE_API_BASE_URL=http://localhost:8000/api/v1
npm ci
npm run dev                 # http://localhost:5173 (generates API types first)
```

The backend must allow this origin: in `backend/.env` set
`CORS_ALLOWED_ORIGINS=http://localhost:5173` and `FRONTEND_URL=http://localhost:5173`, then restart
it. Open **http://localhost:5173/dev/ui** (development builds only): the "Browser → API" panel
confirms the connection.

Everything in Docker, from the repository root: `docker compose up` (frontend on :5173, API on
:8000, Mailpit on :8025); add `--profile prod` for the nginx build on :8080.

## Scripts

| Script                                  | Does                                                                                   |
| --------------------------------------- | -------------------------------------------------------------------------------------- |
| `npm run dev`                           | Vite dev server (regenerates `src/lib/api/schema.d.ts` from `../backend/openapi.yaml`) |
| `npm run api:types` / `api:types:check` | Regenerate / verify generated API types                                                |
| `npm run typecheck`                     | TypeScript, strict                                                                     |
| `npm run lint`                          | ESLint (typescript, react-hooks, jsx-a11y) + Prettier check                            |
| `npm run test`                          | Vitest + Testing Library + MSW                                                         |
| `npm run screenshots`                   | Playwright: every route at 390 px and 1440 px into `e2e/__screenshots__/`              |
| `npm run build`                         | Production build into `dist/`                                                          |

Regenerate design assets: `python3 scripts/make-land-mask.py` (land mask from Natural Earth),
`node scripts/capture-static-planet.mjs && python3 scripts/to-webp.py` (static planet, dev server running).
