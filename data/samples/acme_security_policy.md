# Acme Corp Information Security Policy

_This is a fictional document used as demo content for the RAG chatbot._

## Accounts and authentication

All staff accounts require multi-factor authentication. Passwords must be at
least 14 characters long. Passwords are never expired on a fixed schedule; they
are reset only if a compromise is suspected.

## Device security

Company laptops must have full-disk encryption enabled and must lock
automatically after 5 minutes of inactivity. Personal devices may access email
and Slack only, and never Restricted data.

## Data classification

Data is classified into four levels: Public, Internal, Confidential, and
Restricted. Restricted data includes customer personally identifiable
information (PII) and payment data. Restricted data must be encrypted both at
rest and in transit, and may only be accessed from managed devices.

## Vendors

Any third party that will handle Confidential or Restricted data must complete a
security review before a contract is signed. The review is repeated annually.

## Access management

Access to systems is granted on a least-privilege basis. Access reviews are
performed quarterly by each system owner. When someone leaves the company, all
of their access is revoked within 24 hours.

## Incident reporting

Report a suspected security incident within 1 hour to the security team at
security@acme.example, and page the on-call responder through PagerDuty. Do not
attempt to investigate or remediate on your own before the incident is
acknowledged.

## Training

Security awareness and phishing training is mandatory for all employees once per
year, and within the first two weeks for new hires.
