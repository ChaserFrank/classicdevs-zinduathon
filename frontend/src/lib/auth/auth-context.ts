import { createContext, useContext } from "react";

import type { AuthResponse, Me } from "@/lib/api/types";

export type AuthState = {
  status: "loading" | "signed-in" | "signed-out";
  user: Me | null;
  /** Store tokens from register/login/GitHub and cache the user. */
  signIn: (response: Pick<AuthResponse, "access" | "refresh" | "user">) => void;
  signOut: () => Promise<void>;
  /** Re-read /me (after verifying email or phone, profile edits…). */
  refreshMe: () => Promise<Me | null>;
};

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
