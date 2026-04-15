# SolClub Architecture and Product Specification

## 1. Document Purpose

This document is the canonical technical and product specification for SolClub.

It consolidates:

- PRD-level requirements
- HLD (High-Level Design)
- LLD (Low-Level Design)
- module boundaries
- data model
- API contracts
- roadmap and constraints

The [README.md](README.md) remains the quick introduction and product basics guide.

## 2. PRD

## 2.1 Product Summary

SolClub is a Solana-native loyalty, rewards, and merchant analytics platform. It turns real payments into loyalty progression, cashback rewards, and NFT-based gamification.

The platform combines:

- blockchain payment verification
- merchant reward configuration
- user onboarding and authentication
- live dashboards
- Supabase-backed persistence
- marketplace experiences for SolClub-minted NFTs

## 2.2 Problem Statement

Current loyalty systems are either too centralized to be engaging or too Web3-heavy to be practical. SolClub bridges both worlds with usable onboarding, clear merchant tools, and on-chain reward proof.

## 2.3 Product Goals

1. Support QR-based Solana payments with reliable reward evaluation.
2. Support Google and wallet-based authentication.
3. Keep onboarding centralized and consistent.
4. Keep wallet setup optional after login.
5. Provide live merchant and client dashboards.
6. Persist all important state in Supabase.
7. Add marketplace capability for SolClub-minted NFTs.

## 2.4 Success Criteria

- successful auth never loops users back to `/auth`
- new users complete onboarding once and reach `/dashboard`
- existing users go directly to `/dashboard`
- wallet setup can be deferred and completed later
- dashboards reflect near real-time data
- transactions, rewards, and NFTs are stored consistently

## 2.5 Scope

In scope:

- Google OAuth login
- wallet connect and managed wallet creation
- centralized onboarding
- user and merchant dashboards
- loyalty progression
- cashback and NFT reward issuance
- marketplace discovery and redemption surfaces
- SolClub NFT buy/sell marketplace with demand-based pricing
- historical NFT price charting
- Supabase persistence
- SSE live updates

Out of scope for now:

- multi-chain support beyond Solana
- production mobile app
- fiat rails
- advanced fraud scoring
- full queue-first architecture migration

## 2.6 Personas

Customer/client needs:

- fast login
- optional wallet connection
- rewards and progress visibility
- transaction and NFT views
- marketplace discovery and participation

Merchant needs:

- onboarding and profile setup
- cashback controls
- analytics and feedback visibility
- NFT distribution visibility
- marketplace participation for curated listings

System operator/developer needs:

- clear module boundaries
- environment-driven config
- reliable persistence
- testable APIs
- gradual evolution path

## 2.7 User Journeys

Google login:

1. User starts Google auth.
2. Callback resolves identity.
3. Existing user goes to `/dashboard`.
4. New user goes to `/onboarding`.
5. Onboarding completes and redirects to `/dashboard`.

Wallet connect:

1. User connects wallet from auth page.
2. Backend checks wallet/account mapping.
3. Existing user goes to `/dashboard`.
4. New user goes to `/onboarding`.

Managed wallet create:

1. User creates new wallet.
2. Backend creates managed wallet.
3. User completes onboarding.
4. User lands on `/dashboard`.

Marketplace flow:

1. User or merchant lists a SolClub-minted NFT.
2. Listing is published with market price.
3. Buyers browse, filter, and inspect chart history.
4. Purchase transfers ownership and updates ledger.
5. Dashboard and marketplace analytics update.

## 2.8 Functional Requirements

Authentication:

- Google OAuth login
- wallet login and managed wallet creation
- username/email/password returning-user login
- signed cookie session persistence
- session inspection endpoint

Onboarding:

- single onboarding form for all new users
- captures profile, role, and optional wallet
- wallet users can set password credentials

Wallet management:

- connect existing wallet
- create managed wallet
- wallet setup is optional after login
- soft prompt for missing wallet on dashboard

Dashboards:

- client dashboard: tier, milestones, transactions, cashback, NFTs
- merchant dashboard: volume, unique clients, rewards, feedback

QR payments:

- create Solana Pay request and QR
- detect payment
- persist transaction
- evaluate cashback and NFT rewards

Real-time updates:

- SSE updates for dashboard and session-driven UI refresh

Marketplace:

- buy/sell SolClub-minted NFTs
- user-to-user and merchant-to-user listings
- demand-driven pricing (above or below mint value)
- historical price graph per NFT
- floor, volume, and trend metrics
- listing moderation and publishing workflow
- redemption and claim history where applicable

## 2.9 Non-Functional Requirements

Performance:

- near real-time data updates
- low-latency auth and onboarding paths

Reliability:

- controlled failure behavior when external providers fail
- no full-app crash on auth or minting errors

Security:

- secure signed session cookies
- protected secret handling
- no plaintext private key exposure where avoidable
- Supabase RLS enforcement

Scalability:

- current modular monolith is acceptable for current stage
- migrate toward event-driven background processing

## 3. HLD (High-Level Design)

## 3.1 System Layers

1. Web UI layer
2. FastAPI application layer
3. Authentication and onboarding layer
4. Loyalty and reward computation layer
5. Payment detection layer
6. NFT minting layer
7. Supabase persistence layer
8. Solana blockchain layer
9. Marketplace pricing and listing layer

## 3.2 HLD Data Flow

```text
Auth / Wallet / Google Login
    -> Session + Onboarding Decision
    -> Dashboard or Onboarding
    -> QR Payment or Marketplace Action
    -> Solana Transaction or Listing Event
    -> Backend Detection and Validation
    -> Loyalty/Marketplace Evaluation
    -> Supabase Write
    -> Live UI Update
```

## 3.3 Service Boundaries

