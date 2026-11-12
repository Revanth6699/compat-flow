# Security baseline — public demo

## Enabled in the current public demo build

- CSV preview is stateless: uploaded content is read for validation and is not written to application storage or the database.
- Persistent catalog import creation returns HTTP 403.
- Import-job status routes are not exposed.
- CSV file size is capped at 5 MB; the complete multipart request body is capped before parsing.
- CSV row count is capped at 10,000.
- Accepted file extension is `.csv`; UTF-8 decoding and CSV structure are validated.
- CORS is restricted to configured frontend origins.
- Production requires a strong `APP_SECRET_KEY`, HTTPS frontend origins, and explicit API hostnames.
- Production API docs are disabled.
- Security response headers and HSTS are enabled in production.

## Not implemented — do not use for real customer data

- User authentication and session management.
- Tenant-level authorization and data isolation.
- Persistent customer catalog storage or background imports.
- Distributed rate limiting / abuse prevention.
- Malware scanning.
- Audit logging, managed backups and tested recovery.
- Formal SAST/DAST and independent security review.

## Public demo operating rules

- Tell visitors to use synthetic or non-confidential test CSVs only.
- Do not enable persistent imports until authentication, tenant authorization and isolation are implemented and tested.
- Configure hosting/CDN-level rate limits for the CSV preview endpoint before broad promotion.
- Keep production secrets out of source control and all `NEXT_PUBLIC_` variables.
