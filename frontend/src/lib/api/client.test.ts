import { http, HttpResponse } from "msw";

import { sessionEvents, tokens } from "@/lib/auth/tokens";
import { API, server } from "@/test/server";

import { api, unwrap } from "./client";
import { ApiError } from "./errors";

const ME = { id: "u1", email: "amina@jobseeker.demo", role: "job_seeker" };
const expired = () => HttpResponse.json({ code: "token_invalid", message: "Token expired" }, { status: 401 });

beforeEach(() => tokens.clear());

describe("api client middleware", () => {
  it("sends the bearer token and a request id", async () => {
    tokens.set({ access: "A1", refresh: "R1" });
    let seen: Headers | undefined;
    server.use(
      http.get(`${API}/me`, ({ request }) => {
        seen = request.headers;
        return HttpResponse.json(ME);
      }),
    );
    await unwrap(api.GET("/api/v1/me"));
    expect(seen?.get("Authorization")).toBe("Bearer A1");
    expect(seen?.get("X-Request-ID")).toMatch(/^[0-9a-f]{16,}$/);
  });

  it("refreshes once for concurrent 401s, stores the rotated token and retries each request once", async () => {
    tokens.set({ access: "OLD", refresh: "R1" });
    let refreshCalls = 0;
    server.use(
      http.get(`${API}/me`, ({ request }) =>
        request.headers.get("Authorization") === "Bearer NEW" ? HttpResponse.json(ME) : expired(),
      ),
      http.post(`${API}/auth/token/refresh`, async ({ request }) => {
        refreshCalls += 1;
        expect(await request.json()).toEqual({ refresh: "R1" });
        return HttpResponse.json({ access: "NEW", refresh: "R2" });
      }),
    );
    const results = await Promise.all([
      unwrap(api.GET("/api/v1/me")),
      unwrap(api.GET("/api/v1/me")),
      unwrap(api.GET("/api/v1/me")),
    ]);
    expect(results).toEqual([ME, ME, ME]);
    expect(refreshCalls).toBe(1);
    expect(tokens.access()).toBe("NEW");
    expect(tokens.refresh()).toBe("R2");
  });

  it("retries only once: a second 401 is returned to the caller", async () => {
    tokens.set({ access: "OLD", refresh: "R1" });
    let meCalls = 0;
    server.use(
      http.get(`${API}/me`, () => {
        meCalls += 1;
        return expired();
      }),
      http.post(`${API}/auth/token/refresh`, () => HttpResponse.json({ access: "NEW", refresh: "R2" })),
    );
    await expect(unwrap(api.GET("/api/v1/me"))).rejects.toMatchObject({ status: 401, code: "token_invalid" });
    expect(meCalls).toBe(2);
  });

  it("ends the session when the refresh fails", async () => {
    tokens.set({ access: "OLD", refresh: "R1" });
    const ended = vi.fn();
    const off = sessionEvents.onEnded(ended);
    server.use(
      http.get(`${API}/me`, expired),
      http.post(`${API}/auth/token/refresh`, () =>
        HttpResponse.json({ code: "token_invalid" }, { status: 401 }),
      ),
    );
    await expect(unwrap(api.GET("/api/v1/me"))).rejects.toBeInstanceOf(ApiError);
    expect(ended).toHaveBeenCalledTimes(1);
    expect(tokens.access()).toBeNull();
    expect(tokens.refresh()).toBeNull();
    off();
  });

  it("does not try to refresh for login failures or other 401 codes", async () => {
    tokens.set({ access: "A", refresh: "R1" });
    const refresh = vi.fn(() => HttpResponse.json({ access: "x", refresh: "y" }));
    server.use(
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json({ code: "invalid_credentials", message: "Nope" }, { status: 401 }),
      ),
      http.post(`${API}/auth/token/refresh`, refresh),
    );
    await expect(
      unwrap(api.POST("/api/v1/auth/login", { body: { email: "a@b.co", password: "x" } })),
    ).rejects.toMatchObject({
      code: "invalid_credentials",
    });
    expect(refresh).not.toHaveBeenCalled();
  });

  it("without a refresh token, a 401 is simply returned", async () => {
    server.use(
      http.get(`${API}/me`, () =>
        HttpResponse.json({ code: "not_authenticated", message: "Sign in" }, { status: 401 }),
      ),
    );
    await expect(unwrap(api.GET("/api/v1/me"))).rejects.toMatchObject({ code: "not_authenticated" });
  });

  it("normalises validation errors with fields and request id", async () => {
    server.use(
      http.post(`${API}/auth/register`, () =>
        HttpResponse.json(
          {
            code: "validation_error",
            message: "Some fields are invalid.",
            fields: { email: ["Taken."], "consents.terms": ["Required."] },
          },
          { status: 400, headers: { "X-Request-ID": "req-123" } },
        ),
      ),
    );
    const error = await unwrap(
      api.POST("/api/v1/auth/register", {
        body: {
          email: "a@b.co",
          password: "x",
          role: "job_seeker",
          fullName: "A",
          consents: { terms: true },
        },
      }),
    ).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 400,
      code: "validation_error",
      fields: { email: ["Taken."] },
      requestId: "req-123",
    });
  });

  it("turns network failures into network_error", async () => {
    server.use(http.get(`${API}/health`, () => HttpResponse.error()));
    await expect(unwrap(api.GET("/api/v1/health"))).rejects.toMatchObject({
      status: 0,
      code: "network_error",
    });
  });
});
