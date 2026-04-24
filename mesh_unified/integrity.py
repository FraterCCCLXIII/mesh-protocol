"""
MESH Protocol - Integrity Layer
LogEvent with prev chain, fork prevention (from Relay v1.4.1)
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Any

from .crypto import sha256, canonical_json, commitment_hash


class OpType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ObjectType(str, Enum):
    ENTITY = "entity"
    CONTENT = "content"
    LINK = "link"
    STATE = "state"
    ATTESTATION = "attestation"
    VIEW = "view"


@dataclass
class LogEvent:
    """
    Append-only log event with prev chain.
    Every write is wrapped in a LogEvent for integrity.
    """
    id: str
    actor: str  # entity_id of who made this change
    seq: int  # Monotonic sequence number
    prev: Optional[str]  # Previous event ID (null for first event)
    
    # The actual change
    op: OpType
    object_type: ObjectType
    object_id: str
    payload: dict
    
    ts: datetime
    sig: bytes
    
    # Optional commitment hash for action verification
    commitment: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "actor": self.actor,
            "seq": self.seq,
            "prev": self.prev,
            "op": self.op.value,
            "object_type": self.object_type.value,
            "object_id": self.object_id,
            "payload": self.payload,
            "ts": self.ts.isoformat(),
            "sig": self.sig.hex(),
            "commitment": self.commitment,
        }
    
    def verify_prev(self, expected_prev: Optional[str]) -> bool:
        """Verify this event correctly references the previous."""
        return self.prev == expected_prev
    
    def compute_commitment(self, action_type: str, input_refs: list, params: dict) -> str:
        """Compute commitment hash for this event."""
        return commitment_hash(self.id, action_type, input_refs, params)


def generate_log_event_id(actor: str, seq: int) -> str:
    """Generate deterministic event ID."""
    return sha256(f"{actor}:{seq}".encode())[:48]


def validate_log_chain(events: list[LogEvent]) -> tuple[bool, Optional[str]]:
    """
    Validate a chain of log events.
    Returns (valid, error_message).
    """
    if not events:
        return True, None
    
    # First event must have prev=None
    if events[0].prev is not None:
        return False, "First event must have prev=None"
    
    # Each subsequent event must reference the previous
    for i in range(1, len(events)):
        if events[i].prev != events[i-1].id:
            return False, f"Event {i} has invalid prev: expected {events[i-1].id}, got {events[i].prev}"
        
        # Sequence must increment
        if events[i].seq != events[i-1].seq + 1:
            return False, f"Event {i} has invalid seq: expected {events[i-1].seq + 1}, got {events[i].seq}"
    
    return True, None


def detect_fork(events_a: list[LogEvent], events_b: list[LogEvent]) -> Optional[int]:
    """
    Detect if two event chains have forked.
    Returns the index where they diverge, or None if no fork.
    """
    min_len = min(len(events_a), len(events_b))
    
    for i in range(min_len):
        if events_a[i].id != events_b[i].id:
            return i
    
    return None
