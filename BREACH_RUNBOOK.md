# Personal Data Breach Response Runbook

**Jurisdiction:** India  
**Status:** Operational draft; legal and security review required  
**Applies to:** CompatFlow web application, APIs, databases, file storage, authentication, billing integrations, support systems, and subprocessors

## 1. Purpose and activation

Use this runbook when an event may have compromised personal data. Suspected incidents must be escalated promptly; do not wait for confirmed exfiltration.

The incident lead owns coordination. Legal counsel determines applicable notification duties, recipients, channels, and deadlines for the specific incident.

## 2. Immediate response

1. Notify the incident lead and security contact.
2. Record the detection time, reporter, affected systems, suspected data categories, affected organizations or individuals, incident window, and evidence sources.
3. Preserve relevant logs, snapshots, and forensic evidence. Record any action that could alter evidence.
4. Contain the incident. Revoke exposed credentials and tokens, isolate affected workloads, disable vulnerable routes or integrations, restrict access, and stop ongoing exfiltration.
5. Contact relevant hosting, database, authentication, payment, and other providers. Request written incident facts and timestamps.
6. Maintain a decision log. Keep incident leadership and legal counsel informed.

Do not destroy evidence during containment unless necessary to stop active harm. Record the reason and scope of any such action.

## 3. Assessment checklist

Update the assessment as evidence becomes available.

- Was personal data involved?
- Which categories of data and approximate number of individuals or records are affected?
- Was data accessed, disclosed, altered, lost, or made unavailable?
- Which organizations, systems, providers, and locations are involved?
- When did the incident begin, and when did the operator become aware?
- What are the likely consequences?
- Were credentials, authentication tokens, payment references, or supplier files exposed?
- What was the root cause, attack path, and duration?
- Which containment and remediation steps have been completed?

Distinguish confirmed facts, estimates, and unknowns. Do not delay a legally required initial notice while waiting for a complete forensic report.

## 4. Regulatory and individual notifications

Rule 7 of the Digital Personal Data Protection Rules, 2025 provides for notice to affected Data Principals without delay and notice to the Data Protection Board without delay, followed by detailed information within 72 hours of awareness, subject to an extension granted by the Board.

**Commencement note:** Rule 7 is scheduled to commence on **13 May 2027**, 18 months after publication of the Rules on 13 November 2025. This runbook is a preparedness procedure. Before relying on a statutory timeline, counsel must confirm commencement, amendments, the prescribed form and channel, and any other applicable duties.

The future Rule 7 timeline does not replace obligations that may apply now under other laws, regulatory directions, or contracts. Counsel must assess any CERT-In, sectoral, customer, and contractual reporting requirements for each incident.

For every notification, record:
- Awareness and decision timestamps.
- Recipient and legal basis.
- Notice content and version.
- Delivery channel and send time.
- Acknowledgement or delivery evidence.
- Follow-up commitments and completion.

## 5. Data Protection Board — initial notice template

**To:** Data Protection Board of India, through the currently prescribed channel  
**Subject:** Initial intimation of personal data breach — [incident reference]

- Data Fiduciary / operator: [confirmed legal name]
- Incident reference: [reference]
- Date and time of awareness: [date, time, timezone]
- Incident start: [known / estimated / unknown]
- Affected systems and services: [systems]
- Nature of breach: [access / disclosure / loss / alteration / unavailability / other]
- Personal data categories: [categories]
- Approximate number of affected Data Principals: [number / estimate]
- Likely consequences: [known facts / under assessment]
- Containment actions: [actions and timestamps]
- Immediate mitigation advice: [steps]
- Investigation status and next update: [details]
- Authorized incident contact: [name, role, monitored contact]

This notice reflects information available at the time of submission. Further particulars will be provided through the prescribed process.

## 6. Data Protection Board — detailed update template

**Subject:** Detailed update to personal data breach notification — [incident reference]

1. Updated chronology and awareness timestamp.
2. Circumstances of the incident and root cause, if known.
3. Categories and approximate number of affected individuals and records.
4. Likely consequences and current risk assessment.
5. Measures completed and planned to mitigate harm.
6. Notices sent to affected individuals, including dates, channels, and response information.
7. Remediation and recurrence-prevention plan.
8. Provider or subprocessor involvement and relevant contacts.
9. Outstanding investigation items and expected update date.
10. Authorized incident contact and evidence index.

If additional time is required, counsel must request an extension through the prescribed channel and record the Board's response. Do not assume an extension has been granted.

## 7. Notice to affected individuals — template

**Subject:** Security notice about your CompatFlow information

We are contacting you because CompatFlow identified a security incident on [date and time] that may have involved your personal data.

**What happened**  
[Plain-language description. Separate confirmed facts from matters still under investigation.]

**Information involved**  
[List only data categories supported by the investigation.]

**What we have done**  
[Containment, access revocation, investigation, and remediation steps.]

**What you can do**  
[Protective steps relevant to the information involved.]

**What happens next**  
[Explain the investigation and when material updates will be provided.]

**Contact**  
[Monitored privacy or security contact]  
Incident reference: [reference]

We will not ask you to disclose your password or one-time authentication code in response to this notice.

## 8. Closure and post-incident review

- Complete the root-cause analysis.
- Verify that remediation is effective.
- Review access logs, secrets, encryption, backups, tenant isolation, and provider controls.
- Reconcile regulatory, individual, customer, and contractual notifications.
- Record lessons, owners, and due dates.
- Update threat models, tests, procedures, and staff guidance.
- Obtain legal and security sign-off before closing the incident.

## 9. Contact register — complete before operational use

| Role | Required contact |
|---|---|
| Incident lead | [Name and monitored contact] |
| Security lead | [Name and monitored contact] |
| Privacy / grievance contact | **Not configured — monitored email and responsible person required** |
| Legal counsel | [Name and emergency contact] |
| Render account contact | [Verified account contact] |
| Supabase account contact | [Verified account contact] |
| Vercel account contact | [Verified account contact] |
| Razorpay incident contact | [Verified account contact] |

Do not publish or rely on placeholder contacts. Confirm that every listed contact is real, accessible, and monitored before operational use.
