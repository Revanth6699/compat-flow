# CompatFlow

CompatFlow is an early-stage supplier catalog workflow product. The repository contains a stateless public demo and a separate authenticated backend development surface. They do not expose the same capabilities.

## Repository implementation status

The backend includes organization authentication and tenant isolation, five catalog record types, shared CSV/XLSX/XLS/JSON/XML parsing and validation, reviewed import commit endpoints, import history/lineage, and one-shot REST API, SFTP and SQL Server connector paths. The authenticated file page currently exposes validation and preview only; file persistence controls are not yet available in that UI.

Connector code has mocked coverage but no REST, SFTP or SQL Server source has been live-verified. SQL Server additionally requires a dedicated SELECT-only login, trusted TLS certificate, Python `pyodbc`, and Microsoft ODBC Driver 18. Do not treat the connectors or multi-source workflow as generally available or production-ready.

The public demo described below remains a separate stateless workflow. It does not expose the full authenticated backend implementation.

## What the public demo does

- Landing page and product workflow overview.
- Downloadable synthetic supplier catalog.
- Upload a non-confidential CSV for validation.
- Checks required columns, required values, malformed rows and duplicate SKUs within the uploaded file.
- Shows validation totals, errors and a preview of up to 10 valid rows.
- Enforces a 5 MB upload limit and a 10,000 data-row limit.

## What the public demo deliberately does not do

- It does not save uploaded CSV files.
- It does not write products to a shared development catalog.
- It does not run persistent import jobs.
- It does not expose import-job status or row-error records.
- It does not provide user accounts, authentication, tenant isolation or production catalog storage.
- It does not publish to Shopify or another storefront.

**Do not upload confidential supplier data, personal information, credentials or production catalog files.** This demo is for product feedback and workflow discovery only.

## Local setup

Requirements: Docker Desktop with Docker Compose.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open:
- Website: http://localhost:3001
- API health: http://localhost:8001/api/v1/health

Stop:

```powershell
docker compose down
```

The public-demo Compose stack runs only the frontend and stateless preview API. PostgreSQL, Redis and the Celery worker are not needed for this demo build.

## Backend tests

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:PYTHONPATH = "."
pytest -q
```

## Deployment

See [docs/DEMO_DEPLOYMENT.md](docs/DEMO_DEPLOYMENT.md). The intended first deployment is:
- Next.js frontend on Vercel, project root directory `frontend`.
- FastAPI preview API on Render Free, using the Dockerfile in `backend`.

Production builds intentionally fail unless the public HTTPS API URL, website URL, monitored contact email and operator/legal name are configured.

## Project status

This is not a production SaaS release. The backend contains authentication, tenant-scoped catalog APIs and persistent import foundations, but production rollout still requires live connector verification, credential-vault and durable sync work, deployment/runtime verification, operational backups, monitoring, abuse-control review, and a formal security review. See [multi-source ingestion status](docs/multi-source-ingestion.md) for the format-by-format boundaries and known limitations.
