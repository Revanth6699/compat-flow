"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { clearSessionFromStorage, getAuthSnapshot, restoreSession, signOut as endSession, subscribeAuth, type AuthUser } from "@/lib/auth-client";

type AuthContextValue = { user: AuthUser | null; accessToken: string | null; loading: boolean; signOut: () => Promise<void> };
const AuthContext = createContext<AuthContextValue>({ user: null, accessToken: null, loading: true, signOut: async () => {} });
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [snapshot, setSnapshot] = useState({ user: null as AuthUser | null, accessToken: null as string | null });
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    const update = () => { const next = getAuthSnapshot(); if (active) setSnapshot({ user: next.user, accessToken: next.accessToken }); };
    const unsubscribe = subscribeAuth(update);
    window.addEventListener("compatflow-auth-change", update);
    const handleStorage = (event: StorageEvent) => {
      if (event.key === "compatflow_refresh_token" && event.newValue === null) {
        clearSessionFromStorage();
        update();
      }
    };
    window.addEventListener("storage", handleStorage);
    restoreSession().finally(() => { if (active) { update(); setLoading(false); } });
    return () => {
      active = false;
      unsubscribe();
      window.removeEventListener("compatflow-auth-change", update);
      window.removeEventListener("storage", handleStorage);
    };
  }, []);
  const value = useMemo(() => ({ ...snapshot, loading, signOut: endSession }), [snapshot, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() { return useContext(AuthContext); }
