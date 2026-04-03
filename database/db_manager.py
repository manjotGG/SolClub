import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from supabase import Client, create_client
except Exception:  # pragma: no cover
    Client = Any
    create_client = None


@dataclass
class SupabaseConfig:
    url: str
    key: str


class DBManager:
    """Supabase-first DB abstraction for gradual migration from SQLite."""

    def __init__(self, config: Optional[SupabaseConfig] = None):
        self.config = config or SupabaseConfig(
            url=os.getenv("SUPABASE_URL", ""),
            key=os.getenv("SUPABASE_SERVICE_KEY", ""),
        )
        self.client: Optional[Client] = None
        self._connect()

    def _connect(self):
        if not self.config.url or not self.config.key or create_client is None:
            self.client = None
            return
        self.client = create_client(self.config.url, self.config.key)

    def is_configured(self) -> bool:
        return self.client is not None

    def health_check(self) -> Dict[str, Any]:
        if not self.client:
            return {"status": "not_configured"}
        try:
            self.client.table("users").select("id").limit(1).execute()
            return {"status": "ok"}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    def upsert_user(self, user_payload: Dict[str, Any]):
        self._require_client()
        return self.client.table("users").upsert(user_payload).execute()

    def upsert_wallet(self, wallet_payload: Dict[str, Any]):
        self._require_client()
        return self.client.table("wallets").upsert(wallet_payload).execute()

    def create_transaction(self, transaction_payload: Dict[str, Any]):
        self._require_client()
        return self.client.table("transactions").insert(transaction_payload).execute()

    def create_nft_record(self, nft_payload: Dict[str, Any]):
        self._require_client()
        return self.client.table("nfts").insert(nft_payload).execute()

    def create_cashback_reward(self, cashback_payload: Dict[str, Any]):
        self._require_client()
        return self.client.table("cashback_rewards").insert(cashback_payload).execute()

    def list_user_transactions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        self._require_client()
        result = (
            self.client.table("transactions")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    def _require_client(self):
        if not self.client:
            raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY.")
