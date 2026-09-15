# FastAPI URL Shortener — Three-Hour Implementation Plan

## Summary

Build one stateless FastAPI service backed by DigitalOcean Managed PostgreSQL. Use synchronous SQLAlchemy 2.x with Psycopg 3, Alembic migrations, Pydantic validation, pytest integration tests, and `uv` for locked dependencies.

Keep the architecture intentionally small: no repository classes, Redis, background workers, Docker image, authentication, or rate limiting. Database uniqueness makes multiple API instances safe.

## API and Data Model

### Endpoints

| Method | Route | Behavior |
|---|---|---|
| `GET` | `/health` | Liveness check; returns `200 {"status":"ok"}` without querying PostgreSQL |
| `GET` | `/ready` | Executes `SELECT 1`; returns 200 when PostgreSQL is reachable, otherwise 503 |
| `POST` | `/api/v1/links` | Creates an automatically generated or custom alias; returns 201 |
| `GET` | `/api/v1/links/{alias}` | Returns metadata or 404 |
| `GET` | `/{alias}` | Atomically records the visit and returns a 307 redirect, or 404 |

Creation request:

```json
{
  "url": "https://example.com/a/long/path",
  "custom_alias": "example-link"
}
```

`custom_alias` is optional. Responses expose:

```json
{
  "id": "uuid",
  "alias": "example-link",
  "original_url": "https://example.com/a/long/path",
  "short_url": "https://short.example/example-link",
  "is_custom": true,
  "created_at": "2026-09-15T20:00:00Z",
  "click_count": 0,
  "last_accessed_at": null
}
```

Rules:

- Accept only absolute HTTP/HTTPS URLs, maximum 2,048 characters, with no embedded credentials.
- Custom aliases are lowercase, 3–32 characters, match `[a-z0-9](?:[a-z0-9-]{1,30}[a-z0-9])?`, and cannot use `api`, `health`, `ready`, `docs`, or `redoc`.
- Automatic aliases are 10 cryptographically random lowercase alphanumeric characters.
- Alias uniqueness is enforced by PostgreSQL. Custom conflicts return 409; automatic collisions retry up to five times.
- Repeated submissions of the same URL create independent short links.
- Build `short_url` from required production configuration `PUBLIC_BASE_URL`, never an untrusted request `Host` header.
- The redirect uses `307` plus `Cache-Control: no-store`, so visits continue reaching the service for counting.

### `short_links` table

- `id UUID PRIMARY KEY`
- `alias VARCHAR(32) NOT NULL UNIQUE`
- `original_url TEXT NOT NULL`
- `is_custom BOOLEAN NOT NULL DEFAULT false`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `click_count BIGINT NOT NULL DEFAULT 0`
- `last_accessed_at TIMESTAMPTZ NULL`

The unique alias constraint supplies the required lookup index. Do not index `original_url`, because URLs are intentionally not deduplicated.

Redirects use one atomic statement equivalent to:

```sql
UPDATE short_links
SET click_count = click_count + 1,
    last_accessed_at = now()
WHERE alias = :alias
RETURNING original_url;
```

## Vertical Implementation Slices

### 1. Bootstrap, `/health`, CI, and First Deployment — 30–40 minutes

