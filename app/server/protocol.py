"""
MESH Protocol Implementation - Full Protocol Compliance
Integrates reference implementation from /implementations/mesh/
"""
import os
import sys
import json
import hashlib
import secrets
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Set, Any, Tuple

# Crypto
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


# ============================================================
# LAYER 1: PRIVACY LAYER
# Ed25519 signatures, X25519 key exchange, AES-256-GCM encryption
# ============================================================

def canonical_json(obj: dict) -> bytes:
    """Deterministic JSON serialization."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SigningKeyPair:
    """Ed25519 signing key pair for root and device keys."""
    
    def __init__(self, private_key: Ed25519PrivateKey):
        self._private = private_key
        self._public = private_key.public_key()
    
    @classmethod
    def generate(cls) -> 'SigningKeyPair':
        return cls(Ed25519PrivateKey.generate())
    
    @classmethod
    def from_seed(cls, seed: bytes) -> 'SigningKeyPair':
        return cls(Ed25519PrivateKey.from_private_bytes(seed[:32]))
    
    @classmethod
    def from_private_bytes(cls, data: bytes) -> 'SigningKeyPair':
        return cls(Ed25519PrivateKey.from_private_bytes(data))
    
    def sign(self, message: bytes) -> bytes:
        return self._private.sign(message)
    
    def public_key_bytes(self) -> bytes:
        return self._public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    def private_key_bytes(self) -> bytes:
        return self._private.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )


def verify_signature(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Verify Ed25519 signature."""
    if len(public_key) != 32 or len(signature) != 64:
        return False
    try:
        pk = Ed25519PublicKey.from_public_bytes(public_key)
        pk.verify(signature, message)
        return True
    except Exception:
        return False


class EncryptionKeyPair:
    """X25519 key pair for E2EE."""
    
    def __init__(self, private_key: X25519PrivateKey):
        self._private = private_key
        self._public = private_key.public_key()
    
    @classmethod
    def generate(cls) -> 'EncryptionKeyPair':
        return cls(X25519PrivateKey.generate())
    
    @classmethod
    def from_private_bytes(cls, data: bytes) -> 'EncryptionKeyPair':
        return cls(X25519PrivateKey.from_private_bytes(data))
    
    def public_key_bytes(self) -> bytes:
        return self._public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    def private_key_bytes(self) -> bytes:
        return self._private.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
    
    def derive_shared_secret(self, peer_public_key: bytes) -> bytes:
        peer_pk = X25519PublicKey.from_public_bytes(peer_public_key)
        return self._private.exchange(peer_pk)


def derive_encryption_key(shared_secret: bytes, info: bytes = b'mesh-v1') -> bytes:
    """Derive AES key from shared secret using HKDF."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=info,
    )
    return hkdf.derive(shared_secret)


def encrypt_aes_gcm(plaintext: bytes, key: bytes) -> Tuple[bytes, bytes]:
    """Encrypt with AES-256-GCM. Returns (nonce, ciphertext)."""
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce, ciphertext


def decrypt_aes_gcm(nonce: bytes, ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt AES-256-GCM."""
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


