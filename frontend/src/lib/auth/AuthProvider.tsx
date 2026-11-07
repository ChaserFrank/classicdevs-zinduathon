/**
 * Session bootstrap and lifecycle (backend docs/AUTH.md):
 * on load, if a refresh token exists → refresh → GET /me before protected routes render.
 * When the client middleware reports a dead session → clear state, toast, /login?next=<path>.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { api, refreshSession, unwrap } from "@/lib/api/client";
import { qk } from "@/lib/api/query-keys";
import type { Me } from "@/lib/api/types";

import { AuthContext, type AuthState } from "./auth-context";
import { sessionEvents, tokens } from "./tokens";

export function AuthProvider({ children, onSessionEnded }: { children: ReactNode; onSessionEnded?: (next: string) => void }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthState["status"]>(() => (tokens.refresh() ? "loading" : "signed-out"));
  const [user, setUser] = useState<Me | null>(null);

  const loadMe = useCallback(async () => {
    const me = await unwrap(api.GET("/api/v1/me"));
    queryClient.setQueryData(qk.me, me);
    setUser(me);
    setStatus("signed-in");
    return me;
  }, [queryClient]);

  useEffect(() => {
    if (!tokens.refresh()) return;
    let alive = true;
    (async () => {
      const ok = tokens.access() ? true : await refreshSession();
      if (!alive) return;
      if (!ok) {
        tokens.clear();
        setStatus("signed-out");
        return;
      }
      try {
        await loadMe();
      } catch {
        if (alive) {
          tokens.clear();
          setStatus("signed-out");
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, [loadMe]);

  useEffect(
    () =>
      sessionEvents.onEnded(() => {
        setUser(null);
        setStatus("signed-out");
        queryClient.clear();
        toast("Your session ended. Sign in again.");
        onSessionEnded?.(window.location.pathname + window.location.search);
      }),
    [queryClient, onSessionEnded],
  );

  const signIn = useCallback<AuthState["signIn"]>(
    ({ access, refresh, user: me }) => {
      tokens.set({ access, refresh });
      queryClient.setQueryData(qk.me, me);
      setUser(me);
      setStatus("signed-in");
    },
    [queryClient],
  );

  const signOut = useCallback(async () => {
    const refresh = tokens.refresh();
    if (refresh) await api.POST("/api/v1/auth/logout", { body: { refresh } }).catch(() => undefined);
    tokens.clear();
    queryClient.clear();
    setUser(null);
    setStatus("signed-out");
  }, [queryClient]);

  const refreshMe = useCallback(async () => {
    try {
      return await loadMe();
    } catch {
      return null;
    }
  }, [loadMe]);

  const value = useMemo<AuthState>(
    () => ({ status, user, signIn, signOut, refreshMe }),
    [status, user, signIn, signOut, refreshMe],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
