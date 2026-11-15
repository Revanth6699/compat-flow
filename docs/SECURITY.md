# Security

**Scope:** Public demo  
**Evidence:** Source-code review. This is not an independent security assessment.

## Controls in the public demo

- CSV preview is stateless. The preview route reads the upload for validation and does not save it to application storage or the database.
- Persistent catalog-import creation returns HTTP 403.
- Import-job status routes are not exposed.
- CSV uploads are limited to 5 MB and 10,000 data rows.
- The complete multipart request body is bounded before parsing.
- The public preview route accepts only files with the `.csv` extension.
- UTF-8 decoding and CSV structure are checked.
- CORS is limited to configured frontend origins.
- Production configuration requires a strong `APP_SECRET_KEY`, HTTPS frontend origins, and explicit API hostnames.
- API documentation is disabled in production.
- Production security response headers and HSTS are enabled.

These points describe the public demo path. They do not establish that every authenticated route or deployed service has the same controls.

## Not yet verified for production

- Independent security review and penetration testing.
- Consistent rate limiting and abuse monitoring across all public routes.
- Malware scanning for uploaded files.
- Backup restoration and disaster-recovery procedures.
- Complete security audit logs and alerting.
- Retention and deletion controls for production supplier data.
- Deployed TLS, response headers, provider settings, and infrastructure encryption.

The repository includes authentication and tenant-scoped backend features. Their presence is not proof that every route enforces the correct permissions or that the deployed environment is configured safely.

## Operating requirements

- Use synthetic or non-confidential files in the public demo.
- Do not enable persistent imports until authentication, tenant authorization, and tenant isolation have been tested for every relevant operation.
- Configure hosting- or CDN-level rate limits for the public CSV preview endpoint before broad promotion.
- Keep credentials out of source control and browser-exposed `NEXT_PUBLIC_*` variables.
- Treat passing builds and unit tests as necessary checks, not as proof of production security.
- Record each unresolved finding, its owner, and the condition for closure before accepting customer data.