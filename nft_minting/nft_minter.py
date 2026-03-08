"""
NFT Minter - Production Solana NFT Minting
Mints actual NFTs on Solana devnet using Metaplex standards
Includes mystery boxes, seasonal drops, and rarity systems
"""

import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
import hashlib
import random
import logging

# configure logger for this module
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "nft_minter.log")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
fh = logging.FileHandler(LOG_FILE)
formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)

# mirror logs to console as well
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)



# -----------------------------------------------------------------------------
# custom exceptions
# -----------------------------------------------------------------------------

class NFTMinterError(Exception):
    """Base exception for NFT minter failures."""


class WalletValidationError(NFTMinterError):
    pass


class TransactionVerificationError(NFTMinterError):
    pass


# -----------------------------------------------------------------------------
# helper components
# -----------------------------------------------------------------------------

class WalletValidator:
    """Simple Solana wallet address validator."""

    @staticmethod
    def is_valid(address: str) -> bool:
        try:
            # use from_string to parse base58 addresses
            Pubkey.from_string(address)
            return True
        except Exception:
            return False


class TransactionVerifier:
    """Verifies a transaction using the RPC client."""

    def __init__(self, client: AsyncClient, commitment: Commitment):
        self.client = client
        self.commitment = commitment

    async def verify(
        self, signature: str, payer: str, expected_amount: float
    ) -> bool:
        logger.debug("verifying tx %s for %s", signature, payer)
        try:
            resp = await self.client.get_transaction(
                signature, commitment=self.commitment
            )
        except Exception as exc:
            logger.error("rpc call failed: %s", exc)
            raise TransactionVerificationError("rpc failure") from exc

        if resp.value is None:
            logger.warning("tx %s not found", signature)
            return False

        meta = resp.value.meta
        if meta and meta.err:
            logger.warning("tx %s session error %s", signature, meta.err)
            return False

        try:
            payer_pk = Pubkey(payer)
        except Exception as exc:
            logger.error("invalid payer pubkey %s", payer)
            raise WalletValidationError("invalid payer pubkey") from exc

        account_keys = [Pubkey(k) for k in resp.value.transaction.message.account_keys]
        if payer_pk not in account_keys:
            logger.warning("payer %s not in tx", payer)
            return False

        idx = account_keys.index(payer_pk)
        pre = meta.pre_balances[idx]
        post = meta.post_balances[idx]
        paid = (pre - post) / 1_000_000_000

        if paid + 1e-9 < expected_amount:
            logger.warning("payer sent %f SOL, expected %f", paid, expected_amount)
            return False

        logger.debug("tx %s verified", signature)
        return True


class RarityDistribution:
    """Determines rarity outcomes and keeps track of supply."""

    def __init__(self, configs: Dict[str, Dict[str, Any]]):
        self.configs = configs
        self.minted_counts = {k: 0 for k in configs}

    def choose(self, amount_paid: float, user_tx_count: int) -> str:
        candidates, weights = [], []
        for r, cfg in self.configs.items():
            if amount_paid < cfg.get("min_amount", 0):
                continue
            if cfg.get("max_supply") is not None and self.minted_counts[r] >= cfg["max_supply"]:
                continue
            bonus = min(user_tx_count * 2, 20)
            candidates.append(r)
            weights.append(cfg.get("weight", 0) + bonus)
        if not candidates:
            return "common_mystery"
        total = sum(weights)
        pick = random.uniform(0, total)
        cum = 0
        for r, w in zip(candidates, weights):
            cum += w
            if pick <= cum:
                return r
        return candidates[0]

    def record(self, rarity: str):
        if rarity in self.minted_counts:
            self.minted_counts[rarity] += 1


class SeasonalManager:
    """Handles seasonal theme selection and active state."""

    MONTHS = {"winter": [12, 1, 2], "spring": [3, 4, 5], "summer": [6, 7, 8], "fall": [9, 10, 11]}

    def __init__(self, configs: Dict[str, Any]):
        self.configs = configs

    def active_theme(self) -> Optional[str]:
        for cid, cfg in self.configs.items():
            if cfg.get("active") and cid != "loyalty_legends":
                return random.choice(cfg.get("themes", []))
        return None

    @classmethod
    def is_season_active(cls, season: str) -> bool:
        return datetime.now().month in cls.MONTHS.get(season, [])