@dataclass
class EncryptedEnvelope:
    """E2EE message envelope for DMs."""
    ephemeral_public_key: bytes
    nonce: bytes
    ciphertext: bytes
    
    def to_dict(self) -> dict:
        return {
            "ephemeral_public_key": self.ephemeral_public_key.hex(),
            "nonce": self.nonce.hex(),
            "ciphertext": self.ciphertext.hex(),
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'EncryptedEnvelope':
        return cls(
            ephemeral_public_key=bytes.fromhex(d["ephemeral_public_key"]),
            nonce=bytes.fromhex(d["nonce"]),
            ciphertext=bytes.fromhex(d["ciphertext"]),
        )


def encrypt_for_recipient(plaintext: bytes, recipient_public_key: bytes) -> EncryptedEnvelope:
    """Encrypt a message for a specific recipient."""
    ephemeral = EncryptionKeyPair.generate()
    shared = ephemeral.derive_shared_secret(recipient_public_key)
    key = derive_encryption_key(shared)
    nonce, ciphertext = encrypt_aes_gcm(plaintext, key)
    return EncryptedEnvelope(
        ephemeral_public_key=ephemeral.public_key_bytes(),
        nonce=nonce,
        ciphertext=ciphertext,
    )


def decrypt_from_sender(envelope: EncryptedEnvelope, recipient_encryption_key: EncryptionKeyPair) -> bytes:
    """Decrypt a message from sender."""
    shared = recipient_encryption_key.derive_shared_secret(envelope.ephemeral_public_key)
    key = derive_encryption_key(shared)
    return decrypt_aes_gcm(envelope.nonce, envelope.ciphertext, key)


# ============================================================
# LAYER 1.1: DEVICE KEY HIERARCHY
# Root key -> Device keys with capabilities
# ============================================================

@dataclass
class DeviceKey:
    """A device key authorized by the root key."""
    device_id: str
    public_key: bytes
    name: str
    authorized_at: datetime
    revoked: bool = False
    capabilities: List[str] = field(default_factory=lambda: ["post", "follow", "dm"])
    sig: bytes = b""  # Signed by root key
    
    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "public_key": self.public_key.hex(),
            "name": self.name,
            "authorized_at": self.authorized_at.isoformat(),
            "revoked": self.revoked,
            "capabilities": self.capabilities,
            "sig": self.sig.hex(),
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'DeviceKey':
        return cls(
            device_id=d["device_id"],
            public_key=bytes.fromhex(d["public_key"]),
            name=d["name"],
            authorized_at=datetime.fromisoformat(d["authorized_at"]),
            revoked=d.get("revoked", False),
            capabilities=d.get("capabilities", ["post", "follow", "dm"]),
            sig=bytes.fromhex(d.get("sig", "")),
        )


def authorize_device_key(
    root_keypair: SigningKeyPair,
    device_public_key: bytes,
    device_name: str,
    capabilities: List[str] = None
) -> DeviceKey:
    """Authorize a new device key signed by root key."""
    device_id = f"dev:{sha256_hex(device_public_key)[:16]}"
    device = DeviceKey(
        device_id=device_id,
        public_key=device_public_key,
        name=device_name,
        authorized_at=datetime.utcnow(),
        capabilities=capabilities or ["post", "follow", "dm"],
    )
    # Sign with root key
    to_sign = {k: v for k, v in device.to_dict().items() if k != "sig"}
    device.sig = root_keypair.sign(canonical_json(to_sign))
    return device


def verify_device_key(device: DeviceKey, root_public_key: bytes) -> bool:
    """Verify device key was authorized by root key."""
    to_verify = {k: v for k, v in device.to_dict().items() if k != "sig"}
    return verify_signature(root_public_key, canonical_json(to_verify), device.sig)


# ============================================================
# LAYER 3: INTEGRITY LAYER
# Multi-head DAG with Lamport clock and auto-merge
# ============================================================

class OpType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MERGE = "merge"


class ObjectType(str, Enum):
    ENTITY = "entity"
    CONTENT = "content"
    LINK = "link"
    ATTESTATION = "attestation"
    DEVICE_KEY = "device_key"
    DM = "dm"


@dataclass
class LogEvent:
    """
    Append-only log event with multi-parent DAG support.
    """
    id: str
    actor: str
    parents: List[str]  # Multi-parent for DAG (replaces single prev)
    lamport: int  # Lamport logical clock
    
    op: OpType
    object_type: ObjectType
    object_id: str
    payload: dict
    
    ts: datetime
    device_id: Optional[str] = None  # Which device created this
    sig: bytes = b""
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "actor": self.actor,
            "parents": self.parents,
            "lamport": self.lamport,
            "op": self.op.value,
            "object_type": self.object_type.value,
            "object_id": self.object_id,
            "payload": self.payload,
            "ts": self.ts.isoformat(),
            "device_id": self.device_id,
            "sig": self.sig.hex() if self.sig else "",
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'LogEvent':
        return cls(
            id=d["id"],
            actor=d["actor"],
            parents=d.get("parents", [d.get("prev")] if d.get("prev") else []),
            lamport=d.get("lamport", d.get("seq", 0)),
            op=OpType(d["op"]),
            object_type=ObjectType(d["object_type"]),
            object_id=d["object_id"],
            payload=d["payload"],
            ts=datetime.fromisoformat(d["ts"]) if isinstance(d["ts"], str) else d["ts"],
            device_id=d.get("device_id"),
            sig=bytes.fromhex(d.get("sig", "")),
        )


def generate_event_id(actor: str, lamport: int, parents: List[str]) -> str:
    """Generate deterministic event ID from components."""
    data = f"{actor}:{lamport}:{','.join(sorted(parents))}"
    return sha256_hex(data.encode())[:48]


def compute_lamport(parent_events: List[LogEvent]) -> int:
    """Compute Lamport clock for new event."""
    if not parent_events:
        return 1
    return max(e.lamport for e in parent_events) + 1


class DAGStore:
    """In-memory DAG storage for events."""
    
    def __init__(self):
        self.events: Dict[str, LogEvent] = {}
        self.heads: Dict[str, Set[str]] = {}  # actor -> set of head event IDs
        self.children: Dict[str, Set[str]] = {}  # event_id -> child event IDs
    
    def add_event(self, event: LogEvent):
        """Add event to DAG."""
        self.events[event.id] = event
        
        # Update children index
        for parent_id in event.parents:
            if parent_id not in self.children:
                self.children[parent_id] = set()
            self.children[parent_id].add(event.id)
        
        # Update heads
        actor = event.actor
        if actor not in self.heads:
            self.heads[actor] = set()
        
        # Remove parents from heads (they're no longer heads)
        for parent_id in event.parents:
            self.heads[actor].discard(parent_id)
        
        # Add this event as head
        self.heads[actor].add(event.id)
    
    def get_heads(self, actor: str) -> List[LogEvent]:
        """Get current head events for an actor."""
        head_ids = self.heads.get(actor, set())
        return [self.events[eid] for eid in head_ids if eid in self.events]
    
    def get_event(self, event_id: str) -> Optional[LogEvent]:
        return self.events.get(event_id)
    
    def get_events_for_actor(self, actor: str) -> List[LogEvent]:
        """Get all events for an actor in topological order."""
        events = [e for e in self.events.values() if e.actor == actor]
        return sorted(events, key=lambda e: e.lamport)
    
    def needs_merge(self, actor: str) -> bool:
        """Check if actor has multiple heads (fork)."""
        return len(self.heads.get(actor, set())) > 1


def auto_merge_strategy_lww(events: List[LogEvent]) -> dict:
    """
    Last-Write-Wins merge strategy.
    For each field, take the value from the event with highest lamport.
    """
    if not events:
        return {}
    
    # Group by object_id
    by_object: Dict[str, List[LogEvent]] = {}
    for e in events:
        if e.object_id not in by_object:
            by_object[e.object_id] = []
        by_object[e.object_id].append(e)
    
    merged = {}
    for object_id, obj_events in by_object.items():
        # Get latest event
        latest = max(obj_events, key=lambda e: (e.lamport, e.ts))
        merged[object_id] = latest.payload
    
    return merged


def create_merge_event(
    actor: str,
    parent_events: List[LogEvent],
    signing_key: SigningKeyPair,
    device_id: Optional[str] = None
) -> LogEvent:
    """Create a merge event that combines multiple heads."""
    parents = [e.id for e in parent_events]
    lamport = compute_lamport(parent_events)
    
    # Merge payloads using LWW
    merged_state = auto_merge_strategy_lww(parent_events)
    
    event = LogEvent(
        id=generate_event_id(actor, lamport, parents),
        actor=actor,
        parents=parents,
        lamport=lamport,
        op=OpType.MERGE,
        object_type=ObjectType.ENTITY,  # Merge events are at entity level
        object_id=actor,
        payload={"merged": True, "parent_count": len(parents), "state": merged_state},
        ts=datetime.utcnow(),
        device_id=device_id,
    )
    
    # Sign
    to_sign = {k: v for k, v in event.to_dict().items() if k != "sig"}
    event.sig = signing_key.sign(canonical_json(to_sign))
    
    return event


# ============================================================
# LAYER 4: SOCIAL LAYER PRIMITIVES
# Entity, Content, Link
# ============================================================

class EntityKind(str, Enum):
    USER = "user"
    GROUP = "group"
    BOT = "bot"


@dataclass
class Entity:
    """A user, group, or bot identity."""
    id: str
    kind: EntityKind
    public_key: bytes  # Root public key
    encryption_key: Optional[bytes] = None  # X25519 public key for DMs
    handle: Optional[str] = None
    profile: dict = field(default_factory=dict)
    device_keys: List[DeviceKey] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    sig: bytes = b""
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "public_key": self.public_key.hex(),
            "encryption_key": self.encryption_key.hex() if self.encryption_key else None,
            "handle": self.handle,
            "profile": self.profile,
            "device_keys": [dk.to_dict() for dk in self.device_keys],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "sig": self.sig.hex() if self.sig else "",
        }


