"""
Relay v2 Implementation - Persistent Storage Layer

Based on Relay_v2.md Two-Layer Architecture:

TRUTH LAYER:
- Identity (§8)
- Event (§10) - append-only, content-addressed
- State (§11) - versioned, mutable
- Attestation (§6) - claims
- Snapshot (§0.5) - checkpoints

VIEW LAYER:
- ViewDefinition (§11.1)
- Boundary (§0.6) - finite inputs for determinism
- Reducers (§17.10)
"""

import json
import asyncio
import aiosqlite
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from crypto import generate_actor_id, generate_event_id, content_hash, canonical_json


# =============================================================================
# TRUTH LAYER - PRIMITIVES
# =============================================================================

@dataclass
class Identity:
    """Identity (§8)."""
    actor_id: str
    public_key: bytes
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    sig: bytes = field(default_factory=bytes)
    
    def to_dict(self) -> dict:
        import base64
        return {
            "actor_id": self.actor_id,
            "public_key": base64.b64encode(self.public_key).decode(),
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }


class EventType(Enum):
    """Event types."""
    POST = "post"
    REACTION = "reaction"
    FOLLOW_ADD = "follow.add"
    FOLLOW_REMOVE = "follow.remove"
    ACTION_REQUEST = "action.request"
    ACTION_COMMIT = "action.commit"
    ACTION_RESULT = "action.result"


@dataclass
class Event:
    """
    Event (§10) - Immutable, append-only, content-addressed.
    
    ID is derived from content hash.
    """
    id: str  # Content-addressed
    actor: str
    type: EventType
    data: dict
    ts: datetime
    parents: List[str] = field(default_factory=list)  # For DAG
    sig: bytes = field(default_factory=bytes)
    
    def to_dict(self) -> dict:
        import base64
        return {
            "id": self.id,
            "actor": self.actor,
            "type": self.type.value,
            "data": self.data,
            "ts": self.ts.isoformat() + "Z",
            "parents": self.parents,
            "sig": base64.b64encode(self.sig).decode() if self.sig else None,
        }


@dataclass
class State:
    """
    State (§11) - Versioned, authoritative, mutable.
    
    Version MUST increment on each update.
    """
    object_id: str
    actor: str
    type: str
    version: int
    payload: dict
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    sig: bytes = field(default_factory=bytes)
    
    def to_dict(self) -> dict:
        return {
            "object_id": self.object_id,
            "actor": self.actor,
            "type": self.type,
            "version": self.version,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }


class AttestationType(Enum):
    """Attestation categories (§6)."""
    TRUST = "trust"
    CONTENT = "content"
    VIEW = "view"
    INDEX = "index"


@dataclass
class Attestation:
    """
    Attestation (§6) - Claims that MUST NOT override facts.
    """
    id: str
    issuer: str
    subject: str
    type: AttestationType
    claim: dict
    ts: datetime
    expires_at: Optional[datetime] = None
    sig: bytes = field(default_factory=bytes)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "issuer": self.issuer,
            "subject": self.subject,
            "type": self.type.value,
            "claim": self.claim,
            "ts": self.ts.isoformat() + "Z",
            "expires_at": self.expires_at.isoformat() + "Z" if self.expires_at else None,
        }


@dataclass
class Snapshot:
    """
    Snapshot (§0.5) - Verifiable checkpoint.
    """
    id: str
    actor: str
    ts: datetime
    event_head: str
    state_hashes: Dict[str, str]  # object_id -> hash
    sig: bytes = field(default_factory=bytes)


# =============================================================================
# VIEW LAYER - PRIMITIVES
# =============================================================================

class ReducerType(Enum):
    """Reducers (§17.10)."""
    CHRONOLOGICAL = "chronological"
    REVERSE_CHRONOLOGICAL = "reverse_chronological"
    ENGAGEMENT = "engagement"


@dataclass
class ViewDefinition:
    """
    ViewDefinition (§11.1) - Signed State with sources + reduce.
    """
    object_id: str
    actor: str
    version: int
    sources: List[dict]
    reduce: ReducerType
    params: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    sig: bytes = field(default_factory=bytes)
    
    def to_dict(self) -> dict:
        return {
            "object_id": self.object_id,
            "actor": self.actor,
            "version": self.version,
            "sources": self.sources,
            "reduce": self.reduce.value,
            "params": self.params,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }


@dataclass
class Boundary:
    """
    Boundary (§0.6) - Finite inputs for determinism.
    
    Same boundary + same definition = same result hash.
    """
    definition_id: str
    definition_version: int
    as_of: datetime
    source_heads: Dict[str, str]  # actor_id -> event_id
    
    def to_dict(self) -> dict:
        return {
            "definition_id": self.definition_id,
            "definition_version": self.definition_version,
            "as_of": self.as_of.isoformat() + "Z",
            "source_heads": self.source_heads,
        }


