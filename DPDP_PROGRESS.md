# DPDP Act (India) implementation progress

**Branch:** `compliance/dpdp`  
**Baseline:** `feature/organization-first-onboarding` at `658df92df407d628d757225f6c0ac6fb22603f65`  
**Status:** Implementation draft; not legal certification. Legal copy is marked for counsel review.

## Decisions recorded

1. Work is isolated on `compliance/dpdp`, based on the latest organization-onboarding code branch so current signup, tenant and catalog workflows are present. Do not merge or deploy without review.
2. Consent is stored as append-only purpose-specific events. Earlier choices are not overwritten. Current purposes: service-processing acknowledgement, optional product updates and per-action AI mapping.
3. AI mapping remains a separate per-action opt-in. It is not bundled into signup consent.
4. Essential authentication/security browser storage remains active. Optional analytics and marketing preferences default off. No non-essential tracker was configured in the reviewed frontend; the consent-change event is a future integration gate, not proof that a tracker vendor is connected.
5. Privacy request submission creates an intake record only. Identity verification, fulfilment, escalation, notification and statutory response tracking are not automated.
6. Do not invent retention periods, legal entity name, formal Grievance Officer identity or provider contract terms. These remain legal/operations decisions.
7. Do not claim DPDP certification or that legal copy is final. Obtain Indian privacy counsel review.

## Data inventory observed in source

| Data category | Collection / processing point | Purpose | Storage / recipient evidence |
|---|---|---|---|
| Account identity | Signup, sign-in, password recovery, Supabase Auth | Authentication and account access | Supabase Auth; app profile in Render PostgreSQL |
| Profile | Signup metadata: name, organization, job title, optional phone/site, industry, team size | Workspace setup and organization administration | Supabase Auth user metadata; organization/profile data in app DB |
| Organization/access | Organization creation, invitations, roles | Tenant access and administration | Render PostgreSQL |
| Contact/demo | Contact API and demo request endpoint | Respond to enquiries and review demo access | Supabase `contact_requests`; demo requests in Render PostgreSQL |
| Reviews | Authenticated review form | Public feedback | Render PostgreSQL; display name/comment may be public |
| Billing | Billing routes and webhook handlers | Subscription/payment processing | Razorpay plus local payment/subscription/webhook records |
| Supplier/catalog | File imports and connector preview/commit | Validation, mapping and catalog operations | Render PostgreSQL and configured import storage; customer supplier systems accessed with submitted connector credentials |
| AI mapping | `/catalog/import/suggest-mappings` | Optional mapping suggestions | Operator-configured OpenAI-compatible HTTPS endpoint receives headers and up to five bounded sample values per header after explicit per-action opt-in |
| Technical metadata | Hosting/API/database/auth provider logs | Delivery, reliability and security | Vercel, Render, Supabase and configured infrastructure; exact log fields/retention require provider verification |

## Third-party services identified in code

- Supabase Auth and Supabase REST storage for contact submissions.
- Vercel for frontend hosting/build delivery (verify actual project configuration).
- Render for backend hosting and PostgreSQL (verify actual service/database configuration).
- Razorpay for payment and subscription processing.
- Operator-configured OpenAI-compatible AI endpoint for optional mapping; exact vendor/model must be confirmed from deployment environment.
- Supplier APIs, SFTP and SQL Server endpoints are customer-selected data sources; customers must ensure authority to connect and submit data.

## Implemented in this branch

- Draft Privacy Notice expanded with data categories, purposes, provider categories, retention caveats, rights, security caveats and grievance contact.
- Draft data-protection clause added to Terms.
- Purpose-specific consent-event model and Alembic migration added.
- Public consent endpoint records separate service-processing and product-update choices.
- Authenticated consent history and withdrawal endpoints added for optional product updates/AI mapping.
- AI mapping action records a per-action consent event and retains the existing opt-in gate.
- Unticked required service-processing acknowledgement and unticked optional product-updates checkbox added to signup and contact/demo form.
- Contact API requires submitted privacy choices and records them before storing an enquiry.
- Cookie banner supports essential/analytics/marketing categories; optional categories default off and preferences dispatch a consent-change event.
- No analytics or marketing tracker is currently loaded by the inspected app; future tracker code must not initialize until affirmative consent.
- Data-rights request intake page/API added for access, correction, erasure, consent withdrawal and grievance.
- Grievance contact link added to footer and Privacy Notice.
- `BREACH_RUNBOOK.md` added with escalation steps and Board/Data Principal notification templates.

