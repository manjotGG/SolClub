# SolClub - Solana NFT Loyalty System Architecture

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Current System Components](#2-current-system-components)
3. [Current Problem](#3-current-problem)
4. [Target Architecture](#4-target-architecture)
5. [Integration Plan](#5-integration-plan-step-by-step)
6. [Safety Rules](#6-safety-rules)
7. [Future Steps](#7-future-steps)

---

## 1. PROJECT OVERVIEW

SolClub is a **Solana-based NFT loyalty program** that rewards users with mystery NFTs when they make payments. The system creates a seamless experience where:

- **Users** scan QR codes to make payments via Solana Pay
- **Backend** automatically detects blockchain transactions
- **Loyalty Engine** assigns rarity based on user history
- **NFTs** are minted and delivered to user wallets

### Key Features
- ✅ Real Solana blockchain integration (devnet)
- ✅ Mystery NFT system with rarity tiers
- ✅ Automatic transaction detection
- ✅ Mobile wallet compatibility (Phantom, Solflare)
- ✅ Production-ready API with FastAPI

### Business Flow
```
User Payment → QR Scan → Solana Pay → Blockchain → Backend Detection → NFT Mint → User Wallet
```

---

## 2. CURRENT SYSTEM COMPONENTS

### Backend (Python - FastAPI)
**Location**: `main.py`, `backend/`

**Responsibilities**:
- Polls Solana devnet every **10 seconds** for new transactions
- Detects payments to merchant wallet
- Extracts user wallet address and payment amount
- Stores transaction records in **SQLite database**
- Provides REST API endpoints for mobile apps

**Key Files**:
- `main.py` - Main entry point and FastAPI server
- `database/db.py` - SQLite database operations
- `backend/test_api.py` - API testing utilities

### Loyalty Engine
**Location**: `loyalty_engine/`

**Responsibilities**:
- Assigns NFT rarity based on user transaction history
- Uses **weighted probability** for rarity distribution:
  - Common Mystery: 60%
  - Rare Mystery: 30%
  - Epic Mystery: 8%
  - Legendary Mystery: 2%
- Adjusts probabilities based on user activity level

**Key Files**:
- `loyalty_engine/loyalty_engine.py` - Core rarity logic
- `loyalty_engine/loyalty_engine.py::get_nft_rarity()` - Main rarity function

### OLD NFT SYSTEM (Python Simulation)
**Location**: `nft_minting/nft_minter.py`

**Current Behavior**:
- **NOT real blockchain minting**
- Simulates NFT creation in database
- Logs `"NFT minted successfully"` (misleading)
- Stores NFT records in JSON files
- Used for testing/development only

**Key Issues**:
- ❌ No real Solana transactions
- ❌ No actual NFTs created
- ❌ Confusing logs (appears real but isn't)

### NEW NFT SYSTEM (Metaplex - Production)
**Location**: `nft_engine/mint.js`

**Real Blockchain Minting**:
- ✅ Uses **Solana Web3.js + Metaplex SDK**
- ✅ Mints actual NFTs on **devnet**
- ✅ Uses **GitHub RAW metadata URLs** for rarity
- ✅ Takes wallet address + rarity as input
- ✅ Production-ready with proper error handling

**Metadata Structure**:
```
metadata/
├── common.json     → Common rarity metadata
├── mystery.json    → Rare rarity metadata
├── epic.json       → Epic rarity metadata
└── legendary.json  → Legendary rarity metadata
```

**Usage**:
```bash
node nft_engine/mint.js <wallet_address> <rarity>
```

---

## 3. CURRENT PROBLEM

### The Core Issue
The backend is currently calling the **OLD Python NFT simulation** instead of the **NEW Metaplex minting system**.

### What's Happening Now
```
Payment Detected → Backend → OLD Python Minter → DB Record → "NFT Minted" Log
```

### What's NOT Happening
```
❌ Real Solana NFT minting
❌ Actual blockchain transactions
❌ NFTs in user wallets
```

### Evidence of Problem
- Logs show `"NFT minted successfully"` but no real NFTs exist
- Users don't receive NFTs in their Phantom/Solflare wallets
- Backend calls `nft_minter.mint_mystery_nft()` (Python simulation)
- `mint.js` (real minting) is never executed

### Impact
- ❌ Misleading user experience
- ❌ No actual NFT rewards
- ❌ Broken loyalty program
- ❌ Production system appears to work but doesn't

---

## 4. TARGET ARCHITECTURE

### Desired Flow
```
User Payment
    ↓
Backend Detects Transaction
    ↓
Extract Wallet + Amount
    ↓
Loyalty Engine Assigns Rarity
    ↓
3-Second Delay (Devnet Stability)
    ↓
Call Node.js Metaplex Minter
    ↓
Real NFT Minted on Solana
    ↓
NFT Delivered to User Wallet
    ↓
Record in Database (for tracking)
```

### Key Requirements
- **Real blockchain minting** (not simulation)
- **Rarity-based metadata** from GitHub RAW URLs
- **Automatic triggering** on payment detection
- **No duplicate minting** (safety critical)
- **Non-blocking execution** (backend continues processing)
- **Clear logging** (distinguish DB vs blockchain operations)

### Integration Points
1. **Transaction Detection** → Keep existing (polling every 10s)
2. **Wallet Extraction** → Keep existing
3. **Rarity Assignment** → Keep existing loyalty engine
4. **NFT Minting** → **REPLACE** with Node.js subprocess call
5. **Database Recording** → Keep existing (but clarify it's tracking only)

---

## 5. INTEGRATION PLAN (STEP BY STEP)

### Phase 1: Preparation
**Goal**: Understand current system without breaking it

1. **Audit Current Flow**
   - Map where `nft_minter.mint_mystery_nft()` is called
   - Identify all places that log NFT minting
   - Document current database schema

2. **Test New System**
   - Verify `mint.js` works independently
   - Test all rarity types: `common`, `mystery`, `epic`, `legendary`
   - Confirm metadata URLs are accessible

### Phase 2: Core Integration

#### Step 1: Disable Old Python NFT Mint Function
**File**: `main.py` (in transaction_watcher function)

**Current Code**:
```python
nft_result = await nft_minter.mint_mystery_nft(...)
```

**New Code**:
```python
# DISABLED: Old Python simulation
# nft_result = await nft_minter.mint_mystery_nft(...)
print("ℹ️ Skipping old Python NFT simulation")
```

#### Step 2: Add Node.js Subprocess Call
**File**: `main.py`

**Add Import**:
```python
import subprocess
import asyncio
```

**New Function**:
```python
async def mint_nft_with_nodejs(wallet: str, rarity: str) -> bool:
    """Call Node.js minting script with proper error handling."""
    try:
        # 3-second delay for devnet stability
        await asyncio.sleep(3)

        # Call mint.js with wallet and rarity
        result = subprocess.run(
            ["node", "nft_engine/mint.js", wallet, rarity],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print(f"✅ Real NFT minted for {wallet[:12]}... (rarity: {rarity})")
            return True
        else:
            print(f"❌ NFT minting failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("❌ NFT minting timeout")
        return False
    except Exception as e:
        print(f"❌ NFT minting error: {e}")
        return False
```

#### Step 3: Replace Mint Call
**File**: `main.py` (in transaction_watcher)

**Replace**:
```python
# OLD: Python simulation
nft_result = await nft_minter.mint_mystery_nft(
    user_wallet=wallet,
    nft_type=rarity,
    transaction_signature=signature,
    amount_paid=amount
)

# NEW: Real blockchain minting
mint_success = await mint_nft_with_nodejs(wallet, rarity)
```

#### Step 4: Update Logging
**File**: `main.py`

**Current Logs** (Misleading):
```
"NFT minted successfully"
```

**New Logs** (Clear):
```
"✅ Real NFT minted for 8WzDXbvfdkVe... (rarity: epic)"
"ℹ️ Database record created for tracking"
```

#### Step 5: Add Duplicate Prevention
**File**: `main.py`

**Add Tracking**:
```python
# Track minted transactions to prevent duplicates
minted_transactions = set()

# Before minting:
if signature in minted_transactions:
    print(f"⏭️ Already minted for transaction {signature}")
    return

# After successful mint:
minted_transactions.add(signature)
```

### Phase 3: Testing & Validation

#### Step 6: Test Integration
1. Start backend: `python main.py server`
2. Make test payment with known wallet
3. Verify NFT appears in wallet
4. Check logs show real minting
5. Confirm database tracking works

#### Step 7: Error Handling
- Test with invalid wallets
- Test network failures
- Test duplicate transactions
- Verify backend continues running

### Phase 4: Production Deployment

#### Step 8: Gradual Rollout
- Deploy to staging first
- Monitor for 24 hours
- Verify all transactions mint NFTs
- Check user feedback

#### Step 9: Full Production
- Deploy to production
- Monitor logs and metrics
- Have rollback plan ready

---

## 6. SAFETY RULES

### Critical: DO NOT Modify
- ❌ **`mint.js`** - Core Metaplex logic
- ❌ **Transaction detection** - Polling every 10 seconds
- ❌ **Wallet extraction** - How user addresses are found
- ❌ **Database schema** - Existing tables and relationships
- ❌ **API endpoints** - Existing mobile app integrations

### Only Replace
- ✅ **NFT minting call** - Replace Python simulation with Node.js subprocess
- ✅ **Logging messages** - Make clear what's DB vs blockchain
- ✅ **Error handling** - Add proper subprocess error handling

### Keep Working
- ✅ **Transaction polling** - Continue every 10 seconds
- ✅ **Database operations** - Keep storing transaction records
- ✅ **API responses** - Mobile apps should see no changes
- ✅ **Loyalty calculations** - Rarity assignment logic unchanged

### Testing Requirements
- ✅ **Backward compatibility** - Old API calls still work
- ✅ **Error isolation** - Minting failures don't crash backend
- ✅ **Performance** - No significant latency increase
- ✅ **Logging** - Clear distinction between operations

---

## 7. FUTURE STEPS

### Phase 1: Enhanced Detection (Q2 2026)
- **Replace polling with webhooks** - Real-time transaction detection
- **Solana WebSocket integration** - Event-driven architecture
- **Reduce latency** from 10 seconds to <1 second

### Phase 2: Database Migration (Q3 2026)
- **Move from SQLite to Supabase** - Cloud database
- **Real-time sync** - Live dashboard updates
- **Backup & recovery** - Production-grade reliability

### Phase 3: Frontend Dashboard (Q4 2026)
- **Admin dashboard** - Monitor transactions & mints
- **User portal** - View NFT collection & history
- **Analytics** - Revenue & engagement metrics
- **Mobile app** - Native iOS/Android experience

### Phase 4: Advanced Features (2027)
- **NFT redemption system** - Trade loyalty points for rewards
- **Seasonal collections** - Limited-time NFT drops
- **Social features** - Leaderboards & achievements
- **Multi-chain support** - Ethereum, Polygon integration

### Technical Roadmap
```
2026 Q2: Event-driven detection
2026 Q3: Supabase migration
2026 Q4: Frontend dashboard
2027 Q1: Redemption system
2027 Q2: Multi-chain expansion
```

---

## Quick Reference

### Current Issues
- Backend calls Python simulation (not real minting)
- Users don't receive actual NFTs
- Misleading logs

### Target Solution
- Replace Python mint call with Node.js subprocess
- Add 3-second delay for stability
- Clear logging (DB vs blockchain)
- Duplicate prevention

### Files to Modify
- `main.py` - Replace mint call, add subprocess function

### Files to NOT Modify
- `mint.js` - Real minting logic
- `nft_minter.py` - Keep for reference
- All other existing files

### Testing Commands
```bash
# Test minting directly
node nft_engine/mint.js <wallet> common

# Start backend
python main.py server

# Check logs
tail -f logs/*.log
```

---

*This architecture document is for the SolClub Solana NFT loyalty system. Last updated: March 30, 2026*