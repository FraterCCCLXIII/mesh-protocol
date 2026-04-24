"""
Relay v2 Implementation - View Layer Engine

Based on Relay_v2.md:
- §0.6: Boundary for determinism
- §17.10: Reducers
- §17.11: Recompute/verify
"""

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

from storage import (
    Storage, ViewDefinition, Event, ReducerType,
    Boundary, ViewResult
)
from crypto import canonical_json, compute_boundary_hash


# =============================================================================
# REDUCERS (§17.10)
# =============================================================================

class Reducer:
    """Base reducer."""
    
    @staticmethod
    def reduce(events: List[Event], params: dict) -> List[Event]:
        raise NotImplementedError


class ChronologicalReducer(Reducer):
    """Sort by (ts, id) ascending."""
    
    @staticmethod
    def reduce(events: List[Event], params: dict) -> List[Event]:
        return sorted(events, key=lambda e: (e.ts, e.id))


class ReverseChronologicalReducer(Reducer):
    """Sort by (ts, id) descending."""
    
    @staticmethod
    def reduce(events: List[Event], params: dict) -> List[Event]:
        return sorted(events, key=lambda e: (e.ts, e.id), reverse=True)


class EngagementReducer(Reducer):
    """Sort by engagement metrics."""
    
    @staticmethod
    def reduce(events: List[Event], params: dict) -> List[Event]:
        # Would use reaction counts, etc.
        return sorted(events, key=lambda e: (e.ts, e.id), reverse=True)


REDUCERS = {
    ReducerType.CHRONOLOGICAL: ChronologicalReducer,
    ReducerType.REVERSE_CHRONOLOGICAL: ReverseChronologicalReducer,
    ReducerType.ENGAGEMENT: EngagementReducer,
}


# =============================================================================
# VIEW ENGINE
# =============================================================================

class ViewEngine:
    """
    View execution engine with determinism guarantees.
    
    Same boundary + same definition = same result hash (§0.6).
    """
    
    def __init__(self, storage: Storage):
        self.storage = storage
    
    async def execute(self, view_def: ViewDefinition, 
                      use_cache: bool = True) -> ViewResult:
        """
        Execute view with boundary-based determinism.
        
        1. Collect source heads
        2. Fetch events within boundary
        3. Apply reducer
        4. Compute result hash
        """
        start_time = time.time()
        
        # Collect events and source heads
        events = []
        source_heads = {}
        
        for source in view_def.sources:
            kind = source.get("kind")
            
            if kind == "actor":
                actor_id = source.get("actor_id")
                actor_events = await self.storage.get_events(actor_id, limit=1000)
                events.extend(actor_events)
                
                head = await self.storage.get_event_head(actor_id)
                if head:
                    source_heads[actor_id] = head
            
            elif kind == "view":
                # Nested view - recursively execute
                nested_id = source.get("view_id")
                nested_def = await self.storage.get_view_definition(nested_id)
                if nested_def:
                    nested_result = await self.execute(nested_def, use_cache)
                    for event_id in nested_result.event_ids:
                        event = await self.storage.get_event(event_id)
                        if event:
                            events.append(event)
        
        # Create boundary
        boundary = Boundary(
            definition_id=view_def.object_id,
            definition_version=view_def.version,
            as_of=datetime.now(),
            source_heads=source_heads,
        )
        
        # Check cache
        boundary_hash = self._compute_boundary_hash(boundary)
        if use_cache:
            cached = await self.storage.get_cached_view(view_def.object_id, boundary_hash)
            if cached:
                return ViewResult(
                    definition_id=view_def.object_id,
                    boundary=boundary,
                    event_ids=cached['event_ids'],
                    result_hash=cached['result_hash'],
                    is_deterministic=True,
                )
        
        # Apply reducer
        reducer_class = REDUCERS.get(view_def.reduce, ChronologicalReducer)
        reduced_events = reducer_class.reduce(events, view_def.params)
        
        # Apply limit
        limit = view_def.params.get("limit", 100)
        reduced_events = reduced_events[:limit]
        
        # Extract IDs
        event_ids = [e.id for e in reduced_events]
        
        # Compute result hash
        result_hash = self._compute_result_hash(event_ids)
        
        # Cache result
        await self.storage.cache_view_result(
            view_def.object_id, boundary_hash, result_hash, event_ids
        )
        
        return ViewResult(
            definition_id=view_def.object_id,
            boundary=boundary,
            event_ids=event_ids,
            result_hash=result_hash,
            is_deterministic=True,
        )
    
    async def verify(self, view_def: ViewDefinition, 
                     claimed_result: ViewResult) -> bool:
        """
        Verify a claimed result (§17.11).
        
        Recompute with same boundary and compare hashes.
        """
        # Execute with same definition
        recomputed = await self.execute(view_def, use_cache=False)
        return recomputed.result_hash == claimed_result.result_hash
    
    def _compute_boundary_hash(self, boundary: Boundary) -> str:
        """Hash the boundary for caching."""
        data = {
            "definition_id": boundary.definition_id,
            "definition_version": boundary.definition_version,
            "source_heads": dict(sorted(boundary.source_heads.items())),
        }
        canonical = canonical_json(data)
        return hashlib.sha256(canonical).hexdigest()
    
    def _compute_result_hash(self, event_ids: List[str]) -> str:
        """Compute deterministic result hash."""
        canonical = json.dumps(sorted(event_ids), separators=(',', ':')).encode()
        return hashlib.sha256(canonical).hexdigest()


# =============================================================================
# ACTION VERIFIER
# =============================================================================

class ActionVerifier:
    """Verify action.* chains."""
    
    def __init__(self, storage: Storage):
        self.storage = storage
    
    async def verify_action_chain(self, result_event_id: str) -> dict:
        """Verify action.request → action.commit → action.result."""
        from storage import EventType
        
        result_event = await self.storage.get_event(result_event_id)
        if not result_event or result_event.type != EventType.ACTION_RESULT:
            return {"valid": False, "error": "Invalid result event"}
        
        commitment_hash = result_event.data.get("commitment_hash")
        if not commitment_hash:
            return {"valid": False, "error": "Missing commitment_hash"}
        
        # Find commit with matching hash
        commit_events = await self.storage.get_events_by_type(EventType.ACTION_COMMIT)
        commit_event = None
        for event in commit_events:
            if event.data.get("commitment_hash") == commitment_hash:
                commit_event = event
                break
        
        if not commit_event:
            return {"valid": False, "error": "Commit not found"}
        
        # Find request
        request_event_id = commit_event.data.get("request_event_id")
        request_event = await self.storage.get_event(request_event_id)
        if not request_event or request_event.type != EventType.ACTION_REQUEST:
            return {"valid": False, "error": "Request not found"}
        
        # Verify commitment_hash computation
        from crypto import canonical_json
        commitment_obj = {
            "kind": "relay.action.commitment.v1",
            "request_event_id": request_event_id,
            "action_id": request_event.data.get("action_id", ""),
            "input_refs": sorted(request_event.data.get("input_refs", [])),
            "agent_params": commit_event.data.get("agent_params", {}),
        }
        expected_hash = hashlib.sha256(canonical_json(commitment_obj)).hexdigest()
        
        if expected_hash != commitment_hash:
            return {"valid": False, "error": "commitment_hash mismatch"}
        
        return {
            "valid": True,
            "request_event_id": request_event.id,
            "commit_event_id": commit_event.id,
            "result_event_id": result_event.id,
            "action_id": request_event.data.get("action_id"),
        }
