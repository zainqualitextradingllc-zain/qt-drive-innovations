-- Lead capture for Diagnostic Assistant (PII lives here, not in PostHog)
create table if not exists public.diagnostic_leads (
  id uuid primary key default gen_random_uuid(),
  session_id text not null,
  contact_method text not null check (contact_method in ('email', 'line')),
  contact_value text not null,
  diagnosis_category text,
  locale text check (locale is null or locale in ('en', 'ja')),
  created_at timestamptz default now()
);

create index if not exists idx_diagnostic_leads_session_id
  on public.diagnostic_leads (session_id);

create index if not exists idx_diagnostic_leads_created_at
  on public.diagnostic_leads (created_at desc);
