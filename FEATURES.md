# Features

Catalog of what the platform does. Grouped by user-facing capability and platform capability.

---

## 1. Customer Portal

### Authentication
- Username + password login with Argon2id verification (per-server pepper).
- Server-side session stored in Redis; opaque `httponly` + `samesite=lax` cookie.
- CSRF token issued at login; required on cookie-auth mutating endpoints.
- Logout destroys server-side session and clears the cookie.

### Upload
- Drag-and-drop or file-picker upload, single or batch (≤ 10 files / request).
- Per-file MIME sniff from magic bytes (PDF / PNG / JPEG / TIFF).
- Per-file size cap (`MAX_FILE_SIZE_MB`, default 10 MB).
- Streaming upload to S3 — body never materialised whole in memory beyond chunked buffering.
- Returns `202 Accepted` with one `job_id + status_url` per file.

### Jobs list
- Filters: status, document type (matched blueprint), date range.
- Pagination (size capped at 100).
- Per-row: filename, status pill, blueprint, pages, cost, created/completed timestamps.
- Querystring-synced filters (shareable URLs, browser back/forward works).

### Job detail
- Side-by-side: PDF iframe (presigned S3 GET, 5-minute TTL) + extracted fields panel.
- Confidence chip rendered next to every leaf field, including fields nested inside objects + array line items (e.g. container line items on a Bill of Lading).
- Raw BDA JSON drawer for debugging.
- Auto-poll every 3 s while status is `queued` or `processing`.
- Error code + message rendered for `failed` jobs.

### API key management
- View last-4 of current key.
- Rotate key — plaintext returned exactly once, then encrypted at rest with Fernet.
- Revoking creates a new key; old key disabled atomically.

---

## 2. Programmatic API

- `x-api-key` header authentication for `POST /jobs` + read endpoints.
- Same session-based code paths gated by a unified `require_api_key_or_session` dependency.
- All responses Pydantic-modelled; OpenAPI spec at `/api/openapi.json`, Swagger UI at `/api/docs`.
- Errors are RFC 7807 `application/problem+json` with stable `type` URIs and `Retry-After` on 429.

---

## 3. Admin Portal

### Dashboard
- Three buckets (24 h / 7 d / 30 d). For each: total jobs, success count, success rate, pages, $ cost.
- Chart.js pie of status mix and line chart of cost over time.

### Users
- List with filters (status, role, search).
- Create user (admin sets initial password).
- Suspend / restore (toggles `status`).
- Rotate any user's API key (returns plaintext once).
- Reset password.
- Soft-delete (sets `deleted_at`; user excluded from auth lookups).

### Jobs (cross-tenant)
- Same list view as customer, but spans every user.
- Drill-in reuses customer detail page (admin role gate enforced server-side).

### Audit log
- Paginated table.
- Filters by action, actor, target user, date range.
- Records every meaningful state change: login / login_failed / logout, jobs_uploaded, user_created / suspended / restored / deleted, password_reset, apikey_rotated.

---

## 4. AI / BDA Pipeline

- `bedrock-data-automation-runtime.invoke_data_automation_async` with `clientToken=job_id` for native idempotency.
- Polled via `get_data_automation_status` with explicit fibonacci-style backoff `[3, 5, 8, 13, 21, 21, …]` and a hard deadline (`BDA_POLL_MAX_SECONDS`).
- Output resolution handles both modes BDA uses: a direct path to `job_metadata.json`, or a prefix to scan. Reads `output_metadata[].segment_metadata[].custom_output_path` + `standard_output_path`.
- Blueprint normalisation against the known set: `bill_of_lading`, `commercial_invoice`, `packing_list`. Anything else stored as `unknown` so downstream UI doesn't render junk taxonomy.
- Confidence flatten walks `explainability_info` recursively — captures confidences for nested objects + array elements, not just top-level scalars.
- Page count fallback: if the custom output reports `pages=0`, the standard output's page count is used.

---

## 5. Job Lifecycle + Billing

- States: `queued → processing → success | failed`.
- Each transition is its own Postgres commit (no long-running open transaction across BDA polls).
- Cost formula matches BDA pricing: `pages × (0.040 + max(0, field_count − 30) × 0.0005)`. Stored as `NUMERIC(10,4)`.
- `started_at`, `completed_at`, `duration_ms` captured for every job.
- Failure paths split:
  - `BdaTerminalFailure` (`ServiceError` / `ClientError` / `MissingOutput` / `TimeoutError`) — clean error code preserved.
  - Unhandled exception — type name + truncated message.
