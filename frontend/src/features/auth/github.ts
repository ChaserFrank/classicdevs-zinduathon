/**
 * GitHub OAuth from the SPA (backend docs/AUTH.md): ask the API for the authorize URL, keep the
 * signed `state` (and where to go next) in sessionStorage, send the browser to GitHub.
 * /auth/github/callback compares the returned state before posting the code to the API.
 */
import { api, unwrap } from "@/lib/api/client";

const STATE_KEY = "skillproof.githubState";
const NEXT_KEY = "skillproof.githubNext";

type Start = {
  role?: "job_seeker" | "recruiter";
  link?: boolean;
  acceptTerms?: boolean;
  emailFeedback?: boolean;
  smsFeedback?: boolean;
  next?: string | null;
};

export async function startGithub(options: Start = {}): Promise<void> {
  const { next, ...query } = options;
  const { authorizeUrl, state } = await unwrap(api.GET("/api/v1/auth/github/authorize", { params: { query } }));
  try {
    sessionStorage.setItem(STATE_KEY, state);
    if (next) sessionStorage.setItem(NEXT_KEY, next);
  } catch {
    /* without storage we can't compare state; the API still verifies its signature */
  }
  window.location.assign(authorizeUrl);
}

export function takeGithubSession(): { state: string | null; next: string | null } {
  try {
    const state = sessionStorage.getItem(STATE_KEY);
    const next = sessionStorage.getItem(NEXT_KEY);
    sessionStorage.removeItem(STATE_KEY);
    sessionStorage.removeItem(NEXT_KEY);
    return { state, next };
  } catch {
    return { state: null, next: null };
  }
}
