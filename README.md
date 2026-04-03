# SolClub

SolClub is a Solana-based loyalty and reward platform for merchants and end users. It combines QR-based payments, loyalty progression, cashback rewards, NFT issuance, merchant analytics, and a browser-based dashboard served by the main FastAPI server.

This repository now has one main product document. The QR flow reference remains in [qr_wallet/qr.md](qr_wallet/qr.md).

## Product Summary

The end-to-end flow is:

1. A merchant creates a QR payment request.
2. A user scans the QR with a Solana wallet and pays on-chain.
3. The backend detects the payment, records the transaction, and evaluates loyalty rules.
4. Cashback and NFT reward decisions are stored in the database.
5. The user and merchant dashboards update with the latest reward and analytics data.

The system is built to support:

- real Solana payments
- merchant cashback pools
- user reward visibility
- loyalty-tier progression
- NFT reward tracking
- interactive dashboards for both merchant and user roles

## What the Product Does

For end users, SolClub shows:

- owned NFTs
- reward previews before paying
- cashback history
- total spending and transaction history
- loyalty tier and next milestone
- feedback submission for rewards and purchases

For merchants, SolClub shows:

- account creation and profile setup
- cashback pool configuration
- franchise registration
- merchant analytics
- NFT distribution tracking
- customer reward feedback
- reward tier breakdowns and transaction totals

## Current Architecture

The current runtime is organized as follows:

- Backend API and server lifecycle: [main.py](main.py)
- Multi-page UI router and SSE stream: [backend/frontend_ui.py](backend/frontend_ui.py)
- Supabase data helpers: [database/db.py](database/db.py)
- Supabase manager and schema support: [database/db_manager.py](database/db_manager.py), [database/supabase_schema.sql](database/supabase_schema.sql)
- Loyalty and reward logic: [loyalty_engine/loyalty_engine.py](loyalty_engine/loyalty_engine.py)
- QR generation and payment flow reference: [qr_wallet/qr_generator.py](qr_wallet/qr_generator.py), [qr_wallet/qr.md](qr_wallet/qr.md)
- Node-based NFT minting engine: [nft_engine/mint.js](nft_engine/mint.js)

## Pages Required for the End User Application

The user-facing application is split into clear pages. These are the pages the end user should have on each side.

### User-Side Pages

1. Client Dashboard
- Route: `/ui/client`
- Purpose: the main user landing page
- Shows: total cashback, transaction count, NFT count, loyalty tier, next milestone, reward preview
- Actions: refresh data, preview reward, view live updates

2. User Rewards Page
- Purpose: detailed reward history view
- Shows: cashback earned, reward tier history, recent transaction-linked rewards
- Actions: inspect reward events, compare loyalty changes over time

3. User NFTs Page
- Purpose: collection and ownership view
- Shows: owned NFTs, rarity/type breakdown, mint addresses, reveal status
- Actions: browse collection and inspect current rewards

4. User Transactions Page
- Purpose: transaction history view
- Shows: amount, merchant, signature, network, timestamp
- Actions: review spending and verify loyalty progression

5. Loyalty Progress Page
- Purpose: progression and gamification page
- Shows: current tier, next milestone, progress toward next tier, spending summary
- Actions: see what is needed to unlock the next reward level

6. Reward Feedback Page
- Purpose: feedback and quality scoring page
- Shows: merchant selector, rating, comment entry
- Actions: submit feedback tied to a merchant

7. Auth Page
- Route: `/ui/auth`
- Purpose: user login and wallet connection entry point
- Shows: wallet connect, managed wallet creation, Google OAuth start

### Merchant-Side Pages

1. Merchant Dashboard
- Route: `/ui/merchant`
- Purpose: merchant overview and live business health
- Shows: unique clients, transaction count, transaction volume, cashback volume, reward tier distribution
- Actions: refresh analytics, inspect NFT distribution, view live updates

2. Merchant Account Page
- Purpose: merchant onboarding and account creation
- Shows: merchant registration form, API key creation result, linked wallet
- Actions: create merchant account

3. Cashback Pool Page
- Purpose: reward policy configuration page
- Shows: cashback percentage, maximum cashback limit, weekly distribution rules
- Actions: create or update merchant reward pool settings

4. Franchise Registration Page
- Purpose: multi-location merchant setup
- Shows: franchise name and location form
- Actions: register franchise locations under a merchant

5. Merchant Analytics Page
- Purpose: live operational reporting
- Shows: transaction totals, spend volume, cashback volume, reward distribution, feedback
- Actions: inspect performance and loyalty outcomes

6. NFT Distribution Tracking Page
- Purpose: NFT issuance visibility
- Shows: recent NFTs distributed to customers, mint addresses, timestamps, wallet owners
- Actions: audit NFT reward flow and merchant reward campaigns

