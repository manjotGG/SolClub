# SolClub PRD

## 1. Executive Summary

SolClub is a Solana-native loyalty, rewards, and merchant analytics platform. It turns real payments into loyalty progression, cashback rewards, and NFT-based gamification. The system combines a blockchain transaction pipeline, merchant reward configuration, user onboarding and authentication, live dashboards, and a Supabase-backed data layer.

This README is the foundation product document for the project. It supersedes older planning notes, architecture sketches, and temporary design files.

Primary product intent:

- make payment-linked loyalty feel instant and visible
- give merchants a configurable rewards engine with live analytics
- keep wallet and Google onboarding simple, optional where possible, and secure
- include a marketplace surface for quests, offers, and reward redemption
- persist all operational data in Supabase for reliability and future scaling

## 2. Product Vision

SolClub is designed as a hybrid Web2/Web3 loyalty system that sits between a merchant payment experience and a user reward experience. A customer pays with Solana, the backend recognizes the transaction, evaluates loyalty rules, and the platform records cashback and NFT rewards in the database while keeping dashboards live.

The product should feel like a modern loyalty layer, not a crypto admin panel.

### Vision Principles

- real payments drive real rewards
- onboarding should be friction-aware, not forced
- wallet is optional but supported everywhere
- merchants and users always see live state, not stale snapshots
- the backend remains the source of truth

## 3. Problem Statement

Current loyalty systems are either too centralized to be interesting or too Web3-heavy to be usable. SolClub solves that by combining:

- Solana payments
- loyalty tiering
- configurable cashback pools
- NFT rewards and rarity logic
- real-time merchant and user dashboards
- onboarding and auth that work for Google users, wallet users, and returning users

## 4. Goals and Success Criteria

### Product Goals

1. Support QR-based Solana payments that reliably evaluate loyalty rewards.
2. Support Google and wallet-based authentication.
3. Keep onboarding centralized and consistent.
4. Make wallet use optional after login, with soft prompts instead of hard blocks.
5. Provide live merchant and client dashboards backed by real data.
6. Persist all important state in Supabase.
7. Keep the architecture modular enough for future scale and migration.

### Success Criteria

- successful auth never loops users back to `/auth`
- a new user can complete onboarding once and reach `/dashboard`
- existing users go straight to `/dashboard`
- wallet setup can be deferred and later completed from dashboard
- merchant analytics and user loyalty data update in near real time
- QR transaction processing stores transactions, rewards, and NFTs consistently

## 5. Scope

### In Scope

- Google OAuth login
- wallet connect login
- managed wallet creation
- centralized onboarding form
- user and merchant dashboards
- loyalty tier progression
- cashback rewards
- NFT reward issuance and tracking
- marketplace discovery and redemption surfaces
- merchant configuration pages
- Supabase persistence and schema support
- SSE-based live updates

### Out of Scope for Now

- multi-chain support beyond Solana
- production mobile application
- fiat payment rails
- advanced fraud scoring beyond basic transaction checks
- full background queue infrastructure migration

## 6. Personas

### Customer / Client

Needs:

- quick login
- optional wallet connection
- visible rewards and progress
- transaction history
- NFT collection view

### Merchant

Needs:

- account onboarding
- cashback pool control
- franchise configuration
- customer analytics
- feedback and reward visibility

### System Operator / Developer

Needs:

- clear module boundaries
- environment-driven configuration
- reliable persistence
- testable backend routes
- room to evolve architecture without rewriting core logic

## 7. End-to-End User Journeys

### 7.1 Google Login Journey

1. User clicks Sign in with Google.
2. Google OAuth authenticates user.
3. Callback returns to backend.
4. Backend checks if user already exists in Supabase.
5. Existing user goes to `/dashboard`.
6. New user goes to `/onboarding`.
7. After onboarding, user goes to `/dashboard`.

### 7.2 Wallet Connect Journey