- Initialize Git and a minimal `app/` package with the FastAPI application, `/health`, settings, and an application factory only where needed for tests.
- Add `pyproject.toml`, `uv.lock`, and `.python-version` pinned to Python 3.12.13. DigitalOcean currently supports `uv` projects directly through its Python buildpack, so no Dockerfile is needed. [DigitalOcean Python buildpack](https://docs.digitalocean.com/products/app-platform/reference/buildpacks/python/)
- Add the first pytest using FastAPI `TestClient`, plus Ruff lint and format configuration.
- Add one GitHub Actions workflow:
  - On pull requests and pushes: install locked dependencies, run `ruff check`, `ruff format --check`, and pytest.
  - On successful `main` pushes: deploy with `digitalocean/app_action/deploy@v2` using the `DIGITALOCEAN_ACCESS_TOKEN` repository secret. [DigitalOcean GitHub Actions deployment](https://docs.digitalocean.com/products/app-platform/how-to/deploy-from-github-actions/)
- Add `.do/app.yaml` with one Python buildpack service, port 8080, `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, a `/health` health check, one smallest production service instance, and deployment-failure alerts.
- Insert the actual `owner/repository` source identifier before deployment, deploy, then smoke-test `/health`.

Acceptance: local and CI tests pass, and the public DigitalOcean URL returns 200 from `/health`.

### 2. PostgreSQL Foundation and Alembic — 35–40 minutes

- Add SQLAlchemy 2.x, Psycopg 3, session dependency, configuration validation, and the `short_links` model.
- Normalize DigitalOcean’s PostgreSQL URL to SQLAlchemy’s `postgresql+psycopg://` driver form.
- Add a PostgreSQL-only `compose.yaml` for local development and the initial Alembic migration.
- Add `/ready`, with database failures logged and returned as a generic 503.
- Create or select a DigitalOcean Managed PostgreSQL cluster, bind its private URL as `DATABASE_URL`, and add a `PRE_DEPLOY` job running `alembic upgrade head`. DigitalOcean requires an existing cluster name for production database bindings and supports pre-deploy jobs for migrations. [App specification](https://docs.digitalocean.com/products/app-platform/reference/app-spec/)
- Switch the App Platform traffic health check to `/ready` and use `/health` as the liveness check. Use `${database-name.DATABASE_PRIVATE_URL}` when the app and database share a VPC. [Database environment variables](https://docs.digitalocean.com/products/app-platform/how-to/use-environment-variables/)

Acceptance: migrations upgrade an empty PostgreSQL database, `/ready` reflects database availability, and deployment runs migrations before accepting traffic.

### 3. Create Short Links — 30–35 minutes

- Add request/response schemas and `POST /api/v1/links`.
- Add the small pure alias-generation function and collision retry loop; keep persistence directly in the endpoint/helper rather than introducing repository and service class layers.
- Return 201 with the metadata body and a `Location` header pointing to `/api/v1/links/{alias}`.
- Cover automatic aliases, custom aliases, URL and alias validation, duplicate custom aliases, retry behavior, reserved aliases, and repeated long URLs.

Acceptance: valid links persist and return usable short URLs; invalid input returns 422 and occupied custom aliases return 409.

### 4. Retrieve Metadata — 15–20 minutes

- Add `GET /api/v1/links/{alias}` using the indexed alias lookup.
- Return the same stable response schema as creation.
- Return FastAPI’s standard `{"detail":"Short link not found"}` 404 response.

Acceptance: metadata remains consistent with the creation response and unknown aliases return 404.

### 5. Redirect and Analytics — 20–25 minutes

- Register `GET /{alias}` last so named health and API routes retain precedence.
- Use the atomic `UPDATE ... RETURNING` operation to increment `click_count`, set `last_accessed_at`, and fetch the destination in one database round trip.
- Return a 307 redirect with the exact stored URL and `Cache-Control: no-store`.
- Test redirects, query-string preservation in stored destinations, missing aliases, repeated click increments, and timestamp updates.

Acceptance: every request increments the counter exactly once before redirecting.

### 6. Final Production Pass — 20–30 minutes

- Run migrations, Ruff, and the full integration suite against PostgreSQL 17 in CI; also run `alembic check` to catch model/migration drift.
- Add a concise README containing local setup, commands, API examples, environment variables, migration workflow, DigitalOcean/GitHub prerequisites, smoke tests, and teardown guidance.
- Verify API docs, error responses, UTC timestamps, startup with missing configuration, deployment alerts, and a clean deployment from `main`.

## Test Plan

CI uses a PostgreSQL 17 service rather than SQLite to exercise the real dialect. Tests run sequentially and truncate `short_links` between cases.

Required scenarios:

- Health works without a database; readiness succeeds and fails correctly.
- Alembic upgrades an empty database and matches SQLAlchemy metadata.
- Automatic and custom creation return 201 and correct metadata.
- Invalid URL schemes, credentials, length, alias characters, reserved aliases, and alias length return 422.
- Custom alias conflicts return 409; generated collisions retry.
- Duplicate long URLs receive distinct automatic aliases.
- Metadata retrieval returns current counts and handles 404.
- Redirect returns 307 and the exact destination.
- Multiple redirects atomically increment `click_count` and update `last_accessed_at`.
- `short_url` always uses configured `PUBLIC_BASE_URL`.

## Assumptions and Deliberate Limits

- Creation and metadata are public, with no authentication or rate limiting, as requested. Document both as the first hardening additions for an internet-scale public service.
- Basic click count and last-access time are included; individual visit events, IP addresses, and user agents are not stored.
- No link editing, deletion, expiration, custom domains, bulk APIs, or URL deduplication.
- A single managed PostgreSQL cluster is the only stateful component. No Redis/cache is warranted for this scope.
- Begin with one service instance; the design remains horizontally safe because collision handling and click increments are enforced atomically by PostgreSQL.
- The managed database cluster name, GitHub `owner/repository`, DigitalOcean region, and final public base URL are deployment-specific values supplied during setup.
