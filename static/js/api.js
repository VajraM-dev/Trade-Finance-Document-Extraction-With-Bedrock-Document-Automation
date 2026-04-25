import { showToast } from "/js/toast.js";

let csrfToken = null;

export function setCsrf(token) {
  csrfToken = token;
}

export function getCsrf() {
  return csrfToken;
}

function newRequestId() {
  return crypto.randomUUID();
}

async function parseProblem(response) {
  try {
    return await response.json();
  } catch {
    return { title: `HTTP ${response.status}`, status: response.status, request_id: "" };
  }
}

export async function apiFetch(path, { method = "GET", json, form, headers = {} } = {}) {
  const requestId = newRequestId();
  const opts = {
    method,
    credentials: "include",
    headers: { "X-Request-ID": requestId, ...headers },
  };
  if (json !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(json);
  }
  if (form !== undefined) {
    opts.body = form;
  }
  if (csrfToken && method !== "GET" && method !== "HEAD") {
    opts.headers["X-CSRF-Token"] = csrfToken;
  }

  const r = await fetch(path, opts);
  if (r.status === 401) {
    location.replace("/login.html");
    throw new Error("unauthorized");
  }
  if (!r.ok) {
    const problem = await parseProblem(r);
    showToast(`${problem.title}${problem.detail ? ` — ${problem.detail}` : ""} (req: ${problem.request_id || requestId})`, "error");
    throw new Error(problem.title);
  }
  if (r.status === 204) return null;
  return r.json();
}

export async function apiUpload(path, files) {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  return apiFetch(path, { method: "POST", form });
}