1. User clicks Connect Wallet.
2. User enters wallet in a modal.
3. Backend checks whether the wallet is already registered.
4. Existing user goes to `/dashboard`.
5. New user goes to `/onboarding`.
6. After onboarding, user goes to `/dashboard`.

### 7.3 Create New Wallet Journey

1. User clicks Create New Wallet.
2. Backend generates a new Solana wallet.
3. User is taken to onboarding.
4. User enters profile details.
5. Wallet is linked to the user in Supabase.
6. User goes to `/dashboard`.

### 7.4 Returning User Journey

1. User opens `/login`.
2. User enters wallet address or username/email plus password where applicable.
3. Backend resolves the account and session.
4. User goes directly to `/dashboard`.

## 8. Functional Requirements

## 8.1 Authentication

The auth layer must support:

- Google OAuth login
- wallet connect login
- managed wallet creation
- username/email/password return login
- session persistence via secure cookies
- session inspection via `/api/auth/session`

Auth rules:

- existing users go directly to dashboard
- new users are routed to onboarding
- no successful login may redirect back to `/auth`
- wallet setup must never be a hard gate to dashboard access

## 8.2 Centralized Onboarding

Onboarding collects:

- username / display name
- email if missing
- password for wallet-based users
- role
- optional wallet address

Onboarding requirements:

- single form for all new users
- invoked by Google first login if user is not yet fully registered
- invoked by new wallet connect/create users
- stores profile data to Supabase users table
- links wallet if present

## 8.3 Wallet Management

Wallet behavior:

- users may connect an existing wallet
- users may create a new Solana wallet
- wallet is optional after login
- wallet can be connected later from dashboard
- dashboard should show a soft prompt if wallet is missing

Wallet prompt behavior:

- non-blocking modal
- can be closed or skipped
- can be reopened later from profile/settings

## 8.4 User Dashboard

Client dashboard must show:

- loyalty tier
- next milestone
- total transactions
- total spent
- cashback total
- NFT count
- recent transactions
- recent rewards
- recent NFTs

## 8.5 Merchant Dashboard

Merchant dashboard must show:

- transaction volume
- cashback volume
- unique client count
- reward tier distribution
- recent NFT issuance
- customer feedback summary

Merchant pages include:

- cashback configuration
- franchise registration
- analytics dashboard
- NFT distribution tracking
- merchant feedback review

## 8.6 QR Payment Flow

QR payment flow must:

- generate a Solana Pay request
- render a QR code for scanning
- detect payment via transaction watcher or API confirmation
- write transaction to database
- evaluate cashback and NFT logic
- update dashboards live

## 8.7 Real-Time Updates

System should use SSE for live updates across client and merchant dashboards.

Live data sources:

- client reward snapshot
- merchant analytics snapshot
- auth/session state where relevant

## 8.8 Marketplace

Marketplace is a first-class product area in the UI shell and should be treated as part of the core SolClub experience, not as an afterthought.

Marketplace should support:

- browsing quests, offers, and featured merchant listings
- reward redemption and claim flows
- promo surfaces tied to loyalty tiers
- marketplace-specific analytics for merchants and the platform
- buying and selling NFTs minted by SolClub
- user-to-user and merchant-to-user NFT resale flows
- higher or lower pricing based on demand signals
- price history graphs for every listed NFT

Current UI references already include Marketplace navigation, an Arcade Marketplace transaction example, and a Free Marketplace Listing reward milestone.

Marketplace pricing model:

- SolClub-minted NFTs can be listed at market-driven prices above or below mint value
- prices should respond to demand, activity, and available supply signals
- the UI should show a historical price chart for each NFT so users can track value over time
- merchant listings and user listings should both be visible where allowed by policy

Future marketplace expansion should include:

- searchable listings
- filters by reward type, merchant, and tier
- moderation / publication workflow for merchant offers
- redemption ledger and claim history
- marketplace performance metrics
- NFT floor price, volume, and trend indicators

## 9. Non-Functional Requirements

### Performance

- near real-time UI updates are preferred
- watcher polling latency should be minimized over time
- auth and onboarding routes should remain fast and stateless except for session persistence

