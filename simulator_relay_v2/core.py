"""
Relay 2.0 Simulator - Core Implementation

Implements the two-layer architecture from Relay_v2.md:
- Truth Layer: Identity, Event, State, Attestation, Snapshot
- View Layer: ViewDefinition, Boundary, Reducers

Based on Relay 2.0 specification (v1.4-1 / v1.5 wire encoding)
"""

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
import base64


# =============================================================================
# TRUTH LAYER - IDENTITY
# =============================================================================

@dataclass
class Identity:
    """
    Identity (§8) - Public keys and actor_id.
    
    id = multihash(SHA-256(public_key))
    """
    id: str  # relay:actor:multihash
    public_key: bytes
    created_at: datetime = field(default_factory=datetime.now)
    sig: bytes = field(default_factory=bytes)

    def to_dict(self) -> dict:
        return {
            "kind": "relay.identity.v1",
            "id": self.id,
            "public_key": base64.b64encode(self.public_key).decode(),
            "created_at": self.created_at.isoformat(),
            "sig": base64.b64encode(self.sig).decode(),
        }

    @staticmethod
    def generate_actor_id(public_key: bytes) -> str:
        """Generate actor_id from public key (§4.3)."""
        hash_bytes = hashlib.sha256(public_key).digest()
        return f"relay:actor:{hash_bytes[:16].hex()}"

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))


# =============================================================================
# TRUTH LAYER - EVENT
# =============================================================================

class EventType(Enum):
    """Event types from Appendix B and C."""
    # Core events
    FOLLOW_ADD = "follow.add"
    FOLLOW_REMOVE = "follow.remove"
    STATE_COMMIT = "state.commit"
    STATE_DELETE = "state.delete"
    KEY_ROTATE = "key.rotate"
    
    # Membership events (v1.3)
    MEMBERSHIP_ADD = "membership.add"
    MEMBERSHIP_REMOVE = "membership.remove"
    TRUST_REVOKE = "trust.revoke"
    STATE_REVOKE = "state.revoke"
    
    # Action events (v1.4)
    ACTION_REQUEST = "action.request"
    ACTION_COMMIT = "action.commit"
    ACTION_RESULT = "action.result"
    
    # Content events
    POST = "post"
    REACTION = "reaction"
    COMMENT = "comment"


@dataclass
class Event:
    """
    Event (§10) - Immutable, append-only, content-addressed.
    
    Wire format uses: ts, prev (single parent), type, data
    2.0 sketch uses: parents (list), timestamp
    """
    id: str  # relay:event:multihash(content)
    actor: str  # relay:actor:...
    type: EventType
    data: dict
    parents: list[str] = field(default_factory=list)  # prev in v1 wire
    timestamp: datetime = field(default_factory=datetime.now)
    sig: bytes = field(default_factory=bytes)
    target: str | None = None  # For follow.*, membership.*, action.*

    def to_dict(self) -> dict:
        return {
            "kind": "relay.event.v1",
            "id": self.id,
            "actor": self.actor,
            "type": self.type.value,
            "data": self.data,
            "parents": self.parents,
            "timestamp": self.timestamp.isoformat(),
            "target": self.target,
            "sig": base64.b64encode(self.sig).decode(),
        }

    @staticmethod
    def compute_id(content: dict) -> str:
        """Compute content-addressed ID."""
        canonical = json.dumps(content, sort_keys=True, separators=(',', ':'))
        hash_bytes = hashlib.sha256(canonical.encode()).digest()
        return f"relay:event:{hash_bytes[:16].hex()}"

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))

    @property
    def prev(self) -> str | None:
        """v1 wire compatibility - single parent."""
        return self.parents[0] if self.parents else None


# =============================================================================
# TRUTH LAYER - STATE
# =============================================================================

class StateType(Enum):
    """State object types."""
    PROFILE = "relay.profile.v1"
    CHANNEL = "relay.channel.v1"
    FEED_DEFINITION = "relay.feed.definition.v1"
    POST = "relay.post.v1"
    SETTINGS = "relay.settings.v1"


@dataclass
class State:
    """
    State (§11) - Versioned, authoritative, mutable objects.
    
    Event chain is authoritative for audit.
    State is authoritative for reads.
    """
    id: str  # relay:obj:...
    actor: str
    type: StateType
    version: int
    payload: dict
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    sig: bytes = field(default_factory=bytes)

    def to_dict(self) -> dict:
        return {
            "kind": "relay.state.v1",
            "id": self.id,
            "actor": self.actor,
            "type": self.type.value,
            "version": self.version,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "sig": base64.b64encode(self.sig).decode(),
        }

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))


