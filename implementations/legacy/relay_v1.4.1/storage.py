"""
Relay v1.4.1 Implementation - Persistent Storage Layer

Based on Relay_v1.4.1.md:
- §8: Identity documents
- §10: Log events with prev chain
- §11: State objects with versioning
- §13: Channels
- §11.1: Feed definitions (v1.4)
"""

import json
import asyncio
import aiosqlite
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from crypto import (
    generate_actor_id, generate_channel_id, generate_event_id,
    verify_object_signature, canonical_json
)


# =============================================================================
# LOG EVENT TYPES (§10, Appendix B, Appendix C)
# =============================================================================

class LogEventType(Enum):
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
    
    # v1.4 action types (§13.4)
    ACTION_REQUEST = "action.request"
    ACTION_COMMIT = "action.commit"
    ACTION_RESULT = "action.result"
    
    # Content
    POST = "post"
    REACTION = "reaction"


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class Identity:
    """Identity document (§8)."""
    actor_id: str
    public_key: bytes
    encryption_key: bytes
    display_name: str = ""
    bio: str = ""
    origins: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    sig: bytes = field(default_factory=bytes)
    
    def to_dict(self) -> dict:
        import base64
        return {
            "actor_id": self.actor_id,
            "keys": {"active": base64.b64encode(self.public_key).decode()},
            "encryption_key": base64.b64encode(self.encryption_key).decode(),
            "display_name": self.display_name,
            "bio": self.bio,
            "origins": self.origins,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }


@dataclass
class LogEvent:
    """
    Log event (§10).
    
    Immutable, append-only with prev chain.
    """
    id: str
    actor: str
    type: LogEventType
    data: dict
    ts: datetime
    prev: Optional[str]  # Previous event in chain
    sig: bytes = field(default_factory=bytes)
    target: Optional[str] = None
    expires_at: Optional[datetime] = None  # v1.5
    
    def to_dict(self) -> dict:
        import base64
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