- `raw_bda_output` JSONB column retained for replay / debugging.

---

## 6. Security

- Argon2id password hashing with `SERVER_PEPPER`.
- API keys: random URL-safe token; stored as Fernet ciphertext + HMAC `key_lookup_hash` for O(1) lookup; only the last-4 visible to UI; plaintext returned once.
- Session tokens minted via `secrets.token_urlsafe(32)`; stored in Redis with TTL.
- CSRF tokens for cookie-auth mutating routes (rotate / admin actions).
- Security headers middleware: `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, CSP scoped to allow S3 origin for the PDF preview only.
- Rate limits via Redis + `limits` library:
  - `60/minute` upload.
  - `300/minute` reads.
  - `10/minute/IP` + `20/hour/user` on login.
- All login attempts written to audit log (success + failure).

---

## 7. Reliability + Resilience

- Tenacity retries on transient AWS errors (`ThrottlingException`, `ServiceUnavailable`, `InternalServerException`) with exponential backoff. Non-transient errors fail fast.
- Tenacity retries on S3 `ClientError` for `list_objects_v2` + `get_object`.
- Celery `task_acks_late=True` + `prefetch_multiplier=1` — tasks ack only after success; broker requeues on worker crash.
- Idempotent BDA invoke via `clientToken=job_id` — safe to retry/dispatch the task multiple times.
- Soft + hard task time limits derived from `BDA_POLL_MAX_SECONDS`.
- Postgres advisory-locked migrations on startup — safe with multiple api replicas.
- Healthchecks on every Docker service; `api` waits on `postgres` / `redis` / `rabbitmq` health.
- `/healthz` (liveness) + `/readyz` (DB + Redis ping) endpoints for orchestrators.

---

## 8. Observability

- structlog-driven JSON logs.
- Every request bound with: `request_id` (echoed back to client), `path`, `method`, `principal_id`, `principal_role`.
- Worker lines additionally bound with: `job_id`, `task_name`, `attempt`.
- Distinct log events at each boundary: `bda.invoke.started`, `bda.invoke.success`, `bda.poll.tick`, `job.completed`, `job.failed`, `job.failed.unhandled`.
- RFC 7807 errors carry `type`, `title`, `status`, `detail` — directly correlatable to logs by `request_id`.

---

## 9. Data Model

| Table | Purpose |
|---|---|
| `users` | citext username + email, role, status, soft-delete `deleted_at`, password_hash. |
| `api_keys` | per-user keys; encrypted ciphertext + lookup hash + last-4. |
| `jobs` | full lifecycle row: input/output S3 URIs, BDA invocation arn, blueprint, pages, fields, cost, JSONB extracted_fields + raw_bda_output, timing. |
| `audit_log` | append-only; bigserial id; actor + action + target + JSONB metadata + IP + UA. |

Indexes: composite `(user_id, created_at)`; GIN on `extracted_fields`; case-insensitive uniqueness on `username` + `email` via citext.

---

## 10. Developer Experience

- Single `docker compose up` boots Postgres + Redis + RabbitMQ + api + worker, with healthcheck gating.
- `uv` for all dependency + execution workflows; `uv.lock` checked in.
- `ruff` (E, F, I, B, UP, S, ASYNC) + `mypy --strict` + pydantic plugin.
- `pytest` matrix:
  - Unit (no infrastructure).
  - Integration (real Postgres + real Redis on localhost; S3 via moto; BDA via in-process fake).
  - E2E (Playwright; needs the full compose stack).
- Seed script: `scripts/seed_admin.py admin admin@example.com <password>`.

---

## 11. Frontend (no-bundler ergonomics)

- Plain HTML files per route — no SPA router, no build step.
- Native ES modules; shared modules in `static/js/*.js`.
- Tailwind + Chart.js via CDN.
- Filters survive in querystring — shareable / bookmarkable.
- Toasts surface RFC 7807 errors uniformly.
- Detail page polls `GET /jobs/{id}` every 3 s while in non-terminal state.

---

## Caveats

- Blueprint outputs are not yet 100% consistent across runs of the same document. The remediation lives on the BDA project / blueprint side (tightening field prompts, adding examples), not in this codebase.
- Demo defaults are tuned for a single AWS account; multi-region failover and BDA project rotation are out of scope.
