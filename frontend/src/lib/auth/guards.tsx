import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { Splash } from "@/components/Splash";
import type { Role } from "@/lib/api/types";

import { useAuth } from "./auth-context";
import { homeFor } from "./redirects";

/**
 * Route guard: signed in, with one of `roles`; recruiters additionally approved unless
 * `allowUnapproved`. Wrong role → their own home; signed out → /login?next=…
 */
export function RequireAuth({
  roles,
  allowUnapproved = false,
  children,
}: {
  roles: Role[];
  allowUnapproved?: boolean;
  children?: ReactNode;
}) {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === "loading") return <Splash />;
  if (status === "signed-out" || !user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (!user.role || !roles.includes(user.role)) return <Navigate to={homeFor(user)} replace />;
  if (user.role === "recruiter" && !allowUnapproved && user.recruiterProfile?.approvalStatus !== "approved") {
    return <Navigate to="/recruiter/pending" replace />;
  }
  return children ? <>{children}</> : <Outlet />;
}

/** Auth screens: already signed in → go home instead of seeing the login form again. */
export function GuestOnly({ children }: { children?: ReactNode }) {
  const { status, user } = useAuth();
  if (status === "loading") return <Splash />;
  if (status === "signed-in" && user) return <Navigate to={homeFor(user)} replace />;
  return children ? <>{children}</> : <Outlet />;
}