# =============================================================================
# TRUTH LAYER - ATTESTATION
# =============================================================================

class ClaimCategory(Enum):
    """Attestation claim categories (§6.2.0)."""
    TRUST = "trust"  # Identity or reputation claims
    CONTENT = "content"  # Labels, warnings
    VIEW = "view"  # Claims about computed View outputs


@dataclass
class Attestation:
    """
    Attestation (§6) - Claims that MUST NOT override Event/State facts.
    """
    id: str
    actor: str  # Attester
    claim: dict  # {category, type, ...}
    target: str  # What is being attested about
    created_at: datetime = field(default_factory=datetime.now)
    sig: bytes = field(default_factory=bytes)

    def to_dict(self) -> dict:
        return {
            "kind": "relay.attestation.v1",
            "id": self.id,
            "actor": self.actor,
            "claim": self.claim,
            "target": self.target,
            "created_at": self.created_at.isoformat(),
            "sig": base64.b64encode(self.sig).decode(),
        }

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))


# =============================================================================
# TRUTH LAYER - SNAPSHOT
# =============================================================================

@dataclass
class Snapshot:
    """
    Snapshot (§0.5) - Verifiable checkpoints.
    
    scope defines what's included.
    Two snapshots are comparable iff same scope, as_of, and ordering.
    """
    id: str
    scope: dict  # {types, actors, id_range, ...}
    as_of: datetime
    merkle_root: str
    object_count: int
    partial: bool = False

    def to_dict(self) -> dict:
        return {
            "kind": "relay.snapshot.v1",
            "id": self.id,
            "scope": self.scope,
            "as_of": self.as_of.isoformat(),
            "merkle_root": self.merkle_root,
            "object_count": self.object_count,
            "partial": self.partial,
        }


# =============================================================================
# VIEW LAYER - VIEW DEFINITION
# =============================================================================

class ReducerType(Enum):
    """Built-in reducer types (§17.10)."""
    CHRONOLOGICAL = "relay.reduce.chronological.v1"
    REVERSE_CHRONOLOGICAL = "relay.reduce.reverse_chronological.v1"
    ENGAGEMENT = "relay.reduce.engagement.v1"
    CUSTOM = "relay.reduce.custom.v1"


@dataclass
class ViewDefinition:
    """
    ViewDefinition (§11.1) - Signed State that names inputs and reduce function.
    
    MUST be implemented as State with type: relay.feed.definition.v1
    """
    id: str
    actor: str  # Curator
    version: int
    sources: list[dict]  # [{kind: "actor_log", actor_id: ...}, ...]
    reduce: ReducerType
    params: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    sig: bytes = field(default_factory=bytes)

    def to_dict(self) -> dict:
        return {
            "kind": "relay.state.v1",
            "type": "relay.feed.definition.v1",
            "id": self.id,
            "actor": self.actor,
            "version": self.version,
            "sources": self.sources,
            "reduce": self.reduce.value,
            "params": self.params,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))


# =============================================================================
# VIEW LAYER - BOUNDARY
# =============================================================================

@dataclass
class EventRange:
    """Per-actor event range for Boundary."""
    actor: str
    from_id: str | None = None
    to_id: str | None = None
    from_ts: datetime | None = None
    to_ts: datetime | None = None


