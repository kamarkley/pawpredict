export interface AuthUser {
  id: string;
  email: string | null;
}

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
  user: AuthUser;
}

export interface AuthResult {
  session: AuthSession | null;
  user: AuthUser | null;
}

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;
const STORAGE_KEY = "pawpredict.auth.session.v1";
let refreshPromise: Promise<AuthSession | null> | null = null;

function requireConfig() {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    throw new Error("Supabase authentication is not configured.");
  }
}

function authHeaders(accessToken?: string): HeadersInit {
  requireConfig();
  const headers: Record<string, string> = {
    apikey: SUPABASE_ANON_KEY,
    "Content-Type": "application/json",
  };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  return headers;
}

function userFromPayload(value: unknown): AuthUser | null {
  if (!value || typeof value !== "object") return null;
  const payload = value as { id?: unknown; email?: unknown };
  if (typeof payload.id !== "string") return null;
  return {
    id: payload.id,
    email: typeof payload.email === "string" ? payload.email : null,
  };
}

function sessionFromPayload(payload: unknown): AuthSession | null {
  if (!payload || typeof payload !== "object") return null;
  const data = payload as {
    access_token?: unknown;
    refresh_token?: unknown;
    expires_at?: unknown;
    expires_in?: unknown;
    user?: unknown;
  };
  const user = userFromPayload(data.user);
  if (
    typeof data.access_token !== "string"
    || typeof data.refresh_token !== "string"
    || !user
  ) return null;
  const expiresAt = typeof data.expires_at === "number"
    ? data.expires_at
    : Math.floor(Date.now() / 1000) + (typeof data.expires_in === "number" ? data.expires_in : 3600);
  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    expiresAt,
    user,
  };
}

function persistSession(session: AuthSession | null) {
  if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  else localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new CustomEvent("pawpredict-auth-changed"));
}

export function getStoredSession(): AuthSession | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as AuthSession;
    if (!value.accessToken || !value.refreshToken || !value.user?.id) return null;
    return value;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

async function authRequest(path: string, body?: unknown, accessToken?: string): Promise<unknown> {
  requireConfig();
  const response = await fetch(`${SUPABASE_URL}/auth/v1${path}`, {
    method: "POST",
    headers: authHeaders(accessToken),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({})) as { msg?: string; message?: string; error_description?: string };
  if (!response.ok) {
    throw new Error(payload.msg ?? payload.message ?? payload.error_description ?? "Authentication failed.");
  }
  return payload;
}

export async function signIn(email: string, password: string): Promise<AuthSession> {
  const payload = await authRequest("/token?grant_type=password", { email, password });
  const session = sessionFromPayload(payload);
  if (!session) throw new Error("Supabase did not return a login session.");
  persistSession(session);
  return session;
}

export async function signUp(email: string, password: string): Promise<AuthResult> {
  const payload = await authRequest("/signup", { email, password });
  const session = sessionFromPayload(payload);
  const raw = payload as { user?: unknown };
  const user = session?.user ?? userFromPayload(raw.user);
  if (session) persistSession(session);
  return { session, user };
}

export async function signOut(): Promise<void> {
  const session = getStoredSession();
  persistSession(null);
  if (!session) return;
  try {
    await authRequest("/logout", undefined, session.accessToken);
  } catch {
    // Local logout must still succeed if the network is unavailable.
  }
}

async function refreshSession(): Promise<AuthSession | null> {
  const current = getStoredSession();
  if (!current?.refreshToken) return null;
  try {
    const payload = await authRequest("/token?grant_type=refresh_token", {
      refresh_token: current.refreshToken,
    });
    const session = sessionFromPayload(payload);
    persistSession(session);
    return session;
  } catch {
    persistSession(null);
    return null;
  }
}

export async function getAccessToken(forceRefresh = false): Promise<string | null> {
  const session = getStoredSession();
  if (!session) return null;
  const now = Math.floor(Date.now() / 1000);
  if (!forceRefresh && session.expiresAt - now > 60) return session.accessToken;
  if (!refreshPromise) {
    refreshPromise = refreshSession().finally(() => { refreshPromise = null; });
  }
  return (await refreshPromise)?.accessToken ?? null;
}
