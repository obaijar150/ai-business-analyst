# Northstar · AI Business Analyst

Northstar is a server-rendered Django business analytics workspace. It combines dataset management, an AI Analyst, automated business insights and reports, KPI exploration, and modern SaaS-style screens for analytics workflows.

## Stack

- Python 3.12+
- Django 5.2
- Django REST Framework + Simple JWT
- Pandas, OpenPyXL, xlrd
- PostgreSQL for normal runs
- SQLite for local demo mode
- Plain HTML, CSS, and vanilla JavaScript (no frontend framework)

## Requirements

- Python 3.12+
- PostgreSQL 16+ for normal runs
- Docker Desktop with Docker Compose for the containerized workflow
- Optional API keys for Gemini or OpenAI if you want external LLM planning

## Quick Start (Local Demo)

```sh
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate --settings=config.local_settings
python manage.py runserver --settings=config.local_settings
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Quick Start (PostgreSQL)

```sh
cp .env.example .env
# edit .env with real PostgreSQL credentials
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Run with Docker

```sh
cp .env.example .env
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000). The health endpoint is at [http://localhost:8000/api/health/](http://localhost:8000/api/health/).

## Environment

`.env.example` contains every supported variable:

```env
DEBUG=True
SECRET_KEY=replace-this-with-a-long-random-secret
ALLOWED_HOSTS=localhost,127.0.0.1
POSTGRES_DB=business_analyst
POSTGRES_USER=business_analyst
POSTGRES_PASSWORD=development-password
POSTGRES_HOST=db
POSTGRES_PORT=5432
AI_PROVIDER=local
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
```

`AI_PROVIDER` may be `local`, `gemini`, or `openai`. The default `local` analyst does not need an API key. External providers only plan analyses; Pandas always computes numerical results.

## Authentication

Create an account at `/register/` and log in at `/login/`. The dashboard, datasets, AI Analyst, insights, and reports pages require an authenticated user.

API authentication uses bearer JWTs:

- `POST /api/auth/register/` accepts `username` and `password`.
- `POST /api/auth/login/` accepts `username` and `password`, and returns access and refresh tokens.
- `GET /api/auth/me/` returns the authenticated user.
- `POST /api/auth/logout/` accepts a `refresh` token and blacklists it.
- `POST /api/auth/token/refresh/` accepts a `refresh` token to issue a new access token.

## Datasets and AI Analyst

Upload and manage CSV or Excel datasets at `/datasets/`. Dataset APIs are authenticated and scoped to the signed-in user.

Dataset APIs:

- `POST /api/datasets/` uploads a multipart form with `file` and an optional `name`.
- `GET /api/datasets/` lists the user's datasets.
- `GET /api/datasets/<id>/` returns dataset metadata, statistics, and a preview.
- `DELETE /api/datasets/<id>/` removes a dataset and its stored file.

AI Analyst:

- Page: `/analyst/`
- `POST /api/analyze/` accepts `dataset_id` and `question`.
- The provider returns only an analysis plan. Pandas executes the calculation and returns the real numeric result, explanation, and evidence.
- Chart specifications can be included for bar, line, pie, and scatter charts.
- AI never generates frontend code or arbitrary SQL.

## Business Intelligence and Reports

Insights and reports are generated from real datasets using Pandas.

- `/insights/` shows KPIs, trends, anomalies, recommendations, and charts.
- `/reports/` lets users create, view, and delete business reports.
- `GET /api/insights/?dataset_id=<id>` returns insights.
- `GET /api/reports/` lists reports.
- `POST /api/reports/` creates a report from `dataset_id` and optional `title`.
- `GET /api/reports/<id>/` returns report details.
- `DELETE /api/reports/<id>/` deletes a report.

## Security Notes

- AI never executes arbitrary code or SQL.
- AI plans are validated against the dataset schema before execution.
- Calculations are read-only and dataset-scoped.
- User data is isolated by owner in APIs and templates.
- Secrets must be stored only in `.env`, which is ignored by Git.
- Uploads are limited to CSV/XLSX/XLS and 25 MB.
- Do not enable billing for Gemini if you want to keep using the free tier.

## Tests

```sh
pytest
```

The test suite uses Django's test runner-style Django test client and an in-memory SQLite database. It includes API, AI provider, dataset, security, and analyst tests.

## Production Deployment

For production, use PostgreSQL and a production WSGI server such as Gunicorn behind Nginx or another reverse proxy.

Recommended approach:

```sh
pip install gunicorn
cp .env.example .env
# set DEBUG=False, SECRET_KEY, ALLOWED_HOSTS, PostgreSQL credentials, and optional AI keys
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

Production checklist:

- Set `DEBUG=False`.
- Use a strong random `SECRET_KEY`.
- Set `ALLOWED_HOSTS` to the production domain.
- Use a managed PostgreSQL database.
- Serve static files through Nginx or `collectstatic` plus WhiteNoise.
- Run migrations before starting.
- Do not expose the Django development server publicly.
- Keep `.env` out of version control.

## Project Structure

```text
config/                 Django settings and URL configuration
dashboard/              Dashboard pages, APIs, AI providers, insights, reports
dashboard/ai/providers/ Swappable analysis provider layer
dashboard/static/       CSS and vanilla JavaScript
templates/dashboard/   Server-rendered pages
Dockerfile
docker-compose.yml
README.md
```