@dataclass
class Boundary:
    """
    Boundary (§0.6) - Defines dataset over which View is evaluated.
    
    Valid for deterministic claims only if it describes a finite set of inputs.
    """
    view_definition_version: int
    event_ranges: list[EventRange] = field(default_factory=list)
    snapshot: str | None = None
    state_scope: dict | None = None
    nested_view_versions: dict[str, int] = field(default_factory=dict)
    as_of: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "view_definition_version": self.view_definition_version,
            "event_ranges": [
                {
                    "actor": er.actor,
                    "from_id": er.from_id,
                    "to_id": er.to_id,
                    "from_ts": er.from_ts.isoformat() if er.from_ts else None,
                    "to_ts": er.to_ts.isoformat() if er.to_ts else None,
                }
                for er in self.event_ranges
            ],
            "snapshot": self.snapshot,
            "state_scope": self.state_scope,
            "nested_view_versions": self.nested_view_versions,
            "as_of": self.as_of.isoformat(),
        }

    def canonical_json(self) -> str:
        """Canonical form for comparison (§0.6.1)."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':'))


# =============================================================================
# VIEW LAYER - VIEW RESULT
# =============================================================================

@dataclass
class ViewResult:
    """Result of View evaluation."""
    view_id: str
    boundary: Boundary
    items: list[str]  # Ordered list of event/state IDs
    result_hash: str
    computation_time_ms: float
    deterministic: bool = True  # False if couldn't fully verify


# =============================================================================
# STORAGE (RELAY)
# =============================================================================

class RelayStorage:
    """
    In-memory relay storage.
    
    Implements Truth Layer storage and indexing.
    """

    def __init__(self, relay_id: str = "relay:origin:default"):
        self.relay_id = relay_id
        
        # Truth Layer
        self.identities: dict[str, Identity] = {}
        self.events: dict[str, Event] = {}
        self.states: dict[str, State] = {}
        self.attestations: dict[str, Attestation] = {}
        self.snapshots: dict[str, Snapshot] = {}
        
        # View Layer
        self.view_definitions: dict[str, ViewDefinition] = {}
        
        # Indexes
        self._events_by_actor: dict[str, list[str]] = {}
        self._events_by_type: dict[EventType, list[str]] = {}
        self._states_by_actor: dict[str, list[str]] = {}
        self._states_by_type: dict[StateType, list[str]] = {}
        self._attestations_by_target: dict[str, list[str]] = {}
        self._actor_heads: dict[str, str] = {}  # Latest event per actor
        
        # Sequence
        self._seq = 0

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    # Identity operations
    def create_identity(self, identity: Identity) -> int:
        self.identities[identity.id] = identity
        return self.next_seq()

    def get_identity(self, actor_id: str) -> Identity | None:
        return self.identities.get(actor_id)

    # Event operations (§10, §16.3, §17.3-4)
    def append_event(self, event: Event) -> int:
        """POST /actors/{actor_id}/log - Append event."""
        self.events[event.id] = event
        
        # Index by actor
        if event.actor not in self._events_by_actor:
            self._events_by_actor[event.actor] = []
        self._events_by_actor[event.actor].append(event.id)
        
        # Index by type
        if event.type not in self._events_by_type:
            self._events_by_type[event.type] = []
        self._events_by_type[event.type].append(event.id)
        
        # Update head
        self._actor_heads[event.actor] = event.id
        
        return self.next_seq()

    def get_event(self, event_id: str) -> Event | None:
        """GET /actors/.../log/events/{event_id}."""
        return self.events.get(event_id)

    def get_actor_log(self, actor_id: str, limit: int = 100, 
                      since_id: str | None = None, 
                      since_ts: datetime | None = None) -> list[Event]:
        """GET /actors/{actor_id}/log - Get actor's event log."""
        event_ids = self._events_by_actor.get(actor_id, [])
        events = [self.events[eid] for eid in event_ids if eid in self.events]
        
        # Filter by since_id
        if since_id:
            try:
                idx = [e.id for e in events].index(since_id)
                events = events[idx + 1:]
            except ValueError:
                pass
        
        # Filter by since_ts
        if since_ts:
            events = [e for e in events if e.timestamp > since_ts]
        
        # Sort by timestamp, then id for determinism
        events.sort(key=lambda e: (e.timestamp, e.id))
        
        return events[:limit]

    def get_actor_head(self, actor_id: str) -> str | None:
        """Get latest event ID for actor."""
        return self._actor_heads.get(actor_id)

    # State operations (§11, §16.1, §17.5)
    def put_state(self, state: State) -> int:
        """PUT /actors/{actor_id}/state/..."""
        # Check version increment
        existing = self.states.get(state.id)
        if existing and state.version <= existing.version:
            raise ValueError(f"Version must increment: {state.version} <= {existing.version}")
        
        self.states[state.id] = state
        
        # Index by actor
        if state.actor not in self._states_by_actor:
            self._states_by_actor[state.actor] = []
        if state.id not in self._states_by_actor[state.actor]:
            self._states_by_actor[state.actor].append(state.id)
        
        # Index by type
        if state.type not in self._states_by_type:
            self._states_by_type[state.type] = []
        if state.id not in self._states_by_type[state.type]:
            self._states_by_type[state.type].append(state.id)
        
        return self.next_seq()

    def get_state(self, state_id: str) -> State | None:
        """GET /actors/.../state/..."""
        return self.states.get(state_id)

    def get_states_by_actor(self, actor_id: str) -> list[State]:
        state_ids = self._states_by_actor.get(actor_id, [])
        return [self.states[sid] for sid in state_ids if sid in self.states]

    # Attestation operations (§6)
    def create_attestation(self, attestation: Attestation) -> int:
        self.attestations[attestation.id] = attestation
        
        # Index by target
        if attestation.target not in self._attestations_by_target:
            self._attestations_by_target[attestation.target] = []
        self._attestations_by_target[attestation.target].append(attestation.id)
        
        return self.next_seq()

    def get_attestations_for(self, target: str) -> list[Attestation]:
        att_ids = self._attestations_by_target.get(target, [])
        return [self.attestations[aid] for aid in att_ids if aid in self.attestations]

    # ViewDefinition operations
    def put_view_definition(self, view_def: ViewDefinition) -> int:
        self.view_definitions[view_def.id] = view_def
        return self.next_seq()

    def get_view_definition(self, view_id: str) -> ViewDefinition | None:
        return self.view_definitions.get(view_id)

    # Snapshot operations
    def create_snapshot(self, snapshot: Snapshot) -> int:
        self.snapshots[snapshot.id] = snapshot
        return self.next_seq()

    def get_snapshot(self, snapshot_id: str) -> Snapshot | None:
        return self.snapshots.get(snapshot_id)

    # Metrics
    def get_metrics(self) -> dict:
        total_size = 0
        total_size += sum(i.size_bytes() for i in self.identities.values())
        total_size += sum(e.size_bytes() for e in self.events.values())
        total_size += sum(s.size_bytes() for s in self.states.values())
        total_size += sum(a.size_bytes() for a in self.attestations.values())
        total_size += sum(v.size_bytes() for v in self.view_definitions.values())
        
        event_type_counts = {}
        for etype, eids in self._events_by_type.items():
            event_type_counts[etype.value] = len(eids)
        
        return {
            "identity_count": len(self.identities),
            "event_count": len(self.events),
            "state_count": len(self.states),
            "attestation_count": len(self.attestations),
            "snapshot_count": len(self.snapshots),
            "view_definition_count": len(self.view_definitions),
            "total_objects": (
                len(self.identities) + len(self.events) + len(self.states) +
                len(self.attestations) + len(self.view_definitions)
            ),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "sequence": self._seq,
            "event_type_counts": event_type_counts,
            "actor_count": len(self._events_by_actor),
        }


