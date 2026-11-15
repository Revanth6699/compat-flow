# Public Demo Deployment

This guide describes the preview-only deployment: a Next.js frontend on Vercel and a FastAPI service on Render. The demo validates and previews data; it does not save visitor uploads or catalog records.

## Deployment layout

| Component | Platform | Configuration |
|---|---|---|
| Frontend | Vercel | Next.js; repository root `frontend` |
| API | Render | FastAPI; Dockerfile in `backend` |
| PostgreSQL, Redis, Celery | Not used | Outside the preview-only deployment |

Persistent imports and import-job status endpoints are disabled in this release.

## Before deployment

- [ ] Confirm that local `.env` files are not committed. Commit `.env.example`, not secrets.
- [ ] Review the changes and the branch that will be deployed.
- [ ] Confirm the name of the person or entity operating the service.
- [ ] Configure a real, monitored contact inbox.
- [ ] Configure a grievance inbox before publishing it as a contact address. Do not publish a placeholder.
- [ ] Use synthetic or non-confidential data for testing.

## Deploy the API to Render

1. In Render, select **New → Web Service**.
2. Connect the GitHub repository.
3. Use the following settings:

| Setting | Value |
|---|---|
| Service name | `compatflow-api` |
| Branch | `main` |
| Root directory | `backend` |
| Runtime | Docker |
| Dockerfile path | `./Dockerfile` |
| Instance type | Free |

4. Set the health-check path to `/api/v1/health`.
5. Add these environment variables:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` |
| `APP_SECRET_KEY` | Unique random secret of at least 32 characters |
| `FRONTEND_ORIGIN` | Exact Vercel production origin, such as `https://your-project.vercel.app` |
| `ALLOWED_HOSTS` | Render service hostname, without the scheme |
| `IMPORT_MAX_UPLOAD_BYTES` | `5242880` |

6. Create the service and wait for deployment and the health check.
7. Confirm the public Render hostname.
8. Request `https://<render-host>/api/v1/health`. The response should include `"status":"ok"`.

Render supplies the runtime port. The repository Dockerfile reads it from the `PORT` environment variable.

Do not add PostgreSQL, Redis, a worker, or a persistent disk to this preview-only API.

## Deploy the frontend to Vercel

1. Create a Vercel project from the repository.
2. Set **Root Directory** to `frontend`.
3. Select Next.js and keep the default build and output settings.
4. Add these Production environment variables:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `https://<render-host>` |
| `NEXT_PUBLIC_CONTACT_EMAIL` | Real, monitored contact inbox |
| `NEXT_PUBLIC_OPERATOR_NAME` | Legal name of the person or entity operating the demo |
| `NEXT_PUBLIC_SITE_URL` | Public Vercel HTTPS origin |
| `NEXT_PUBLIC_GRIEVANCE_EMAIL` | Real, monitored grievance inbox; set only after it exists |

Do not add `/api/v1` to `NEXT_PUBLIC_API_BASE_URL`; the frontend appends the API route.

5. Deploy the frontend.
6. Add the final Vercel origin to Render's `FRONTEND_ORIGIN`.
7. Check that `ALLOWED_HOSTS` contains the Render hostname without a scheme.
8. Redeploy the API after changing its environment variables.

## Verify the deployment

- [ ] The homepage and navigation load over HTTPS.
- [ ] `/catalog/import` downloads the sample CSV.
- [ ] The sample CSV validates and returns the expected row preview.
- [ ] Missing required columns produce a validation error.
- [ ] Duplicate SKUs are reported within the uploaded file.
- [ ] Non-CSV files are rejected.
- [ ] Files larger than 5 MB are rejected.
- [ ] `POST /api/v1/catalog/import` returns HTTP 403.
- [ ] `GET /api/v1/catalog/import/{job_id}` returns HTTP 404.
- [ ] API documentation is disabled in production.
- [ ] Browser developer tools show no CORS errors.
- [ ] The application works in a private browser session.
- [ ] The service responds after sleeping and waking.

## Operating the public demo

- Describe the release as a CSV validation demo, not a production catalog-import service.
- State clearly that uploads are not saved and products are not imported.
- Ask visitors to use synthetic or non-confidential files.
- Configure provider- or CDN-level rate limits for `POST /api/v1/catalog/import/preview` before broad promotion.
- Monitor Render instance hours, bandwidth, build usage, and service logs.
- Tell visitors that the free service may sleep after inactivity and that the first request after sleep can take about a minute.
- Check the contact inbox regularly.

## Render Free plan limits

- Free web services spin down after 15 minutes without inbound traffic.
- Waking a sleeping service typically takes about one minute.
- The filesystem is ephemeral. Files may disappear after restarts, redeploys, or spin-down.
- Free services do not support persistent disks.
- Monthly instance-hour and other usage limits apply.

This setup is suitable for testing and collecting product feedback. It does not provide production availability.

## Not included in this release

Before accepting real customer catalog imports, implement and verify:

- Authentication and tenant-level authorization for every operation.
- Tenant isolation for catalog reads and writes.
- Private object storage.
- Upload retention and deletion controls.
- Rate limiting and abuse prevention.
- Audit logging.
- Managed backups and tested recovery.
- Security testing.

Do not re-enable persistent import endpoints until these controls have been verified.