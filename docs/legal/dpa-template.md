# Data Processing Agreement (DPA) — Template

**Status:** Draft template for review by qualified counsel before use with customers.
Not legal advice. Replace all bracketed placeholders before execution.

---

This Data Processing Agreement ("**DPA**") forms part of the Agreement between
**GeoRisk Engine, Inc.** ("**Processor**") and **[Customer legal name]**
("**Controller**") for the provision of the GeoRisk Engine location risk
intelligence platform and API (the "**Service**"). This DPA reflects the
parties' obligations under the EU General Data Protection Regulation
(Regulation (EU) 2016/679, "**GDPR**") and, where applicable, the UK GDPR.

## 1. Subject Matter and Scope

1.1 This DPA applies where Processor processes Personal Data on behalf of
Controller in connection with the Service.

1.2 In most GeoRisk Engine use cases, inputs are **asset coordinates,
facility identifiers, and sector metadata** rather than Personal Data.
This DPA governs the limited cases where Customer-submitted data (e.g.
account contacts, user accounts, uploaded portfolio files) contains
Personal Data.

## 2. Definitions

Terms such as "Personal Data," "Processing," "Controller," "Processor,"
"Data Subject," and "Supervisory Authority" have the meanings given in
Article 4 GDPR.

## 3. Details of Processing (Article 28(3) GDPR)

| | |
|---|---|
| **Subject matter** | Provision of the GeoRisk Engine API, dashboards, and report exports |
| **Duration** | Term of the underlying Agreement, plus any retention period in Section 8 |
| **Nature and purpose** | Hosting, storage, and processing of account and portfolio data to generate environmental/operational risk scores and reports |
| **Categories of Data Subjects** | Controller's authorized users (employees/contractors); individuals referenced in uploaded portfolio metadata, if any |
| **Categories of Personal Data** | Name, business email, account credentials, IP address (access logs); Controller-uploaded portfolio data is not expected to contain special category data |
| **Special category data** | Not intended to be processed. Controller shall not submit special category data via the Service. |

## 4. Processor Obligations

Processor shall:

4.1 Process Personal Data only on documented instructions from Controller,
including with regard to international transfers, unless required by law.

4.2 Ensure persons authorized to process Personal Data are bound by
confidentiality obligations.

4.3 Implement appropriate technical and organizational measures (see
Section 7 / Annex II).

4.4 Not engage a sub-processor without prior general or specific written
authorization from Controller (see Section 5).

4.5 Assist Controller, taking into account the nature of processing, in
responding to Data Subject requests under Articles 15–22 GDPR.

4.6 Assist Controller in ensuring compliance with Articles 32–36 GDPR
(security, breach notification, DPIAs), taking into account the nature of
processing and information available to Processor.

4.7 At Controller's choice, delete or return all Personal Data after the
end of the provision of services, and delete existing copies unless
applicable law requires storage (see Section 8).

4.8 Make available to Controller all information necessary to demonstrate
compliance with Article 28 and allow for, and contribute to, audits
including inspections, conducted by Controller or an auditor mandated by
Controller (see Section 9).

## 5. Sub-processors

5.1 Controller provides general authorization for Processor to engage
sub-processors for hosting, infrastructure, and email/communications,
provided Processor:

- maintains an up-to-date list of sub-processors (current sub-processors:
  **[cloud hosting provider]**, **[email/communications provider]**, list
  to be maintained at `[URL]`);
- imposes data protection obligations on sub-processors equivalent to
  those in this DPA; and
- notifies Controller of any intended changes, giving Controller the
  opportunity to object on reasonable grounds.

## 6. International Transfers

6.1 Where Personal Data is transferred outside the European Economic Area
or UK, Processor shall ensure an appropriate transfer mechanism is in place
(e.g. EU Standard Contractual Clauses, UK International Data Transfer
Agreement/Addendum, or an adequacy decision).

## 7. Security Measures (Annex II)

Processor shall implement and maintain technical and organizational
measures including, as applicable:

- Encryption of Personal Data in transit (TLS) and at rest;
- Access controls based on least privilege, with authenticated API access
  (e.g. bearer tokens / API keys);
- Logging and monitoring of access to systems processing Personal Data;
- Regular vulnerability management and patching;
- Backup and disaster recovery procedures;
- Employee confidentiality and security awareness training.

*[Expand into a full Annex II security exhibit before execution.]*

## 8. Data Retention and Deletion

8.1 Upon termination of the Agreement, or upon Controller's written
request, Processor shall delete or return Personal Data within
**[30/60/90]** days, except where retention is required by applicable law,
in which case Processor shall continue to protect such data and limit
processing to the purpose of that legal requirement.

## 9. Audit Rights

9.1 Processor shall make available information reasonably necessary to
demonstrate compliance with this DPA, including responses to security
questionnaires, and shall permit audits no more than once per 12-month
period (or following a Personal Data Breach), on reasonable notice and
subject to confidentiality.

## 10. Personal Data Breach

10.1 Processor shall notify Controller without undue delay, and in any
event within **[48/72]** hours, after becoming aware of a Personal Data
Breach affecting Controller's Personal Data, and shall provide reasonably
requested information to enable Controller to meet its own notification
obligations under Articles 33–34 GDPR.

## 11. Liability

11.1 Liability under this DPA is subject to the limitations and exclusions
of liability set out in the Agreement, except where prohibited by
applicable law.

## 12. Governing Law

12.1 This DPA is governed by the laws specified in the Agreement, without
prejudice to any mandatory provisions of GDPR regarding the rights of Data
Subjects and Supervisory Authorities.

---

**Annex I — List of Sub-processors:** *[to be maintained and linked]*

**Annex II — Technical and Organizational Measures:** *[to be expanded
prior to execution; pending input from security review]*
