"""
MESH View Layer (spec §9 / Appendix C) — home timeline request validation and cost records.

The relay exposes a named user-facing view: ``home_timeline`` (``GET /api/users/{id}/feed?view=home_timeline``).
Pathological or abusive parameters are rejected before hitting SQLite.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# Defaults aligned with MESH spec v1.1 §9.2 / Appendix C
DEFAULT_MAX_EXECUTION_TIME_MS = 5000
DEFAULT_MAX_EVENTS_SCANNED = 100_000
DEFAULT_MAX_RESULT_SIZE = 1000
# Pathological / DoS-style limits for this demo relay
MAX_TIMELINE_LIMIT = 200
MAX_TIMELINE_OFFSET = 20_000
MAX_FOLLOWS_FOR_FEED = 10_000


@dataclass
class ViewExecutionLimits:
    """Spec §9.2 style limits (documented; enforced partially on this relay)."""

    max_execution_time_ms: int = DEFAULT_MAX_EXECUTION_TIME_MS
    max_events_scanned: int = DEFAULT_MAX_EVENTS_SCANNED
    max_result_size: int = DEFAULT_MAX_RESULT_SIZE


HOME_TIMELINE_VIEW = "home_timeline"


@dataclass
class HomeTimelineCost:
    """Documented cost estimate (§9.3) for the home_timeline view."""

    view: str
    follow_count: int
    limit: int
    offset: int
    estimated_events_scanned: int
    attestation_lookups: int = 0
    est_time_ms: float = 0.0
    limits: ViewExecutionLimits = field(default_factory=ViewExecutionLimits)
    would_reject_appendix_c_plus_moderation: str = ""  # blank if under Appendix C + labels budget

    def to_dict(self) -> dict:
        d = {
            "view": self.view,
            "follow_count": self.follow_count,
            "limit": self.limit,
            "offset": self.offset,
            "estimated_events_scanned": self.estimated_events_scanned,
            "attestation_lookups": self.attestation_lookups,
            "est_time_ms": round(self.est_time_ms, 2),
            "max_execution_time_ms": self.limits.max_execution_time_ms,
            "max_events_scanned": self.limits.max_events_scanned,
        }
        if self.would_reject_appendix_c_plus_moderation:
            d["note"] = self.would_reject_appendix_c_plus_moderation
        return d


class ViewRejectionError(Exception):
    """Invalid or too-expensive view request (HTTP 400 / 413)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code
        self.detail = message


def validate_and_estimate_home_timeline(
    follow_count: int, limit: int, offset: int, include_labels: bool
) -> Tuple[int, int, HomeTimelineCost]:
    """
    Validate home_timeline parameters; return (effective_limit, effective_offset, cost).

    Raises:
        ViewRejectionError: pathological or out-of-bounds (§9.5 / abuse patterns).
    """
    if follow_count < 0:
        raise ViewRejectionError("Invalid follow count", 400)
    if follow_count > MAX_FOLLOWS_FOR_FEED:
        raise ViewRejectionError(
            f"Too many follow edges ({follow_count}); max {MAX_FOLLOWS_FOR_FEED} for this relay",
            413,
        )
    if limit < 1:
        raise ViewRejectionError("limit must be at least 1", 400)
    if limit > MAX_TIMELINE_LIMIT:
        raise ViewRejectionError(
            f"limit {limit} exceeds max {MAX_TIMELINE_LIMIT} (pathological or misconfigured client)",
            400,
        )
    if offset < 0:
        raise ViewRejectionError("offset must be non-negative", 400)
    if offset > MAX_TIMELINE_OFFSET:
        raise ViewRejectionError(
            f"offset {offset} exceeds max {MAX_TIMELINE_OFFSET} (pathological deep pagination)",
            400,
        )

    # Rough scan estimate (Appendix C style): O(scope × window); cap to max_events_scanned.
    scope = follow_count + 1  # include self
    window = min(limit + offset + 1, DEFAULT_MAX_RESULT_SIZE * 2)
    est_events = int(min(max(scope, 1) * window, DEFAULT_MAX_EVENTS_SCANNED))

    att_lookups = 0
    if include_labels:
        # One moderation subject lookup per feed row (§9.2 max_attestation_lookups)
        att_lookups = min(limit, DEFAULT_MAX_RESULT_SIZE)
        if att_lookups > 10_000:
            raise ViewRejectionError(
                "labels=1: attestation_lookups would exceed 10,000 (Appendix C); reduce limit",
                413,
            )

    t0 = time.perf_counter()
    _ = sum(range(min(limit, 100)))  # bound micro-work for est_time
    est_time_ms = (time.perf_counter() - t0) * 1000.0
    if est_time_ms < 0.01:
        est_time_ms = 0.01

    cost = HomeTimelineCost(
        view=HOME_TIMELINE_VIEW,
        follow_count=follow_count,
        limit=limit,
        offset=offset,
        estimated_events_scanned=est_events,
        attestation_lookups=att_lookups,
        est_time_ms=est_time_ms,
    )

    return limit, offset, cost


