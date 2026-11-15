# Razorpay Subscription Setup

CompatFlow uses Razorpay Subscriptions for recurring billing. Do not use Razorpay one-time Orders for plan subscriptions.

## 1. Backend environment variables

Set these on the backend service. Do not expose secret values to the frontend.

- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`
- `RAZORPAY_PLAN_IDS_JSON`

### Plan ID mapping

`RAZORPAY_PLAN_IDS_JSON` maps each CompatFlow plan and billing interval to a Razorpay Plan ID.

Example using placeholder IDs:

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

Create the corresponding plans in Razorpay Dashboard under **Subscriptions → Plans**.

Razorpay plans are immutable. Create a new plan when price or billing frequency changes. Set currency and amount deliberately.

CompatFlow's seeded plan prices are currently stored in USD. Do not convert them to INR or assume the merchant account supports international recurring-card payments. Confirm enabled currencies and recurring payment methods before creating live plans.

Use test-mode plan IDs with test-mode API keys. Do not mix test and live IDs.

## 2. Webhook configuration

Configure this endpoint in Razorpay Dashboard:

`POST https://<your-backend-host>/api/v1/billing/webhooks/razorpay`

Set a webhook secret and subscribe to:

- `subscription.authenticated`
- `subscription.activated`
- `subscription.charged`
- `subscription.pending`
- `subscription.halted`
- `subscription.paused`
- `subscription.resumed`
- `subscription.cancelled`
- `subscription.completed`

Copy the same secret into `RAZORPAY_WEBHOOK_SECRET`.

Signature verification uses the original raw request bytes and the `X-Razorpay-Signature` header. Event deduplication uses `x-razorpay-event-id`.

## 3. Subscription API flow

1. An organization owner calls `POST /api/v1/billing/subscriptions` with `plan_code`, `billing_interval`, and `total_count`.
2. The backend creates the Razorpay subscription and returns the provider subscription ID and public key ID for Checkout.
3. The frontend submits `razorpay_payment_id`, `razorpay_subscription_id`, and `razorpay_signature` to `POST /api/v1/billing/subscriptions/verify-checkout`, along with the local `subscription_id`.
4. Checkout signature verification does not activate entitlements. The backend waits for the verified `subscription.activated` webhook.
5. Renewal, failure, pause, resume, and cancellation events update local subscription and payment records.
6. Owners can request cancellation through `POST /api/v1/billing/subscriptions/{subscription_id}/cancel`. Razorpay's webhook remains authoritative for the final state.

Monthly subscriptions allow up to 120 billing cycles; yearly subscriptions allow up to 10. A new subscription cannot be created while the organization has an unresolved active, trialing, pending, or past-due subscription.

## 4. Not configured or not verified

- No Razorpay credentials or plan IDs are committed to the repository.
- No live or test Dashboard webhook has been confirmed as configured and delivered to the backend.
- No real customer payment has been run.
- Plan changes are not automated. Upgrade/downgrade behavior depends on payment method and account eligibility. Do not assume UPI AutoPay, eMandate, and card subscriptions have identical update behavior.
- Refund initiation and reconciliation are not exposed as customer-facing APIs.
