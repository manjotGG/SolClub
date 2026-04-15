# SolClub

## Introduction

SolClub is a Solana-native loyalty and rewards platform for merchants and users. It connects real Solana payments to loyalty progression, cashback rewards, NFT issuance, and live dashboard insights.

The product is designed to keep onboarding easy while still enabling Web3-native experiences.

Core ideas:

- real payments trigger real rewards
- wallet is supported but not forced at every step
- merchants get configurable reward controls and analytics
- users get clear reward visibility and progression
- marketplace interactions can extend NFT value after minting

## Product Basics

### What SolClub Does

- QR-based Solana payments
- loyalty tier progression
- cashback reward calculations
- NFT reward minting and ownership tracking
- user and merchant dashboards with live updates
- centralized auth and onboarding
- marketplace direction for SolClub-minted NFT buy/sell flows

### Primary Product Areas

- Authentication and onboarding
- Wallet connect and managed wallet support
- Client dashboard and reward visibility
- Merchant dashboard and business analytics
- QR payment and transaction detection
- Loyalty engine and NFT issuance
- Marketplace (pricing and history graph roadmap)

### Canonical Routes

- pages: `/auth`, `/login`, `/onboarding`, `/dashboard`
- auth APIs: `/api/auth/*`

## Quick Start

### Requirements

- Python environment
- Supabase project
- Solana RPC endpoint (recommended)

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
- `UI_URL`

### Run Locally

```bash
pip install -r requirements.txt
python main.py server
```

Open:

- `/auth`
- `/login`
- `/dashboard`

## Documentation Map

- Full PRD, HLD, and LLD: [architecture.md](architecture.md)
- QR payment reference: [qr_wallet/qr.md](qr_wallet/qr.md)
- Backend entry point: [main.py](main.py)

## Current Status

SolClub currently runs as a modular FastAPI backend with Supabase persistence, dashboard UI flows, and reward logic integrated across payments, loyalty, and NFT components.

Marketplace capabilities are now part of the product direction and are specified in detail in [architecture.md](architecture.md).
