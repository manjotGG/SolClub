"""Migrated from nft_engine/mint.js.

This module mirrors the original JavaScript NFT minting flow using the
available Solana Python tooling and logs errors with the same structure.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from solders.keypair import Keypair
    from solana.rpc.api import Client
except ImportError as exc:  # pragma: no cover - environment-specific
    raise ImportError(
        "Missing Solana dependencies for mint.py. Install with 'pip install solana solders'."
    ) from exc

try:
    from metaplex import Metaplex  # type: ignore
    from metaplex.foundation import keypair_identity  # type: ignore
except ImportError as exc:  # pragma: no cover - dependency may be unavailable
    raise ImportError(
        "Missing metaplex-python dependency for mint.py. Install with 'pip install metaplex-python'."
    ) from exc

logger = logging.getLogger(__name__)

KEYPAIR_PATH = Path(__file__).resolve().parent.parent / "data" / "nft_minter_keypair.json"


def load_keypair_from_file(file_path: Path) -> Any:
    raw = json.loads(Path(file_path).read_text(encoding="utf-8"))
    secret_key = raw

    if not isinstance(secret_key, list) or not secret_key:
        raise ValueError("Invalid keypair file format: expected non-empty array")

    return Keypair.from_bytes(bytes(secret_key))


def get_rarity_uri(rarity: str) -> str:
    uri: Optional[str] = None

    if rarity == "common":
        uri = "https://raw.githubusercontent.com/manjotGG/SolClub/8e47e480a03201059370a79a73bd59ea1e03baf0/metadata/common.json"
    if rarity == "mystery":
        uri = "https://raw.githubusercontent.com/manjotGG/SolClub/8e47e480a03201059370a79a73bd59ea1e03baf0/metadata/mystery.json"
    if rarity == "epic":
        uri = "https://raw.githubusercontent.com/manjotGG/SolClub/8e47e480a03201059370a79a73bd59ea1e03baf0/metadata/epic.json"
    if rarity == "legendary":
        uri = "https://raw.githubusercontent.com/manjotGG/SolClub/8e47e480a03201059370a79a73bd59ea1e03baf0/metadata/legendary.json"

    if not uri:
        raise ValueError(
            f"Unsupported rarity: {rarity}. Supported values are common, mystery, epic, legendary."
        )

    logger.info("Selected rarity: %s", rarity)
    logger.info("Selected URI: %s", uri)

    return uri


def mint_nft_to_wallet(recipient_wallet_address: str, rarity: str = "common") -> Dict[str, Any]:
    try:
        logger.info("Minting NFT...")
        logger.info("Requested rarity: %s", rarity)

        if not recipient_wallet_address:
            raise ValueError("recipient_wallet_address argument is required")

        recipient_public_key = recipient_wallet_address
        wallet_keypair = load_keypair_from_file(KEYPAIR_PATH)

        logger.info("Minter wallet: %s", wallet_keypair.pubkey())
        logger.info("Recipient wallet: %s", recipient_public_key)

        uri = get_rarity_uri(rarity)
        connection = Client("https://api.devnet.solana.com")
        balance = connection.get_balance(wallet_keypair.pubkey()).value

        logger.info("Minter balance: %s SOL", balance / 1_000_000_000)

        try:
            metaplex = Metaplex(connection)
            metaplex.use(keypair_identity(wallet_keypair))
        except Exception as exc:  # pragma: no cover - import/runtime guard
            raise ImportError(
                "Missing metaplex-python dependency for mint.py. Install with 'pip install metaplex-python'."
            ) from exc

        nft = metaplex.nfts().create(
            {
                "uri": uri,
                "name": "SolClub NFT",
                "seller_fee_basis_points": 0,
                "token_owner": recipient_public_key,
            }
        )

        logger.info("Mint address: %s", nft.address)
        logger.info("NFT Minted successfully")

        return nft
    except Exception as error:  # noqa: BLE001 - preserve error logging behavior
        logger.error("===== FULL ERROR =====")
        logger.error("%s", error)

        if getattr(error, "logs", None):
            logger.error("===== LOGS =====")
            logger.error("%s", error.logs)

        if getattr(error, "cause", None):
            logger.error("===== CAUSE =====")
            logger.error("%s", error.cause)

        raise


if __name__ == "__main__":
    recipient_arg = sys.argv[1] if len(sys.argv) > 1 else None
    rarity_arg = sys.argv[2] if len(sys.argv) > 2 else "common"

    logger.info("FILE STARTED")
    if not recipient_arg:
        logger.info("No recipient public key passed. To test call `python mint.py <recipientPublicKey> [rarity]`.")
    else:
        try:
            mint_nft_to_wallet(recipient_arg, rarity_arg)
        except Exception as error:
            logger.error("Error in main execution: %s", error)
            raise SystemExit(1)