### Reliability

- backend must continue running if one external service is unavailable
- Google auth failures must not crash the app
- wallet minting failures must return controlled errors

### Security

- secure auth session cookies
- no private keys in plaintext where avoidable
- environment secrets only for sensitive config
- row-level security in Supabase

### Scalability

- current polling design is acceptable for local/dev and early stage
- future event/webhook model should replace polling where possible
- Supabase is the central data layer for scale migration

## 10. High-Level Design (HLD)

## 10.1 System Overview

The platform consists of the following layers:

1. Web UI layer
2. FastAPI application layer
3. Authentication and onboarding layer
4. Loyalty and reward computation layer
5. Transaction watcher / payment detection layer
6. NFT minting layer
7. Supabase persistence layer
8. Solana blockchain layer

### HLD Data Flow

```text
Auth / Wallet / Google Login
	-> Session + Onboarding Decision
	-> Dashboard or Onboarding
	-> QR Payment or Wallet Action
	-> Solana Transaction
	-> Backend Detection
	-> Loyalty Engine
	-> Cashback / NFT Decision
	-> Supabase Write
	-> Live UI Update
```

## 10.2 Service Boundaries

- `main.py` orchestrates app startup, middleware, and server lifecycle.
- `backend/frontend_ui.py` owns UI pages, auth/session APIs, and live streams.
- `backend/client_merchant_platform.py` owns platform/business APIs and Solana wallet/auth helpers.
- `database/db.py` owns database operations and compatibility fallbacks.
- `database/db_manager.py` owns the Supabase connection client.
- `loyalty_engine/loyalty_engine.py` owns reward logic.
- `qr_wallet/qr_generator.py` owns Solana Pay QR generation.
- `nft_engine/mint.js` owns Metaplex-based NFT minting.

## 10.3 Architecture Style

Current style:

- modular monolith
- event-driven UI updates via SSE
- polling-based blockchain detection
- API-driven frontend

Future style:

- more event-driven ingestion
- webhook or websocket-based transaction triggers
- asynchronous job queue for minting and reward computation

## 11. Low-Level Design (LLD)

## 11.1 Auth Module LLD

Responsibilities:

- create and validate sessions
- determine onboarding requirement
- handle Google OAuth start and callback
- handle wallet connect/create
- handle login and logout

Important behaviors:

- session stores role, wallet, user reference, onboarding flag, expiry
- Google callback normalizes redirect URI
- login endpoint checks user by wallet, email, or username where supported
- onboarding completion writes profile data and clears onboarding flag

## 11.2 Onboarding Module LLD

Responsibilities:

- collect user profile information
- store users table data
- attach wallet if present
- route to dashboard on completion

Fields:

- display name
- email
- role
- wallet address
- password for wallet-created users

## 11.3 Wallet Module LLD

Responsibilities:

- connect existing wallet
- create managed testnet wallet
- persist wallet record
- optionally link wallet to user

Important rules:

- wallet setup should never block dashboard access permanently
- wallet creation is optional and can be deferred

## 11.4 Dashboard Module LLD

Responsibilities:

- render client/merchant dashboards
- hydrate with live backend data
- subscribe to SSE stream
- provide wallet prompt if wallet is missing

## 11.5 Loyalty Engine LLD

Responsibilities:

- evaluate tier progression
- determine cashback rate
- determine NFT rarity
- compute next milestone

Future extension:

- merchant cashback pool configuration
- weekly transaction windows
- progressive cashback ladders
- dual reward outputs: cashback + NFT

## 11.6 NFT Minting Module LLD

Responsibilities:

- call Metaplex mint logic via Node.js
- generate mint address
- attach metadata URI
- persist NFT records

## 11.7 QR Payment Module LLD

Responsibilities:

- build Solana Pay request URL
- generate QR image
- let merchant display QR for payments

## 11.8 Database Module LLD

Responsibilities:

- central Supabase access
- CRUD helpers
- compatibility fallbacks for schema drift
- wallet/user linking
- reward and transaction storage

