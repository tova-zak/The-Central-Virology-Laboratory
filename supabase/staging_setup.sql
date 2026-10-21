-- =====================================================================
-- Central Virology Laboratory - Supabase STAGING setup
--
-- *** NOT FOR EXECUTION ON THE EXISTING `virology-lab` PROJECT. ***
-- The existing project already has public.batches and the private bucket
-- `virology-lab-uploads`. This file is DOCUMENTATION of the required schema,
-- to be used ONLY to bootstrap a NEW, SEPARATE, EMPTY Supabase environment.
-- NEVER run this on production or on any project holding clinical data.
--
-- Idempotent: safe to re-run. Contains no DROP / TRUNCATE / DELETE.
-- Run in: Supabase Dashboard -> SQL Editor.
--
-- What the backend uses (backend/app/services/storage/storage_adapter.py):
--   * ONE table  public.batches   (PostgREST, service-role key only)
--   * ONE private Storage bucket  (name must equal SUPABASE_BUCKET_NAME)
-- The backend uses only the service-role key. No anon/authenticated access
-- is needed, so RLS is enabled with NO policies.
-- =====================================================================

-- 1. Table (schema mirrors the contract in storage_adapter.py docstring).
--    updated_at stays TIMESTAMP (no tz): it is the optimistic-lock token.
create table if not exists public.batches (
  batch_id   text primary key,
  batch_data jsonb not null,
  created_at timestamp default now(),
  updated_at timestamp default now()
);

create index if not exists idx_batches_created
  on public.batches (created_at desc);

-- 2. RLS on, no policies: only the service role (bypasses RLS) can access.
alter table public.batches enable row level security;
revoke all on table public.batches from anon, authenticated;

-- 3. PRIVATE storage bucket. If you change the name here, set the same
--    value in SUPABASE_BUCKET_NAME. Do NOT add storage policies for
--    anon/authenticated.
insert into storage.buckets (id, name, public)
values ('virology-lab-uploads', 'virology-lab-uploads', false)
on conflict (id) do nothing;

-- 4. Verification: 'public' must be false for the bucket.
select id, public from storage.buckets;

-- ---------------------------------------------------------------------
-- Optional verification queries (run manually):
-- select to_regclass('public.batches');                      -- not null
-- select relrowsecurity from pg_class
--   where oid = 'public.batches'::regclass;                  -- true
-- select * from pg_policies
--   where schemaname = 'public' and tablename = 'batches';   -- 0 rows
-- select * from pg_policies
--   where schemaname = 'storage' and tablename = 'objects';  -- no anon/authenticated policy
-- select count(*) from public.batches;                       -- 0 on a new project
-- ---------------------------------------------------------------------
