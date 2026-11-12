# Public demo deployment guide

## Deployment architecture

- **Frontend:** Vercel (Next.js), repository root directory `frontend`.
- **API:** Render Free Web Service (FastAPI), Dockerfile in `backend`.
- **Database / Redis / Celery:** Not required for this preview-only release.

This deployment is deliberately limited to CSV validation and preview. It does not persist visitor files or catalog records. Persistent imports and job-status endpoints are disabled.

## 0. Before deployment

1. Make sure `.env` is not committed. Commit `.env.example`, not `.env`.
2. Push the reviewed source changes to the existing GitHub repository.
3. Confirm the real operator/legal name and a monitored contact email.
4. Do not use production supplier files for testing.

## 1. Deploy the API to Render

1. Sign in to Render and choose **New > Web Service**.
2. Connect your GitHub account and select the CompatFlow repository.
3. Configure the service:

| Setting | Value |
|---|---|
| Name | compatflow-api |
| Branch | main |
| Root Directory | `backend` |
| Runtime | Docker |
| Dockerfile Path | `./Dockerfile` |
| Instance Type | Free |

4. Under Advanced settings, set the health check path to:

`/api/v1/health`

5. Add these environment variables:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` |
| `APP_SECRET_KEY` | A unique randomly generated secret of at least 32 characters |
| `FRONTEND_ORIGIN` | Your exact Vercel production origin, e.g. `https://your-project.vercel.app` |
| `ALLOWED_HOSTS` | Your Render service hostname only, without `https://`, e.g. `compatflow-api.onrender.com` |
| `IMPORT_MAX_UPLOAD_BYTES` | `5242880` |

6. Create the Web Service and wait for its first deployment and health check.
7. Generate or confirm the service's public `onrender.com` URL.
8. Test `https://YOUR-RENDER-HOST/api/v1/health`. Expected response includes `"status":"ok"`.

Render supplies the runtime port. The existing Dockerfile uses the `PORT` environment variable.

Do not add a database, Redis, worker or persistent disk for this preview-only API.

## 2. Deploy the frontend to Vercel

1. Create a Vercel project from the same GitHub repository.
2. Set **Root Directory** to `frontend`.
3. Framework preset: Next.js. Leave build and output settings at their defaults.
4. Set these environment variables for Production:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `https://YOUR-RENDER-HOST` |
| `NEXT_PUBLIC_CONTACT_EMAIL` | A real monitored email inbox |
| `NEXT_PUBLIC_OPERATOR_NAME` | The legal name of the person or entity operating the demo |
| `NEXT_PUBLIC_SITE_URL` | Your public Vercel HTTPS website origin |

Do not append `/api/v1` to `NEXT_PUBLIC_API_BASE_URL`. The frontend appends the API route itself.

5. Deploy the frontend.
6. Copy the final Vercel production origin and update Render's `FRONTEND_ORIGIN` to that exact origin.
7. Confirm `ALLOWED_HOSTS` contains the Render hostname, without a scheme.
8. Redeploy the Render API after changing its environment variables.

## 3. Verify before sharing the URL

- Homepage and navigation load over HTTPS.
- `/catalog/import` downloads the sample CSV.
- Sample CSV validates and returns the expected row preview.
- A CSV with missing required columns returns a validation error.
- A CSV with duplicate SKUs reports duplicates within the uploaded file.
- A non-CSV file is rejected.
- A file larger than 5 MB is rejected.
- `POST /api/v1/catalog/import` returns HTTP 403.
- `GET /api/v1/catalog/import/{job_id}` returns HTTP 404.
- API docs are disabled in production.
- Browser developer tools show no CORS errors.
- Test from a private/incognito browser session.
- Test again after the Render service has spun down and woken up.

## 4. Public-demo operating rules

- Promote this as a CSV validation demo, not a production catalog import platform.
- State clearly that uploads are not saved and no products are imported.
- Ask visitors to use synthetic or non-confidential test files only.
- Configure provider/CDN-level request rate limits for `POST /api/v1/catalog/import/preview` before broad promotion.
- Monitor Render instance hours, bandwidth, build usage and service logs.
- Explain that the free service may sleep after inactivity and the first request may be slow.
- Keep a monitored contact inbox and review incoming feedback.

## 5. Render Free limitations

- Free web services spin down after 15 minutes without inbound traffic.
- Waking a sleeping service typically takes about one minute.
- The filesystem is ephemeral. Files written by the service can disappear after restarts, redeploys or spin-down.
- Free services do not support persistent disks.
- Free instance hours and other monthly usage limits apply.

This plan is intended for testing and product feedback, not production availability.

## 6. Not included in this release

Real customer catalog imports require, at minimum, authentication, tenant-level authorization on every operation, per-tenant catalog isolation, private object storage, upload retention/deletion controls, rate limiting, audit logging, backups and security testing.

Do not re-enable persistent import endpoints until these are implemented and verified.