- `main.py`: app bootstrap, middleware, router composition
- `backend/frontend_ui.py`: UI pages, auth/session APIs, SSE streams
- `backend/client_merchant_platform.py`: platform APIs, wallet/auth utilities
- `database/db.py`: data access layer and compatibility fallbacks
- `database/db_manager.py`: Supabase client management
- `loyalty_engine/loyalty_engine.py`: reward logic
- `qr_wallet/qr_generator.py`: Solana Pay QR generation
- `nft_engine/mint.js`: NFT minting integration

## 3.4 Architecture Style

Current:

- modular monolith
- API-driven frontend
- SSE for live updates
- polling-based transaction detection

Target:

- event-driven ingestion
- async workers for minting and reward operations
- stronger observability and retry policies

## 4. LLD (Low-Level Design)

## 4.1 Auth Module LLD

Responsibilities:

- create and validate sessions
- resolve onboarding requirement
- handle Google OAuth start/callback
- handle wallet connect/create and login/logout

Key details:

- session includes role, wallet, user reference, onboarding flags, timestamps
- successful auth routes to `/dashboard` or `/onboarding`

## 4.2 Onboarding Module LLD

Responsibilities:

- collect display name, email, role, wallet, credentials
- persist to `users`
- link wallet when provided
- clear onboarding requirement and redirect

## 4.3 Wallet Module LLD

Responsibilities:

- connect existing wallets
- create managed wallets
- persist wallet metadata
- support deferred wallet setup post-login

## 4.4 Dashboard Module LLD

Responsibilities:

- render role-aware dashboards
- hydrate and refresh data
- subscribe to SSE channels
- show wallet prompt when needed

## 4.5 Loyalty Module LLD

Responsibilities:

- compute tier progression
- compute cashback rate and amount
- compute NFT reward outcome and rarity

## 4.6 NFT Minting Module LLD

Responsibilities:

- invoke Node-based minting process
- persist mint address and metadata links
- sync minted NFT record to database

## 4.7 QR Module LLD

Responsibilities:

- build Solana Pay URL
- render QR code
- support payment attribution flow

## 4.8 Database Module LLD

Responsibilities:

- centralized Supabase access and CRUD operations
- compatibility behavior for schema drift
- user-wallet linking and analytics queries

## 4.9 Marketplace Module LLD

Responsibilities:

- NFT listing lifecycle: draft -> published -> sold -> settled
- buy/sell flows between users and merchants
- dynamic demand-aware pricing signals
- historical chart data generation and retrieval

Pricing logic inputs:

- mint baseline value
- recent sale velocity
- active listing count
- bid/ask spread
- wallet/merchant demand signals

Charting requirements:

- per-NFT historical price points
- rolling floor trend
- recent volume trend
- time ranges: 24h, 7d, 30d, all-time

## 5. Data Model

Core entities:

- `users`
- `wallets`
- `transactions`
- `nfts`
- `cashback_rewards`
- `merchant_profiles`
- `franchises`
- `loyalty_tiers`
- `auth_challenges`
- `reward_feedback`

Marketplace entities to add:

- `nft_listings`
- `nft_listing_events`
- `nft_sales`
- `nft_price_history`

Suggested marketplace schema fields:

- `nft_listings`: `id`, `nft_id`, `seller_user_id`, `seller_merchant_id`, `list_price`, `currency`, `status`, `created_at`, `updated_at`
- `nft_sales`: `id`, `listing_id`, `buyer_user_id`, `buyer_merchant_id`, `sale_price`, `tx_signature`, `created_at`
- `nft_price_history`: `id`, `nft_id`, `price`, `source`, `recorded_at`

## 6. API Design

Canonical auth API:

- `GET /api/auth/session`
- `GET /api/auth/onboarding-status`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/google/start`
- `GET /api/auth/google/callback`
- `POST /api/auth/session/start`
- `POST /api/auth/onboarding/complete`
- `POST /api/auth/wallet/connect`
- `POST /api/auth/wallet/create`

Canonical page routes:

- `GET /auth`
- `GET /login`
- `GET /onboarding`
- `GET /dashboard`

Marketplace API targets:

- `GET /api/marketplace/listings`
- `POST /api/marketplace/listings`
- `GET /api/marketplace/listings/{listing_id}`
- `POST /api/marketplace/listings/{listing_id}/buy`
- `GET /api/marketplace/nfts/{nft_id}/price-history`
- `GET /api/marketplace/metrics`

## 7. Roadmap

Phase 1: hardening and cleanup

- normalize all auth flows around `/api/auth/*`
- complete onboarding and dashboard quality pass

Phase 2: wallet UX improvements

- dashboard-based reconnect and wallet status widgets

Phase 3: event-driven ingestion

- reduce polling and introduce robust retry/backoff

Phase 4: production-ready security

- strengthen RLS and token policies
- audit logging and secret rotation

Phase 5: platform expansion

- segmentation, campaign presets, richer analytics

Phase 6: marketplace expansion

- listing creation and promotion tools
- search/filtering and analytics
- NFT pricing and charting capabilities

Phase 7: scalability infrastructure

- workers, caching, and event-stream processing

## 8. Risks and Constraints

- Solana RPC delays can impact reward and sale confirmation latency
- wallet provider behavior can affect signing reliability
- schema drift between old and new data stores can create edge cases
- polling is not ideal for high-volume production workloads
- cross-language runtime (Python + Node) increases operational complexity

## 9. Acceptance Criteria

- auth and onboarding route users correctly with no redirect loops
- wallet connect/create works for both new and existing users
- reward outputs are persisted consistently
- dashboards reflect live platform state
- marketplace can list, buy, and settle SolClub-minted NFTs
- each NFT exposes historical pricing graph data
- marketplace analytics expose floor, volume, and trend indicators
