# CompatFlow

CompatFlow is an early-stage supplier catalog workflow product. This repository currently contains a **public demo build** focused on CSV structure and row validation.

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

This is not a production SaaS release. Authentication, tenant isolation, persistent import execution, supplier-specific catalog reconciliation, backups, monitoring, abuse controls and a formal security review are not implemented in this demo build.
