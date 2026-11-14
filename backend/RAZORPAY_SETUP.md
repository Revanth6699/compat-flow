# Razorpay Subscriptions Setup

CompatFlow uses Razorpay Subscriptions for recurring billing. Do not use Razorpay one-time Orders for plan subscriptions.

## Required backend environment variables

Set these on the backend service (never expose the secret values to the frontend):

- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`
- `RAZORPAY_PLAN_IDS_JSON`

`RAZORPAY_PLAN_IDS_JSON` maps each CompatFlow plan and billing interval to a Razorpay Plan ID. Example with placeholder IDs:

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

Create the corresponding plans in Razorpay Dashboard under **Subscriptions → Plans**. Existing Razorpay plans are immutable; create a new plan when price or billing frequency changes. Set the actual currency and amount deliberately. CompatFlow's seeded plan prices are currently stored in USD; do not convert them to INR or assume that a Razorpay merchant account has international recurring-card access. Confirm the account's enabled currencies and recurring payment methods before creating live plans.

Use test-mode plan IDs with test-mode API keys. Do not mix test and live IDs.

## Webhook configuration

Configure this endpoint in Razorpay Dashboard:

`POST https://<your-backend-host>/api/v1/billing/webhooks/razorpay`

Set a webhook secret and configure these subscription events:

- `subscription.authenticated`
- `subscription.activated`
- `subscription.charged`
- `subscription.pending`
- `subscription.halted`
- `subscription.paused`
- `subscription.resumed`
- `subscription.cancelled`
- `subscription.completed`

Copy the same webhook secret into `RAZORPAY_WEBHOOK_SECRET`. Signature verification uses the original raw request bytes and the `X-Razorpay-Signature` header. Event deduplication uses `x-razorpay-event-id`.

## API flow

1. An organization owner calls `POST /api/v1/billing/subscriptions` with `plan_code`, `billing_interval`, and `total_count`.
2. The backend creates the Razorpay subscription and returns the provider subscription ID and public key ID for Razorpay Checkout.
3. The frontend submits `razorpay_payment_id`, `razorpay_subscription_id`, and `razorpay_signature` to `POST /api/v1/billing/subscriptions/verify-checkout`, along with the local `subscription_id`.
4. Checkout signature verification does not itself activate entitlements. The backend waits for the verified `subscription.activated` webhook.
5. Razorpay renewal, failure, pause, resume, and cancellation events update the local subscription and payment records.
6. Owners can request cancellation through `POST /api/v1/billing/subscriptions/{subscription_id}/cancel`. Razorpay's webhook remains authoritative for the final state.

Monthly subscriptions allow up to 120 billing cycles; yearly subscriptions allow up to 10. A new subscription cannot be created while the organization has an unresolved active, trialing, pending, or past-due subscription.

## Not yet enabled

- No Razorpay credentials or plan IDs are committed to the repository.
- No live/test Dashboard webhook has been configured or delivered to the backend.
- No real customer payment has been run.
- Plan changes are not automated. Razorpay's upgrade/downgrade support depends on payment method and account eligibility; do not assume that UPI AutoPay, eMandate, and card subscriptions have identical update behavior.
- Refund initiation and reconciliation are not exposed as customer-facing APIs yet.
