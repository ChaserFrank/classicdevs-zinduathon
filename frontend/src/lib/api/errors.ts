/** Every failed call becomes an ApiError with the backend's {code, message, fields} shape. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields?: Record<string, string[]>,
    public requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ErrorBody = { code?: unknown; message?: unknown; fields?: unknown };

export function toApiError(status: number, body: unknown, requestId?: string): ApiError {
  const b = (body && typeof body === "object" ? body : {}) as ErrorBody;
  const code = typeof b.code === "string" ? b.code : status === 0 ? "network_error" : "server_error";
  const message = typeof b.message === "string" ? b.message : messageFor(code);
  const fields =
    b.fields && typeof b.fields === "object" ? (b.fields as Record<string, string[]>) : undefined;
  return new ApiError(status, code, message, fields, requestId);
}

/** Plain, specific UI copy per error code (no apologies). Backend messages are used otherwise. */
const COPY: Record<string, string> = {
  validation_error: "Check the highlighted fields.",
  permission_denied: "Your account can't do this.",
  email_not_verified: "Verify your email first.",
  no_public_repos: "This GitHub account has no public repositories yet. Push a project and analyse again.",
  github_not_linked: "Connect your GitHub account to run an analysis.",
  rate_limited: "Too many requests. Try again in a minute.",
  github_rate_limited: "GitHub's rate limit was reached. Try again in a minute.",
  analysis_in_progress: "An analysis is already running.",
  server_error: "Something went wrong on our side. Try again.",
  network_error: "We couldn't reach SkillProof. Check your connection and try again.",
  invalid_credentials: "Email or password is incorrect.",
  recruiter_not_approved: "Your recruiter account is waiting for approval.",
};

export function messageFor(code: string): string {
  return COPY[code] ?? "Something went wrong on our side. Try again.";
}

/** The message to show a user: our copy for known codes (keeping the backend's retry time). */
export function userMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return messageFor("server_error");
  if (error.code === "rate_limited" && /\d+ seconds/.test(error.message)) return error.message;
  if (error.code === "github_rate_limited") return error.message || messageFor(error.code);
  return COPY[error.code] ?? error.message;
}

/** Field errors keyed by our form field names (backend keys are camelCase, nested with dots). */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || !error.fields) return {};
  return Object.fromEntries(Object.entries(error.fields).map(([k, v]) => [k, v.join(" ")]));
}
