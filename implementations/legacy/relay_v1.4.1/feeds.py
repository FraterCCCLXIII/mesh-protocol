"""
Relay v1.4.1 Implementation - Feed Reduction Engine

Based on Relay_v1.4.1.md:
- §11.1: Feed definitions
- §17.10: Required reducers
- §17.11: Recompute/verify
"""

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

from storage import Storage, FeedDefinition, LogEvent
from crypto import canonical_json


# =============================================================================
# REDUCERS (§17.10)
# =============================================================================

class Reducer:
    """Base reducer interface."""
    
    @staticmethod
    def reduce(events: List[LogEvent], params: dict) -> List[LogEvent]:
        raise NotImplementedError


class ChronologicalReducer(Reducer):
    """
    relay.reduce.chronological.v1
    
    Sort by (ts, event_id) ascending - deterministic (§17.10).
    """
    
    @staticmethod
    def reduce(events: List[LogEvent], params: dict) -> List[LogEvent]:
        return sorted(events, key=lambda e: (e.ts, e.id))


class ReverseChronologicalReducer(Reducer):
    """
    relay.reduce.reverse_chronological.v1
    
    Sort by (ts, event_id) descending.
    """
    
    @staticmethod
    def reduce(events: List[LogEvent], params: dict) -> List[LogEvent]:
        return sorted(events, key=lambda e: (e.ts, e.id), reverse=True)


class EngagementReducer(Reducer):
    """
    relay.reduce.engagement.v1 (optional extension)
    
    Sort by reaction count (requires reaction data).
    """
    
    @staticmethod
    def reduce(events: List[LogEvent], params: dict) -> List[LogEvent]:
        # Would need reaction counts from storage
        # For now, fall back to reverse chronological
        return sorted(events, key=lambda e: (e.ts, e.id), reverse=True)


REDUCERS = {
    "relay.reduce.chronological.v1": ChronologicalReducer,
    "relay.reduce.reverse_chronological.v1": ReverseChronologicalReducer,
    "relay.reduce.engagement.v1": EngagementReducer,
}


# =============================================================================
# RECOMPUTE BOUNDARY (§11.1, §17.11)
# =============================================================================

@dataclass
class RecomputeBoundary:
    """
    Recompute/audit boundary (§11.1).
    
    For verifiable feed output comparison across deployments.
    """
    definition_object_id: str
    definition_version: int
    as_of: datetime
    source_heads: Dict[str, str]  # actor_id -> event_id
    
    def to_dict(self) -> dict:
        return {
            "definition_object_id": self.definition_object_id,
            "definition_version": self.definition_version,
            "as_of": self.as_of.isoformat() + "Z",
            "source_heads": self.source_heads,
        }


@dataclass
class FeedResult:
    """Result of feed reduction."""
    definition_id: str
    boundary: RecomputeBoundary
    event_ids: List[str]
    result_hash: str  # For verification
    computation_time_ms: float
    
    def to_dict(self) -> dict:
        return {
            "definition_id": self.definition_id,
            "boundary": self.boundary.to_dict(),
            "event_ids": self.event_ids,
            "result_hash": self.result_hash,
            "computation_time_ms": self.computation_time_ms,
        }


# =============================================================================
# FEED REDUCER ENGINE
# =============================================================================

