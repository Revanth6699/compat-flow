# Gmail notifications

CompatFlow sends platform notifications to the configured Gmail inbox for new demo access requests and general contact submissions.

## OAuth setup

1. Enable the Gmail API in the Google Cloud project.
2. Configure the OAuth consent screen and add the notification Gmail account as a test user while testing.
3. Create a Web application OAuth client.
4. Register the environment-specific callback URI:
   - Staging: `https://compat-flow-staging.onrender.com/api/v1/notifications/gmail/oauth/callback`
   - Production: `https://compat-flow.onrender.com/api/v1/notifications/gmail/oauth/callback`
5. Add the OAuth client credentials to the backend service environment.
6. Open `/api/v1/notifications/gmail/oauth/start` on that same backend, sign in as the configured notification Gmail account, and authorize the `gmail.send` scope.
7. Copy the one-time refresh token from the callback page into the backend secret `GMAIL_REFRESH_TOKEN`. Never commit or share it.

The callback verifies the signed, time-limited OAuth state and checks that the Google account matches `GMAIL_SENDER_EMAIL`. The refresh token is displayed once for manual transfer into Render; it is not written to application logs or the repository.

## Backend environment

- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`
- `GMAIL_SENDER_EMAIL` (defaults to `sarvasettyrevanth.66@gmail.com`)
- `GMAIL_NOTIFICATION_TO_EMAIL` (defaults to `sarvasettyrevanth.66@gmail.com`)
- `GMAIL_OAUTH_REDIRECT_URI` (must exactly match the Google OAuth client)
- `CONTACT_NOTIFICATION_SECRET` (random shared secret; configure the same value in the backend and the Vercel server environment)

The frontend also requires `CONTACT_NOTIFICATION_SECRET` as a server-only Vercel environment variable. It must not use a `NEXT_PUBLIC_` prefix.

## Notification behavior

- Demo requests are persisted by the backend first; email is attempted only after the database commit.
- General contact messages are persisted in Supabase first; the Next.js server then calls the backend notification endpoint using the shared secret.
- Email delivery failures are logged but do not reverse a successful database write or make the visitor resubmit a saved form.
- The notification endpoint is not exposed to browsers without the shared secret.
- Access tokens are refreshed from Google's OAuth token endpoint when a notification is sent. Only the `gmail.send` Gmail scope is requested, alongside OpenID/email identity scopes used to verify the account.

## Testing and deployment

Configure and test staging before production. Keep OAuth client secrets, refresh tokens, and the contact notification secret in provider secret managers only. Do not add them to source control, frontend bundles, screenshots, or support messages.

For an OAuth app with an External audience left in Testing, Google may expire refresh tokens after seven days for non-basic scopes. Revisit the Google Auth Platform publishing status before relying on this for ongoing production notifications.