class ContentKind(str, Enum):
    POST = "post"
    ARTICLE = "article"
    COMMENT = "comment"
    DM = "dm"
    MEDIA = "media"


@dataclass
class Content:
    """A piece of content (post, article, comment, DM)."""
    id: str
    author: str
    kind: ContentKind
    body: str
    media: List[str] = field(default_factory=list)
    reply_to: Optional[str] = None
    encrypted: Optional[EncryptedEnvelope] = None  # For DMs
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    sig: bytes = b""
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "author": self.author,
            "kind": self.kind.value,
            "body": self.body if not self.encrypted else "[encrypted]",
            "media": self.media,
            "reply_to": self.reply_to,
            "encrypted": self.encrypted.to_dict() if self.encrypted else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "sig": self.sig.hex() if self.sig else "",
        }


class LinkKind(str, Enum):
    FOLLOW = "follow"
    LIKE = "like"
    REPOST = "repost"
    BLOCK = "block"
    MUTE = "mute"
    MEMBER = "member"
    ADMIN = "admin"
    SUBSCRIBE = "subscribe"


@dataclass 
class Link:
    """A relationship between entities/content."""
    id: str
    source: str
    target: str
    kind: LinkKind
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    sig: bytes = b""
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "kind": self.kind.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "sig": self.sig.hex() if self.sig else "",
        }