## Security observations / gaps

- **CAPTCHA:** No verified CAPTCHA integration found in the reviewed contact flow; a honeypot is present but is not equivalent to verified bot protection.
- **Encryption at rest:** Import file storage writes bytes to the configured storage directory. Application-level file encryption was not identified in the reviewed path. Verify Render disk encryption, database encryption, backups, access controls and key management. This review did not establish a fail-open encryption control; do not claim one was proven.
- **HTTPS:** Production frontend build configuration requires HTTPS website/API URLs; backend production configuration validates HTTPS frontend origins and emits HSTS. Source review does not prove deployed certificates, redirects, all custom domains or third-party endpoints are correctly configured. Verify live TLS settings.
- **Privacy requests:** Intake records are not yet routed to a monitored mailbox/dashboard; no automated identity verification or fulfilment workflow exists.
- **Consent proof:** Events store supplied email, purpose, choice, notice version, source and timestamp. Public intake does not independently verify control of the supplied email; stronger proof may be required.
- **Rate limiting/abuse:** New public privacy endpoints need rate limiting, abuse monitoring and bot controls.
- **Retention:** No complete category-specific retention schedule or automatic deletion jobs were confirmed.
- **Provider governance:** DPA/subprocessor lists, data locations, cross-border safeguards and provider retention settings must be checked against contracts and account settings.
- **Contact inbox:** Confirm `NEXT_PUBLIC_CONTACT_EMAIL` and `NEXT_PUBLIC_GRIEVANCE_EMAIL` resolve to monitored inboxes. Fallback is a placeholder, not verified contact.
- **Legal entity:** Confirm operator legal name/address and formal Grievance Officer details.

## Required lawyer review

1. Applicability and commencement/transition of each DPDP Act/Rules obligation for this operator and processing.
2. Whether required service-processing acknowledgement and each purpose are legally appropriate; avoid bundled/coerced consent where another lawful basis applies.
3. Final notice contents, data-fiduciary identity, notice delivery/withdrawal requirements and children/guardian applicability.
4. Retention schedule, deletion exceptions, backups, audit logs and legal holds.
5. Grievance Officer appointment, contact publication and response process.
6. Customer/fiduciary and processor roles, DPA and contractual allocation.
7. International processing, provider contracts and transfer restrictions.
8. Breach assessment and notification duties, current Board formats/timelines and any additional CERT-In/sectoral obligations.

## Open implementation and operational items

- Add rate limiting and verified CAPTCHA/alternative bot controls to public forms and privacy endpoints.
- Add email notification and authenticated, audited admin queue for privacy requests; assign owner and SLA.
- Add identity verification, request status transitions, audit trail, access report/export and deletion execution with legal-hold handling.
- Implement category-based retention configuration and scheduled deletion; validate backup and log retention.
- Verify infrastructure-managed encryption at rest and implement application-level encryption where risk assessment requires it.
- Test consent recording and withdrawal end-to-end; ensure future tracker code is blocked until consent.
- Confirm actual AI provider and update notice/provider list.
- Verify production HTTPS/TLS and provider data locations.
- Add automated tests for consent endpoints, migration, request intake and frontend form gates.
- Run backend tests, frontend lint/build and staging migration after backup/recovery verification.
- Counsel must approve all legal copy before production publication.

## Verification record

- Source review was performed against the organization-onboarding branch at the baseline commit above.
- Branch changes have not yet been run through CI or deployed.
- No production or staging database has been changed.
