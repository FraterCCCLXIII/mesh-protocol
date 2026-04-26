"""
Fetch content attestation labels from the MESH moderation service (optional).
Only issuers in MESH_ATTESTATION_ISSUER_ALLOWLIST are surfaced to clients.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Set

LABEL_TYPES_BADGE = frozenset({"spam", "harassment", "nsfw", "misleading"})


def moderation_base_url() -> str:
    return (os.environ.get("MESH_MODERATION_URL") or "").rstrip("/")


def parse_issuer_allowlist() -> Set[str]:
    raw = os.environ.get("MESH_ATTESTATION_ISSUER_ALLOWLIST", "")
    return {x.strip() for x in raw.split(",") if x.strip()}


async def fetch_labels_for_subjects(
    subject_ids: List[str],
    allowlist: Set[str],
) -> Dict[str, List[dict]]:
    """
    For each content id, GET /api/subjects/{id}/labels on the moderation service.
    Returns map subject_id -> list of {type, issuer, id} (filtered).
    If URL missing or allowlist empty, returns {}.
    """
    base = moderation_base_url()
    if not base or not allowlist or not subject_ids:
        return {}

    try:
        import httpx
    except ImportError:
        return {}

    out: Dict[str, List[dict]] = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for sid in subject_ids:
            try:
                r = await client.get(f"{base}/api/subjects/{sid}/labels")
                if r.status_code != 200:
                    out[sid] = []
                    continue
                try:
                    data = r.json()
                except (ValueError, TypeError):
                    out[sid] = []
                    continue
                labels = data.get("labels") or []
                kept: List[dict] = []
                for a in labels:
                    issuer = a.get("issuer")
                    t = a.get("type")
                    if issuer not in allowlist:
                        continue
                    if t not in LABEL_TYPES_BADGE:
                        continue
                    if a.get("revoked"):
                        continue
                    claim: Dict[str, Any] = {}
                    if isinstance(a.get("claim"), str):
                        try:
                            claim = json.loads(a["claim"])
                        except (json.JSONDecodeError, TypeError):
                            claim = {}
                    elif isinstance(a.get("claim"), dict):
                        claim = a["claim"]
                    kept.append(
                        {
                            "id": a.get("id"),
                            "type": t,
                            "issuer": issuer,
                            "claim": claim,
                        }
                    )
                out[sid] = kept
            except Exception as e:
                out[sid] = []
                if os.environ.get("MESH_MODERATION_DEBUG"):
                    import sys

                    print(f"[moderation] label fetch failed for {sid}: {e}", file=sys.stderr)
    return out