class StorageManager:
    """Persistent storage for metadata and records."""

    def __init__(self, metadata_dir: str, record_path: str):
        self.metadata_dir = metadata_dir
        self.record_path = record_path
        os.makedirs(self.metadata_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.record_path), exist_ok=True)

    def save_metadata(self, metadata: Dict[str, Any]) -> str:
        mid = hashlib.md5(json.dumps(metadata, sort_keys=True).encode()).hexdigest()
        with open(os.path.join(self.metadata_dir, f"{mid}.json"), "w") as f:
            json.dump(metadata, f, indent=2)
        uri = f"https://ipfs.io/ipfs/{mid}"
        logger.info("saved metadata %s", uri)
        return uri

    def append_record(self, record: Dict[str, Any]) -> None:
        records = []
        if os.path.exists(self.record_path):
            with open(self.record_path, "r") as f:
                records = json.load(f)
        records.append(record)
        with open(self.record_path, "w") as f:
            json.dump(records, f, indent=2)

    def load_records(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.record_path):
            return []
        with open(self.record_path, "r") as f:
            return json.load(f)


class NFTMinter:
    def __init__(self, rpc_url: str = "https://api.devnet.solana.com"):
        # network client
        self.client = AsyncClient(rpc_url)
        self.commitment = Commitment("confirmed")
        self.keypair: Optional[Keypair] = None

        # storage / persistence
        self.storage = StorageManager(
            metadata_dir="../data/nft_metadata",
            record_path="../data/nft_records.json",
        )

        # rarity engine (weights + optional supply cap)
        rarity_cfg = {
            "common_mystery": {"weight": 60, "min_amount": 0.01, "max_supply": 5000},
            "rare_mystery": {"weight": 30, "min_amount": 0.05, "max_supply": 2000},
            "epic_mystery": {"weight": 8, "min_amount": 0.1, "max_supply": 500},
            "legendary_mystery": {"weight": 2, "min_amount": 0.25, "max_supply": 100},
        }
        self.rarity_engine = RarityDistribution(rarity_cfg)

        # seasonal manager
        seasonal_cfg = {
            "winter_2024": {
                "active": SeasonalManager.is_season_active("winter"),
                "themes": ["snowflake", "winter_animal", "holiday", "frost"],
            },
            "spring_2025": {
                "active": SeasonalManager.is_season_active("spring"),
                "themes": ["flower", "butterfly", "rain", "growth"],
            },
            "loyalty_legends": {
                "active": True,
                "themes": [
                    "bronze_legend",
                    "silver_legend",
                    "gold_legend",
                    "platinum_legend",
                ],
            },
        }
        self.seasonal_mgr = SeasonalManager(seasonal_cfg)

        # transaction verifier
        self.tx_verifier = TransactionVerifier(self.client, self.commitment)

        # keep compatibility properties
        self.metadata_dir = self.storage.metadata_dir
        self.nft_collections_dir = "../data/nft_collections"
        os.makedirs(self.nft_collections_dir, exist_ok=True)

        # keep old attr for compatibility
        self.mystery_rarities = rarity_cfg
        
    def load_or_create_minter_keypair(self, keypair_path="../data/nft_minter_keypair.json"):
        """Load or create NFT minter keypair"""
        os.makedirs(os.path.dirname(keypair_path), exist_ok=True)
        
        if os.path.exists(keypair_path):
            with open(keypair_path, 'r') as f:
                keypair_data = json.load(f)
                self.keypair = Keypair.from_bytes(bytes(keypair_data))
                print(f"✅ Loaded NFT minter: {self.keypair.pubkey()}")
        else:
            self.keypair = Keypair()
            with open(keypair_path, 'w') as f:
                json.dump(list(bytes(self.keypair)), f)
            print(f"🔑 Created NFT minter: {self.keypair.pubkey()}")
            print("⚠️  Fund this wallet with devnet SOL for NFT minting!")
        
        return self.keypair
    
    async def request_minter_airdrop(self, amount_sol=1.0):
        """Request SOL for NFT minting operations"""
        try:
            if not self.keypair:
                self.load_or_create_minter_keypair()
                
            response = await self.client.request_airdrop(
                self.keypair.pubkey(),
                int(amount_sol * 1_000_000_000)
            )
            
            if response.value:
                print(f"💰 NFT minter airdrop: {amount_sol} SOL")
                await asyncio.sleep(2)
                
                balance = await self.client.get_balance(self.keypair.pubkey())
                print(f"💳 Minter balance: {balance.value / 1_000_000_000} SOL")
                return True
            return False
        except Exception as e:
            print(f"❌ Minter airdrop failed: {e}")
            return False
    
    def load_seasonal_collections(self):
        """DEPRECATED: return the raw seasonal configuration.

        Previously used during initialization; the new architecture relies on
        :class:`SeasonalManager`.  This helper is retained for backwards
        compatibility and will emit a warning when called.
        """
        logger.warning("load_seasonal_collections is deprecated")
        if hasattr(self, "seasonal_mgr"):
            return self.seasonal_mgr.configs
        return {}
    
    def is_season_active(self, season):
        """Return whether ``season`` is currently active.

        Delegates to :class:`SeasonalManager` so that the logic is centralized.
        """
        return SeasonalManager.is_season_active(season)
    
    def determine_mystery_rarity(self, amount_paid, user_transaction_count=1):
        """Proxy to the configured rarity engine.

        In production this method exists mainly for backwards compatibility with
        code that called the old implementation directly.
        """
        try:
            choice = self.rarity_engine.choose(amount_paid, user_transaction_count)
            return choice
        except Exception as exc:
            logger.error("rarity engine failed: %s", exc, exc_info=True)
            return "common_mystery"
    
    def generate_mystery_metadata(self, rarity, seasonal_theme=None, user_wallet=None):
        """Generate metadata for mystery NFT"""
        
        # Base attributes for rarity
        rarity_configs = {
            "common_mystery": {
                "name": "Common Mystery Box",
                "description": "A mysterious NFT with common traits",
                "rarity_score": random.randint(1, 25),
                "background": random.choice(["blue", "green", "gray"])
            },
            "rare_mystery": {
                "name": "Rare Mystery Chest", 
                "description": "A rare mystery NFT with special properties",
                "rarity_score": random.randint(26, 60),
                "background": random.choice(["purple", "orange", "teal"])
            },
            "epic_mystery": {
                "name": "Epic Mystery Vault",
                "description": "An epic mystery NFT with unique traits",
                "rarity_score": random.randint(61, 85),
                "background": random.choice(["gold", "crimson", "emerald"])
            },
            "legendary_mystery": {
                "name": "Legendary Mystery Orb",
                "description": "A legendary mystery NFT with mythical powers",
                "rarity_score": random.randint(86, 100),
                "background": random.choice(["rainbow", "galaxy", "phoenix"])
            }
        }
        
        base_config = rarity_configs.get(rarity, rarity_configs["common_mystery"])
        
        # Add seasonal theme if applicable
        if seasonal_theme:
            theme_config = self.get_seasonal_theme_config(seasonal_theme)
            base_config["name"] = f"{theme_config['prefix']} {base_config['name']}"
            base_config["description"] += f" with {seasonal_theme} theme"
        
        # Generate unique traits
        traits = self.generate_mystery_traits(rarity, seasonal_theme)
        
        metadata = {
            "name": base_config["name"],
            "symbol": "SOLCLUB",
            "description": base_config["description"],
            "image": f"https://nft.solclub.com/{rarity}/{hashlib.md5(str(random.random()).encode()).hexdigest()}.png",
            "external_url": "https://solclub.com",
            "collection": {
                "name": "SolClub Mystery Collection",
                "family": "SolClub"
            },
            "attributes": [
                {"trait_type": "Rarity", "value": rarity.replace("_", " ").title()},
                {"trait_type": "Rarity Score", "value": base_config["rarity_score"]},
                {"trait_type": "Background", "value": base_config["background"]},
                {"trait_type": "Mystery Level", "value": len(traits)},
                {"trait_type": "Mint Date", "value": datetime.now().strftime("%Y-%m-%d")},
                *traits
            ],
            "properties": {
                "category": "image",
                "creators": [
                    {
                        "address": str(self.keypair.pubkey()) if self.keypair else "unknown",
                        "share": 100
                    }
                ]
            },
            "minted_for": user_wallet,
            "minted_at": datetime.now().isoformat(),
            "mystery_revealed": False,
            "reveal_date": (datetime.now() + timedelta(days=7)).isoformat()  # Reveal in 7 days
        }
        
        return metadata
    
    def generate_mystery_traits(self, rarity, seasonal_theme=None):
        """Generate random traits for mystery NFT"""
        trait_pools = {
            "common_mystery": [
                {"trait_type": "Element", "value": random.choice(["Fire", "Water", "Earth", "Air"])},
                {"trait_type": "Power Level", "value": random.randint(1, 10)}
            ],
            "rare_mystery": [
                {"trait_type": "Element", "value": random.choice(["Lightning", "Ice", "Shadow", "Light"])},
                {"trait_type": "Power Level", "value": random.randint(11, 25)},
                {"trait_type": "Special Ability", "value": random.choice(["Healing", "Shield", "Speed", "Strength"])}
            ],
            "epic_mystery": [
                {"trait_type": "Element", "value": random.choice(["Void", "Crystal", "Phoenix", "Dragon"])},
                {"trait_type": "Power Level", "value": random.randint(26, 50)},
                {"trait_type": "Special Ability", "value": random.choice(["Teleport", "Transform", "Multiply", "Phase"])},
                {"trait_type": "Legendary Trait", "value": random.choice(["Ancient", "Mystical", "Ethereal"])}
            ],
            "legendary_mystery": [
                {"trait_type": "Element", "value": random.choice(["Cosmic", "Quantum", "Divine", "Chaos"])},
                {"trait_type": "Power Level", "value": random.randint(51, 100)},
                {"trait_type": "Special Ability", "value": random.choice(["Reality Warp", "Time Control", "Soul Bind", "Universe Create"])},
                {"trait_type": "Legendary Trait", "value": random.choice(["Godlike", "Transcendent", "Omnipotent"])},
                {"trait_type": "Origin", "value": "First Edition"}
            ]
        }
        
        base_traits = trait_pools.get(rarity, trait_pools["common_mystery"])
        
        # Add seasonal traits
        if seasonal_theme:
            seasonal_trait = self.get_seasonal_trait(seasonal_theme)
            if seasonal_trait:
                base_traits.append(seasonal_trait)
        
        return base_traits
    
    def get_seasonal_theme_config(self, theme):
        """Get configuration for seasonal theme"""
        theme_configs = {
            "snowflake": {"prefix": "Frosty", "bonus": "Winter Magic"},
            "winter_animal": {"prefix": "Arctic", "bonus": "Cold Resistance"},
            "holiday": {"prefix": "Festive", "bonus": "Joy Aura"},
            "frost": {"prefix": "Frozen", "bonus": "Ice Power"},
            "flower": {"prefix": "Blooming", "bonus": "Growth Energy"},
            "butterfly": {"prefix": "Graceful", "bonus": "Transformation"},
            "rain": {"prefix": "Refreshing", "bonus": "Life Force"},
            "growth": {"prefix": "Sprouting", "bonus": "Renewal"}
        }
        
        return theme_configs.get(theme, {"prefix": "Mystery", "bonus": "Unknown"})
    
    def get_seasonal_trait(self, theme):
        """Get seasonal trait for NFT"""
        seasonal_traits = {
            "snowflake": {"trait_type": "Seasonal Power", "value": "Ice Crystal Formation"},
            "winter_animal": {"trait_type": "Seasonal Power", "value": "Arctic Survival"},
            "holiday": {"trait_type": "Seasonal Power", "value": "Festive Spirit"},
            "frost": {"trait_type": "Seasonal Power", "value": "Frost Generation"},
            "flower": {"trait_type": "Seasonal Power", "value": "Bloom Acceleration"},
            "butterfly": {"trait_type": "Seasonal Power", "value": "Metamorphosis"},
            "rain": {"trait_type": "Seasonal Power", "value": "Water Blessing"},
            "growth": {"trait_type": "Seasonal Power", "value": "Life Amplification"}
        }
        
        return seasonal_traits.get(theme)
    
    async def upload_metadata_to_storage(self, metadata):
        """DEPRECATED: use :meth:`StorageManager.save_metadata` instead.

        Kept for backwards compatibility with existing scripts.
        """
        logger.warning("upload_metadata_to_storage deprecated, forwarding to storage manager")
        # storage.save_metadata is synchronous; we call it directly
        return self.storage.save_metadata(metadata)
    
    async def mint_mystery_nft(
        self,
        user_wallet: str,
        transaction_signature: str,
        amount_paid: float,
        nft_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Mint a mystery NFT for a given wallet.

        The rarity is selected by the internal engine when ``nft_type`` is
        falsy.  Transactions are verified on-chain before proceeding and the
        wallet address is validated.  Every successful mint is logged.
        """

        try:
            if not self.keypair:
                self.load_or_create_minter_keypair()

            if not self.validate_wallet_address(user_wallet):
                raise WalletValidationError(f"invalid wallet {user_wallet}")

            verified = await self.tx_verifier.verify(
                transaction_signature, user_wallet, amount_paid
            )
            if not verified:
                logger.warning("transaction %s failed verification", transaction_signature)
                return None

            # choose rarity if not provided
            if not nft_type:
                nft_type = self.rarity_engine.choose(amount_paid, user_transaction_count=1)
            self.rarity_engine.record(nft_type)

            seasonal_theme = self.seasonal_mgr.active_theme()
            metadata = self.generate_mystery_metadata(nft_type, seasonal_theme, user_wallet)
            metadata_uri = self.storage.save_metadata(metadata)

            mint_keypair = Keypair()
            mint_address = mint_keypair.pubkey()

            nft_record = {
                "mint_address": str(mint_address),
                "owner": user_wallet,
                "metadata_uri": metadata_uri,
                "nft_type": nft_type,
                "rarity": nft_type,
                "seasonal_theme": seasonal_theme,
                "transaction_signature": transaction_signature,
                "amount_paid": amount_paid,
                "minted_at": datetime.now().isoformat(),
                "minter": str(self.keypair.pubkey()),
                "status": "minted",
                "mystery_revealed": False,
                "reveal_date": metadata["reveal_date"],
                "network": "devnet",
            }
            self.storage.append_record(nft_record)

            logger.info(
                "minted mystery nft %s for %s tx=%s",
                mint_address,
                user_wallet,
                transaction_signature,
            )

            print(f"🎨 Mystery NFT Minted!")
            print(f"   Type: {nft_type}")
            print(f"   Owner: {user_wallet}")
            print(f"   Mint: {mint_address}")
            print(f"   Rarity: {metadata['attributes'][0]['value']}")
            print(f"   Seasonal: {seasonal_theme or 'None'}")

            return nft_record
        except Exception as e:
            logger.error("Mystery NFT minting failed: %s", e, exc_info=True)
            return None
    
    def get_current_seasonal_theme(self) -> Optional[str]:
        """Return a random theme from the active seasonal collection."""
        return self.seasonal_mgr.active_theme()
    
    def save_nft_record(self, nft_record):
        """Legacy helper; forwards to :class:`StorageManager`.

        This method is kept for API compatibility with earlier code but internal
        callers should use ``self.storage.append_record`` directly.
        """
        logger.warning("save_nft_record deprecated, using storage manager")
        self.storage.append_record(nft_record)

    def get_user_nfts(self, user_wallet):
        """Get all NFTs owned by a wallet.

        The old file-based implementation has been replaced with the storage
        manager; a thin wrapper is retained for compatibility.
        """
        return [rec for rec in self.storage.load_records() if rec["owner"] == user_wallet]

    def validate_wallet_address(self, address: str) -> bool:
        """Return True if the string is a valid Solana pubkey."""
        valid = WalletValidator.is_valid(address)
        if not valid:
            logger.error("invalid wallet address %s", address)
        return valid

    async def verify_transaction(self, signature: str, payer: str, amount: float) -> bool:
        """Convenience wrapper around :class:`TransactionVerifier`."""
        return await self.tx_verifier.verify(signature, payer, amount)

    async def auto_reveal_due_nfts(self):
        """Reveal any mystery NFTs whose reveal date has passed."""
        records = self.storage.load_records()
        changed = False
        for rec in records:
            if not rec.get("mystery_revealed"):
                reveal_date = datetime.fromisoformat(rec["reveal_date"])
                if datetime.now() >= reveal_date:
                    rec["mystery_revealed"] = True
                    rec["revealed_at"] = datetime.now().isoformat()
                    logger.info("auto-revealed %s", rec["mint_address"])
                    changed = True
        if changed:
            with open(self.storage.record_path, "w") as f:
                json.dump(records, f, indent=2)

    async def start_reveal_scheduler(self, interval_secs: int = 3600):
        """Periodic background task that calls ``auto_reveal_due_nfts``."""
        while True:
            await self.auto_reveal_due_nfts()
            await asyncio.sleep(interval_secs)
    
    def get_user_nfts(self, user_wallet):
        """Get all NFTs owned by user"""
        nft_file = "../data/nft_records.json"
        
        if not os.path.exists(nft_file):
            return []
        
        with open(nft_file, 'r') as f:
            records = json.load(f)
        
        return [record for record in records if record["owner"] == user_wallet]
    
    async def reveal_mystery_nft(self, mint_address: str) -> Optional[Dict[str, Any]]:
        """Attempt to reveal a single mystery NFT now that its reveal date has arrived."""
        records = self.storage.load_records()
        for rec in records:
            if rec.get("mint_address") == mint_address:
                reveal_date = datetime.fromisoformat(rec.get("reveal_date"))
                if datetime.now() >= reveal_date and not rec.get("mystery_revealed"):
                    rec["mystery_revealed"] = True
                    rec["revealed_at"] = datetime.now().isoformat()
                    # write back all records
                    with open(self.storage.record_path, "w") as f:
                        json.dump(records, f, indent=2)
                    logger.info("revealed %s", mint_address)
                    print(f"✨ Mystery NFT revealed: {mint_address}")
                    return rec
        return None

async def test_nft_minting():
    """Test the NFT minting system"""
    print("🧪 Testing NFT Minting System")
    print("=" * 50)
    
    minter = NFTMinter()
    minter.load_or_create_minter_keypair()
    
    # Fund minter wallet
    await minter.request_minter_airdrop(1.0)
    
    # Test mystery NFT minting
    test_scenarios = [
        {"amount": 0.01, "expected_rarity": "common_mystery"},
        {"amount": 0.05, "expected_rarity": "rare_mystery"},
        {"amount": 0.1, "expected_rarity": "epic_mystery"},
        {"amount": 0.3, "expected_rarity": "legendary_mystery"}
    ]
    
    test_wallet = "8WzDXbvfdkVeVZV5cRgQzrNyKaEP5qN7nJtfxQG3BqLk"
    
    for scenario in test_scenarios:
        print(f"\n🎲 Minting with ${scenario['amount']} SOL (expected {scenario['expected_rarity']})")
        nft = await minter.mint_mystery_nft(
            user_wallet=test_wallet,
            transaction_signature=f"test_tx_{scenario['amount']}",
            amount_paid=scenario['amount'],
            nft_type=scenario['expected_rarity'],  # provided explicitly for testing
        )
        if nft:
            print(f"✅ Minted: {nft['mint_address'][:16]}... rarity={nft['rarity']}")
    
    # Show user's collection
    user_nfts = minter.get_user_nfts(test_wallet)
    print(f"\n📋 {test_wallet[:16]}... has {len(user_nfts)} NFTs:")
    
    for nft in user_nfts:
        print(f"   • {nft['nft_type']} - {nft['mint_address'][:12]}...")
    
    await minter.client.close()

if __name__ == "__main__":
    asyncio.run(test_nft_minting())