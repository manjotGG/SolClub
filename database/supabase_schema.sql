-- SolClub Supabase migration schema
-- Apply in Supabase SQL editor.

create extension if not exists "pgcrypto";

create table if not exists public.users (
  id uuid primary key default gen_random_uuid(),
  email text unique,
  display_name text,
  role text not null check (role in ('client', 'merchant', 'admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.wallets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  wallet_address text not null unique,
  network text not null default 'testnet',
  provider text,
  is_primary boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.merchant_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  business_name text not null,
  cashback_pool_percentage numeric(6,4) not null default 0.0200,
  max_cashback_limit numeric(12,6) not null default 0.050000,
  weekly_distribution_rules jsonb not null default '{"base_rate": 0.01, "tiers": [{"min_transactions": 3, "rate": 0.02}, {"min_transactions": 5, "rate": 0.03}, {"min_transactions": 10, "rate": 0.05}]}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.franchises (
  id uuid primary key default gen_random_uuid(),
  merchant_profile_id uuid not null references public.merchant_profiles(id) on delete cascade,
  franchise_name text not null,
  location text,
  created_at timestamptz not null default now()
);

create table if not exists public.loyalty_tiers (
  id uuid primary key default gen_random_uuid(),
  tier_name text not null unique,
  min_weekly_transactions int not null,
  cashback_rate numeric(6,4) not null,
  created_at timestamptz not null default now()
);

create table if not exists public.transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete set null,
  merchant_profile_id uuid references public.merchant_profiles(id) on delete set null,
  wallet_address text not null,
  signature text not null unique,
  amount numeric(12,6) not null,
  network text not null default 'testnet',
  created_at timestamptz not null default now()
);

create table if not exists public.nfts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete set null,
  wallet_address text not null,
  transaction_id uuid references public.transactions(id) on delete set null,
  nft_type text not null,
  mint_address text not null unique,
  metadata_uri text,
  created_at timestamptz not null default now()
);

create table if not exists public.cashback_rewards (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete set null,
  wallet_address text not null,
  transaction_id uuid references public.transactions(id) on delete set null,
  merchant_profile_id uuid references public.merchant_profiles(id) on delete set null,
  cashback_amount numeric(12,6) not null,
  cashback_rate numeric(6,4) not null,
  reward_tier text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_transactions_wallet_created_at on public.transactions(wallet_address, created_at desc);
create index if not exists idx_transactions_merchant_created_at on public.transactions(merchant_profile_id, created_at desc);
create index if not exists idx_cashback_wallet_created_at on public.cashback_rewards(wallet_address, created_at desc);

alter table public.users enable row level security;
alter table public.wallets enable row level security;
alter table public.transactions enable row level security;
alter table public.nfts enable row level security;
alter table public.cashback_rewards enable row level security;
alter table public.merchant_profiles enable row level security;
alter table public.franchises enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'users' and policyname = 'users_self_select'
  ) then
    create policy users_self_select on public.users
      for select using (id = auth.uid());
  end if;

  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'wallets' and policyname = 'wallets_owner_select'
  ) then
    create policy wallets_owner_select on public.wallets
      for select using (user_id = auth.uid());
  end if;

  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'transactions' and policyname = 'transactions_owner_select'
  ) then
    create policy transactions_owner_select on public.transactions
      for select using (user_id = auth.uid());
  end if;

  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'nfts' and policyname = 'nfts_owner_select'
  ) then
    create policy nfts_owner_select on public.nfts
      for select using (user_id = auth.uid());
  end if;

  if not exists (
    select 1 from pg_policies where schemaname = 'public' and tablename = 'cashback_rewards' and policyname = 'cashback_owner_select'
  ) then
    create policy cashback_owner_select on public.cashback_rewards
      for select using (user_id = auth.uid());
  end if;
end $$;
