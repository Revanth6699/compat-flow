# CompatFlow

CompatFlow is a supplier-catalog workflow project. It provides file parsing, catalog mapping and validation, and connector workflows. The repository contains a public demo path and additional authenticated backend capabilities that are still subject to rollout and verification.

## Current release boundary

The public demo is a stateless CSV validation experience.

**Available in the public demo**
- Download a synthetic supplier catalog.
- Upload a non-confidential CSV for validation.
- Check required columns and values, malformed rows, and duplicate SKUs within the uploaded file.
- Review validation totals, errors, and a preview of up to 10 valid rows.
- Enforce a 5 MB upload limit and a 10,000 data-row limit.

**Not available in the public demo**
- Persistent file or catalog storage.
- Persistent import jobs or import-job status.
- Shared development-catalog writes.
- Storefront publishing.
- Production supplier-data processing.

The repository also contains authenticated multi-format ingestion and connector code. These paths have separate API, authorization, plan, and rollout boundaries. Their presence in the repository does not mean every format or supplier connector is generally available or live-verified. See [Multi-source ingestion](docs/multi-source-ingestion.md).

> **Data handling:** Do not submit confidential supplier data, personal information, credentials, or production catalog files to the public demo. Use synthetic or otherwise non-confidential test data.

## Architecture

| Component | Technology | Responsibility |
|---|---|---|
| Frontend | Next.js | Web application and user workflows |
| API | FastAPI | Validation, mapping, catalog and connector endpoints |
| Identity | Supabase Auth | Authentication and email verification |
| Application database | PostgreSQL | Organization and catalog records |
| Queue / rate limiting | Redis | Background-work infrastructure and connector rate limiting |
| Billing | Razorpay | Subscription billing, subject to account configuration |

Actual deployment configuration and provider settings must be verified independently.

## Local development

### Requirements

- Docker Desktop
- Docker Compose

### Start the public demo stack

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open:
- Frontend: http://localhost:3001
- API health: http://localhost:8001/api/v1/health

Stop:

```powershell
docker compose down
```

The public-demo Compose stack runs the frontend and stateless preview API. PostgreSQL, Redis, and Celery are not required for this demo configuration.

### Run backend tests

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:PYTHONPATH = "."
pytest -q
```

## Documentation

| Document | Contents |
|---|---|
| [Product scope](docs/PRODUCT_SCOPE.md) | Product purpose, workflow, and exclusions |
| [Multi-source ingestion](docs/multi-source-ingestion.md) | File formats, connectors, limits, and implementation boundaries |
| [Catalog record model](docs/catalog-record-model.md) | Products, identifiers, variants, offers, and inventory |
| [AI-assisted mapping](docs/column-mapping-ai-design.md) | AI mapping contract, consent, evaluation, and limitations |
| [Demo deployment](docs/DEMO_DEPLOYMENT.md) | Public demo deployment and verification |
| [Security baseline](docs/SECURITY.md) | Current demo controls and known gaps |
| [Backend operations](backend/OPERATIONS.md) | Runtime configuration and operational procedures |
| [Authentication](backend/docs/authentication.md) | Supabase Auth, onboarding, invitations, and tenant permissions |
| [Razorpay setup](backend/RAZORPAY_SETUP.md) | Subscription and webhook configuration |
| [DPDP implementation status](DPDP_PROGRESS.md) | India privacy audit, decisions, and open work |
| [Breach response runbook](BREACH_RUNBOOK.md) | Incident response steps and notification templates |

## Project status

This repository is not evidence of a production-ready SaaS release or legal compliance certification. Before production use, verify authentication and tenant isolation for every route, persistent import controls, provider configuration, backups and recovery, monitoring, abuse prevention, security testing, privacy operations, and legal documentation.

See the linked scope, security, deployment, and DPDP documents for specific implementation status. Do not infer readiness from the existence of code or documentation.
