# Document Automation — AWS Bedrock Data Automation IDP Demo

End-to-end Intelligent Document Processing platform built around **AWS Bedrock Data Automation (BDA)** for logistics documents (Bill of Lading, Commercial Invoice, Packing List). Customers upload PDFs through a web portal or API; BDA classifies + extracts structured fields with confidence scores; admins see usage, cost, and per-customer audit trails.

The platform demonstrates how a single managed service (BDA) replaces the traditional OCR → layout-analysis → classifier → extraction pipeline, while still wrapping it in production-grade plumbing: async FastAPI, Celery on RabbitMQ, Postgres, Redis, structured logs, rate limits, retries, and RFC 7807 errors.

---

## Disclaimer

**This project is not about Trade Finance.** The focus is on building production-grade pipelines around **AWS Bedrock Data Automation**. Trade finance documents (Bill of Lading, Commercial Invoice, Packing List) were chosen only because realistic dummy samples are easy to generate and ship publicly — unlike sensitive documents (Aadhaar, PAN, passports, bank statements) which carry PII and regulatory risk in a demo.

The backend is document-agnostic. To repurpose it for any other domain (KYC, healthcare forms, contracts, receipts, custom internal docs), point the worker at **your own BDA project + blueprints** via `BDA_PROJECT_ARN` / `BDA_PROFILE_ARN`. No code changes required for new document types — extracted fields, confidence scores, and cost accounting all flow through generic parsing.

---

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI (async) on uvicorn, Pydantic v2, pydantic-settings |
| Workers | Celery 5.4 on RabbitMQ, single `process_document(job_id)` task |
| Data | Postgres 16 (asyncpg + SQLAlchemy 2 async), Alembic migrations |
| Cache / sessions / rate-limit | Redis 7 |
| Object storage | S3 via aioboto3 (input + BDA output buckets) |
| AI | AWS Bedrock Data Automation (`bedrock-data-automation-runtime`) |
| Auth | Argon2 passwords, server-side Redis sessions, Fernet-encrypted API keys |
| Frontend | Static HTML + native ES modules + Tailwind/Chart.js via CDN (no bundler) |
| Tests | pytest, pytest-asyncio, moto (S3), fakeredis, Playwright (E2E) |
| Tooling | uv, ruff, mypy, structlog |

---

## Architecture

```
Browser ──► FastAPI ──► Postgres
              │  ▲       Redis (sessions, rate-limit, api-key cache)
              │  │
              ▼  │
           RabbitMQ ──► Celery Worker ──► AWS Bedrock Data Automation
                                              │
                                              ▼
                                          S3 (in / out)
```

- API streams uploads to S3, inserts a `queued` job row, dispatches Celery task.
- Worker calls `invoke_data_automation_async`, polls `get_data_automation_status` with tenacity backoff, fetches `custom_output/result.json` from S3, normalises fields + flattens confidences, computes cost, writes back to Postgres.
- Frontend polls `GET /jobs/{id}` every 3s while status is `queued|processing`.

---

## Quick Start

### 1. Configure env

```bash
cp .env.example .env
# fill in: AWS keys, S3_INPUT_BUCKET / S3_OUTPUT_BUCKET, BDA_PROJECT_ARN, BDA_PROFILE_ARN
# rotate SESSION_SECRET / SERVER_PEPPER / FERNET_KEY (32-byte secrets)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Boot stack

```bash
docker compose up --build
```

Services (with healthchecks): `postgres`, `redis`, `rabbitmq`, `api`, `worker`. Migrations run on api startup behind a Postgres advisory lock.

### 3. Seed admin

```bash
docker compose exec api uv run python scripts/seed_admin.py admin admin@example.com hunter2-strong
```

### 4. Open portal

- Customer / admin login: <http://localhost:8000/login.html>
- API docs (Swagger): <http://localhost:8000/api/docs>
- RabbitMQ management UI: <http://localhost:15672> (`guest`/`guest`)

---

## Development (without Docker)

```bash
# bring up just the dependencies
docker compose up -d postgres redis rabbitmq

# install
uv sync

# run api
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# run worker
uv run celery -A app.worker.celery_app worker --concurrency=10 --loglevel=INFO

