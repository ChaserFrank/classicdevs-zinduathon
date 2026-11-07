/**
 * Token storage (backend docs/AUTH.md): the access token lives in memory only; the refresh token
 * in localStorage so a reload can restore the session. localStorage can throw (private mode,
 * blocked storage), so every access is guarded and the app still works for the current tab.
 */
const REFRESH_KEY = "skillproof.refresh";

let accessToken: string | null = null;
let memoryRefresh: string | null = null; // used when localStorage is unavailable

export type TokenPair = { access: string; refresh: string };

export const tokens = {
  access: () => accessToken,
  refresh(): string | null {
    try {
      return window.localStorage.getItem(REFRESH_KEY) ?? memoryRefresh;
    } catch {
      return memoryRefresh;
    }
  },
  set(pair: TokenPair) {
    accessToken = pair.access;
    memoryRefresh = pair.refresh;
    try {
      window.localStorage.setItem(REFRESH_KEY, pair.refresh);
    } catch {
      /* keep the in-memory copy */
    }
  },
  clear() {
    accessToken = null;
    memoryRefresh = null;
    try {
      window.localStorage.removeItem(REFRESH_KEY);
    } catch {
      /* nothing to clear */
    }
  },
};

/** Fired when a refresh fails: the AuthProvider signs out and sends the user to /login?next=… */
type Listener = () => void;
const listeners = new Set<Listener>();
export const sessionEvents = {
  onEnded(listener: Listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  ended() {
    listeners.forEach((l) => l());
  },
};
