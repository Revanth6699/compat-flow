# Security Baseline

**Scope:** Current public demo build  
**Status:** Source-level summary; not an independent security assessment

## Controls present in the public demo

- CSV preview is stateless. Uploaded content is read for validation and is not written to application storage or the database.
- Persistent catalog import creation returns HTTP 403.
- Import-job status routes are not exposed.
- CSV uploads are limited to 5 MB.
- The complete multipart request body is bounded before parsing.
- CSV data is limited to 10,000 rows.
- Only the `.csv` extension is accepted by the public preview route.
- UTF-8 decoding and CSV structure are validated.
- CORS is restricted to configured frontend origins.
- Production configuration requires a strong `APP_SECRET_KEY`, HTTPS frontend origins, and explicit API hostnames.
- Production API documentation is disabled.
- Production security response headers and HSTS are enabled.

These controls describe the public demo path. They must not be assumed to apply identically to every authenticated backend route or deployment.

## Not implemented or not verified for production use

- Independent security review and formal penetration testing.
- Complete distributed rate limiting and abuse monitoring for every public route.
- Malware scanning for uploaded files.
- Verified backup and recovery procedures.
- Complete security audit logging and alerting.
- Production supplier-data retention and deletion controls.
- Live verification of deployed TLS, headers, provider settings, and infrastructure encryption.

Authentication and tenant-scoped backend features exist in the repository, but each route and deployment must be reviewed and tested before production use.

## Operating rules

- Use synthetic or non-confidential test files in the public demo.
- Do not enable persistent imports until authentication, tenant authorization, and tenant isolation are verified for every relevant operation.
- Configure hosting or CDN-level rate limits for the public CSV preview endpoint before broad promotion.
- Keep secrets out of source control and browser-exposed `NEXT_PUBLIC_*` variables.
- Do not treat a successful build or unit test as proof of production security.
- Record unresolved findings and owners before enabling customer data processing.
