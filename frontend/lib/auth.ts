/**
 * Auth utilities: token storage, user state, login/logout helpers.
 */

export type User = {
  id: string;
  email: string;
  org_id: string;
  org_name: string | null;
  role: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

const TOKEN_KEY = "sourcer_token";
const USER_KEY = "sourcer_user";

// ── Token Storage ──────────────────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ── User Storage ───────────────────────────────────────────────────────────

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setUser(user: User): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearUser(): void {
  localStorage.removeItem(USER_KEY);
}

// ── Auth Actions ───────────────────────────────────────────────────────────

export function saveAuth(response: AuthResponse): void {
  setToken(response.access_token);
  setUser(response.user);
}

export function clearAuth(): void {
  clearToken();
  clearUser();
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

// ── API Helpers ────────────────────────────────────────────────────────────

export function getAuthHeaders(): Record<string, string> {
  const token = getToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}
