"""
Relay v1.4-1 / v1.5 Simulator - Core Implementation

Implements the wire protocol from Relay_v1.4.1.md:
- Identity (§8) with actor_id = multihash(SHA-256(pubkey))
- Log events (§10) with prev chain
- State objects (§11) with versioning
- Channels (§13) with channel_id from genesis
- Feed definitions (§11.1) with reducers (§17.10)
- Action events (§13.4): request, commit, result

Based on Relay v1.4-1 / v1.5 Stack Spec
"""

import hashlib
import json
import time
import uuid
import base64
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# =============================================================================
# IDENTIFIERS (§4.2, §4.3)
# =============================================================================

def multihash_sha256(data: bytes) -> str:
    """Create multihash with SHA-256 (code 0x12, 32-byte digest)."""
    digest = hashlib.sha256(data).digest()
    # Multihash: varint(0x12) + varint(32) + digest
    # Simplified: just use hex of digest with prefix
    return f"1220{digest.hex()}"


def generate_actor_id(public_key: bytes) -> str:
    """
    Generate actor_id from Ed25519 public key (§4.3).
    actor_id = relay:actor: + multihash(SHA-256(raw 32-byte pubkey))
    """
    mh = multihash_sha256(public_key)
    return f"relay:actor:{mh[:32]}"  # Truncate for readability


def generate_channel_id(genesis: dict) -> str:
    """
    Generate channel_id from genesis document (§4.3.1).
    channel_id = relay:channel: + multihash(SHA-256(canonical JSON of genesis))
    """
    canonical = json.dumps(genesis, sort_keys=True, separators=(',', ':'))
    mh = multihash_sha256(canonical.encode('utf-8'))
    return f"relay:channel:{mh[:32]}"


def generate_object_id(content: dict = None) -> str:
    """Generate content-addressed object_id (§4.2)."""
    if content:
        canonical = json.dumps(content, sort_keys=True, separators=(',', ':'))
        mh = multihash_sha256(canonical.encode('utf-8'))
        return f"relay:obj:{mh[:24]}"
    return f"relay:obj:{uuid.uuid4().hex[:24]}"


def generate_event_id() -> str:
    """Generate event_id for log events."""
    return f"relay:event:{uuid.uuid4().hex[:24]}"


# =============================================================================
# LOG EVENTS (§10)
# =============================================================================

class LogEventType(Enum):
    """Log event types from Appendix B and C."""
    # MVP types (Appendix B)
    FOLLOW_ADD = "follow.add"
    FOLLOW_REMOVE = "follow.remove"
    STATE_COMMIT = "state.commit"
    STATE_DELETE = "state.delete"
    KEY_ROTATE = "key.rotate"
    
    # v1.3 types (Appendix C)
    MEMBERSHIP_ADD = "membership.add"
    MEMBERSHIP_REMOVE = "membership.remove"
    TRUST_REVOKE = "trust.revoke"
    STATE_REVOKE = "state.revoke"
    
    # v1.4 action types (Appendix C, §13.4)
    ACTION_REQUEST = "action.request"
    ACTION_COMMIT = "action.commit"
    ACTION_RESULT = "action.result"
    
    # Content types (common usage)
    POST = "post"
    REACTION = "reaction"


@dataclass
class LogEvent:
    """
    Log event (§10) - Immutable, append-only.
    
    Wire format uses: type, data, ts, prev, sig
    """
    id: str
    actor: str  # actor_id
    type: LogEventType
    data: dict
    ts: datetime  # RFC 3339 timestamp
    prev: str | None  # Previous event in chain (null for genesis)
    sig: bytes = field(default_factory=bytes)
    target: str | None = None  # For follow.*, membership.*, action.*
    expires_at: datetime | None = None  # v1.5 optional

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "actor": self.actor,
            "type": self.type.value,
            "data": self.data,
            "ts": self.ts.isoformat() + "Z",
            "prev": self.prev,
            "sig": base64.b64encode(self.sig).decode() if self.sig else None,
        }
        if self.target:
            result["target"] = self.target
        if self.expires_at:
            result["expires_at"] = self.expires_at.isoformat() + "Z"
        return result

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))


