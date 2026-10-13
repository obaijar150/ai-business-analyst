# Northstar · AI Business Analyst foundation

A server-rendered Django application for a business analysis workspace. It includes a responsive dashboard, PostgreSQL configuration, Django REST Framework APIs, CSV and Excel dataset management, and an AI Analyst that plans analyses with Gemini and computes results locally with Pandas.

## Requirements

- Docker Desktop with Docker Compose, or Python 3.12+ and PostgreSQL 16

## Run with Docker

```sh
cp .env.example .env
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000). The health endpoint is at [http://localhost:8000/api/health/](http://localhost:8000/api/health/).

## Authentication

Create an account at `/register/` and log in at `/login/`. The dashboard requires a signed-in user; sign out with the button in the sidebar.

API authentication uses bearer JWTs:

- `POST /api/auth/register/` accepts `username` and `password`.
- `POST /api/auth/login/` accepts `username` and `password`, and returns access and refresh tokens.
- `GET /api/auth/me/` returns the authenticated user. Send the access token as `Authorization: Bearer <access-token>`.
- `POST /api/auth/logout/` accepts a `refresh` token and blacklists it. Send a valid access token with the request.
- `POST /api/auth/token/refresh/` accepts a `refresh` token to issue a new access token.

## Datasets and AI Analyst

Upload and manage CSV or Excel datasets at `/datasets/`. Dataset APIs are authenticated and scoped to the signed-in user:

- `POST /api/datasets/` uploads a multipart form with `file` and an optional `name`.
- `GET /api/datasets/` lists the user's datasets.
- `GET /api/datasets/<id>/` returns dataset metadata, statistics, and a preview.
- `DELETE /api/datasets/<id>/` removes a dataset and its stored file.

Ask questions at `/analyst/` or call `POST /api/analyze/` with `dataset_id` and `question`. By default, Northstar uses a built-in local analyst (`AI_PROVIDER=local`) that maps common questions to supported Pandas calculations without an API key. Optional LLM providers can be enabled by setting `AI_PROVIDER=gemini` with `GEMINI_API_KEY`, or `AI_PROVIDER=openai` with `OPENAI_API_KEY`. In every case the provider only selects columns and an allowed operation; Pandas computes the returned numerical results from the stored dataset.

## Run locally

For a local demo without Docker or PostgreSQL, create a virtual environment, install `requirements.txt`, copy `.env.example` to `.env`, then run:

```sh
python manage.py migrate --settings=config.local_settings
python manage.py runserver --settings=config.local_settings
```

The default settings and Docker Compose configuration use PostgreSQL.

## Tests

```sh
pytest
```

The test suite uses Django's test client and an in-memory SQLite database, so it can run without a PostgreSQL service. PostgreSQL remains the application's configured runtime database.

## Structure

```text
config/                 Django settings and URL configuration
dashboard/              Dashboard page, health API, and static assets
templates/dashboard/    Server-rendered dashboard
Dockerfile
docker-compose.yml
requirements.txt
```
