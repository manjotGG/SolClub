-- SolClub Supabase schema (Supabase/PostgreSQL)
-- Apply in Supabase SQL editor.
-- Username-centric identity: `username` is the canonical primary key for users.

create extension if not exists "pgcrypto";

-- Drop existing tables to ensure clean migration to username schema
drop table if exists public.reward_feedback cascade;
drop table if exists public.auth_challenges cascade;
drop table if exists public.payment_requests cascade;
drop table if exists public.cashback_rewards cascade;
drop table if exists public.nfts cascade;
drop table if exists public.transactions cascade;
drop table if exists public.loyalty_tiers cascade;
drop table if exists public.franchises cascade;
drop table if exists public.merchant_profiles cascade;
drop table if exists public.merchants cascade;
drop table if exists public.wallets cascade;
drop table if exists public.client_profiles cascade;
drop table if exists public.users cascade;

-- ============================================================
-- USERS — username is the primary key
-- ============================================================
create table if not exists public.users (
  username text primary key,
  email text unique,
  display_name text,
  google_sub text unique,
  password_hash text,
  password_salt text,
  role text not null default 'client' check (role in ('client', 'merchant', 'admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ============================================================
-- CLIENT PROFILES — keyed by username
-- ============================================================
create table if not exists public.client_profiles (
  username text primary key references public.users(username) on delete cascade,
  primary_wallet text,
  joined_date timestamptz not null default now(),
  loyalty_tier text not null default 'bronze',
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ============================================================
-- WALLETS — linked to username
-- ============================================================
create table if not exists public.wallets (
  id bigserial primary key,
  username text references public.users(username) on delete set null,
  wallet_address text not null unique,
  network text not null default 'testnet',
  provider text,
  is_primary boolean not null default true,
  managed_wallet boolean not null default false,
  encrypted_secret text,
  created_by text,
  created_at timestamptz not null default now()
);

-- ============================================================
-- MERCHANTS
-- ============================================================
create table if not exists public.merchants (
  id bigserial primary key,
  name text not null,
  wallet_address text not null,
  api_key text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.merchant_profiles (
  id bigint primary key,
  name text,
  cashback_pool_percentage numeric(10,4) not null default 2.0,
  max_cashback_limit numeric(18,6) not null default 0.05,
  weekly_distribution_rules jsonb not null default '{"base_rate":0.01,"tiers":[{"min_transactions":3,"rate":0.02},{"min_transactions":5,"rate":0.03},{"min_transactions":10,"rate":0.05}]}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into public.merchant_profiles (id, name)
values (1, 'Default Merchant')
on conflict (id) do nothing;

create table if not exists public.franchises (
  id bigserial primary key,
  merchant_id bigint not null references public.merchant_profiles(id) on delete cascade,
  franchise_name text not null,
  location text,
  created_at timestamptz not null default now()
);

-- ============================================================
-- LOYALTY TIERS
-- ============================================================
create table if not exists public.loyalty_tiers (
  id bigserial primary key,
  tier_name text not null unique,
  min_weekly_transactions int not null,
  cashback_rate numeric(10,4) not null,
  created_at timestamptz not null default now()
);

insert into public.loyalty_tiers (tier_name, min_weekly_transactions, cashback_rate)
values
  ('Bronze', 0, 0.01),
  ('Silver', 3, 0.02),
  ('Gold', 5, 0.03),
  ('Platinum', 10, 0.05)
on conflict (tier_name) do nothing;

-- ============================================================
-- TRANSACTIONS — wallet_address for chain data, username for identity
-- ============================================================
create table if not exists public.transactions (
  id bigserial primary key,
  wallet_address text not null,
  username text references public.users(username) on delete set null,
  merchant_id bigint not null default 1 references public.merchant_profiles(id),
  amount numeric(18,6) not null,
  signature text not null unique,
  network text not null default 'testnet',
  created_at timestamptz not null default now()
);

-- ============================================================
-- NFTS — wallet_address for chain data, username for identity
-- ============================================================
create table if not exists public.nfts (
  id bigserial primary key,
  wallet_address text not null,
  username text references public.users(username) on delete set null,
  nft_type text not null,
  mint_address text not null unique,
  metadata_uri text,
  created_at timestamptz not null default now()
);

-- ============================================================
-- CASHBACK REWARDS — wallet_address for chain data, username for identity
-- ============================================================
create table if not exists public.cashback_rewards (
  id bigserial primary key,
  wallet_address text not null,
  username text references public.users(username) on delete set null,
  merchant_id bigint not null references public.merchant_profiles(id),
  transaction_id bigint references public.transactions(id) on delete set null,
  transaction_signature text not null unique,
  transaction_amount numeric(18,6) not null,
  cashback_amount numeric(18,6) not null,
  cashback_rate numeric(10,6) not null default 0,
  reward_tier text not null,
  created_at timestamptz not null default now()
);

-- ============================================================
-- PAYMENT REQUESTS
-- ============================================================
create table if not exists public.payment_requests (
  reference text primary key,
  user_wallet text not null,
  store_id text not null,
  status text not null,
  qr_type text not null,
  amount numeric(18,6),
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

-- ============================================================
-- AUTH CHALLENGES
-- ============================================================
create table if not exists public.auth_challenges (
  id bigserial primary key,
  wallet_address text not null,
  nonce text not null,
  expires_at timestamptz not null,
  used boolean not null default false,
  used_at timestamptz,
  created_at timestamptz not null default now(),
  unique(wallet_address, nonce)
);

-- ============================================================
-- REWARD FEEDBACK
-- ============================================================
create table if not exists public.reward_feedback (
  id bigserial primary key,
  wallet_address text not null,
  merchant_id bigint not null references public.merchant_profiles(id),
  rating int not null check (rating between 1 and 5),
  message text,
  created_at timestamptz not null default now()
);

-- ============================================================
-- INDEXES
-- ============================================================
create index if not exists idx_wallets_username on public.wallets(username);
create index if not exists idx_transactions_username on public.transactions(username);
create index if not exists idx_transactions_wallet_created_at on public.transactions(wallet_address, created_at desc);
create index if not exists idx_transactions_merchant_created_at on public.transactions(merchant_id, created_at desc);
create index if not exists idx_cashback_username on public.cashback_rewards(username);
create index if not exists idx_cashback_wallet_created_at on public.cashback_rewards(wallet_address, created_at desc);
create index if not exists idx_nfts_username on public.nfts(username);
create index if not exists idx_nfts_wallet_created_at on public.nfts(wallet_address, created_at desc);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
alter table public.users enable row level security;
alter table public.client_profiles enable row level security;
alter table public.wallets enable row level security;
alter table public.merchants enable row level security;
alter table public.merchant_profiles enable row level security;
alter table public.franchises enable row level security;
alter table public.loyalty_tiers enable row level security;
alter table public.transactions enable row level security;
alter table public.nfts enable row level security;
alter table public.cashback_rewards enable row level security;
alter table public.payment_requests enable row level security;
alter table public.auth_challenges enable row level security;
alter table public.reward_feedback enable row level security;

-- Minimal read policies (adjust with your auth model in production)
do $$
begin
  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'client_profiles' and policyname = 'client_profiles_read'
  ) then
    create policy client_profiles_read on public.client_profiles for select using (true);
  end if;

  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'transactions' and policyname = 'transactions_read'
  ) then
    create policy transactions_read on public.transactions for select using (true);
  end if;

  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'nfts' and policyname = 'nfts_read'
  ) then
    create policy nfts_read on public.nfts for select using (true);
  end if;

  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'cashback_rewards' and policyname = 'cashback_rewards_read'
  ) then
    create policy cashback_rewards_read on public.cashback_rewards for select using (true);
  end if;

  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'merchant_profiles' and policyname = 'merchant_profiles_read'
  ) then
    create policy merchant_profiles_read on public.merchant_profiles for select using (true);
  end if;
end $$;