# =============================================================================
# VIEW LAYER - REDUCER ENGINE
# =============================================================================

class ReducerEngine:
    """
    Executes reducers over event/state inputs (§17.10, §17.11).
    
    Deterministic only with valid Boundary.
    """

    def __init__(self, storage: RelayStorage):
        self.storage = storage

    def execute(self, view_def: ViewDefinition, boundary: Boundary) -> ViewResult:
        """Execute a view with given boundary."""
        start_time = time.time()
        
        # Validate boundary
        if not self._validate_boundary(view_def, boundary):
            return ViewResult(
                view_id=view_def.id,
                boundary=boundary,
                items=[],
                result_hash="",
                computation_time_ms=0,
                deterministic=False,
            )
        
        # Collect inputs from sources
        items = []
        for source in view_def.sources:
            source_items = self._collect_source(source, boundary)
            items.extend(source_items)
        
        # Apply reducer
        sorted_items = self._apply_reducer(items, view_def.reduce, view_def.params)
        
        # Extract IDs
        result_ids = [item.id for item in sorted_items]
        
        # Compute result hash
        result_hash = self._compute_hash(result_ids)
        
        computation_time = (time.time() - start_time) * 1000
        
        return ViewResult(
            view_id=view_def.id,
            boundary=boundary,
            items=result_ids,
            result_hash=result_hash,
            computation_time_ms=computation_time,
            deterministic=True,
        )

    def _validate_boundary(self, view_def: ViewDefinition, boundary: Boundary) -> bool:
        """Validate boundary has finite inputs (§0.6)."""
        # Check view definition version matches
        if boundary.view_definition_version != view_def.version:
            return False
        
        # Check all sources have bounded ranges
        for source in view_def.sources:
            if source.get("kind") == "actor_log":
                actor_id = source.get("actor_id")
                # Must have a range for this actor
                has_range = any(
                    er.actor == actor_id and (er.to_id or er.to_ts)
                    for er in boundary.event_ranges
                )
                # Or snapshot covers it
                if not has_range and not boundary.snapshot:
                    return False
        
        return True

    def _collect_source(self, source: dict, boundary: Boundary) -> list[Event]:
        """Collect items from a source."""
        kind = source.get("kind")
        
        if kind == "actor_log":
            actor_id = source.get("actor_id")
            
            # Find range for this actor
            event_range = None
            for er in boundary.event_ranges:
                if er.actor == actor_id:
                    event_range = er
                    break
            
            if event_range:
                events = self.storage.get_actor_log(
                    actor_id,
                    since_id=event_range.from_id,
                    since_ts=event_range.from_ts,
                )
                # Filter to range
                if event_range.to_ts:
                    events = [e for e in events if e.timestamp <= event_range.to_ts]
                if event_range.to_id:
                    try:
                        idx = [e.id for e in events].index(event_range.to_id)
                        events = events[:idx + 1]
                    except ValueError:
                        pass
                return events
            else:
                return self.storage.get_actor_log(actor_id)
        
        elif kind == "feed":
            # Nested view - resolve and execute
            nested_id = source.get("feed_id")
            nested_def = self.storage.get_view_definition(nested_id)
            if nested_def:
                nested_version = boundary.nested_view_versions.get(nested_id, nested_def.version)
                nested_boundary = Boundary(
                    view_definition_version=nested_version,
                    event_ranges=boundary.event_ranges,
                    as_of=boundary.as_of,
                )
                nested_result = self.execute(nested_def, nested_boundary)
                return [self.storage.get_event(eid) for eid in nested_result.items if self.storage.get_event(eid)]
        
        return []

    def _apply_reducer(self, items: list[Event], reducer: ReducerType, params: dict) -> list[Event]:
        """Apply reducer to sort/filter items (§17.10)."""
        if reducer == ReducerType.CHRONOLOGICAL:
            # Sort by (ts, event_id) - deterministic cross-actor order
            return sorted(items, key=lambda e: (e.timestamp, e.id))
        
        elif reducer == ReducerType.REVERSE_CHRONOLOGICAL:
            return sorted(items, key=lambda e: (e.timestamp, e.id), reverse=True)
        
        elif reducer == ReducerType.ENGAGEMENT:
            # Sort by engagement (reactions, etc.) - need to count attestations
            def engagement_score(event: Event) -> int:
                attestations = self.storage.get_attestations_for(event.id)
                reactions = [a for a in attestations if a.claim.get("type") == "reaction"]
                return len(reactions)
            
            return sorted(items, key=lambda e: (-engagement_score(e), e.timestamp, e.id))
        
        else:
            # Default: chronological
            return sorted(items, key=lambda e: (e.timestamp, e.id))

    def _compute_hash(self, result_ids: list[str]) -> str:
        """Compute deterministic hash of results."""
        canonical = json.dumps(result_ids, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def recompute_and_verify(self, view_id: str, claimed_result: ViewResult) -> bool:
        """
        Recompute view and verify against claimed result (§17.11).
        
        This is how clients verify a feed wasn't manipulated.
        """
        view_def = self.storage.get_view_definition(view_id)
        if not view_def:
            return False
        
        recomputed = self.execute(view_def, claimed_result.boundary)
        
        return recomputed.result_hash == claimed_result.result_hash


# =============================================================================
# ID GENERATORS
# =============================================================================

def generate_actor_id(name: str = None) -> str:
    if name:
        hash_bytes = hashlib.sha256(name.encode()).digest()
    else:
        hash_bytes = hashlib.sha256(uuid.uuid4().bytes).digest()
    return f"relay:actor:{hash_bytes[:16].hex()}"


def generate_event_id(content: dict = None) -> str:
    if content:
        canonical = json.dumps(content, sort_keys=True, separators=(',', ':'))
        hash_bytes = hashlib.sha256(canonical.encode()).digest()
    else:
        hash_bytes = hashlib.sha256(uuid.uuid4().bytes).digest()
    return f"relay:event:{hash_bytes[:16].hex()}"


def generate_state_id(actor: str, type_str: str) -> str:
    combined = f"{actor}:{type_str}:{uuid.uuid4().hex[:8]}"
    return f"relay:obj:{hashlib.sha256(combined.encode()).hexdigest()[:24]}"


def generate_attestation_id() -> str:
    return f"relay:att:{uuid.uuid4().hex[:16]}"


def generate_view_id(name: str) -> str:
    return f"relay:view:{name.lower().replace(' ', '-')}"
