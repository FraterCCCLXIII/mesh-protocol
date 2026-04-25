"""
Cryptographic verification and deterministic ID helpers for the MESH FastAPI relay (main.py).

Delegates to protocol.py for Ed25519 verification and shared primitives. Content and log IDs
match the demo relay's historical scheme (canonical JSON / seq-based) as used in main.py.
"""
from __future__ import annotations

from protocol import (
    canonical_json,
    generate_entity_id,
    generate_link_id,
    sha256_hex,
    verify_signature,
)


def generate_content_id(content_dict: dict) -> str:
    """Deterministic content id from canonical JSON (demo relay schema)."""
    return sha256_hex(canonical_json(content_dict))[:48]


def generate_log_event_id(actor: str, seq: int) -> str:
    """Sequential log event id for sqlite-backed event log in main.py."""
    return sha256_hex(f"{actor}:{seq}".encode())[:48]


__all__ = [
    "canonical_json",
    "generate_content_id",
    "generate_entity_id",
    "generate_link_id",
    "generate_log_event_id",
    "sha256_hex",
    "verify_signature",
]