## 12. Modules and Responsibilities

### Core Modules

#### `main.py`
- server bootstrap
- middleware
- static mounts
- router registration
- lifecycle hooks

#### `backend/frontend_ui.py`
- auth UI routes
- onboarding routes
- dashboard routes
- SSE streams
- client and merchant UI API endpoints

#### `backend/client_merchant_platform.py`
- Google OAuth flow for platform-side integration
- wallet challenge / verify flows
- merchant and client platform APIs
- wallet funding and account setup

#### `database/db.py`
- all Supabase data access helpers
- user / wallet / transaction / NFT persistence
- merchant analytics access
- reward feedback and franchise helpers

#### `database/db_manager.py`
- Supabase client management
- health checks
- connection lifecycle

#### `database/supabase_schema.sql`
- canonical schema for Supabase tables

#### `loyalty_engine/loyalty_engine.py`
- reward tier evaluation
- cashback and NFT decision engine

#### `qr_wallet/qr_generator.py`
- QR creation for Solana Pay requests

#### `nft_engine/mint.js`
- Node-based NFT minting engine

### Supporting Modules

- `loyalty_engine/dashboard.py`
- `nft_minting/nft_minter.py`
- `nft_minting/nft_gallery.py`
- `qr_wallet/qr_viewer.py`
- `frontend/templates/*`
- `frontend/static/*`

## 13. Data Model

### `users`

Fields:

- `id`
- `email`
- `display_name`
- `google_sub`
- `password_hash`
- `password_salt`
- `role`
- `created_at`
- `updated_at`

### `wallets`

Fields:

- `id`
- `user_id`
- `wallet_address`
- `network`
- `provider`
- `is_primary`
- `managed_wallet`
- `encrypted_secret`
- `created_by`
- `created_at`

### `transactions`

Fields:

- `id`
- `wallet_address`
- `merchant_id`
- `amount`
- `signature`
- `network`
- `created_at`

### `nfts`

Fields:

- `id`
- `wallet_address`
- `nft_type`
- `mint_address`
- `metadata_uri`
- `created_at`

### `cashback_rewards`

Fields:

- `id`
- `wallet_address`
- `merchant_id`
- `transaction_id`
- `transaction_signature`
- `transaction_amount`
- `cashback_amount`
- `cashback_rate`
- `reward_tier`
- `created_at`

### `merchant_profiles`

Fields:

- `id`
- `name`
- `cashback_pool_percentage`
- `max_cashback_limit`
- `weekly_distribution_rules`

### `franchises`

Fields:

- `id`
- `merchant_id`
- `franchise_name`
- `location`

### `loyalty_tiers`

Fields:

- `tier_name`
- `min_weekly_transactions`
- `cashback_rate`

### `auth_challenges`

Fields:

- `wallet_address`
- `nonce`
- `expires_at`
- `used`

### `reward_feedback`

Fields:

- `wallet_address`
- `merchant_id`
- `rating`
- `message`

## 14. API Design

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

Dashboard and module APIs remain available under the UI and platform layers for backward compatibility and role-specific views.

## 15. Authentication and Session Model

Session should store:

- role
- wallet
- user reference
- onboarding required flag
- issued-at timestamp
- expiry timestamp

Rules:

- `/api/auth/session` must return the current session accurately
- every authenticated request should carry the session cookie
- successful auth must always route to `/dashboard` or `/onboarding`
- successful auth must never route back to `/auth`

## 16. Future Implementation Roadmap

### Phase 1: Hardening and Cleanup

- remove legacy `/ui/api/auth/*` usage from frontend
- keep backward compatibility only as a short-lived safety layer
- finalize auth and onboarding templates
- standardize all auth code paths around `/api/auth/*`

### Phase 2: Wallet UX Improvements

- move wallet connect into reusable dashboard modal
- let users reconnect wallet from profile/settings
- add wallet status card to dashboard header
- support "maybe later" wallet deferral everywhere

### Phase 3: Event-Driven Ingestion

