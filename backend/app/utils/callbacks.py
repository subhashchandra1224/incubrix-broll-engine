"""HMAC-SHA256 callback signing and delivery.

When a job has a ``callback_url`` and ``CALLBACK_HMAC_SECRET`` is set, the worker
signs a payload and POSTs it to the URL with the signature in the
``X-IncuBrix-Signature`` header (Integration Standard point 3).

The signature is HMAC-SHA256 over the canonical (order-stable) JSON of the
payload, so the receiver recomputes the same digest over the received body.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-IncuBrix-Signature"


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(payload: dict[str, Any], secret: str) -> str:
    """HMAC-SHA256(secret, canonical JSON of payload) as lowercase hex."""
    return hmac.new(secret.encode("utf-8"), _canonical(payload), hashlib.sha256).hexdigest()


def sign_bytes(body: bytes, secret: str) -> str:
    """HMAC-SHA256(secret, body) as lowercase hex. Used to sign the exact bytes sent."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def send(
    url: str,
    payload: dict[str, Any],
    secret: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 10.0,
) -> None:
    """POST the signed payload to the callback URL.

    A custom httpx.Client (with a mock transport) can be injected for tests.
    """
    body = _canonical(payload)
    headers = {SIGNATURE_HEADER: sign_bytes(body, secret), "Content-Type": "application/json"}
    own_client = client is None
    c = client or httpx.Client()
    try:
        resp = c.post(url, content=body, headers=headers, timeout=timeout)
        log.info("Callback to %s -> %s", url, resp.status_code)
    finally:
        if own_client:
            c.close()
