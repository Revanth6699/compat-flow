# Razorpay Subscription Setup

CompatFlow uses Razorpay Subscriptions for recurring plan billing. Do not use one-time Razorpay Orders for subscriptions.

## Backend configuration

Set these variables on the backend service. Do not expose their values to the frontend.

- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`
- `RAZORPAY_PLAN_IDS_JSON`

### Plan ID mapping

`RAZORPAY_PLAN_IDS_JSON` maps each CompatFlow plan and billing interval to a Razorpay Plan ID.

The following is an example with placeholder IDs:

```json
{
  "starter:month": "plan_replace_with_test_id",
  "starter:year": "plan_replace_with_test_annual_id",
  "growth:month": "plan_replace_with_test_id",
  "growth:year": "plan_replace_with_test_annual_id",
  "business:month": "plan_replace_with_test_id",
  "business:year": "plan_replace_with_test_annual_id",
  "enterprise:month": "plan_replace_with_test_id",
  "enterprise:year": "plan_replace_with_test_annual_id"
}
```

Create the matching plans in the Razorpay Dashboard under **Subscriptions → Plans**.

Razorpay plans cannot be edited after creation. Create a new plan when the price or billing frequency changes, and set the currency and amount deliberately.

The seeded CompatFlow plan prices are currently stored in USD. Do not convert them to INR or assume the merchant account supports international recurring-card payments. Check the account's enabled currencies and recurring payment methods before creating live plans.

Use test plan IDs with test API keys and live plan IDs with live API keys. Do not mix environments.

## Webhook setup

Configure this endpoint in the Razorpay Dashboard:

`POST https://<your-backend-host>/api/v1/billing/webhooks/razorpay`

Set a webhook secret and subscribe to these events:

- `subscription.authenticated`
- `subscription.activated`
- `subscription.charged`
- `subscription.pending`
- `subscription.halted`
- `subscription.paused`
- `subscription.resumed`
- `subscription.cancelled`
- `subscription.completed`

Set the same secret as `RAZORPAY_WEBHOOK_SECRET`.

The backend verifies the signature against the original request bytes and the `X-Razorpay-Signature` header. It uses `x-razorpay-event-id` to detect duplicate events.

## Subscription flow

1. An organization owner calls `POST /api/v1/billing/subscriptions` with `plan_code`, `billing_interval`, and `total_count`.
2. The backend creates the Razorpay subscription and returns the provider subscription ID and public key ID for Checkout.
3. The frontend sends `razorpay_payment_id`, `razorpay_subscription_id`, and `razorpay_signature` to `POST /api/v1/billing/subscriptions/verify-checkout`, together with the local `subscription_id`.
4. A valid Checkout signature does not activate entitlements. The backend waits for a verified `subscription.activated` webhook.
5. Renewal, failure, pause, resume, and cancellation events update the local subscription and payment records.
6. An owner can request cancellation through `POST /api/v1/billing/subscriptions/{subscription_id}/cancel`. The webhook remains authoritative for the final subscription state.

Monthly subscriptions allow up to 120 billing cycles; yearly subscriptions allow up to 10. A new subscription cannot be created while the organization has an unresolved active, trialing, pending, or past-due subscription.

## Current setup gaps

- No Razorpay credentials or plan IDs are committed to the repository.
- A test or live Dashboard webhook has not been confirmed as configured and successfully delivered to the backend.
- No real customer payment has been run.
- Plan upgrades and downgrades are not automated. Behavior depends on the payment method and account eligibility. UPI AutoPay, eMandate, and card subscriptions should not be assumed to behave identically.
- Refund initiation and reconciliation are not available through customer-facing APIs.