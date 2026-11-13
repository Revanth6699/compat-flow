create extension if not exists pgcrypto;

create table if not exists public.contact_requests (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text not null,
  organization text not null,
  role text not null,
  message text not null,
  intent text not null default 'general' check (intent in ('general','demo')),
  status text not null default 'new' check (status in ('new','reviewing','approved','declined','invited')),
  created_at timestamptz not null default now()
);

alter table public.contact_requests enable row level security;

-- No anon/authenticated policies: public submissions are written only by
-- the server-side API using the Supabase service-role key.
revoke all on public.contact_requests from anon, authenticated;
grant all on public.contact_requests to service_role;

create table if not exists public.demo_access (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  status text not null default 'approved' check (status in ('approved','revoked')),
  invited_at timestamptz,
  expires_at timestamptz,
  created_at timestamptz not null default now()
);

alter table public.demo_access enable row level security;
revoke all on public.demo_access from anon, authenticated;
grant all on public.demo_access to service_role;
