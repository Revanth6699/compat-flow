# CompatFlow

CompatFlow is a supplier-catalog workflow application. It provides tools for validating product data, mapping supplier fields to a shared catalog structure, and reviewing imports from files and external sources.

This repository contains both a public demo and authenticated workflows. They have different capabilities and release boundaries; code being present does not mean a feature is enabled in a deployed environment.

## What the public demo does

The public demo provides stateless CSV validation.

- Download a sample supplier catalog.
- Upload a non-confidential CSV file.
- Check required fields, malformed rows, missing values, and duplicate SKUs within the file.
- Review validation results and a preview of up to 10 valid rows.
- Uploads are limited to 5 MB and 10,000 data rows.

The public demo does not save uploaded files, create persistent import jobs, write to a shared catalog, or publish products to a storefront.

**Use synthetic or non-confidential test data.** Do not upload customer information, personal data, credentials, confidential supplier records, or production catalog files.

## Other workflows in the repository

The backend also contains authenticated workflows for multi-format file ingestion, catalog records, AI-assisted field mapping, and supplier-source connectors.

Their availability depends on authentication, organization permissions, subscription entitlements, provider configuration, and deployment settings. The current file-upload interface supports validation and preview; it does not expose the backend file-commit endpoint. REST, SFTP, and SQL Server connectors have not been verified against live supplier systems.

See [Multi-source ingestion](docs/multi-source-ingestion.md) for the exact status and limits of each input type.

## Technology

| Area | Technology | Use |
|---|---|---|
| Web application | Next.js | Pages and user workflows |
| API | FastAPI | Validation, mapping, catalog, and connector endpoints |
| Authentication | Supabase Auth | User identity and email verification |
| Application data | PostgreSQL | Organizations, catalog records, and import history |
| Background work and rate limits | Redis | Queue infrastructure and distributed connector limits |
| Billing | Razorpay | Subscription billing, subject to account setup |

Provider configuration, deployed versions, and service availability must be checked in the target environment.

## Run the public demo locally

### Requirements

- Docker Desktop
- Docker Compose

### Start the application

From the repository root:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open the following addresses:

| Service | Address |
|---|---|
| Web application | http://localhost:3001 |
| API health check | http://localhost:8001/api/v1/health |

Stop the containers:

```powershell
docker compose down
```

This Compose configuration starts the frontend and the stateless preview API. PostgreSQL, Redis, and Celery are not required for the public demo.

## Run backend tests

The commands below use Python 3.12 on Windows PowerShell:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:PYTHONPATH = "."
pytest -q
```

Run frontend checks from the `frontend` directory using the scripts defined in `package.json`.

## Repository layout

```text
.
├── backend/       FastAPI application, migrations, and operations guides
├── docs/          Product, data model, ingestion, security, and deployment notes
├── frontend/      Next.js application
├── supabase/      Supabase configuration and migrations
├── README.md
└── docker-compose.yml
```

## Documentation

| Document | Description |
|---|---|
| [Product scope](docs/PRODUCT_SCOPE.md) | Intended users, workflows, and current exclusions |
| [Multi-source ingestion](docs/multi-source-ingestion.md) | File formats, connectors, limits, and verification status |
| [Catalog record model](docs/catalog-record-model.md) | Products, variants, offers, inventory, and identifiers |
| [AI-assisted mapping](docs/column-mapping-ai-design.md) | Mapping request contract, evaluation, and safeguards |
| [Dataset audit](docs/column-mapping-dataset-audit.md) | Benchmark source, preparation, and limitations |
| [Industry-aware validation](docs/industry-aware-catalog-validation.md) | Industry profiles, field mapping, and validation rules |
| [Demo deployment](docs/DEMO_DEPLOYMENT.md) | Deployment steps for the public demo |
| [Security](docs/SECURITY.md) | Security controls and known gaps |
| [Backend operations](backend/OPERATIONS.md) | Authentication, connectors, migrations, and deletion procedures |
| [Authentication](backend/docs/authentication.md) | Signup, invitations, and organization access |
| [Razorpay setup](backend/RAZORPAY_SETUP.md) | Subscription and webhook configuration |

## Release and deployment limits

Do not describe CompatFlow as a production-ready catalog-import service based only on this repository. Before enabling a workflow for customers, verify its deployed configuration, organization-level access controls, provider credentials, database migrations, backups, monitoring, rate limits, and failure handling.

A connector that passes mocked tests has not been proven against a live supplier. A backend endpoint that can commit records is not necessarily exposed in the user interface. Keep product descriptions aligned with what is deployed and verified.
