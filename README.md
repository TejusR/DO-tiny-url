# Tiny URL

Tiny URL is a small URL-shortening service built with FastAPI, SQLAlchemy, and PostgreSQL. It
provides a browser interface and JSON API for creating short links, following them, and viewing
basic click analytics.

## Architecture flow

The diagram below maps the request lifecycle and the system's high-level data flow. The FastAPI
application serves both the static browser UI and the API; SQLAlchemy is the only path to
PostgreSQL.

```mermaid
flowchart LR
    User[Browser or API client]
    App[FastAPI application]
    UI[Static HTML, CSS, and JavaScript]
    Validation[Pydantic request validation]
    Alias[Custom alias or random alias generator]
    ORM[SQLAlchemy session]
    DB[(PostgreSQL<br/>short_links)]
    Destination[Original destination URL]

    User -->|GET /| App
    App --> UI
    UI --> User

    User -->|POST /api/v1/links| App
    App --> Validation
    Validation --> Alias
    Alias -->|INSERT link; retry generated collisions| ORM
    ORM --> DB
    DB -->|Stored link metadata| ORM
    ORM -->|201 and short URL| App
    App --> User

    User -->|GET /api/v1/links/:alias| App
    App -->|SELECT metadata| ORM
    ORM --> DB
    DB -->|URL and analytics| ORM
    ORM --> App
    App -->|200 link metadata| User

    User -->|GET /:alias| App
    App -->|Atomic UPDATE count and timestamp<br/>RETURNING original URL| ORM
    ORM --> DB
    DB -->|Original URL| ORM
    ORM --> App
    App -->|307, Cache-Control: no-store| User
    User --> Destination

    User -->|GET /health| App
    User -->|GET /ready| App
    App -->|SELECT 1 for readiness| ORM
    ORM --> DB
```

Key implementation details:

- `POST /api/v1/links` validates an absolute HTTP(S) URL and an optional custom alias. Automatic
  aliases are cryptographically random; uniqueness is enforced by PostgreSQL and collisions are
  retried up to five times.
- `GET /api/v1/links/{alias}` returns the stored destination and analytics without incrementing the
  click count.
- `GET /{alias}` atomically increments `click_count`, updates `last_accessed_at`, and returns a
  non-cacheable `307 Temporary Redirect` to the exact stored URL.
- `GET /health` reports process health. `GET /ready` checks database connectivity.
- Alembic owns the database schema, including the unique constraint on `short_links.alias`.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for Python and dependency management
- Docker with Docker Compose for the local PostgreSQL database

The project targets Python 3.12. The checked-in `uv.lock` and `.python-version` files keep the
development environment reproducible.

## Setup

From the repository root, install the locked application and development dependencies:

```bash
uv sync --locked --all-groups
```

Start PostgreSQL and wait for it to become healthy:

```bash
docker compose up -d postgres
docker compose ps
```

Apply the database migrations:

```bash
uv run alembic upgrade head
```

No environment file is required for local development. These defaults match `compose.yaml`:

| Variable | Local default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://tiny_url:tiny_url@localhost:5432/tiny_url` | PostgreSQL connection string |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Base used when returning short URLs |
| `ENVIRONMENT` | `development` | Runtime environment name |

To override them, create a `.env` file in the repository root. `postgres://` and `postgresql://`
database URLs are automatically normalized to the Psycopg 3 SQLAlchemy driver. In production,
`PUBLIC_BASE_URL` must be set to a non-local absolute HTTP(S) URL.

## Run

Start the development server with reload enabled:

```bash
uv run uvicorn app.main:app --reload
```

Then open [http://localhost:8000](http://localhost:8000). Interactive API documentation is
available at [http://localhost:8000/docs](http://localhost:8000/docs).

Example API usage:

```bash
curl -i http://localhost:8000/api/v1/links \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/docs","custom_alias":"example-docs"}'

curl http://localhost:8000/api/v1/links/example-docs

curl -i http://localhost:8000/example-docs
```

The final command returns a redirect. Add `-L` only when you want `curl` to follow it to the
destination.

## Test

Run the automated test suite:

```bash
uv run pytest
```

The application tests use isolated in-memory databases or test doubles, so the quick suite does
not require the local PostgreSQL container. To run the complete verification used by CI, start
PostgreSQL as described in **Setup**, then run:

```bash
uv run ruff check .
uv run ruff format --check .
uv run alembic upgrade head
uv run alembic check
uv run pytest
```

`alembic check` verifies that the SQLAlchemy models and committed migrations remain consistent.

