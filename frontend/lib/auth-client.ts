"use client";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export type AuthUser = { id: string; email?: string; user_metadata?: { full_name?: string } };
type AuthSession = { access_token: string; refresh_token: string; expires_at?: number; expires_in?: number; user: AuthUser };
let accessToken: string | null = null;
let currentUser: AuthUser | null = null;
let accessTokenExpiresAt = 0;
const listeners = new Set<() => void>();
const STORAGE_KEY = "compatflow_refresh_token";
const PKCE_VERIFIER_KEY = "compatflow_pkce_verifier";

function notify() { listeners.forEach((listener) => listener()); }
function base64Url(bytes: Uint8Array) {
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}
async function createPkceChallenge() {
  const verifierBytes = crypto.getRandomValues(new Uint8Array(32));
  const verifier = base64Url(verifierBytes);
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  localStorage.setItem(PKCE_VERIFIER_KEY, verifier);
  return base64Url(new Uint8Array(digest));
}
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
  accessTokenExpiresAt = session.expires_at ?? (Date.now() / 1000 + (session.expires_in ?? 3600));
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
export async function exchangeCodeForSession(code: string) {
  const verifier = localStorage.getItem(PKCE_VERIFIER_KEY);
  if (!verifier) throw new Error("The sign-in verification session is missing or expired. Request a new email link.");
  const session = await authRequest<AuthSession>("token?grant_type=pkce", { auth_code: code, code_verifier: verifier });
  localStorage.removeItem(PKCE_VERIFIER_KEY);
  applySession(session);
  return session.user;
}
export async function signIn(email: string, password: string) {
  const session = await authRequest<AuthSession>("token?grant_type=password", { email: email.trim().toLowerCase(), password });
  applySession(session);
  return session.user;
}
export async function signUp(email: string, password: string, redirectPath = "/workspace") {
  const { url, key } = config();
  const safeNext = redirectPath.startsWith("/") && !redirectPath.startsWith("//") ? redirectPath : "/workspace";
  const redirectTo = `${window.location.origin}/auth/callback?next=${encodeURIComponent(safeNext)}`;
  const codeChallenge = await createPkceChallenge();
  const signupUrl = new URL(`${url}/auth/v1/signup`);
  signupUrl.searchParams.set("redirect_to", redirectTo);
  const response = await fetch(signupUrl.toString(), {
    method: "POST",
    headers: { apikey: key, "Content-Type": "application/json" },
    body: JSON.stringify({ email: email.trim().toLowerCase(), password, data: {}, code_challenge: codeChallenge, code_challenge_method: "s256" }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    localStorage.removeItem(PKCE_VERIFIER_KEY);
    throw new Error(data.msg || data.message || data.error_description || "Could not create the account.");
  }
  if (data.access_token && data.refresh_token && data.user) {
    localStorage.removeItem(PKCE_VERIFIER_KEY);
    applySession(data as AuthSession);
  }
  return data as { user?: AuthUser; access_token?: string };
}
export async function requestPasswordReset(email: string) {
  const { url, key } = config();
  const redirectTo = `${window.location.origin}/auth/reset-password`;
  const codeChallenge = await createPkceChallenge();
  const recoveryUrl = new URL(`${url}/auth/v1/recover`);
  recoveryUrl.searchParams.set("redirect_to", redirectTo);
  const response = await fetch(recoveryUrl.toString(), {
    method: "POST", headers: { apikey: key, "Content-Type": "application/json" },
    body: JSON.stringify({ email: email.trim().toLowerCase(), code_challenge: codeChallenge, code_challenge_method: "s256" }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    localStorage.removeItem(PKCE_VERIFIER_KEY);
    throw new Error(data.msg || data.message || "Could not send the password reset email.");
  }
}
export async function updatePassword(password: string) {
  if (!accessToken) throw new Error("Your session has expired. Sign in again before changing your password.");
  await authRequest("user", { password }, accessToken);
}
export async function updateProfile(fullName: string) {
  if (!accessToken) throw new Error("Your session has expired. Sign in again before updating your profile.");
  const { url, key } = config();
  const response = await fetch(`${url}/auth/v1/user`, {
    method: "PUT",
    headers: { apikey: key, "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ data: { full_name: fullName.trim() } }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.msg || data.message || "Could not update your profile.");
  currentUser = data as AuthUser;
  notify();
  return currentUser;
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
  if (accessToken && accessTokenExpiresAt < Date.now() / 1000 + 60) {
    const refreshToken = sessionStorage.getItem(STORAGE_KEY);
    if (refreshToken) {
      const refreshed = await authRequest<AuthSession>("token?grant_type=refresh_token", { refresh_token: refreshToken });
      applySession(refreshed);
    }
  }
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
