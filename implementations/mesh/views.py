"""
MESH Protocol - View Layer
ViewDefinitions, reducers, boundary determinism (from Relay v2)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any, Callable

from .crypto import sha256, canonical_json, boundary_hash


class ReducerType(str, Enum):
    CHRONOLOGICAL = "chronological"
    REVERSE_CHRONOLOGICAL = "reverse_chronological"
    RANKED = "ranked"
    GROUPED = "grouped"
    CUSTOM = "custom"


class SourceKind(str, Enum):
    ACTOR = "actor"  # Events from specific actor
    FOLLOWS = "follows"  # Events from followed actors
    GROUP = "group"  # Events in a group
    TAG = "tag"  # Events with tag
    ALL = "all"  # All events (with filters)


@dataclass
class Source:
    """Source specification for a view."""
    kind: SourceKind
    actor_id: Optional[str] = None
    group_id: Optional[str] = None
    tag: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "actor_id": self.actor_id,
            "group_id": self.group_id,
            "tag": self.tag,
        }


@dataclass
class Filter:
    """Filter specification for a view."""
    exclude_actors: list[str] = field(default_factory=list)
    exclude_kinds: list[str] = field(default_factory=list)
    require_attestations: list[dict] = field(default_factory=list)
    exclude_attestations: list[dict] = field(default_factory=list)
    min_timestamp: Optional[datetime] = None
    max_timestamp: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "exclude_actors": self.exclude_actors,
            "exclude_kinds": self.exclude_kinds,
            "require_attestations": self.require_attestations,
            "exclude_attestations": self.exclude_attestations,
            "min_timestamp": self.min_timestamp.isoformat() if self.min_timestamp else None,
            "max_timestamp": self.max_timestamp.isoformat() if self.max_timestamp else None,
        }


@dataclass
class ViewDefinition:
    """
    Defines how to compute a feed/view.
    Same definition + same boundary = same result (determinism).
    """
    id: str
    owner: str  # entity_id
    version: int  # Must increment on update
    
    sources: list[Source]
    filters: list[Filter]
    reducer: ReducerType
    params: dict  # Reducer-specific params (limit, offset, etc.)
    
    created_at: datetime
    updated_at: datetime
    sig: bytes
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner": self.owner,
            "version": self.version,
            "sources": [s.to_dict() for s in self.sources],
            "filters": [f.to_dict() for f in self.filters],
            "reducer": self.reducer.value,
            "params": self.params,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "sig": self.sig.hex(),
        }


@dataclass
class ViewResult:
    """
    Result of executing a view.
    Includes boundary_hash for verification.
    """
    view_id: str
    view_version: int
    
    # Determinism
    boundary_hash: str  # hash(event_ids + actor_heads)
    result_hash: str  # hash(output)
    
    # Result
    event_ids: list[str]
    computed_at: datetime
    
    # Cache control
    cached: bool = False
    cache_expires: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "view_id": self.view_id,
            "view_version": self.view_version,
            "boundary_hash": self.boundary_hash,
            "result_hash": self.result_hash,
            "event_ids": self.event_ids,
            "computed_at": self.computed_at.isoformat(),
            "cached": self.cached,
            "cache_expires": self.cache_expires.isoformat() if self.cache_expires else None,
        }


class ViewEngine:
    """Executes view definitions."""
    
    def __init__(self, storage):
        self.storage = storage
        self._cache: dict[str, ViewResult] = {}
    
    async def execute(self, view_def: ViewDefinition, use_cache: bool = True) -> ViewResult:
        """Execute a view definition and return results."""
        
        # Check cache
        cache_key = f"{view_def.id}:{view_def.version}"
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached.cache_expires and cached.cache_expires > datetime.now():
                return cached
        
        # Gather events from sources
        event_ids = []
        actor_heads = {}
        
        for source in view_def.sources:
            if source.kind == SourceKind.ACTOR and source.actor_id:
                events = await self.storage.get_events_by_actor(source.actor_id)
                event_ids.extend([e.id for e in events])
                head = await self.storage.get_log_head(source.actor_id)
                if head:
                    actor_heads[source.actor_id] = head
            
            elif source.kind == SourceKind.FOLLOWS and source.actor_id:
                following = await self.storage.get_following(source.actor_id)
                for followed_id in following:
                    events = await self.storage.get_events_by_actor(followed_id)
                    event_ids.extend([e.id for e in events])
                    head = await self.storage.get_log_head(followed_id)
                    if head:
                        actor_heads[followed_id] = head
        
        # Apply filters
        for filt in view_def.filters:
            if filt.exclude_actors:
                events_to_check = await self.storage.get_events_batch(event_ids)
                event_ids = [e.id for e in events_to_check 
                           if e.actor not in filt.exclude_actors]
        
        # Apply reducer
        if view_def.reducer == ReducerType.CHRONOLOGICAL:
            events = await self.storage.get_events_batch(event_ids)
            events.sort(key=lambda e: e.ts)
            event_ids = [e.id for e in events]
        
        elif view_def.reducer == ReducerType.REVERSE_CHRONOLOGICAL:
            events = await self.storage.get_events_batch(event_ids)
            events.sort(key=lambda e: e.ts, reverse=True)
            event_ids = [e.id for e in events]
        
        # Apply limit
        limit = view_def.params.get("limit", 100)
        event_ids = event_ids[:limit]
        
        # Compute boundary hash (determinism)
        b_hash = boundary_hash(event_ids, actor_heads)
        
        # Compute result hash
        r_hash = sha256(canonical_json({"events": event_ids}))
        
        result = ViewResult(
            view_id=view_def.id,
            view_version=view_def.version,
            boundary_hash=b_hash,
            result_hash=r_hash,
            event_ids=event_ids,
            computed_at=datetime.now(),
            cached=False,
        )
        
        # Cache result
        self._cache[cache_key] = result
        
        return result
