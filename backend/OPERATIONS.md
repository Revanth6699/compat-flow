# Backend operations

## Initial organization owner provisioning

Supabase Auth owns password registration and login. The FastAPI service validates Supabase access tokens and maps authenticated Supabase users to CompatFlow organization profiles.

The first verified user must be provisioned as the owner of the initial organization. This is deliberately an operator-run command, not a public API endpoint: an unauthenticated public bootstrap endpoint would let an arbitrary visitor claim the first-owner role.

### Prerequisites

1. Apply all Alembic migrations from the current backend branch to the intended database.
2. Register the initial user through Supabase Auth and confirm the user's email.
3. Obtain a fresh Supabase access token for that user.
4. Run the command from the `backend/` directory with these environment variables set:
   - `DATABASE_URL`: the intended database URL, using `postgresql+psycopg://`.
   - `SUPABASE_URL`: the Supabase project URL.
   - `SUPABASE_ANON_KEY`: the Supabase publishable/anon key.
   - `SUPABASE_ACCESS_TOKEN`: the initial user's access token. Keep it private; do not commit it or paste it into logs or chat.

### Run

```powershell
$env:SUPABASE_ACCESS_TOKEN = "YOUR_FRESH_SUPABASE_ACCESS_TOKEN"
python -m scripts.provision_owner --organization-name "Your Organization"
Remove-Item Env:SUPABASE_ACCESS_TOKEN
```

The command asks Supabase to validate the token and requires a confirmed email. It then creates the initial organization and owner profile in one database transaction. It refuses to run if the Supabase identity is already linked or an active owner already exists. It never prints the access token.

Run this only against the intended staging database during staging validation. Do not point it at production until the rollout has been separately approved.

### Subsequent users

Additional users should register or sign in through Supabase Auth and join an existing organization through the invitation workflow. Do not create additional owners with this bootstrap command. Organization self-service signup and multi-organization membership are not implemented by this initial-owner operation.