- replace more polling with event/webhook style ingestion
- use job queue for mint operations and reward writes
- add backoff and retry policies for Solana RPC failures

### Phase 4: Production-Ready Security

- tighter RLS policies in Supabase
- short-lived auth tokens with refresh strategy
- audit logging for onboarding, wallet linking, and reward events
- secret rotation and deployment hardening

### Phase 5: Platform Expansion

- richer merchant segmentation
- reward campaign presets
- advanced analytics and exports
- multi-merchant / franchise reporting

### Phase 6: Marketplace Expansion

- launch marketplace browsing and redemption as a core destination
- add listing creation and promotion tools for merchants
- add quest and offer publishing workflows
- add marketplace search, filtering, and analytics

### Phase 7: Scalability and Infrastructure

- background workers
- caching layer
- transactional event stream architecture
- production reverse proxy and separate frontend deployment if needed

## 17. Risks and Constraints

- Solana RPC latency can delay reward finality.
- Wallet signature verification is sensitive to browser and provider behavior.
- SQLite legacy data may diverge from Supabase schema until all migrations are complete.
- Polling-based detection is acceptable early-stage but not ideal at scale.
- Cross-language Node minting adds operational overhead.

## 18. Operational Considerations

### Runtime Dependencies

- Python backend on port 8000
- Node.js for NFT minting
- Supabase as source of truth
- Solana testnet RPC

### Environment Variables

Required:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `APP_AUTH_SECRET`
- `WALLET_ENCRYPTION_KEY`

Recommended:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- `SOLANA_RPC_URL`
- `ALLOWED_HOSTS`
- `FORCE_HTTPS`
- `UI_URL`

### Local Run

```bash
pip install -r requirements.txt
python main.py server
```

Open:

- `/auth`
- `/login`
- `/dashboard`

## 19. Acceptance Criteria

The system is considered functionally ready when:

- Google login creates or resolves a Supabase user correctly.
- Existing users go straight to `/dashboard`.
- New users are routed to onboarding and then to `/dashboard`.
- Wallet connect/create can be skipped and revisited later.
- Auth page only shows the four required actions.
- Merchant and client dashboards use live data.
- QR payment flow stores transaction, reward, and NFT decisions.
- Supabase is the primary persistence layer.

## 20. Reference Modules

- [main.py](main.py)
- [backend/frontend_ui.py](backend/frontend_ui.py)
- [backend/client_merchant_platform.py](backend/client_merchant_platform.py)
- [database/db.py](database/db.py)
- [database/db_manager.py](database/db_manager.py)
- [database/supabase_schema.sql](database/supabase_schema.sql)
- [loyalty_engine/loyalty_engine.py](loyalty_engine/loyalty_engine.py)
- [qr_wallet/qr_generator.py](qr_wallet/qr_generator.py)
- [qr_wallet/qr.md](qr_wallet/qr.md)
- [nft_engine/mint.js](nft_engine/mint.js)

## 21. Legacy Documents

This README now replaces prior architecture and planning notes. The obsolete planning artifacts are removed from the repo so this file is the main source of product truth.

- [main.py](main.py)
- [backend/frontend_ui.py](backend/frontend_ui.py)
- [frontend/templates/client.html](frontend/templates/client.html)
- [frontend/templates/merchant.html](frontend/templates/merchant.html)
- [frontend/templates/auth.html](frontend/templates/auth.html)
- [frontend/static/js/client.js](frontend/static/js/client.js)
- [frontend/static/js/merchant.js](frontend/static/js/merchant.js)
- [frontend/static/js/auth.js](frontend/static/js/auth.js)
- [qr_wallet/qr.md](qr_wallet/qr.md)

## Summary

SolClub is now a unified Solana loyalty platform with a single FastAPI backend, a multi-page front end, Supabase-backed storage, merchant analytics, user rewards, real-time updates, and a clear QR payment flow reference. The README is the main handoff document for the product, and `qr_wallet/qr.md` remains as the detailed QR-specific reference.
