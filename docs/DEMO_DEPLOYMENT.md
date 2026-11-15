# Public Demo Deployment

## 1. Deployment architecture

| Component | Platform | Configuration |
|---|---|---|
| Frontend | Vercel (Next.js) | Repository root: `frontend` |
| API | Render (FastAPI) | Dockerfile in `backend` |
| Database, Redis, Celery | Not required | Not part of the preview-only release |

This deployment is limited to CSV validation and preview. It does not persist visitor files or catalog records. Persistent imports and job-status endpoints are disabled.

## 2. Pre-deployment checklist

- [ ] Confirm `.env` is not committed. Commit `.env.example`, not local secrets.
- [ ] Review the source changes and target branch.
- [ ] Confirm the operator's legal name.
- [ ] Configure a real, monitored contact inbox.
- [ ] Configure a grievance inbox before publishing a grievance contact; do not use a placeholder as a live address.
- [ ] Use synthetic or non-confidential data for testing.

## 3. Deploy the API to Render

1. In Render, select **New → Web Service**.
2. Connect the GitHub repository.
3. Configure:

| Setting | Value |
|---|---|
| Name | `compatflow-api` |
| Branch | `main` |
| Root directory | `backend` |
| Runtime | Docker |
| Dockerfile path | `./Dockerfile` |
| Instance type | Free |

4. Set the health check path to `/api/v1/health`.
5. Configure:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` |
| `APP_SECRET_KEY` | Unique random secret of at least 32 characters |
| `FRONTEND_ORIGIN` | Exact Vercel production origin, e.g. `https://your-project.vercel.app` |
| `ALLOWED_HOSTS` | Render service hostname only, without scheme |
| `IMPORT_MAX_UPLOAD_BYTES` | `5242880` |

6. Create the service and wait for deployment and health check.
7. Confirm the public Render hostname.
8. Test `https://<render-host>/api/v1/health`. The response should include `"status":"ok"`.

Render supplies the runtime port. The repository Dockerfile uses the `PORT` environment variable.

Do not add a database, Redis, worker, or persistent disk for this preview-only API.

## 4. Deploy the frontend to Vercel

1. Create a Vercel project from the repository.
2. Set **Root Directory** to `frontend`.
3. Select Next.js and retain the default build/output settings.
4. Configure Production environment variables:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `https://<render-host>` |
| `NEXT_PUBLIC_CONTACT_EMAIL` | Real monitored contact inbox |
| `NEXT_PUBLIC_OPERATOR_NAME` | Legal name of the person or entity operating the demo |
| `NEXT_PUBLIC_SITE_URL` | Public Vercel HTTPS origin |
| `NEXT_PUBLIC_GRIEVANCE_EMAIL` | Real monitored grievance inbox; configure only after it exists |

Do not append `/api/v1` to `NEXT_PUBLIC_API_BASE_URL`; the frontend appends the API route.

5. Deploy the frontend.
6. Copy the final Vercel origin into Render's `FRONTEND_ORIGIN`.
7. Confirm `ALLOWED_HOSTS` contains the Render hostname without a scheme.
8. Redeploy the API after changing its environment variables.

## 5. Verification before sharing

- [ ] Homepage and navigation load over HTTPS.
- [ ] `/catalog/import` downloads the sample CSV.
- [ ] Sample CSV validates and returns the expected row preview.
- [ ] Missing required columns produce a validation error.
- [ ] Duplicate SKUs are reported within the uploaded file.
- [ ] Non-CSV files are rejected.
- [ ] Files larger than 5 MB are rejected.
- [ ] `POST /api/v1/catalog/import` returns HTTP 403.
- [ ] `GET /api/v1/catalog/import/{job_id}` returns HTTP 404.
- [ ] API documentation is disabled in production.
- [ ] Browser developer tools show no CORS errors.
- [ ] A private/incognito browser session works.
- [ ] The service works after sleeping and waking.

## 6. Public demo operating rules

- Describe the release as a CSV validation demo, not a production catalog-import platform.
- State that uploads are not saved and products are not imported.
- Ask visitors to use synthetic or non-confidential test files only.
- Configure provider/CDN-level rate limits for `POST /api/v1/catalog/import/preview` before broad promotion.
- Monitor Render instance hours, bandwidth, build usage, and service logs.
- Disclose that the free service may sleep after inactivity and that the first request may be slow.
- Monitor the contact inbox.

## 7. Render Free limitations

- Free web services spin down after 15 minutes without inbound traffic.
- Waking a sleeping service typically takes about one minute.
- The filesystem is ephemeral; files can disappear after restarts, redeploys, or spin-down.
- Free services do not support persistent disks.
- Monthly instance-hour and other usage limits apply.

This plan is intended for testing and product feedback, not production availability.

## 8. Excluded from this release

Real customer catalog imports require, at minimum:
- Authentication and tenant-level authorization on every operation.
- Verified per-tenant catalog isolation.
- Private object storage.
- Upload retention and deletion controls.
- Rate limiting and abuse prevention.
- Audit logging.
- Managed backups and tested recovery.
- Security testing.

Do not re-enable persistent import endpoints until these controls are implemented and verified.
