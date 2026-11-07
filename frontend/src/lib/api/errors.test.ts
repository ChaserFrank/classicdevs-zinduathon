import { ApiError, fieldErrors, messageFor, toApiError, userMessage } from "./errors";

describe("error mapping", () => {
  it("uses our copy for known codes", () => {
    expect(userMessage(new ApiError(403, "permission_denied", "x"))).toBe("Your account can't do this.");
    expect(userMessage(new ApiError(400, "no_public_repos", "x"))).toMatch(/no public repositories/);
    expect(userMessage(new ApiError(400, "github_not_linked", "x"))).toBe(
      "Connect your GitHub account to run an analysis.",
    );
  });

  it("keeps the backend's retry time for rate limits", () => {
    expect(
      userMessage(new ApiError(429, "rate_limited", "Too many requests. Try again in 42 seconds.")),
    ).toMatch(/42 seconds/);
    expect(userMessage(new ApiError(429, "rate_limited", "Throttled"))).toBe(
      "Too many requests. Try again in a minute.",
    );
  });

  it("falls back to the backend message for codes we don't map", () => {
    expect(userMessage(new ApiError(400, "terms_required", "Accept the terms."))).toBe("Accept the terms.");
    expect(userMessage(new Error("boom"))).toBe(messageFor("server_error"));
  });

  it("builds errors from odd bodies", () => {
    expect(toApiError(502, "<html>")).toMatchObject({ code: "server_error" });
    expect(toApiError(0, null)).toMatchObject({ code: "network_error" });
  });

  it("flattens field errors", () => {
    const e = new ApiError(400, "validation_error", "x", { email: ["Taken.", "Invalid."] });
    expect(fieldErrors(e)).toEqual({ email: "Taken. Invalid." });
    expect(fieldErrors(new Error())).toEqual({});
  });
});
