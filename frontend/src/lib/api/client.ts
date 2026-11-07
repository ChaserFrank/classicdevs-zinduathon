/**
 * The typed API client. Types come from backend/openapi.yaml (src/lib/api/schema.d.ts).
 *
 * Middleware:
 *  1. Authorization: Bearer <access> and X-Request-ID on every request.
 *  2. On 401 (token_invalid / not_authenticated) with a refresh token: ONE shared refresh call
 *     for all concurrent requests, then each original request is retried once. If the refresh
 *     fails, tokens are cleared and sessionEvents.ended() fires.
 */
import createClient, { type Middleware } from "openapi-fetch";

import { sessionEvents, tokens, type TokenPair } from "@/lib/auth/tokens";
import { env } from "@/lib/env";

import { toApiError } from "./errors";
import type { paths } from "./schema";

export const API_BASE_URL: string = env.apiBaseUrl;
// Paths in the schema include the /api/v1 prefix, so the client's base is the origin.
const ORIGIN = API_BASE_URL.replace(/\/api\/v1$/, "");

const NO_REFRESH = ["/auth/login", "/auth/register", "/auth/token/refresh", "/auth/github/callback"];
const pending = new Map<string, Request>(); // request id → untouched clone, for one retry

let refreshing: Promise<boolean> | null = null;

/** Exchange the refresh token. Single-flight: concurrent callers share one network call. */
export function refreshSession(fetchImpl: typeof fetch = fetch): Promise<boolean> {
  const refresh = tokens.refresh();
  if (!refresh) return Promise.resolve(false);
  refreshing ??= (async () => {
    try {
      const response = await fetchImpl(`${API_BASE_URL}/auth/token/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });
      if (!response.ok) return false;
      tokens.set((await response.json()) as TokenPair);
      return true;
    } catch {
      return false;
    } finally {
      queueMicrotask(() => {
        refreshing = null;
      });
    }
  })();
  return refreshing;
}

function newRequestId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID().replace(/-/g, "")
    : Math.random().toString(16).slice(2).padEnd(16, "0");
}

export function authMiddleware(fetchImpl: typeof fetch = fetch): Middleware {
  return {
    onRequest({ request }) {
      const id = newRequestId();
      request.headers.set("X-Request-ID", id);
      const access = tokens.access();
      if (access) request.headers.set("Authorization", `Bearer ${access}`);
      pending.set(id, request.clone());
      return request;
    },
    async onResponse({ request, response }) {
      const id = request.headers.get("X-Request-ID") ?? "";
      const original = pending.get(id);
      pending.delete(id);
      if (response.status !== 401 || !original) return response;
      const path = new URL(request.url).pathname.replace(/^\/api\/v1/, "");
      if (NO_REFRESH.some((p) => path.startsWith(p)) || !tokens.refresh()) return response;

      const body = (await response
        .clone()
        .json()
        .catch(() => ({}))) as { code?: string };
      if (body.code !== "token_invalid" && body.code !== "not_authenticated") return response;

      if (!(await refreshSession(fetchImpl))) {
        tokens.clear();
        sessionEvents.ended();
        return response;
      }
      const retry = new Request(original, { headers: new Headers(original.headers) });
      retry.headers.set("Authorization", `Bearer ${tokens.access()}`);
      return fetchImpl(retry); // retried once: a second 401 is returned as-is
    },
  };
}

export function makeClient(fetchImpl: typeof fetch = (...args) => fetch(...args)) {
  const client = createClient<paths>({ baseUrl: ORIGIN, fetch: fetchImpl });
  client.use(authMiddleware(fetchImpl));
  return client;
}

export const api = makeClient();

/**
 * Await an openapi-fetch call and return its data, or throw an ApiError (also for network
 * failures). Keeps every caller's error handling the same.
 */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result;
  try {
    result = await call;
  } catch {
    throw toApiError(0, null);
  }
  const { data, error, response } = result;
  if (!response.ok || error !== undefined) {
    throw toApiError(response.status, error, response.headers.get("X-Request-ID") ?? undefined);
  }
  return data as T;
}
