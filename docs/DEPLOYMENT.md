# TripMate Deployment Guide

This guide is provider-neutral and does not perform a deployment.

## Runtime assumptions

- Linux Python service for the production Gunicorn command.
- HTTPS terminated by the platform or a trusted reverse proxy.
- Persistent storage when retaining the current SQLite database.
- Python 3.13-compatible runtime and dependencies from `requirements.txt`.

## Build and release

```bash
python -m pip install -r requirements.txt
python -m flask --app run:app db upgrade
```

Set at minimum:

```text
TRIPMATE_ENV=production
TRIPMATE_SECRET_KEY=<strong random secret>
DATABASE_URL=<database URI, optional when persistent SQLite is available>
```

Set `DEEPSEEK_API_KEY` only when enabling the Travel Assistant. The normal Web application remains usable without it.

## Start command

```bash
gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --access-logfile - --error-logfile - wsgi:app
```

Gunicorn is the Linux production WSGI process. Windows development continues to use the documented Flask/PowerShell workflow.

## Health and proxy settings

- Configure platform health checks to `GET /health`.
- Leave `TRIPMATE_TRUST_PROXY=false` unless the app is behind exactly one trusted proxy that sets `X-Forwarded-*` headers.
- When that topology is confirmed, set `TRIPMATE_TRUST_PROXY=true`; the app trusts one proxy hop only.

## SQLite persistence

The MVP defaults to `instance/tripmate.db`. On an ephemeral filesystem, that file can disappear during restart or redeployment. Use a persistent volume for a short-lived demo. For a long-running public service, migrate the existing SQLAlchemy/Alembic workflow to a managed PostgreSQL database in a separate, tested change. V1.7 does not perform that migration.

## Release safety

- Run `flask db upgrade` before starting new application workers.
- Never replace migrations with `db.create_all()` in production.
- Never run `seed-demo` in production; the command rejects production mode.
- Keep Secret Keys and DeepSeek credentials in platform environment settings.
- Add platform-level request/rate limits before a broad public launch.