# ============================================================
# LAYER 5: MODERATION LAYER
# Attestations with conflict resolution
# ============================================================

class AttestationType(str, Enum):
    SPAM = "spam"
    NSFW = "nsfw"
    MISLEADING = "misleading"
    HARASSMENT = "harassment"
    VERIFIED = "verified"
    TRUSTED = "trusted"
    BOT = "bot"


@dataclass
class Attestation:
    """A third-party claim about an entity or content."""
    id: str
    issuer: str  # Who made this attestation
    subject: str  # What it's about
    type: AttestationType
    claim: dict
    evidence: Optional[dict] = None
    confidence: float = 1.0  # 0.0 - 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    sig: bytes = b""
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "issuer": self.issuer,
            "subject": self.subject,
            "type": self.type.value,
            "claim": self.claim,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "sig": self.sig.hex() if self.sig else "",
        }


def resolve_attestation_conflicts(
    attestations: List[Attestation],
    trusted_issuers: Set[str],
    resolution_strategy: str = "trusted_majority"
) -> dict:
    """
    Resolve conflicting attestations.
    Strategies: trusted_majority, most_recent, highest_confidence
    """
    if not attestations:
        return {"resolved": None, "conflicts": []}
    
    # Separate by trust
    trusted = [a for a in attestations if a.issuer in trusted_issuers]
    untrusted = [a for a in attestations if a.issuer not in trusted_issuers]
    
    if resolution_strategy == "trusted_majority":
        # Count votes from trusted sources
        votes: Dict[str, int] = {}
        for a in trusted:
            label = a.type.value
            votes[label] = votes.get(label, 0) + 1
        
        if votes:
            winner = max(votes.items(), key=lambda x: x[1])
            return {
                "resolved": winner[0],
                "confidence": winner[1] / len(trusted),
                "trusted_votes": votes,
                "conflicts": [a.to_dict() for a in untrusted if a.type.value != winner[0]],
            }
    
    elif resolution_strategy == "most_recent":
        latest = max(attestations, key=lambda a: a.created_at)
        return {
            "resolved": latest.type.value,
            "confidence": latest.confidence,
            "source": latest.issuer,
        }
    
    elif resolution_strategy == "highest_confidence":
        best = max(attestations, key=lambda a: a.confidence)
        return {
            "resolved": best.type.value,
            "confidence": best.confidence,
            "source": best.issuer,
        }
    
    return {"resolved": None, "conflicts": [a.to_dict() for a in attestations]}


