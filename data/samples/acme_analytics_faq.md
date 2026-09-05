# Acme Analytics — Support FAQ

_This is a fictional document used as demo content for the RAG chatbot._

## Plans and pricing

- **Free**: 10,000 tracked events per month and up to 3 dashboards.
- **Pro**: $49 per user per month. Unlimited dashboards and 12 months of data
  retention.
- **Enterprise**: custom pricing. Adds SSO/SAML, 24 months of data retention,
  and a 99.9% uptime SLA.

## Data retention

Retention is 12 months on Pro and 24 months on Enterprise. On the Free plan,
events older than 30 days are aggregated and raw events are deleted.

## Regions and data residency

Acme Analytics runs in two regions: US (Northern Virginia) and EU (Frankfurt).
You choose your region when the account is created. The region cannot be changed
afterwards — you would need to open a new account and re-import your data.

## Exporting data

You can export data as CSV or JSON through the REST API. The API rate limit is
100 requests per minute on Pro and 1,000 requests per minute on Enterprise. The
Free plan does not include API access.

## Integrations

Supported integrations are Segment, Snowflake, Google BigQuery, and outbound
webhooks. Additional connectors are available on Enterprise on request.

## Accounts and sign-in

Reset your password from the "Forgot password" link on the sign-in page. After 5
failed sign-in attempts the account is locked for 15 minutes. Enterprise
customers can enforce SSO and disable password sign-in entirely.

## Support response times

Pro customers receive a response within 1 business day. Enterprise customers
receive a response within 4 hours, 24/7, for issues marked urgent.