7. Merchant Feedback Page
- Purpose: customer feedback and reward quality view
- Shows: ratings, comments, timestamps
- Actions: review customer sentiment around rewards

## Current UI Routes

The following pages are implemented in the FastAPI UI layer:

- [Client dashboard](http://localhost:8000/ui/client)
- [Merchant dashboard](http://localhost:8000/ui/merchant)
- [Auth dashboard](http://localhost:8000/ui/auth)

Supporting UI API endpoints are served under `/ui/api/...` and live updates are streamed from `/ui/events`.

## Frontend Files

The UI is made of real HTML, CSS, and JavaScript files:

- [frontend/templates/base.html](frontend/templates/base.html)
- [frontend/templates/client.html](frontend/templates/client.html)
- [frontend/templates/merchant.html](frontend/templates/merchant.html)
- [frontend/templates/auth.html](frontend/templates/auth.html)
- [frontend/static/css/app.css](frontend/static/css/app.css)
- [frontend/static/js/client.js](frontend/static/js/client.js)
- [frontend/static/js/merchant.js](frontend/static/js/merchant.js)
- [frontend/static/js/auth.js](frontend/static/js/auth.js)

## Real-Time Updates

The UI uses server-sent events for live updates.

- Client stream: `/ui/events?channel=client&wallet=...&merchant_id=...&amount=...`
- Merchant stream: `/ui/events?channel=merchant&merchant_id=...`
- Auth stream: `/ui/events?channel=auth`

Why this matters:

- it avoids frequent manual refreshes
- it keeps reward and analytics panels current
- it gives the user a gamified, live dashboard experience

## QR Payment Flow

The QR flow reference is kept in [qr_wallet/qr.md](qr_wallet/qr.md). In summary:

1. The QR generator creates a Solana Pay payment URL.
2. A QR code is created from that URL.
3. A user scans the QR using Phantom, Solflare, or another Solana wallet.
4. The backend detects the merchant payment.
5. The loyalty engine evaluates cashback and NFT reward outcomes.
6. The system stores the transaction and reward records.
7. The UI updates the merchant and user views.

## Data and Persistence

The live system uses Supabase-backed helper functions.

Primary tracked entities:

- users
- wallets
- transactions
- nfts
- cashback_rewards
- merchant_profiles
- franchises
- loyalty_tiers
- auth_challenges
- reward_feedback

Relevant files:

- [database/db.py](database/db.py)
- [database/db_manager.py](database/db_manager.py)
- [database/supabase_schema.sql](database/supabase_schema.sql)
- [database/migrate_local_data_to_supabase.py](database/migrate_local_data_to_supabase.py)

## Authentication and Wallet Flow

Supported auth and wallet features:

- Google OAuth start flow
- wallet challenge and signature verification
- existing wallet connection
- managed wallet creation for testnet

Security-related environment variables:

- `APP_AUTH_SECRET`
- `WALLET_ENCRYPTION_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`

## Merchant Features

Merchant-side capabilities include:

- account creation
- franchise registration
- cashback pool configuration
- analytics dashboard
- NFT distribution tracking
- feedback review
- reward rule management

## User Features

User-side capabilities include:

- wallet connect
- auto-created managed wallet flow
- reward preview before payment
- owned NFT view
- cashback and reward history
- transaction history
- loyalty progress tracking
- feedback submission

## What We Completed Today

- Moved the frontend to the existing FastAPI server.
- Split the UI into separate user, merchant, and auth pages.
- Added live SSE updates.
- Mounted static frontend assets in the API server.
- Removed the separate Flask runtime.
- Consolidated project documentation into this single README.
- Verified user, merchant, and stream endpoints with live smoke checks.

## What Still Needs Work

- production-grade auth hardening
- full Google OAuth callback completion with real credentials
- final Supabase migration validation across all new tables
- stronger event-driven ingestion to reduce polling
- better QR reference matching for precise payment attribution
- deployment config for production hosting and reverse proxying

## How to Run the Web App

```bash
pip install -r requirements.txt
python main.py server
```

Then open:

- `http://localhost:8000/ui/client`
- `http://localhost:8000/ui/merchant`
- `http://localhost:8000/ui/auth`

If port 8000 is busy, stop the existing listener first, then start again.

Windows helper:

```bash
run_full_stack.bat
```

## Environment Variables

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

## Technical Notes

- The backend watcher currently polls the merchant wallet for transactions.
- The UI is responsive and uses real data from the backend APIs.
- The current structure is designed so merchant and user views stay separate but share one backend.
- The loyalty engine still drives reward tier logic, cashback calculation, and NFT rarity selection.

## Reference Files

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
