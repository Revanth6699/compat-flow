# DPDP Act (India) — Implementation Record

**Branch:** `compliance/dpdp`  
**Baseline:** `feature/organization-first-onboarding` at `658df92df407d628d757225f6c0ac6fb22603f65`  
**Review date:** 15 November 2026  
**Status:** Technical implementation draft. This document is not a legal opinion or compliance certification.

## 1. Executive status

The branch adds privacy notices, purpose-specific consent records, privacy-request intake, tracker preference controls, and breach-response documentation.

The implementation is not ready to be described as DPDP-compliant. Several operational controls are incomplete, legal copy requires Indian privacy counsel review, and the grievance contact has not been configured.

### Release blockers

- Configure a real, monitored grievance/privacy contact.
- Confirm the operator's legal identity and responsible privacy contact.
- Implement privacy-request identity verification, review, fulfilment, notification, and audit workflow.
- Define and implement retention and deletion schedules.
- Verify provider contracts, subprocessors, processing locations, and security controls.
- Obtain Indian privacy counsel review before public legal claims or production publication.

## 2. Commencement snapshot

The official Gazette commencement notifications phase the Act and Rules. The main Data Fiduciary duties and rights provisions (Act sections 3–17 and related provisions) and Rules 3, 5–16, 22, and 23 are scheduled to commence 18 months after 13 November 2025: **13 May 2027**.

Rule 4 commenced on **13 November 2026** and concerns Consent Manager registration and obligations. This implementation does not provide a Consent Manager service; counsel should confirm whether the operator has any relevant role.

Rule 7 breach-notification requirements and Rule 14 rights/grievance mechanisms are scheduled future commencement items as of the review date. This does not remove duties that may apply under other laws, regulatory directions, or contracts.

