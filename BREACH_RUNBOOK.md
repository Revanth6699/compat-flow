# Personal Data Breach Response Runbook (India)

**Status:** Operational draft — security/legal counsel approval required.  
**Scope:** CompatFlow website, APIs, databases, file storage, authentication, billing integrations, support systems and subprocessors.

## 1. First response

1. Anyone who suspects a personal-data breach must immediately notify the incident lead and security contact. Do not wait for proof of exfiltration.
2. Record first-detection time, reporter, affected systems, suspected data categories, affected tenants/individuals, time window and evidence sources.
3. Preserve logs, snapshots and evidence. Do not delete, rotate or overwrite evidence unless needed to contain an active threat; record the action.
4. Contain the incident: revoke exposed credentials/tokens, isolate affected workloads, disable vulnerable routes/integrations, restrict access and block ongoing exfiltration.
5. Engage hosting, database, authentication, payment and other relevant providers. Obtain written incident facts and timestamps.
6. Maintain a decision log and keep legal counsel and incident leadership informed.

## 2. Assessment

Determine and keep updating: whether personal data was involved; categories and approximate number of affected Data Principals; whether data was accessed, altered, lost, disclosed or rendered unavailable; likely consequences; affected organizations, providers and locations; root cause, attack vector and duration; exposure of credentials, payment references, authentication tokens or supplier files; and containment/remediation steps.

Do not delay required notifications while waiting for a perfect forensic picture. Send an initial notice with known facts and provide updates.

## 3. Regulatory and individual notifications

The DPDP Rules provide for notice to affected Data Principals without delay and notice to the Data Protection Board without delay, followed by detailed information within 72 hours of becoming aware of the breach (subject to any extension granted by the Board). Counsel must confirm applicable commencement, current prescribed form/channel and any additional CERT-In, sectoral or contractual deadlines for the incident.

Record awareness time, notice send times, channels and acknowledgements. This runbook does not replace legal advice or other reporting duties.

## 4. Board notification — initial notice template

**To:** Data Protection Board of India (through the currently prescribed channel)  
**Subject:** Initial intimation of personal data breach — [incident reference]

- Data Fiduciary: [confirmed legal name and contact]
- Date/time of awareness: [date, time, timezone]
- Date/time incident is believed to have begun: [known/estimated/unknown]
- Systems/services affected: [systems]
- Nature of breach: [unauthorized access/disclosure/loss/alteration/unavailability/other]
- Categories of personal data: [categories]
- Approximate Data Principals affected: [number/current estimate]
- Likely impact/consequences: [known/under assessment]
- Containment actions completed: [actions and timestamps]
- Immediate mitigation/advice for affected individuals: [steps]
- Investigation status and next update: [details]
- Incident contact: [name, role, monitored phone/email]

This initial notification is based on information currently available. Further particulars and updates will be supplied through the prescribed process.

## 5. Board notification — detailed update within 72 hours template

**Subject:** Detailed update to personal data breach notification — [incident reference]

1. Updated chronology and awareness timestamp.
2. Detailed circumstances and root cause, if known.
3. Categories and approximate number of affected Data Principals and records.
4. Likely consequences and risk assessment.
5. Measures implemented and planned to mitigate harm.
6. Notices sent to Data Principals, dates, channels and response information.
7. Remediation, monitoring and recurrence-prevention plan.
8. Provider/subprocessor involvement and relevant contact details.
9. Facts still under investigation and expected date for further update.
10. Authorized incident contact and supporting evidence index.

If more time is needed, counsel must request an extension through the prescribed channel and document the Board's response. Do not assume an extension is granted.

## 6. Notice to affected Data Principals — template

**Subject:** Important security notice about your CompatFlow information

We are contacting you because CompatFlow identified a security incident on [date/time] that may have involved your personal data.

**What happened:** [plain-language description; distinguish confirmed facts from investigation].

**Information involved:** [specific categories; do not speculate].

**What we have done:** [containment, access revocation, investigation and remediation].

**What you can do:** [specific protective steps relevant to the data involved].

**What happens next:** We are continuing to investigate and will provide material updates where appropriate.

**Contact:** [monitored privacy/security contact]. Reference: [incident reference].

We regret the concern this may cause. We will not ask you to disclose your password or one-time authentication code in response to this notice.

## 7. Closure and post-incident review

- Complete root-cause analysis and verify remediation.
- Review access logs, secrets, encryption, backups, tenant isolation and provider controls.
- Track regulatory, individual, customer and contractual notifications.
- Record lessons learned, owners and due dates.
- Update threat models, tests, runbooks and staff training.
- Obtain legal/security sign-off before closure.

## 8. Contacts (complete before launch)

- Incident lead: [name / 24x7 contact]
- Security lead: [name / 24x7 contact]
- Grievance Officer / Privacy contact: [name / monitored email / postal address]
- Legal counsel: [name / emergency contact]
- Render support/account contact: [verified]
- Supabase support/account contact: [verified]
- Vercel support/account contact: [verified]
- Razorpay incident contact: [verified]
