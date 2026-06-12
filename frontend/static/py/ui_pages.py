"""Migrated from frontend/static/js/ui-pages.js.

This server-side Python module preserves the session helpers and request wrapper
from the original browser script, while the DOM-only helpers are stubbed because
there is no browser document/window runtime in Python.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import requests

SOLCLUB_ROLE_KEY = "solclub_role"
SOLCLUB_WALLET_KEY = "solclub_wallet"
AUTH_BASE = "/api/auth"

_SESSION_STORE: Dict[str, str] = {}


def _select(selector: str, root: Optional[Any] = None) -> Any:
    """Browser-only helper; this Python migration has no DOM runtime."""
    raise NotImplementedError("$(selector) is browser-only and is not available in this Python migration.")


def _select_all(selector: str, root: Optional[Any] = None) -> Any:
    """Browser-only helper; this Python migration has no DOM runtime."""
    raise NotImplementedError("$$(selector) is browser-only and is not available in this Python migration.")


globals()["$"] = _select
globals()["$$"] = _select_all


def pageId() -> str:
    """Browser-only helper; this Python migration has no document.body dataset."""
    raise NotImplementedError("pageId() is browser-only and is not available in this Python migration.")


def normalizeLabel(text: Any) -> str:
    """Browser-only helper; this Python migration has no DOM text nodes."""
    raise NotImplementedError("normalizeLabel(text) is browser-only and is not available in this Python migration.")


def findClickableLabel(node: Any) -> str:
    """Browser-only helper; this Python migration has no DOM node traversal."""
    raise NotImplementedError("find_clickable_label(node) is browser-only and is not available in this Python migration.")


def set_local_session(role: Optional[str], wallet: Optional[str]) -> None:
    if role:
        _SESSION_STORE[SOLCLUB_ROLE_KEY] = role
    if wallet:
        _SESSION_STORE[SOLCLUB_WALLET_KEY] = wallet


def clear_local_session() -> None:
    _SESSION_STORE.pop(SOLCLUB_ROLE_KEY, None)
    _SESSION_STORE.pop(SOLCLUB_WALLET_KEY, None)


def api_json(url: str, options: Optional[Dict[str, Any]] = None) -> Any:
    options = dict(options or {})
    headers = {"Content-Type": "application/json", **(options.pop("headers", {}) or {})}

    request_kwargs: Dict[str, Any] = {"headers": headers}
    request_kwargs.update(options)

    if "body" in request_kwargs:
        body_value = request_kwargs.pop("body")
        if isinstance(body_value, (dict, list)):
            request_kwargs["json"] = body_value
        else:
            request_kwargs["data"] = body_value

    with requests.Session() as session:
        response = session.request("GET" if "method" not in request_kwargs else request_kwargs.pop("method"), url, **request_kwargs)

    content_type = response.headers.get("content-type", "")
    data = response.json() if "application/json" in content_type else response.text

    if not response.ok:
        detail = data if isinstance(data, str) else (data.get("detail") if isinstance(data, dict) else json.dumps(data))
        raise RuntimeError(detail or f"Request failed ({response.status_code})")

    return data
