"use client";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export type AuthUser = { id: string; email?: string };
type AuthSession = { access_token: string; refresh_token: string; expires_at?: number; expires_in?: number; user: AuthUser };
let accessToken: string | null = null;
let currentUser: AuthUser | null = null;\nlet accessTokenExpiresAt = 0;
const listeners = new Set<() => void>();
const STORAGE_KEY = "compatflow_refresh_token";

function notify() { listeners.forEach((listener) => listener()); }
function config() {
  if (!supabaseUrl || !supabaseAnonKey) throw new Error("Authentication is not configured. Set the public Supabase URL and anon key.");
  return { url: supabaseUrl.replace(/\/$/, ""), key: supabaseAnonKey };
}
async function authRequest<T>(path: string, body?: unknown, token?: string): Promise<T> {
  const { url, key } = config();
  const response = await fetch(`${url}/auth/v1/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { apikey: key, "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data.msg || data.message || data.error_description || data.error || "Authentication request failed.";
    throw new Error(String(message));
  }
  return data as T;
}
function applySession(session: AuthSession) {
  accessToken = session.access_token;
  currentUser = session.user;
  if (typeof window !== "undefined") {
    sessionStorage.setItem(STORAGE_KEY, session.refresh_token);
    window.dispatchEvent(new Event("compatflow-auth-change"));
  }
  notify();
}
export function subscribeAuth(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
export function getAuthSnapshot() { return { user: currentUser, accessToken, loading: false }; }
export async function signIn(email: string, password: string) {
  const session = await authRequest<AuthSession>("token?grant_type=password", { email: email.trim().toLowerCase(), password });
  applySession(session);
  return session.user;
}
export async function signUp(email: string, password: string, redirectPath = "/workspace") {
  const { url } = config();
  const safeNext = redirectPath.startsWith("/") && !redirectPath.startsWith("//") ? redirectPath : "/workspace";
  const redirectTo = `${window.location.origin}/auth/callback?next=${encodeURIComponent(safeNext)}`;
  const response = await fetch(`${url}/auth/v1/signup?redirect_to=${encodeURIComponent(redirectTo)}`, {
    method: "POST",
    headers: { apikey: config().key, "Content-Type": "application/json" },
    body: JSON.stringify({ email: email.trim().toLowerCase(), password, data: {} }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.msg || data.message || data.error_description || "Could not create the account.");
  if (data.access_token && data.refresh_token && data.user) applySession(data as AuthSession);
  return data as { user?: AuthUser; access_token?: string };
}
export async function requestPasswordReset(email: string) {
  const { url, key } = config();
  const redirectTo = `${window.location.origin}/auth/reset-password`;
  const response = await fetch(`${url}/auth/v1/recover?redirect_to=${encodeURIComponent(redirectTo)}`, {
    method: "POST", headers: { apikey: key, "Content-Type": "application/json" },
    body: JSON.stringify({ email: email.trim().toLowerCase() }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.msg || data.message || "Could not send the password reset email.");
  }
}
export async function updatePassword(password: string) {
  if (!accessToken) throw new Error("Your recovery session has expired. Request a new password reset email.");
  await authRequest("user", { password }, accessToken);
}
export async function signOut() {
  const token = accessToken;
  accessToken = null; currentUser = null;
  if (typeof window !== "undefined") {
    sessionStorage.removeItem(STORAGE_KEY);
    window.dispatchEvent(new Event("compatflow-auth-change"));
  }
  notify();
  if (token) {
    try { await authRequest("logout", {}, token); } catch { /* Local session is already cleared. */ }
  }
}
export async function restoreSession() {
  if (typeof window === "undefined") return;
  const refreshToken = sessionStorage.getItem(STORAGE_KEY);
  if (!refreshToken) return;
  try {
    const session = await authRequest<AuthSession>("token?grant_type=refresh_token", { refresh_token: refreshToken });
    applySession(session);
  } catch {
    sessionStorage.removeItem(STORAGE_KEY);
    accessToken = null; currentUser = null; notify();
  }
}
export function setSessionFromCallback(session: AuthSession) { applySession(session); }
export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!accessToken) throw new Error("Sign in is required to access this resource.");
  const response = await fetch(`${API_BASE.replace(/\/$/, "")}${path}`, {
    ...init,
    headers: { ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...init.headers, Authorization: `Bearer ${accessToken}` },
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.message || "The request could not be completed.");
  return data as T;
}
