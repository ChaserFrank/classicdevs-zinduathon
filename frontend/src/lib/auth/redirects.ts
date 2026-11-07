import type { Me } from "@/lib/api/types";

/** Where each role lands after sign-in (FRONTEND_PROMPT §5). */
export function homeFor(user: Me): string {
  if (user.role === "admin") return "/admin";
  if (user.role === "recruiter") {
    return user.recruiterProfile?.approvalStatus === "approved" ? "/recruiter" : "/recruiter/pending";
  }
  return "/app";
}

/** Only same-site relative paths are honoured for ?next= (no open redirects). */
export function safeNext(next: string | null | undefined): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/login")) return null;
  return next;
}