@dataclass
class StateObject:
    """
    State object (§11).
    
    Versioned, mutable. Version MUST increment on each update.
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
        import base64
        return {
            "object_id": self.object_id,
            "actor": self.actor,
            "type": self.type,
            "version": self.version,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
            "sig": base64.b64encode(self.sig).decode() if self.sig else None,
        }


@dataclass
class ChannelGenesis:
    """Channel genesis document (§4.3.1)."""
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
    """Channel with membership (§13)."""
    channel_id: str
    genesis: ChannelGenesis
    owner: str
    members: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class FeedDefinition:
    """
    Feed definition (§11.1, v1.4).
    
    State type: relay.feed.definition.v1
    """
    object_id: str
    actor: str
    version: int
    sources: List[dict]
    reduce: str  # relay.reduce.chronological.v1 or relay.reduce.reverse_chronological.v1
    params: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    sig: bytes = field(default_factory=bytes)
    
    def to_dict(self) -> dict:
        return {
            "object_id": self.object_id,
            "actor": self.actor,
            "type": "relay.feed.definition.v1",
            "version": self.version,
            "sources": self.sources,
            "reduce": self.reduce,
            "params": self.params,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }


# =============================================================================
# SQLITE STORAGE
# =============================================================================

class Storage:
    """Async SQLite storage for Relay v1.4.1 wire protocol."""
    
    def __init__(self, db_path: str = "relay.db"):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None
    
    async def initialize(self):
        """Initialize database."""
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        
        await self.db.executescript("""
            -- Identities (§8)
            CREATE TABLE IF NOT EXISTS identities (
                actor_id TEXT PRIMARY KEY,
                public_key BLOB NOT NULL,
                encryption_key BLOB NOT NULL,
                display_name TEXT,
                bio TEXT,
                origins TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sig BLOB
            );
            
            -- Log events (§10)
            CREATE TABLE IF NOT EXISTS log_events (
                id TEXT PRIMARY KEY,
                actor TEXT NOT NULL,
                type TEXT NOT NULL,
                data TEXT NOT NULL,
                ts TEXT NOT NULL,
                prev TEXT,
                sig BLOB,
                target TEXT,
                expires_at TEXT,
                seq INTEGER NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_log_actor ON log_events(actor);
            CREATE INDEX IF NOT EXISTS idx_log_type ON log_events(type);
            CREATE INDEX IF NOT EXISTS idx_log_target ON log_events(target);
            CREATE INDEX IF NOT EXISTS idx_log_prev ON log_events(prev);
            CREATE INDEX IF NOT EXISTS idx_log_seq ON log_events(seq);
            
            -- State objects (§11)
            CREATE TABLE IF NOT EXISTS state_objects (
                object_id TEXT PRIMARY KEY,
                actor TEXT NOT NULL,
                type TEXT NOT NULL,
                version INTEGER NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sig BLOB
            );
            
            CREATE INDEX IF NOT EXISTS idx_state_actor ON state_objects(actor);
            CREATE INDEX IF NOT EXISTS idx_state_type ON state_objects(type);
            
            -- Channels (§13)
            CREATE TABLE IF NOT EXISTS channels (
                channel_id TEXT PRIMARY KEY,
                genesis TEXT NOT NULL,
                owner TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            
            -- Channel members
            CREATE TABLE IF NOT EXISTS channel_members (
                channel_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                role TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (channel_id, actor_id)
            );
            
            -- Feed definitions (§11.1)
            CREATE TABLE IF NOT EXISTS feed_definitions (
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
            
            -- Log heads (latest event per actor)
            CREATE TABLE IF NOT EXISTS log_heads (
                actor_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL
            );
            
            -- Sequence counter
            CREATE TABLE IF NOT EXISTS sequence (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                seq INTEGER NOT NULL DEFAULT 0
            );
            
            INSERT OR IGNORE INTO sequence (id, seq) VALUES (1, 0);
            
            -- Sync state (for federation)
            CREATE TABLE IF NOT EXISTS sync_state (
                relay_url TEXT PRIMARY KEY,
                last_seq INTEGER NOT NULL,
                last_sync TEXT NOT NULL
            );
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
    # IDENTITY APIS (§8)
    # =========================================================================
    
    async def put_identity(self, identity: Identity) -> int:
        """PUT identity document."""
        await self.db.execute("""
            INSERT OR REPLACE INTO identities 
            (actor_id, public_key, encryption_key, display_name, bio, origins, 
             created_at, updated_at, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            identity.actor_id,
            identity.public_key,
            identity.encryption_key,
            identity.display_name,
            identity.bio,
            json.dumps(identity.origins),
            identity.created_at.isoformat(),
            identity.updated_at.isoformat(),
            identity.sig,
        ))
        await self.db.commit()
        return await self.next_seq()
    
    async def get_identity(self, actor_id: str) -> Optional[Identity]:
        """GET /actors/{actor_id}/identity"""
        async with self.db.execute(
            "SELECT * FROM identities WHERE actor_id = ?", (actor_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Identity(
                    actor_id=row['actor_id'],
                    public_key=row['public_key'],
                    encryption_key=row['encryption_key'],
                    display_name=row['display_name'] or "",
                    bio=row['bio'] or "",
                    origins=json.loads(row['origins']) if row['origins'] else {},
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    sig=row['sig'] or b'',
                )
        return None
    
    # =========================================================================
    # LOG APIS (§10, §16.3, §17.3-4)
    # =========================================================================
    
    async def append_log(self, event: LogEvent) -> int:
        """
        POST /actors/{actor_id}/log - Append event.
        
        Validates prev chain per §10.
        """
        # Validate prev chain
        async with self.db.execute(
            "SELECT event_id FROM log_heads WHERE actor_id = ?", (event.actor,)
        ) as cursor:
            row = await cursor.fetchone()
            current_head = row['event_id'] if row else None
        
        if event.prev != current_head:
            if not (event.prev is None and current_head is None):
                raise ValueError(f"Invalid prev: expected {current_head}, got {event.prev}")
        
        seq = await self.next_seq()
        
        # Insert event
        await self.db.execute("""
            INSERT INTO log_events (id, actor, type, data, ts, prev, sig, target, expires_at, seq)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.id,
            event.actor,
            event.type.value,
            json.dumps(event.data),
            event.ts.isoformat(),
            event.prev,
            event.sig,
            event.target,
            event.expires_at.isoformat() if event.expires_at else None,
            seq,
        ))
        
        # Update head
        await self.db.execute("""
            INSERT OR REPLACE INTO log_heads (actor_id, event_id) VALUES (?, ?)
        """, (event.actor, event.id))
        
        await self.db.commit()
        return seq
    
    async def get_log(self, actor_id: str, limit: int = 100, 
                      since_seq: int = 0) -> List[LogEvent]:
        """GET /actors/{actor_id}/log"""
        async with self.db.execute("""
            SELECT * FROM log_events 
            WHERE actor = ? AND seq > ?
            ORDER BY seq ASC
            LIMIT ?
        """, (actor_id, since_seq, limit)) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
    
    async def get_log_head(self, actor_id: str) -> Optional[str]:
        """Get latest event_id for actor."""
        async with self.db.execute(
            "SELECT event_id FROM log_heads WHERE actor_id = ?", (actor_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row['event_id'] if row else None
    
    async def get_event(self, event_id: str) -> Optional[LogEvent]:
        """GET /actors/.../log/events/{event_id}"""
        async with self.db.execute(
            "SELECT * FROM log_events WHERE id = ?", (event_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_event(row)
        return None
    
    async def get_events_by_type(self, event_type: LogEventType, 
                                  limit: int = 100) -> List[LogEvent]:
        """Get events by type."""
        async with self.db.execute("""
            SELECT * FROM log_events WHERE type = ?
            ORDER BY seq DESC LIMIT ?
        """, (event_type.value, limit)) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_event(row) for row in rows]
    
    def _row_to_event(self, row) -> LogEvent:
        return LogEvent(
            id=row['id'],
            actor=row['actor'],
            type=LogEventType(row['type']),
            data=json.loads(row['data']),
            ts=datetime.fromisoformat(row['ts']),
            prev=row['prev'],
            sig=row['sig'] or b'',
            target=row['target'],
            expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
        )
    
    # =========================================================================
    # STATE APIS (§11, §16.1)
    # =========================================================================
    
    async def put_state(self, state: StateObject) -> int:
        """
        PUT /actors/{actor_id}/state/{object_id}
        
        Version MUST increment (§16.1).
        """
        # Check version
        async with self.db.execute(
            "SELECT version FROM state_objects WHERE object_id = ?", (state.object_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and state.version <= row['version']:
                raise ValueError(f"Version must increment: {state.version} <= {row['version']}")
        
        await self.db.execute("""
            INSERT OR REPLACE INTO state_objects 
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
    
    async def get_state(self, object_id: str) -> Optional[StateObject]:
        """GET /actors/{actor_id}/state/{object_id}"""
        async with self.db.execute(
            "SELECT * FROM state_objects WHERE object_id = ?", (object_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return StateObject(
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
    # CHANNEL APIS (§13)
    # =========================================================================
    
    async def create_channel(self, genesis: ChannelGenesis) -> Channel:
        """Create channel with genesis (§4.3.1)."""
        channel_id = generate_channel_id(genesis.to_dict())
        
        await self.db.execute("""
            INSERT INTO channels (channel_id, genesis, owner, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            channel_id,
            json.dumps(genesis.to_dict()),
            genesis.owner_actor_id,
            genesis.created_at.isoformat(),
        ))
        
        # Owner is first member
        await self.db.execute("""
            INSERT INTO channel_members (channel_id, actor_id, role, joined_at)
            VALUES (?, ?, ?, ?)
        """, (channel_id, genesis.owner_actor_id, "owner", genesis.created_at.isoformat()))
        
        await self.db.commit()
        
        return Channel(
            channel_id=channel_id,
            genesis=genesis,
            owner=genesis.owner_actor_id,
            members=[genesis.owner_actor_id],
            created_at=genesis.created_at,
        )
    
    async def get_channel(self, channel_id: str) -> Optional[Channel]:
        async with self.db.execute(
            "SELECT * FROM channels WHERE channel_id = ?", (channel_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            
            # Get members
            async with self.db.execute(
                "SELECT actor_id FROM channel_members WHERE channel_id = ?", (channel_id,)
            ) as mem_cursor:
                members = [m['actor_id'] for m in await mem_cursor.fetchall()]
            
            genesis_dict = json.loads(row['genesis'])
            return Channel(
                channel_id=channel_id,
                genesis=ChannelGenesis(
                    kind=genesis_dict['kind'],
                    owner_actor_id=genesis_dict['owner_actor_id'],
                    name=genesis_dict['name'],
                    created_at=datetime.fromisoformat(genesis_dict['created_at'].rstrip('Z')),
                ),
                owner=row['owner'],
                members=members,
                created_at=datetime.fromisoformat(row['created_at']),
            )
    
    async def add_channel_member(self, channel_id: str, actor_id: str, role: str = "member"):
        await self.db.execute("""
            INSERT OR IGNORE INTO channel_members (channel_id, actor_id, role, joined_at)
            VALUES (?, ?, ?, ?)
        """, (channel_id, actor_id, role, datetime.now().isoformat()))
        await self.db.commit()
    
    # =========================================================================
    # FEED DEFINITION APIS (§11.1)
    # =========================================================================
    
    async def put_feed_definition(self, feed_def: FeedDefinition) -> int:
        """PUT feed definition."""
        async with self.db.execute(
            "SELECT version FROM feed_definitions WHERE object_id = ?", (feed_def.object_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and feed_def.version <= row['version']:
                raise ValueError("Version must increment")
        
        await self.db.execute("""
            INSERT OR REPLACE INTO feed_definitions
            (object_id, actor, version, sources, reduce, params, created_at, updated_at, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feed_def.object_id,
            feed_def.actor,
            feed_def.version,
            json.dumps(feed_def.sources),
            feed_def.reduce,
            json.dumps(feed_def.params),
            feed_def.created_at.isoformat(),
            feed_def.updated_at.isoformat(),
            feed_def.sig,
        ))
        await self.db.commit()
        return await self.next_seq()
    
    async def get_feed_definition(self, object_id: str) -> Optional[FeedDefinition]:
        async with self.db.execute(
            "SELECT * FROM feed_definitions WHERE object_id = ?", (object_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return FeedDefinition(
                    object_id=row['object_id'],
                    actor=row['actor'],
                    version=row['version'],
                    sources=json.loads(row['sources']),
                    reduce=row['reduce'],
                    params=json.loads(row['params']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    sig=row['sig'] or b'',
                )
        return None
    
    # =========================================================================
    # SOCIAL GRAPH QUERIES
    # =========================================================================
    
    async def get_followers(self, actor_id: str) -> List[str]:
        """Get followers (from follow.add events targeting this actor)."""
        async with self.db.execute("""
            SELECT DISTINCT actor FROM log_events 
            WHERE type = 'follow.add' AND target = ?
            AND actor NOT IN (
                SELECT actor FROM log_events 
                WHERE type = 'follow.remove' AND target = ?
            )
        """, (actor_id, actor_id)) as cursor:
            rows = await cursor.fetchall()
            return [row['actor'] for row in rows]
    
    async def get_following(self, actor_id: str) -> List[str]:
        """Get who this actor follows."""
        async with self.db.execute("""
            SELECT DISTINCT target FROM log_events 
            WHERE type = 'follow.add' AND actor = ?
            AND target NOT IN (
                SELECT target FROM log_events 
                WHERE type = 'follow.remove' AND actor = ?
            )
        """, (actor_id, actor_id)) as cursor:
            rows = await cursor.fetchall()
            return [row['target'] for row in rows]
    
    # =========================================================================
    # METRICS
    # =========================================================================
    
    async def get_metrics(self) -> dict:
        metrics = {}
        
        async with self.db.execute("SELECT COUNT(*) FROM identities") as c:
            metrics['identity_count'] = (await c.fetchone())[0]
        
        async with self.db.execute("SELECT COUNT(*) FROM log_events") as c:
            metrics['event_count'] = (await c.fetchone())[0]
        
        async with self.db.execute("SELECT COUNT(*) FROM state_objects") as c:
            metrics['state_count'] = (await c.fetchone())[0]
        
        async with self.db.execute("SELECT COUNT(*) FROM channels") as c:
            metrics['channel_count'] = (await c.fetchone())[0]
        
        async with self.db.execute("SELECT COUNT(*) FROM feed_definitions") as c:
            metrics['feed_definition_count'] = (await c.fetchone())[0]
        
        async with self.db.execute("SELECT seq FROM sequence WHERE id = 1") as c:
            metrics['sequence'] = (await c.fetchone())[0]
        
        # Event type breakdown
        async with self.db.execute("""
            SELECT type, COUNT(*) as count FROM log_events GROUP BY type
        """) as c:
            metrics['event_breakdown'] = {row['type']: row['count'] for row in await c.fetchall()}
        
        return metrics
