# TripMate Deployment Guide

This guide prepares a Railway deployment but does not create or deploy a service.

## Runtime assumptions

- Linux Python service for the production Gunicorn command.
- HTTPS terminated by the platform or a trusted reverse proxy.
- Managed PostgreSQL for Railway; local development continues to default to SQLite.
- Python 3.13-compatible runtime and dependencies from `requirements.txt`.

## Build and release

```bash
python -m pip install -r requirements.txt
python -m flask --app run:app db upgrade
```

`railway.json` runs the migration command as a pre-deploy step. It never seeds data.

## Railway variables

For a complete portfolio demo, configure these names in the Railway Web Service:

```text
TRIPMATE_ENV=demo
SECRET_KEY=<set a strong secret in Railway>
DATABASE_URL=${{Postgres.DATABASE_URL}}
DEEPSEEK_API_KEY=<set only in Railway>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
TRIPMATE_TRUST_PROXY=true
```

`Postgres` is an example service name. Adjust the reference to match the PostgreSQL service in the same Railway project. Do not paste or commit its generated credentials. `TRIPMATE_SECRET_KEY` may be used instead of the generic `SECRET_KEY`.

Use `TRIPMATE_ENV=production` for a non-demo production service. The Agent variables are optional when the Travel Assistant is intentionally disabled; the normal Web application and `/health` remain available without them. Railway variables override local files, and `demo`/`production` never load `.env`.

## Start command

```bash
gunicorn --bind 0.0.0.0:$PORT --workers 2 wsgi:app
```

Gunicorn is the Linux production WSGI process. Windows development continues to use the documented Flask/PowerShell workflow.

## Health and proxy settings

- Configure platform health checks to `GET /health`.
- Leave `TRIPMATE_TRUST_PROXY=false` unless the app is behind exactly one trusted proxy that sets `X-Forwarded-*` headers.
- When that topology is confirmed, set `TRIPMATE_TRUST_PROXY=true`; the app trusts one proxy hop only.

## PostgreSQL and migrations

`DATABASE_URL` accepts Railway's `postgresql://` form and is normalized to SQLAlchemy's installed psycopg 3 dialect. `python -m flask --app run:app db upgrade` must build an empty database through the complete Alembic history. Application startup never calls `db.create_all()` or `stamp`.

No local PostgreSQL server is installed by this repository. Before a public release, verify the migration history against a disposable PostgreSQL service; never point migration tests at user data.

## Portfolio demo data

`demo` inherits all production security flags and requires a real environment Secret Key. It differs only by allowing an administrator to run the following command explicitly once after migrations:

```bash
python -m flask --app run:app seed-demo
```

The command is not part of `railway.json`, Gunicorn startup or application startup. It refuses to run when `TRIPMATE_ENV=production` and refuses to overwrite a database that already contains users.

## Release safety

- Run `flask db upgrade` before starting new application workers.
- Never replace migrations with `db.create_all()` in production.
- Never run `seed-demo` in production; use `demo` only for an intentional portfolio dataset.
- Keep Secret Keys and DeepSeek credentials in platform environment settings.
- Add platform-level request/rate limits before a broad public launch.