# tests
uv run pytest
uv run ruff check src tests
uv run mypy src
```

Integration tests need real Postgres + Redis on localhost. Create the test DB once:

```bash
docker compose exec postgres psql -U app -d app -c "CREATE DATABASE test_app;"
```

E2E (Playwright) needs the full stack running:

```bash
uv run playwright install chromium
uv run pytest tests/e2e
```

---

## API Surface

All paths prefixed `/api/v1`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/auth/login` | none | Login → session cookie + CSRF |
| `POST` | `/auth/logout` | session | Destroy session |
| `GET`  | `/auth/me` | session | Current user |
| `GET`  | `/me/api-key` | session | Show last-4 of API key |
| `POST` | `/me/api-key/rotate` | session + CSRF | Rotate (returns plaintext once) |
| `POST` | `/jobs` | session or `x-api-key` | Upload 1–10 files (multipart) |
| `GET`  | `/jobs` | session or api key | List + filters + pagination |
| `GET`  | `/jobs/{id}` | session or api key | Job detail + extracted fields |
| `GET`  | `/jobs/{id}/raw` | session or api key | Raw BDA output JSON |
| `GET`  | `/jobs/{id}/preview` | session or api key | Presigned S3 GET (PDF) |
| `GET`  | `/usage` | session | Per-user usage + cost |
| `GET`  | `/admin/dashboard` | admin | Aggregate buckets (24h / 7d / 30d) |
| `GET`  | `/admin/users` | admin | List users + filters |
| `POST` | `/admin/users` | admin | Create user |
| `PATCH`/`DELETE` | `/admin/users/{id}` | admin | Suspend / restore / soft-delete |
| `GET`  | `/admin/jobs` | admin | All jobs across tenants |
| `GET`  | `/admin/audit` | admin | Audit log |
| `GET`  | `/healthz` / `/readyz` | none | Liveness / readiness |

Errors are RFC 7807 (`application/problem+json`) with stable `type` URIs. All requests carry an `X-Request-ID`, returned in the response and propagated through structlog.

---

## Repository Layout

```
code/
├── src/app/
│   ├── main.py                 # FastAPI app + lifespan + middleware
│   ├── settings.py             # pydantic-settings
│   ├── db/                     # engine, models, migrations runner
│   ├── repos/                  # query functions (users, api_keys, jobs, audit)
│   ├── routes/                 # auth, me, jobs, usage, admin, health
│   ├── services/               # passwords, sessions, apikeys, presign,
│   │                           # uploads, csrf, billing, jobs_runner
│   ├── deps/                   # FastAPI dependencies (auth, db, redis, ratelimit)
│   ├── middleware/             # request_id, log_context, security_headers, errors
│   ├── bda/                    # client, invoke, poll, parse
│   └── worker/                 # celery_app, tasks
├── alembic/                    # migrations
├── static/                     # frontend (no bundler)
│   ├── customer/               # upload + jobs + side-by-side PDF viewer
│   ├── admin/                  # dashboard, users, jobs, audit
│   └── js/                     # native ES modules
├── tests/
│   ├── unit/                   # passwords, sessions, billing, parse, …
│   ├── integration/            # auth flow, jobs lifecycle, rate-limit, admin
│   └── e2e/                    # Playwright smoke
├── scripts/seed_admin.py
├── docker-compose.yml
├── Dockerfile                  # multi-stage uv image
└── pyproject.toml
```

---

## Production Features

- Async-only Python (no sync DB / sync HTTP in request path).
- Server-side sessions (Redis), Argon2id password hashing with per-server pepper.
- API keys: random token, Fernet-encrypted at rest, HMAC lookup hash, last-4 displayed.
- Rate limits via `limits` + Redis: `60/min` upload, `300/min` reads, login 10/min/IP + 20/h/user.
- Tenacity-backed retries on transient BDA + S3 errors; idempotent BDA invoke via `clientToken=job_id`.
- Celery `task_acks_late=True`, `prefetch_multiplier=1`, soft + hard time limits.
- Structured JSON logs (structlog) bound with `request_id`, `user_id`, `job_id`.
- RFC 7807 errors, security headers middleware, CSRF for cookie-auth mutating endpoints.
- Postgres advisory-locked migrations on startup.
- GIN index on `jobs.extracted_fields`; cost stored as `NUMERIC(10,4)`.
- Healthchecks on every Docker service.

---

## Documentation

- [`FEATURES.md`](FEATURES.md) — feature catalog.

---

## License

MIT — see [`LICENSE`](LICENSE).