@dataclass
class ViewResult:
    """Result of view execution."""
    definition_id: str
    boundary: Boundary
    event_ids: List[str]
    result_hash: str
    is_deterministic: bool = True
    
    def to_dict(self) -> dict:
        return {
            "definition_id": self.definition_id,
            "boundary": self.boundary.to_dict(),
            "event_ids": self.event_ids,
            "result_hash": self.result_hash,
            "is_deterministic": self.is_deterministic,
        }


# =============================================================================
# SQLITE STORAGE
# =============================================================================

class Storage:
    """Async SQLite storage for Relay v2 two-layer architecture."""
    
    def __init__(self, db_path: str = "relay_v2.db"):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None
    
    async def initialize(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        
        await self.db.executescript("""
            -- TRUTH LAYER --
            
            -- Identities
            CREATE TABLE IF NOT EXISTS identities (
                actor_id TEXT PRIMARY KEY,
                public_key BLOB NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sig BLOB
            );
            
            -- Events (append-only, content-addressed)
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                actor TEXT NOT NULL,
                type TEXT NOT NULL,
                data TEXT NOT NULL,
                ts TEXT NOT NULL,
                parents TEXT NOT NULL,
                sig BLOB,
                seq INTEGER NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor);
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
            CREATE INDEX IF NOT EXISTS idx_events_seq ON events(seq);
            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
            
            -- Event heads per actor
            CREATE TABLE IF NOT EXISTS event_heads (
                actor_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL
            );
            
            -- States (versioned)
            CREATE TABLE IF NOT EXISTS states (
                object_id TEXT PRIMARY KEY,
                actor TEXT NOT NULL,
                type TEXT NOT NULL,
                version INTEGER NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sig BLOB
            );
            
            CREATE INDEX IF NOT EXISTS idx_states_actor ON states(actor);
            CREATE INDEX IF NOT EXISTS idx_states_type ON states(type);
            
            -- Attestations
            CREATE TABLE IF NOT EXISTS attestations (
                id TEXT PRIMARY KEY,
                issuer TEXT NOT NULL,
                subject TEXT NOT NULL,
                type TEXT NOT NULL,
                claim TEXT NOT NULL,
                ts TEXT NOT NULL,
                expires_at TEXT,
                sig BLOB
            );
            
            CREATE INDEX IF NOT EXISTS idx_attestations_issuer ON attestations(issuer);
            CREATE INDEX IF NOT EXISTS idx_attestations_subject ON attestations(subject);
            CREATE INDEX IF NOT EXISTS idx_attestations_type ON attestations(type);
            
            -- Snapshots
            CREATE TABLE IF NOT EXISTS snapshots (
                id TEXT PRIMARY KEY,
                actor TEXT NOT NULL,
                ts TEXT NOT NULL,
                event_head TEXT NOT NULL,
                state_hashes TEXT NOT NULL,
                sig BLOB
            );
            
            -- VIEW LAYER --
            
            -- View definitions
            CREATE TABLE IF NOT EXISTS view_definitions (
                object_id TEXT PRIMARY KEY,
                actor TEXT NOT NULL,
                version INTEGER NOT NULL,
                sources TEXT NOT NULL,
                reduce TEXT NOT NULL,
                params TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sig BLOB
            );
            
            -- View execution cache
            CREATE TABLE IF NOT EXISTS view_cache (
                definition_id TEXT NOT NULL,
                boundary_hash TEXT NOT NULL,
                result_hash TEXT NOT NULL,
                event_ids TEXT NOT NULL,
                computed_at TEXT NOT NULL,
                PRIMARY KEY (definition_id, boundary_hash)
            );
            
            -- Sequence
            CREATE TABLE IF NOT EXISTS sequence (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                seq INTEGER NOT NULL DEFAULT 0
            );
            
            INSERT OR IGNORE INTO sequence (id, seq) VALUES (1, 0);
        """)
        
        await self.db.commit()
    
    async def close(self):
        if self.db:
            await self.db.close()
    
    async def next_seq(self) -> int:
        async with self.db.execute(
            "UPDATE sequence SET seq = seq + 1 WHERE id = 1 RETURNING seq"
        ) as cursor:
            row = await cursor.fetchone()
            await self.db.commit()
            return row[0]
    
    # =========================================================================
    # TRUTH LAYER - Identity
    # =========================================================================
    
    async def put_identity(self, identity: Identity) -> int:
        await self.db.execute("""
            INSERT OR REPLACE INTO identities 
            (actor_id, public_key, created_at, updated_at, sig)
            VALUES (?, ?, ?, ?, ?)
        """, (
            identity.actor_id,
            identity.public_key,
            identity.created_at.isoformat(),
            identity.updated_at.isoformat(),
            identity.sig,
        ))
        await self.db.commit()
        return await self.next_seq()
    
    async def get_identity(self, actor_id: str) -> Optional[Identity]:
        async with self.db.execute(
            "SELECT * FROM identities WHERE actor_id = ?", (actor_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Identity(
                    actor_id=row['actor_id'],
                    public_key=row['public_key'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    sig=row['sig'] or b'',
                )
        return None
    
    # =========================================================================
    # TRUTH LAYER - Events
    # =========================================================================
    
    async def append_event(self, event: Event) -> int:
        """Append event (content-addressed, append-only)."""
        seq = await self.next_seq()
        
        await self.db.execute("""
            INSERT INTO events (id, actor, type, data, ts, parents, sig, seq)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.id,
            event.actor,
            event.type.value,
            json.dumps(event.data),
            event.ts.isoformat(),
            json.dumps(event.parents),
            event.sig,
            seq,
        ))
        
        # Update head
        await self.db.execute("""
            INSERT OR REPLACE INTO event_heads (actor_id, event_id) VALUES (?, ?)
        """, (event.actor, event.id))
        
        await self.db.commit()
        return seq
    
    async def get_event(self, event_id: str) -> Optional[Event]:
        async with self.db.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_event(row)
        return None
    
    async def get_events(self, actor_id: str, limit: int = 100) -> List[Event]:
        async with self.db.execute("""
            SELECT * FROM events WHERE actor = ?
            ORDER BY seq DESC LIMIT ?
        """, (actor_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
    
    async def get_event_head(self, actor_id: str) -> Optional[str]:
        async with self.db.execute(
            "SELECT event_id FROM event_heads WHERE actor_id = ?", (actor_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row['event_id'] if row else None
    
    async def get_events_by_type(self, event_type: EventType, limit: int = 100) -> List[Event]:
        async with self.db.execute("""
            SELECT * FROM events WHERE type = ?
            ORDER BY seq DESC LIMIT ?
        """, (event_type.value, limit)) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
    
    def _row_to_event(self, row) -> Event:
        return Event(
            id=row['id'],
            actor=row['actor'],
            type=EventType(row['type']),
            data=json.loads(row['data']),
            ts=datetime.fromisoformat(row['ts']),
            parents=json.loads(row['parents']),
            sig=row['sig'] or b'',
        )
    
    # =========================================================================
    # TRUTH LAYER - States
    # =========================================================================
    
    async def put_state(self, state: State) -> int:
        """Put state (version MUST increment)."""
        async with self.db.execute(
            "SELECT version FROM states WHERE object_id = ?", (state.object_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and state.version <= row['version']:
                raise ValueError(f"Version must increment: {state.version} <= {row['version']}")
        
        await self.db.execute("""
            INSERT OR REPLACE INTO states 
            (object_id, actor, type, version, payload, created_at, updated_at, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            state.object_id,
            state.actor,
            state.type,
            state.version,
            json.dumps(state.payload),
            state.created_at.isoformat(),
            state.updated_at.isoformat(),
            state.sig,
        ))
        await self.db.commit()
        return await self.next_seq()
    
    async def get_state(self, object_id: str) -> Optional[State]:
        async with self.db.execute(
            "SELECT * FROM states WHERE object_id = ?", (object_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return State(
                    object_id=row['object_id'],
                    actor=row['actor'],
                    type=row['type'],
                    version=row['version'],
                    payload=json.loads(row['payload']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    sig=row['sig'] or b'',
                )
        return None
    
    # =========================================================================
    # TRUTH LAYER - Attestations
    # =========================================================================
    
    async def put_attestation(self, attestation: Attestation) -> int:
        await self.db.execute("""
            INSERT OR REPLACE INTO attestations 
            (id, issuer, subject, type, claim, ts, expires_at, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            attestation.id,
            attestation.issuer,
            attestation.subject,
            attestation.type.value,
            json.dumps(attestation.claim),
            attestation.ts.isoformat(),
            attestation.expires_at.isoformat() if attestation.expires_at else None,
            attestation.sig,
        ))
        await self.db.commit()
        return await self.next_seq()
    
    async def get_attestations_for(self, subject: str) -> List[Attestation]:
        async with self.db.execute(
            "SELECT * FROM attestations WHERE subject = ?", (subject,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_attestation(row) for row in rows]
    
    async def get_attestations_by(self, issuer: str) -> List[Attestation]:
        async with self.db.execute(
            "SELECT * FROM attestations WHERE issuer = ?", (issuer,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_attestation(row) for row in rows]
    
    def _row_to_attestation(self, row) -> Attestation:
        return Attestation(
            id=row['id'],
            issuer=row['issuer'],
            subject=row['subject'],
            type=AttestationType(row['type']),
            claim=json.loads(row['claim']),
            ts=datetime.fromisoformat(row['ts']),
            expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
            sig=row['sig'] or b'',
        )
    
    # =========================================================================
    # VIEW LAYER - View Definitions
    # =========================================================================
    
    async def put_view_definition(self, view_def: ViewDefinition) -> int:
        async with self.db.execute(
            "SELECT version FROM view_definitions WHERE object_id = ?", (view_def.object_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and view_def.version <= row['version']:
                raise ValueError("Version must increment")
        
        await self.db.execute("""
            INSERT OR REPLACE INTO view_definitions
            (object_id, actor, version, sources, reduce, params, created_at, updated_at, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            view_def.object_id,
            view_def.actor,
            view_def.version,
            json.dumps(view_def.sources),
            view_def.reduce.value,
            json.dumps(view_def.params),
            view_def.created_at.isoformat(),
            view_def.updated_at.isoformat(),
            view_def.sig,
        ))
        await self.db.commit()
        return await self.next_seq()
    
    async def get_view_definition(self, object_id: str) -> Optional[ViewDefinition]:
        async with self.db.execute(
            "SELECT * FROM view_definitions WHERE object_id = ?", (object_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return ViewDefinition(
                    object_id=row['object_id'],
                    actor=row['actor'],
                    version=row['version'],
                    sources=json.loads(row['sources']),
                    reduce=ReducerType(row['reduce']),
                    params=json.loads(row['params']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    sig=row['sig'] or b'',
                )
        return None
    
    # =========================================================================
    # VIEW LAYER - Caching
    # =========================================================================
    
    async def cache_view_result(self, definition_id: str, boundary_hash: str,
                                 result_hash: str, event_ids: List[str]):
        await self.db.execute("""
            INSERT OR REPLACE INTO view_cache
            (definition_id, boundary_hash, result_hash, event_ids, computed_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            definition_id,
            boundary_hash,
            result_hash,
            json.dumps(event_ids),
            datetime.now().isoformat(),
        ))
        await self.db.commit()
    
    async def get_cached_view(self, definition_id: str, boundary_hash: str) -> Optional[dict]:
        async with self.db.execute("""
            SELECT * FROM view_cache 
            WHERE definition_id = ? AND boundary_hash = ?
        """, (definition_id, boundary_hash)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "result_hash": row['result_hash'],
                    "event_ids": json.loads(row['event_ids']),
                }
        return None
    
    # =========================================================================
    # SOCIAL GRAPH
    # =========================================================================
    
    async def get_followers(self, actor_id: str) -> List[str]:
        async with self.db.execute("""
            SELECT DISTINCT actor FROM events 
            WHERE type = 'follow.add' AND json_extract(data, '$.target') = ?
        """, (actor_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row['actor'] for row in rows]
    
    async def get_following(self, actor_id: str) -> List[str]:
        async with self.db.execute("""
            SELECT DISTINCT json_extract(data, '$.target') as target 
            FROM events 
            WHERE type = 'follow.add' AND actor = ?
        """, (actor_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row['target'] for row in rows if row['target']]
    
    # =========================================================================
    # METRICS
    # =========================================================================
    
    async def get_metrics(self) -> dict:
        metrics = {"layer": "two-layer (truth/view)"}
        
        # Truth layer
        async with self.db.execute("SELECT COUNT(*) FROM identities") as c:
            metrics['identity_count'] = (await c.fetchone())[0]
        
        async with self.db.execute("SELECT COUNT(*) FROM events") as c:
            metrics['event_count'] = (await c.fetchone())[0]
        
        async with self.db.execute("SELECT COUNT(*) FROM states") as c:
            metrics['state_count'] = (await c.fetchone())[0]
        
        async with self.db.execute("SELECT COUNT(*) FROM attestations") as c:
            metrics['attestation_count'] = (await c.fetchone())[0]
        
        # View layer
        async with self.db.execute("SELECT COUNT(*) FROM view_definitions") as c:
            metrics['view_definition_count'] = (await c.fetchone())[0]
        
        async with self.db.execute("SELECT COUNT(*) FROM view_cache") as c:
            metrics['cached_views'] = (await c.fetchone())[0]
        
        async with self.db.execute("SELECT seq FROM sequence WHERE id = 1") as c:
            metrics['sequence'] = (await c.fetchone())[0]
        
        # Event breakdown
        async with self.db.execute("""
            SELECT type, COUNT(*) as count FROM events GROUP BY type
        """) as c:
            metrics['event_breakdown'] = {row['type']: row['count'] for row in await c.fetchall()}
        
        return metrics