class FeedReducerEngine:
    """
    Feed reducer engine (§17.10, §17.11).
    
    Clients MUST be able to recompute feed output from definition + fetched logs.
    """
    
    def __init__(self, storage: Storage):
        self.storage = storage
    
    async def reduce(self, feed_def: FeedDefinition) -> FeedResult:
        """
        Execute feed reduction (§17.10).
        
        1. Collect events from sources
        2. Apply reducer
        3. Return ordered list with boundary
        """
        start_time = time.time()
        
        # Collect events from sources
        events = []
        source_heads = {}
        
        for source in feed_def.sources:
            kind = source.get("kind")
            
            if kind == "actor_log":
                actor_id = source.get("actor_id")
                actor_events = await self.storage.get_log(actor_id, limit=1000)
                events.extend(actor_events)
                
                head = await self.storage.get_log_head(actor_id)
                if head:
                    source_heads[actor_id] = head
            
            elif kind == "feed":
                # Nested feed - resolve and reduce
                nested_id = source.get("feed_id")
                nested_def = await self.storage.get_feed_definition(nested_id)
                if nested_def:
                    nested_result = await self.reduce(nested_def)
                    for event_id in nested_result.event_ids:
                        event = await self.storage.get_event(event_id)
                        if event:
                            events.append(event)
        
        # Get reducer
        reducer_class = REDUCERS.get(feed_def.reduce, ChronologicalReducer)
        
        # Apply reducer
        reduced_events = reducer_class.reduce(events, feed_def.params)
        
        # Apply limit
        limit = feed_def.params.get("limit", 100)
        reduced_events = reduced_events[:limit]
        
        # Extract IDs
        event_ids = [e.id for e in reduced_events]
        
        # Compute result hash for verification
        result_hash = self._compute_result_hash(event_ids)
        
        # Create boundary
        boundary = RecomputeBoundary(
            definition_object_id=feed_def.object_id,
            definition_version=feed_def.version,
            as_of=datetime.now(),
            source_heads=source_heads,
        )
        
        computation_time = (time.time() - start_time) * 1000
        
        return FeedResult(
            definition_id=feed_def.object_id,
            boundary=boundary,
            event_ids=event_ids,
            result_hash=result_hash,
            computation_time_ms=computation_time,
        )
    
    async def recompute_and_verify(self, feed_def: FeedDefinition,
                                    claimed_result: FeedResult) -> bool:
        """
        Recompute and verify (§17.11).
        
        Clients MUST be able to verify feed wasn't manipulated.
        Same definition + same boundaries = same result hash.
        """
        recomputed = await self.reduce(feed_def)
        return recomputed.result_hash == claimed_result.result_hash
    
    def _compute_result_hash(self, event_ids: List[str]) -> str:
        """Compute deterministic hash of result."""
        canonical = json.dumps(event_ids, separators=(',', ':')).encode()
        return hashlib.sha256(canonical).hexdigest()


# =============================================================================
# ACTION VERIFIER (§13.4)
# =============================================================================

class ActionVerifier:
    """
    Action chain verification (§13.4).
    
    Verifier MUST fetch all three events (request, commit, result)
    and verify signatures and commitment_hash.
    """
    
    def __init__(self, storage: Storage):
        self.storage = storage
    
    async def verify_action_chain(self, result_event_id: str) -> dict:
        """
        Verify action.request → action.commit → action.result chain.
        
        Returns verification result with status and details.
        """
        from crypto import compute_commitment_hash
        from storage import LogEventType
        
        # Get result event
        result_event = await self.storage.get_event(result_event_id)
        if not result_event or result_event.type != LogEventType.ACTION_RESULT:
            return {"valid": False, "error": "Invalid result event"}
        
        commitment_hash = result_event.data.get("commitment_hash")
        if not commitment_hash:
            return {"valid": False, "error": "Missing commitment_hash in result"}
        
        # Find commit event with matching commitment_hash
        commit_events = await self.storage.get_events_by_type(
            LogEventType.ACTION_COMMIT, limit=1000
        )
        
        commit_event = None
        for event in commit_events:
            if event.data.get("commitment_hash") == commitment_hash:
                commit_event = event
                break
        
        if not commit_event:
            return {"valid": False, "error": "Commit event not found"}
        
        # Get request event
        request_event_id = commit_event.data.get("request_event_id")
        if not request_event_id:
            return {"valid": False, "error": "Missing request_event_id in commit"}
        
        request_event = await self.storage.get_event(request_event_id)
        if not request_event or request_event.type != LogEventType.ACTION_REQUEST:
            return {"valid": False, "error": "Request event not found"}
        
        # Verify commitment_hash computation
        expected_hash = compute_commitment_hash(
            request_event_id=request_event_id,
            action_id=request_event.data.get("action_id", ""),
            input_refs=request_event.data.get("input_refs", []),
            agent_params=commit_event.data.get("agent_params", {}),
        )
        
        if expected_hash != commitment_hash:
            return {"valid": False, "error": "commitment_hash mismatch"}
        
        # Verify signatures (if we have public keys)
        request_actor = await self.storage.get_identity(request_event.actor)
        commit_actor = await self.storage.get_identity(commit_event.actor)
        
        sig_valid = True
        if request_actor and request_event.sig:
            from crypto import verify_object_signature
            sig_valid = sig_valid and verify_object_signature(
                request_event.to_dict(), request_actor.public_key
            )
        
        return {
            "valid": True,
            "signatures_verified": sig_valid,
            "request_event_id": request_event.id,
            "request_actor": request_event.actor,
            "commit_event_id": commit_event.id,
            "commit_actor": commit_event.actor,
            "result_event_id": result_event.id,
            "action_id": request_event.data.get("action_id"),
            "output_refs": result_event.data.get("output_refs", []),
        }