Official Gazette sources:
- [G.S.R. 843(E) — Act commencement](https://egazette.gov.in/WriteReadData/2025/267647.pdf)
- [G.S.R. 846(E) — DPDP Rules, 2025](https://egazette.gov.in/WriteReadData/2025/267650.pdf)

Counsel must verify commencement, amendments, and applicability before relying on this summary.

## 3. Decisions and implementation boundaries

1. Work is isolated on `compliance/dpdp`, based on the organization-onboarding branch. Do not merge or deploy without review.
2. Consent is stored as append-only, purpose-specific events. Earlier choices are not overwritten.
3. AI mapping remains a separate, per-action opt-in. It is not bundled into signup consent.
4. Essential authentication and security storage remains active. Optional analytics and marketing preferences default off.
5. No non-essential analytics or marketing tracker was found in the reviewed frontend. The consent-change event is an integration hook, not evidence that a tracker vendor is configured.
6. Privacy request submission currently creates an intake record. It does not complete identity verification or fulfilment.
7. Do not invent retention periods, operator identity, Grievance Officer details, email addresses, or provider contract terms.
8. Do not describe the application as DPDP-certified or legally compliant. Obtain Indian privacy counsel review.

## 4. Personal-data inventory

| Data category | Collection point | Purpose | Storage / recipient evidence |
|---|---|---|---|
| Account identity | Signup, sign-in, password recovery | Authentication and account access | Supabase Auth; profile in Render PostgreSQL |
| Profile | Signup metadata: name, organization, job title, optional phone/site, industry, team size | Workspace setup and administration | Supabase Auth metadata and application database |
| Organization and access | Organization creation, invitations, roles | Tenant access and administration | Render PostgreSQL |
| Contact and demo requests | Contact API and demo request endpoint | Respond to enquiries and review demo access | Supabase `contact_requests`; demo requests in Render PostgreSQL |
| Reviews | Authenticated review form | Collect and potentially publish feedback | Render PostgreSQL; display name and comment may be public |
| Billing | Billing routes and webhook handlers | Subscription and payment processing | Razorpay and local payment/subscription/webhook records |
| Supplier/catalog data | File imports and connector preview/commit | Validation, mapping, and catalog operations | Render PostgreSQL and configured import storage; customer-selected supplier systems |
| AI mapping samples | `/catalog/import/suggest-mappings` | Optional mapping suggestions | Configured OpenAI-compatible HTTPS endpoint receives headers and up to five bounded sample values per header after explicit opt-in |
| Technical metadata | Hosting, API, database, and authentication logs | Delivery, reliability, and security | Vercel, Render, Supabase, and configured infrastructure; exact fields and retention require provider verification |

This inventory is based on source review. Confirm deployed configuration, provider logs, and actual data flows before treating it as exhaustive.

## 5. Third-party services identified

- **Supabase:** authentication and Supabase REST storage for contact submissions.
- **Vercel:** frontend hosting and build delivery; verify deployed project configuration.
- **Render:** backend hosting and PostgreSQL; verify actual service and database configuration.
- **Razorpay:** payment and subscription processing.
- **Configured AI provider:** optional mapping endpoint; the deployed vendor and model must be confirmed from environment configuration.
- **Customer-selected supplier systems:** REST APIs, SFTP, and SQL Server sources. Customers must have authority to connect and submit the data.

Provider contracts, subprocessors, processing locations, retention, and transfer arrangements have not been fully verified.

## 6. Implemented in this branch

- Expanded draft Privacy Notice with data categories, purposes, provider categories, retention caveats, rights, security caveats, and grievance contact.
- Added a data-protection clause to Terms.
- Added a purpose-specific consent-event model and database migration.
- Added consent recording for service-processing acknowledgement and optional product updates.
- Added authenticated consent history and withdrawal endpoints for optional product updates and AI mapping.
- Preserved per-action AI mapping opt-in and recorded the consent event.
- Added unticked service-processing acknowledgement and optional product-updates controls to signup and contact/demo forms.
- Added a separate opt-in for public review publication and records affirmative choices as `public_review` consent.
- Added catalog-upload and supplier-connector authorization/data-minimization attestations. These are customer-authority declarations, not a substitute for consent from individuals whose data may be present.
- Added cookie preference controls for essential, analytics, and marketing categories. Optional categories default off.
- Added privacy-request intake for access, correction, erasure, consent withdrawal, and grievance.
- Added grievance contact links to the footer and Privacy Notice.
- Added [BREACH_RUNBOOK.md](BREACH_RUNBOOK.md) with incident steps and notification templates.

## 7. Security findings

| Area | Finding | Required action |
|---|---|---|
| CAPTCHA / abuse controls | No verified CAPTCHA integration was found in the reviewed contact flow. A honeypot is present but is not equivalent to verified bot protection. | Add rate limiting and verified CAPTCHA or an appropriate alternative. |
| File encryption | Application-level encryption was not identified in the reviewed import-storage path. This review did not establish a fail-open encryption control. | Verify infrastructure encryption, backups, access controls, and key management. Assess application-level encryption. |
| HTTPS | Production configuration validates HTTPS origins and enables HSTS. Source review does not prove deployed TLS, redirects, or third-party endpoint configuration. | Verify live certificates, redirects, headers, and provider endpoints. |
| Privacy requests | Intake is not routed to a monitored mailbox or authenticated administration queue. Identity verification and fulfilment are not automated. | Implement ownership verification, assignment, fulfilment, status, notification, and audit trail. |
| Consent proof | Events store supplied email, purpose, choice, notice version, source, and timestamp. Public intake does not independently verify control of the supplied email. | Add suitable verification and anti-abuse controls. |
| Retention | No complete category-specific schedule or automatic deletion jobs were confirmed. | Define, approve, implement, and test retention and deletion. |
| Provider governance | DPAs, subprocessors, data locations, transfer safeguards, and provider retention settings remain unverified. | Review provider contracts and account settings. |
| Operator contact | `NEXT_PUBLIC_CONTACT_EMAIL` and `NEXT_PUBLIC_GRIEVANCE_EMAIL` are not confirmed as monitored inboxes. The current fallback is a placeholder. | Configure real monitored contacts before publication. |
| Operator identity | Legal operator name/address and formal Grievance Officer details are not confirmed. | Confirm the operator identity and obtain legal advice on required disclosures. |

## 8. Grievance contact status

**Status: Not configured.**

The operator currently has no domain or public website identity for a domain-based mailbox and has not created a dedicated grievance inbox. This is not a blocker to continuing code work, but it is an operational release item.

- Do not invent or publish an email address.
- Keep the grievance contact as a clearly marked configuration placeholder.
- A dedicated monitored email account can be used before a domain-based address exists, subject to counsel's review of the required contact details.
- Configure `NEXT_PUBLIC_GRIEVANCE_EMAIL` only after the inbox exists and is monitored.
- Confirm who is responsible for reading, assigning, and responding to requests.

## 9. Legal review required

An Indian privacy lawyer should review:

1. Applicability and commencement of each Act/Rules obligation for the operator and its processing.
2. Whether each consent purpose and acknowledgement is appropriate and sufficiently specific.
3. Notice contents, Data Fiduciary identity, withdrawal method, and children/guardian applicability.
4. Retention periods, deletion exceptions, backups, logs, and legal holds.
5. Grievance Officer appointment, contact publication, and grievance process, including Rule 14(3) once applicable.
6. Customer/operator roles, Data Fiduciary and processor allocation, and contractual terms.
7. Provider contracts, subprocessors, processing locations, and transfers.
8. Breach assessment and notification duties, prescribed Board channels, and other reporting obligations.

All privacy and Terms copy remains **Draft — Legal Review Required**.

## 10. Open implementation and operational work

- [ ] Configure a real, monitored grievance email and confirm the responsible person.
- [ ] Confirm operator legal identity and address.
- [ ] Add rate limiting and verified bot controls to public forms and privacy endpoints.
- [ ] Add email notification and an authenticated, audited privacy-request queue.
- [ ] Add identity verification and request status transitions.
- [ ] Implement access report/export, correction, withdrawal, and erasure fulfilment with legal-hold handling.
- [ ] Define category-based retention and scheduled deletion.
- [ ] Validate backup and log retention.
- [ ] Verify infrastructure encryption at rest and assess application-level encryption.
- [ ] Test consent recording and withdrawal end to end.
- [ ] Confirm the configured AI provider and update provider disclosures.
- [ ] Verify production TLS and provider data locations.
- [ ] Add automated tests for consent endpoints, migration, request intake, and frontend gates.
- [ ] Run staging migration only after a verified backup and explicit operational approval.
- [ ] Obtain Indian privacy counsel approval before publishing final legal copy.

## 11. Verification record

- Source review was performed against the organization-onboarding branch at the baseline commit above.
- CI at `56ec34024f0d28f68fc41b685c5cbbdcd97c41b3`: backend 242 passed / 4 skipped; Ruff and Bandit passed; Alembic upgrade passed; frontend lint/build passed; backend runtime image build passed; industry-ingestion suite 242 passed / 4 skipped.
- CI at `99f280ef4bbed1a49cfac891e02867d980748195`: backend regression tests, Alembic upgrade, Ruff, Bandit, backend runtime image build, frontend lint/build, and industry-ingestion suite passed.
- Latest documentation commit and current branch CI status must be checked separately; historical CI results do not prove the latest commit is green.
- No staging or production migration/deployment has been run as part of this work.