# =============================================================================
# STATE OBJECTS (§11)
# =============================================================================

class StateType(Enum):
    """State object types."""
    PROFILE = "relay.profile.v1"
    FEED_DEFINITION = "relay.feed.definition.v1"  # v1.4
    CHANNEL_CONFIG = "relay.channel.config.v1"
    SETTINGS = "relay.settings.v1"
    POST = "post"


@dataclass
class StateObject:
    """
    State object (§11) - Versioned, mutable.
    
    Version MUST increment on each update.
    """
    object_id: str
    actor: str
    type: StateType
    version: int
    payload: dict
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    sig: bytes = field(default_factory=bytes)

    def to_dict(self) -> dict:
        return {
            "object_id": self.object_id,
            "actor": self.actor,
            "type": self.type.value,
            "version": self.version,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
            "sig": base64.b64encode(self.sig).decode() if self.sig else None,
        }

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))


# =============================================================================
# IDENTITY (§8)
# =============================================================================

@dataclass
class Identity:
    """
    Identity document (§8).
    
    actor_id = relay:actor: + multihash(SHA-256(pubkey))
    """
    actor_id: str
    public_key: bytes  # Raw 32-byte Ed25519 public key
    display_name: str = ""
    bio: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    origins: dict = field(default_factory=dict)  # log, state URLs
    sig: bytes = field(default_factory=bytes)

    def to_dict(self) -> dict:
        return {
            "actor_id": self.actor_id,
            "keys": {
                "active": base64.b64encode(self.public_key).decode(),
            },
            "display_name": self.display_name,
            "bio": self.bio,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
            "origins": self.origins,
            "sig": base64.b64encode(self.sig).decode() if self.sig else None,
        }

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))


# =============================================================================
# CHANNELS (§13)
# =============================================================================

@dataclass
class ChannelGenesis:
    """
    Channel genesis document (§4.3.1).
    
    Used to compute channel_id.
    """
    kind: str = "relay.channel.genesis.v1"
    owner_actor_id: str = ""
    name: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "owner_actor_id": self.owner_actor_id,
            "name": self.name,
            "created_at": self.created_at.isoformat() + "Z",
        }


@dataclass
class Channel:
    """Channel with membership."""
    channel_id: str
    genesis: ChannelGenesis
    owner: str
    members: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


# =============================================================================
# FEED DEFINITIONS (§11.1, v1.4)
# =============================================================================

class ReducerType(Enum):
    """
    Required reducers (§17.10).
    
    v1.4 requires chronological and reverse_chronological.
    """
    CHRONOLOGICAL = "relay.reduce.chronological.v1"
    REVERSE_CHRONOLOGICAL = "relay.reduce.reverse_chronological.v1"


@dataclass
class FeedDefinition:
    """
    Feed definition (§11.1, v1.4).
    
    State type: relay.feed.definition.v1
    """
    object_id: str
    actor: str  # Curator
    version: int
    sources: list[dict]  # [{kind: "actor_log", actor_id: ...}, ...]
    reduce: ReducerType
    params: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "object_id": self.object_id,
            "actor": self.actor,
            "type": "relay.feed.definition.v1",
            "version": self.version,
            "sources": self.sources,
            "reduce": self.reduce.value,
            "params": self.params,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))


# =============================================================================
# ACTION EVENTS (§13.4, v1.4)
# =============================================================================

