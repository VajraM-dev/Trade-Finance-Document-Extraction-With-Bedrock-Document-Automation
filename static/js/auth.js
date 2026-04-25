import { apiFetch, setCsrf } from "/js/api.js";

let cached = null;

export async function ensureAuthed(requireRole) {
  if (cached) return cached;
  const me = await apiFetch("/api/v1/auth/me");
  setCsrf(me.csrf_token);
  cached = me;
  if (requireRole && me.role !== requireRole) {
    location.replace("/login.html");
    throw new Error("forbidden");
  }
  return me;
}

export async function logout() {
  await apiFetch("/api/v1/auth/logout", { method: "POST" });
  cached = null;
  location.replace("/login.html");
}