# ============================================================
# LAYER 6: VIEW LAYER
# Deterministic view computation with limits
# ============================================================

@dataclass
class ViewDefinition:
    """A view definition for computing derived state."""
    id: str
    name: str
    description: str
    filter_expr: str  # Expression to filter events
    reduce_expr: str  # Expression to reduce events to state
    max_events: int = 10000  # Execution limit
    max_time_ms: int = 5000  # Time limit
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "filter_expr": self.filter_expr,
            "reduce_expr": self.reduce_expr,
            "max_events": self.max_events,
            "max_time_ms": self.max_time_ms,
        }


class ViewExecutor:
    """Execute views with resource limits."""
    
    def __init__(self, max_events: int = 10000, max_time_ms: int = 5000):
        self.max_events = max_events
        self.max_time_ms = max_time_ms
        self.events_processed = 0
    
    def execute_timeline_view(
        self,
        events: List[LogEvent],
        followed_ids: Set[str],
        limit: int = 100
    ) -> List[dict]:
        """Execute a timeline view (posts from followed users)."""
        self.events_processed = 0
        results = []
        
        for event in events:
            if self.events_processed >= self.max_events:
                break
            
            self.events_processed += 1
            
            if (event.object_type == ObjectType.CONTENT and
                event.op == OpType.CREATE and
                event.actor in followed_ids):
                results.append(event.payload)
                
                if len(results) >= limit:
                    break
        
        return results
    
    def execute_feed_view(
        self,
        content_events: List[LogEvent],
        link_events: List[LogEvent],
        followed_ids: Set[str],
        limit: int = 100
    ) -> List[dict]:
        """Execute a full feed view with engagement metrics."""
        # Build engagement counts
        engagement: Dict[str, dict] = {}
        for event in link_events:
            if event.object_type == ObjectType.LINK and event.op == OpType.CREATE:
                target = event.payload.get("target", "")
                kind = event.payload.get("kind", "")
                if target not in engagement:
                    engagement[target] = {"likes": 0, "reposts": 0, "replies": 0}
                if kind == "like":
                    engagement[target]["likes"] += 1
                elif kind == "repost":
                    engagement[target]["reposts"] += 1
        
        # Get content with engagement
        results = []
        for event in sorted(content_events, key=lambda e: e.ts, reverse=True):
            if (event.object_type == ObjectType.CONTENT and
                event.op == OpType.CREATE and
                event.actor in followed_ids):
                
                content = dict(event.payload)
                content["engagement"] = engagement.get(event.object_id, {"likes": 0, "reposts": 0, "replies": 0})
                results.append(content)
                
                if len(results) >= limit:
                    break
        
        return results


# ============================================================
# ID GENERATION HELPERS
# ============================================================

def generate_entity_id(public_key: bytes) -> str:
    return f"ent:{sha256_hex(public_key)[:32]}"


def generate_content_id(author: str, body: str, ts: datetime) -> str:
    data = f"{author}:{body}:{ts.isoformat()}"
    return sha256_hex(data.encode())[:48]


def generate_link_id(source: str, kind: str, target: str) -> str:
    return sha256_hex(f"{source}:{kind}:{target}".encode())[:32]


def generate_attestation_id(issuer: str, subject: str, type: str) -> str:
    return sha256_hex(f"{issuer}:{subject}:{type}".encode())[:32]


# ============================================================
# SYNC PROTOCOL HELPERS
# ============================================================

def compute_sync_diff(
    local_events: Dict[str, LogEvent],
    remote_event_ids: Set[str]
) -> Tuple[Set[str], Set[str]]:
    """Compute sync difference between local and remote."""
    local_ids = set(local_events.keys())
    missing_local = remote_event_ids - local_ids
    missing_remote = local_ids - remote_event_ids
    return missing_local, missing_remote


def topological_sort(events: List[LogEvent]) -> List[LogEvent]:
    """Sort events in topological order (parents before children)."""
    event_map = {e.id: e for e in events}
    visited = set()
    result = []
    
    def visit(event_id: str):
        if event_id in visited or event_id not in event_map:
            return
        event = event_map[event_id]
        for parent_id in event.parents:
            visit(parent_id)
        visited.add(event_id)
        result.append(event)
    
    for e in events:
        visit(e.id)
    
    return result