def compute_commitment_hash(request_event_id: str, action_id: str, 
                            input_refs: list[str], agent_params: dict) -> str:
    """
    Compute commitment_hash for action.commit (§13.4).
    
    SHA-256 of canonical relay.action.commitment.v1 object.
    """
    commitment = {
        "kind": "relay.action.commitment.v1",
        "request_event_id": request_event_id,
        "action_id": action_id,
        "input_refs": sorted(input_refs),
        "agent_params": agent_params,
    }
    canonical = json.dumps(commitment, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class ActionRequest:
    """action.request event data (§13.4, Appendix C)."""
    action_id: str  # Canonical interoperable action identifier
    action: str | None = None  # Human-facing label (optional)
    input_refs: list[str] = field(default_factory=list)


@dataclass
class ActionCommit:
    """action.commit event data (§13.4, Appendix C)."""
    request_event_id: str
    commitment_hash: str
    agent_params: dict = field(default_factory=dict)


@dataclass
class ActionResult:
    """action.result event data (§13.4, Appendix C)."""
    commitment_hash: str
    output_refs: list[str] = field(default_factory=list)


# =============================================================================
# STORAGE (ORIGIN/RELAY)
# =============================================================================

class RelayStorage:
    """
    In-memory relay storage implementing wire protocol.
    
    Supports:
    - Actor origins (identity, log, state)
    - Channels (membership)
    - Feed definitions (v1.4)
    """

    def __init__(self, origin_url: str = "https://relay.example"):
        self.origin_url = origin_url
        
        # Identity storage
        self.identities: dict[str, Identity] = {}
        
        # Log storage (per actor)
        self.logs: dict[str, list[LogEvent]] = {}
        self.log_heads: dict[str, str] = {}  # actor_id -> latest event_id
        
        # State storage (per actor)
        self.states: dict[str, StateObject] = {}
        
        # Channel storage
        self.channels: dict[str, Channel] = {}
        
        # Feed definitions (v1.4)
        self.feed_definitions: dict[str, FeedDefinition] = {}
        
        # Indexes
        self._events_by_type: dict[LogEventType, list[str]] = {}
        self._events_by_target: dict[str, list[str]] = {}
        
        # Sequence
        self._seq = 0

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    # === Identity APIs (§8) ===
    
    def put_identity(self, identity: Identity) -> int:
        """PUT identity document."""
        self.identities[identity.actor_id] = identity
        return self.next_seq()

    def get_identity(self, actor_id: str) -> Identity | None:
        """GET /actors/{actor_id}/identity"""
        return self.identities.get(actor_id)

    # === Log APIs (§10, §16.3, §17.3-4) ===
    
    def append_log(self, event: LogEvent) -> int:
        """
        POST /actors/{actor_id}/log - Append event.
        
        Validates prev chain.
        """
        actor_id = event.actor
        
        # Initialize log if needed
        if actor_id not in self.logs:
            self.logs[actor_id] = []
        
        # Validate prev
        current_head = self.log_heads.get(actor_id)
        if event.prev != current_head:
            # Allow if this is the first event (prev=None, no head)
            if not (event.prev is None and current_head is None):
                raise ValueError(f"Invalid prev: expected {current_head}, got {event.prev}")
        
        # Append
        self.logs[actor_id].append(event)
        self.log_heads[actor_id] = event.id
        
        # Index by type
        if event.type not in self._events_by_type:
            self._events_by_type[event.type] = []
        self._events_by_type[event.type].append(event.id)
        
        # Index by target
        if event.target:
            if event.target not in self._events_by_target:
                self._events_by_target[event.target] = []
            self._events_by_target[event.target].append(event.id)
        
        return self.next_seq()

    def get_log(self, actor_id: str, limit: int = 100, 
                since: str | None = None) -> list[LogEvent]:
        """GET /actors/{actor_id}/log - Get actor's log."""
        events = self.logs.get(actor_id, [])
        
        if since:
            # Find index of since event
            try:
                idx = next(i for i, e in enumerate(events) if e.id == since)
                events = events[idx + 1:]
            except StopIteration:
                pass
        
        return events[:limit]

    def get_log_head(self, actor_id: str) -> str | None:
        """Get latest event_id for actor."""
        return self.log_heads.get(actor_id)

    def get_event(self, event_id: str) -> LogEvent | None:
        """GET /actors/.../log/events/{event_id}"""
        for events in self.logs.values():
            for event in events:
                if event.id == event_id:
                    return event
        return None

    # === State APIs (§11, §16.1, §17.5) ===
    
    def put_state(self, state: StateObject) -> int:
        """
        PUT /actors/{actor_id}/state/{object_id}
        
        Version MUST increment (§16.1).
        """
        existing = self.states.get(state.object_id)
        if existing:
            if state.version <= existing.version:
                raise ValueError(f"Version must increment: {state.version} <= {existing.version}")
        
        self.states[state.object_id] = state
        return self.next_seq()

    def get_state(self, object_id: str) -> StateObject | None:
        """GET /actors/{actor_id}/state/{object_id}"""
        return self.states.get(object_id)

    def get_states_by_actor(self, actor_id: str) -> list[StateObject]:
        """Get all states for an actor."""
        return [s for s in self.states.values() if s.actor == actor_id]

    # === Channel APIs (§13) ===
    
    def create_channel(self, genesis: ChannelGenesis) -> Channel:
        """Create channel with genesis (§4.3.1)."""
        channel_id = generate_channel_id(genesis.to_dict())
        channel = Channel(
            channel_id=channel_id,
            genesis=genesis,
            owner=genesis.owner_actor_id,
            members=[genesis.owner_actor_id],
        )
        self.channels[channel_id] = channel
        return channel

    def get_channel(self, channel_id: str) -> Channel | None:
        return self.channels.get(channel_id)

    def add_member(self, channel_id: str, actor_id: str) -> bool:
        channel = self.channels.get(channel_id)
        if channel and actor_id not in channel.members:
            channel.members.append(actor_id)
            return True
        return False

    def remove_member(self, channel_id: str, actor_id: str) -> bool:
        channel = self.channels.get(channel_id)
        if channel and actor_id in channel.members:
            channel.members.remove(actor_id)
            return True
        return False

    # === Feed Definition APIs (§11.1, v1.4) ===
    
    def put_feed_definition(self, feed_def: FeedDefinition) -> int:
        """PUT feed definition."""
        existing = self.feed_definitions.get(feed_def.object_id)
        if existing:
            if feed_def.version <= existing.version:
                raise ValueError(f"Version must increment")
        
        self.feed_definitions[feed_def.object_id] = feed_def
        return self.next_seq()

    def get_feed_definition(self, object_id: str) -> FeedDefinition | None:
        return self.feed_definitions.get(object_id)

    # === Metrics ===
    
    def get_metrics(self) -> dict:
        total_events = sum(len(events) for events in self.logs.values())
        total_size = 0
        total_size += sum(i.size_bytes() for i in self.identities.values())
        total_size += sum(e.size_bytes() for events in self.logs.values() for e in events)
        total_size += sum(s.size_bytes() for s in self.states.values())
        total_size += sum(f.size_bytes() for f in self.feed_definitions.values())
        
        event_type_counts = {}
        for etype, eids in self._events_by_type.items():
            event_type_counts[etype.value] = len(eids)
        
        return {
            "identity_count": len(self.identities),
            "actor_count": len(self.logs),
            "event_count": total_events,
            "state_count": len(self.states),
            "channel_count": len(self.channels),
            "feed_definition_count": len(self.feed_definitions),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "sequence": self._seq,
            "event_type_counts": event_type_counts,
        }


# =============================================================================
# FEED REDUCER ENGINE (§17.10, §17.11)
# =============================================================================

@dataclass
class RecomputeBoundary:
    """
    Recompute/audit boundary (§11.1, §17.11).
    
    For verifiable feed output comparison.
    """
    definition_object_id: str
    definition_version: int
    as_of: datetime
    source_heads: dict[str, str]  # actor_id -> event_id


@dataclass
class FeedResult:
    """Result of feed reduction."""
    definition_id: str
    boundary: RecomputeBoundary
    event_ids: list[str]
    result_hash: str
    computation_time_ms: float


class FeedReducer:
    """
    Feed reducer engine (§17.10, §17.11).
    
    Clients MUST be able to recompute feed output from definition + fetched logs.
    """

    def __init__(self, storage: RelayStorage):
        self.storage = storage

    def reduce(self, feed_def: FeedDefinition) -> FeedResult:
        """
        Execute feed reduction (§17.10).
        
        Collects events from sources, applies reducer, returns ordered list.
        """
        start_time = time.time()
        
        # Collect events from sources
        events = []
        source_heads = {}
        
        for source in feed_def.sources:
            kind = source.get("kind")
            
            if kind == "actor_log":
                actor_id = source.get("actor_id")
                actor_events = self.storage.get_log(actor_id, limit=1000)
                events.extend(actor_events)
                
                head = self.storage.get_log_head(actor_id)
                if head:
                    source_heads[actor_id] = head
            
            elif kind == "feed":
                # Nested feed - resolve and reduce
                nested_id = source.get("feed_id")
                nested_def = self.storage.get_feed_definition(nested_id)
                if nested_def:
                    nested_result = self.reduce(nested_def)
                    for event_id in nested_result.event_ids:
                        event = self.storage.get_event(event_id)
                        if event:
                            events.append(event)
        
        # Apply reducer
        if feed_def.reduce == ReducerType.CHRONOLOGICAL:
            # Sort by (ts, event_id) - deterministic (§17.10)
            events.sort(key=lambda e: (e.ts, e.id))
        elif feed_def.reduce == ReducerType.REVERSE_CHRONOLOGICAL:
            events.sort(key=lambda e: (e.ts, e.id), reverse=True)
        
        # Apply limit if specified
        limit = feed_def.params.get("limit", 100)
        events = events[:limit]
        
        # Extract IDs
        event_ids = [e.id for e in events]
        
        # Compute result hash
        result_hash = self._compute_hash(event_ids)
        
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

    def recompute_and_verify(self, feed_def: FeedDefinition, 
                             claimed_result: FeedResult) -> bool:
        """
        Recompute and verify (§17.11).
        
        Clients MUST be able to verify feed wasn't manipulated.
        """
        recomputed = self.reduce(feed_def)
        return recomputed.result_hash == claimed_result.result_hash

    def _compute_hash(self, event_ids: list[str]) -> str:
        canonical = json.dumps(event_ids, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()


# =============================================================================
# ACTION VERIFIER (§13.4)
# =============================================================================

class ActionVerifier:
    """
    Action verification (§13.4).
    
    Verifier MUST fetch all three events and verify signatures and commitment_hash.
    """

    def __init__(self, storage: RelayStorage):
        self.storage = storage

    def verify_action_chain(self, result_event_id: str) -> dict:
        """
        Verify action.request -> action.commit -> action.result chain.
        
        Returns verification result with status and details.
        """
        result_event = self.storage.get_event(result_event_id)
        if not result_event or result_event.type != LogEventType.ACTION_RESULT:
            return {"valid": False, "error": "Invalid result event"}
        
        commitment_hash = result_event.data.get("commitment_hash")
        if not commitment_hash:
            return {"valid": False, "error": "Missing commitment_hash in result"}
        
        # Find commit event with same commitment_hash
        commit_event = None
        for events in self.storage.logs.values():
            for event in events:
                if (event.type == LogEventType.ACTION_COMMIT and 
                    event.data.get("commitment_hash") == commitment_hash):
                    commit_event = event
                    break
            if commit_event:
                break
        
        if not commit_event:
            return {"valid": False, "error": "Commit event not found"}
        
        request_event_id = commit_event.data.get("request_event_id")
        if not request_event_id:
            return {"valid": False, "error": "Missing request_event_id in commit"}
        
        request_event = self.storage.get_event(request_event_id)
        if not request_event or request_event.type != LogEventType.ACTION_REQUEST:
            return {"valid": False, "error": "Request event not found"}
        
        # Verify commitment_hash
        expected_hash = compute_commitment_hash(
            request_event_id=request_event_id,
            action_id=request_event.data.get("action_id", ""),
            input_refs=request_event.data.get("input_refs", []),
            agent_params=commit_event.data.get("agent_params", {}),
        )
        
        if expected_hash != commitment_hash:
            return {"valid": False, "error": "commitment_hash mismatch"}
        
        return {
            "valid": True,
            "request_event_id": request_event.id,
            "commit_event_id": commit_event.id,
            "result_event_id": result_event.id,
            "action_id": request_event.data.get("action_id"),
            "output_refs": result_event.data.get("output_refs", []),
        }
