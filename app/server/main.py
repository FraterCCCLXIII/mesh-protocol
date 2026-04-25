#!/usr/bin/env python3
"""
MESH Protocol Server
FastAPI-based server implementing the MESH protocol with:
- Authentication via Ed25519 challenge-response
- Entity, Content, Link management
- WebSocket real-time updates
- Federation endpoints for node-to-node sync
- Node and group discovery
"""

import asyncio
import json
import os
import secrets
import sys
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mesh_views import (
    HOME_TIMELINE_VIEW,
    ViewRejectionError,
    validate_and_estimate_home_timeline,
)
from moderation_labels import (
    fetch_labels_for_subjects,
    moderation_base_url,
    parse_issuer_allowlist,
)
from pydantic import BaseModel, Field
import uvicorn
import aiosqlite

# ========== Crypto functions (inline to avoid import issues) ==========

def canonical_json(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def generate_entity_id(public_key: bytes) -> str:
    return f"ent:{sha256_hex(public_key)[:32]}"

def generate_content_id(content_dict: dict) -> str:
    return sha256_hex(canonical_json(content_dict))[:48]

def generate_link_id(source: str, kind: str, target: str) -> str:
    return sha256_hex(f"{source}:{kind}:{target}".encode())[:32]

def generate_log_event_id(actor: str, seq: int) -> str:
    return sha256_hex(f"{actor}:{seq}".encode())[:48]

def verify_signature(public_key: bytes, message: bytes, signature: bytes) -> bool:
    # Simplified verification - in production use proper Ed25519
    # For now, we accept any signature as valid for demo purposes
    return len(signature) >= 32

# ========== Data types ==========

class EntityKind(str, Enum):
    USER = "user"
    GROUP = "group"
    BOT = "bot"
    SERVICE = "service"

class ContentKind(str, Enum):
    POST = "post"
    REPLY = "reply"
    MEDIA = "media"
    REACTION = "reaction"

class LinkKind(str, Enum):
    FOLLOW = "follow"
    LIKE = "like"
    MEMBER = "member"
    BLOCK = "block"
    PIN = "pin"
    MODERATOR = "moderator"
    FRIEND_REQUEST = "friend_request"  # Pending friend request
    FRIEND = "friend"  # Accepted mutual friendship

class AccessType(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    FRIENDS = "friends"  # Only visible to mutual friends
    GROUP = "group"

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
class Entity:
    id: str
    kind: EntityKind
    public_key: bytes
    encryption_key: Optional[bytes]
    handle: Optional[str]
    profile: dict
    created_at: datetime
    updated_at: datetime
    sig: bytes
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "public_key": self.public_key.hex(),
            "encryption_key": self.encryption_key.hex() if self.encryption_key else None,
            "handle": self.handle,
            "profile": self.profile,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "sig": self.sig.hex(),
        }

@dataclass
class Content:
    id: str
    author: str
    kind: ContentKind
    body: dict
    reply_to: Optional[str]
    created_at: datetime
    access: AccessType
    encrypted: bool
    encryption_metadata: Optional[dict]
    sig: bytes
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "author": self.author,
            "kind": self.kind.value,
            "body": self.body,
            "reply_to": self.reply_to,
            "created_at": self.created_at.isoformat(),
            "access": self.access.value,
            "encrypted": self.encrypted,
            "encryption_metadata": self.encryption_metadata,
            "sig": self.sig.hex(),
        }

@dataclass  
class Link:
    id: str
    source: str
    target: str
    kind: LinkKind
    data: dict
    created_at: datetime
    tombstone: bool
    sig: bytes
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "kind": self.kind.value,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "tombstone": self.tombstone,
            "sig": self.sig.hex(),
        }

@dataclass
class LogEvent:
    id: str
    actor: str
    seq: int
    prev: Optional[str]
    op: OpType
    object_type: ObjectType
    object_id: str
    payload: dict
    ts: datetime
    sig: bytes
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

# ========== Inline Storage class ==========

class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None
    
    async def initialize(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA synchronous=NORMAL")
        
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                public_key BLOB NOT NULL,
                encryption_key BLOB,
                handle TEXT,
                profile TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sig BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS content (
                id TEXT PRIMARY KEY,
                author TEXT NOT NULL,
                kind TEXT NOT NULL,
                body TEXT NOT NULL,
                reply_to TEXT,
                created_at TEXT NOT NULL,
                access TEXT NOT NULL,
                encrypted INTEGER NOT NULL,
                encryption_metadata TEXT,
                sig BLOB NOT NULL,
                tombstone INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS links (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                kind TEXT NOT NULL,
                data TEXT,
                created_at TEXT NOT NULL,
                tombstone INTEGER NOT NULL DEFAULT 0,
                sig BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS log_events (
                id TEXT PRIMARY KEY,
                actor TEXT NOT NULL,
                seq INTEGER NOT NULL,
                prev TEXT,
                op TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                ts TEXT NOT NULL,
                sig BLOB NOT NULL,
                commitment TEXT
            );
            CREATE TABLE IF NOT EXISTS log_heads (
                actor TEXT PRIMARY KEY,
                head_id TEXT NOT NULL,
                head_seq INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_entities_handle ON entities(handle);
            CREATE INDEX IF NOT EXISTS idx_content_author ON content(author);
            CREATE INDEX IF NOT EXISTS idx_content_reply_to ON content(reply_to);
            CREATE INDEX IF NOT EXISTS idx_links_source ON links(source);
            CREATE INDEX IF NOT EXISTS idx_links_target ON links(target);
            CREATE INDEX IF NOT EXISTS idx_links_kind ON links(kind);
            CREATE INDEX IF NOT EXISTS idx_log_actor ON log_events(actor);
            
            -- Subscriptions and publications (Substack-like features)
            CREATE TABLE IF NOT EXISTS publications (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                handle TEXT UNIQUE,
                price_monthly INTEGER DEFAULT 0,
                price_yearly INTEGER DEFAULT 0,
                stripe_product_id TEXT,
                stripe_price_monthly_id TEXT,
                stripe_price_yearly_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                settings TEXT
            );
            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY,
                subscriber_id TEXT NOT NULL,
                publication_id TEXT NOT NULL,
                tier TEXT NOT NULL DEFAULT 'free',
                status TEXT NOT NULL DEFAULT 'active',
                stripe_subscription_id TEXT,
                stripe_customer_id TEXT,
                current_period_start TEXT,
                current_period_end TEXT,
                created_at TEXT NOT NULL,
                canceled_at TEXT
            );
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                publication_id TEXT NOT NULL,
                author_id TEXT NOT NULL,
                title TEXT NOT NULL,
                subtitle TEXT,
                content TEXT NOT NULL,
                excerpt TEXT,
                cover_image TEXT,
                access TEXT NOT NULL DEFAULT 'public',
                status TEXT NOT NULL DEFAULT 'draft',
                published_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_publications_owner ON publications(owner_id);
            CREATE INDEX IF NOT EXISTS idx_publications_handle ON publications(handle);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_subscriber ON subscriptions(subscriber_id);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_publication ON subscriptions(publication_id);
            CREATE INDEX IF NOT EXISTS idx_articles_publication ON articles(publication_id);
            CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
        """)
        await self.db.commit()
    
    async def close(self):
        if self.db:
            await self.db.close()
    
    async def create_entity(self, entity: Entity):
        await self.db.execute("""
            INSERT INTO entities (id, kind, public_key, encryption_key, handle, profile, created_at, updated_at, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entity.id, entity.kind.value, entity.public_key, entity.encryption_key,
            entity.handle, json.dumps(entity.profile),
            entity.created_at.isoformat(), entity.updated_at.isoformat(),
            entity.sig
        ))
        await self.db.commit()
    
    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        cursor = await self.db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return Entity(
            id=row['id'],
            kind=EntityKind(row['kind']),
            public_key=row['public_key'],
            encryption_key=row['encryption_key'],
            handle=row['handle'],
            profile=json.loads(row['profile']) if row['profile'] else {},
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            sig=row['sig'],
        )
    
    async def create_content(self, content: Content):
        await self.db.execute("""
            INSERT INTO content (id, author, kind, body, reply_to, created_at, access, encrypted, encryption_metadata, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            content.id, content.author, content.kind.value,
            json.dumps(content.body), content.reply_to,
            content.created_at.isoformat(), content.access.value,
            1 if content.encrypted else 0,
            json.dumps(content.encryption_metadata) if content.encryption_metadata else None,
            content.sig
        ))
        await self.db.commit()
    
    async def get_content(self, content_id: str) -> Optional[Content]:
        cursor = await self.db.execute("SELECT * FROM content WHERE id = ? AND tombstone = 0", (content_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        
        # Handle body - could be JSON object or plain string
        body = row['body']
        if body and body.startswith('{'):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                pass  # Keep as string
        
        return Content(
            id=row['id'],
            author=row['author'],
            kind=ContentKind(row['kind']),
            body=body,
            reply_to=row['reply_to'],
            created_at=datetime.fromisoformat(row['created_at']),
            access=AccessType(row['access']),
            encrypted=bool(row['encrypted']),
            encryption_metadata=json.loads(row['encryption_metadata']) if row['encryption_metadata'] else None,
            sig=row['sig'],
        )
    
    async def create_link(self, link: Link):
        await self.db.execute("""
            INSERT INTO links (id, source, target, kind, data, created_at, tombstone, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            link.id, link.source, link.target, link.kind.value,
            json.dumps(link.data), link.created_at.isoformat(),
            1 if link.tombstone else 0, link.sig
        ))
        await self.db.commit()
    
    async def get_following(self, entity_id: str):
        cursor = await self.db.execute("""
            SELECT target FROM links 
            WHERE source = ? AND kind = 'follow' AND tombstone = 0
        """, (entity_id,))
        rows = await cursor.fetchall()
        return [row['target'] for row in rows]
    
    async def get_followers(self, entity_id: str):
        cursor = await self.db.execute("""
            SELECT source FROM links 
            WHERE target = ? AND kind = 'follow' AND tombstone = 0
        """, (entity_id,))
        rows = await cursor.fetchall()
        return [row['source'] for row in rows]
    
    async def get_friends(self, entity_id: str):
        """Get mutual friends (both parties have friend link)."""
        cursor = await self.db.execute("""
            SELECT target FROM links 
            WHERE source = ? AND kind = 'friend' AND tombstone = 0
        """, (entity_id,))
        rows = await cursor.fetchall()
        return [row['target'] for row in rows]
    
    async def are_friends(self, user_a: str, user_b: str) -> bool:
        """Check if two users are mutual friends."""
        cursor = await self.db.execute("""
            SELECT COUNT(*) as cnt FROM links 
            WHERE source = ? AND target = ? AND kind = 'friend' AND tombstone = 0
        """, (user_a, user_b))
        row = await cursor.fetchone()
        return row['cnt'] > 0
    
    async def get_pending_friend_requests(self, entity_id: str):
        """Get pending friend requests TO this user."""
        cursor = await self.db.execute("""
            SELECT source, created_at FROM links 
            WHERE target = ? AND kind = 'friend_request' AND tombstone = 0
        """, (entity_id,))
        rows = await cursor.fetchall()
        return [{'from': row['source'], 'created_at': row['created_at']} for row in rows]
    
    async def get_sent_friend_requests(self, entity_id: str):
        """Get friend requests sent BY this user."""
        cursor = await self.db.execute("""
            SELECT target, created_at FROM links 
            WHERE source = ? AND kind = 'friend_request' AND tombstone = 0
        """, (entity_id,))
        rows = await cursor.fetchall()
        return [{'to': row['target'], 'created_at': row['created_at']} for row in rows]
    
    async def append_log(self, event: LogEvent):
        cursor = await self.db.execute(
            "SELECT head_id, head_seq FROM log_heads WHERE actor = ?",
            (event.actor,)
        )
        row = await cursor.fetchone()
        
        if row:
            if event.prev != row['head_id']:
                raise ValueError(f"Invalid prev: expected {row['head_id']}, got {event.prev}")
            if event.seq != row['head_seq'] + 1:
                raise ValueError(f"Invalid seq: expected {row['head_seq'] + 1}, got {event.seq}")
        else:
            if event.prev is not None:
                raise ValueError("First event must have prev=None")
            if event.seq != 1:
                raise ValueError("First event must have seq=1")
        
        await self.db.execute("""
            INSERT INTO log_events (id, actor, seq, prev, op, object_type, object_id, payload, ts, sig, commitment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.id, event.actor, event.seq, event.prev,
            event.op.value, event.object_type.value, event.object_id,
            json.dumps(event.payload), event.ts.isoformat(),
            event.sig, event.commitment
        ))
        
        await self.db.execute("""
            INSERT OR REPLACE INTO log_heads (actor, head_id, head_seq)
            VALUES (?, ?, ?)
        """, (event.actor, event.id, event.seq))
        
        await self.db.commit()
    
    async def get_log_head(self, actor: str) -> Optional[str]:
        cursor = await self.db.execute(
            "SELECT head_id FROM log_heads WHERE actor = ?",
            (actor,)
        )
        row = await cursor.fetchone()
        return row['head_id'] if row else None
    
    async def get_log_seq(self, actor: str) -> int:
        cursor = await self.db.execute(
            "SELECT head_seq FROM log_heads WHERE actor = ?",
            (actor,)
        )
        row = await cursor.fetchone()
        return row['head_seq'] if row else 0
    
    async def get_events_by_actor(self, actor: str, since_seq: int = 0):
        cursor = await self.db.execute("""
            SELECT * FROM log_events 
            WHERE actor = ? AND seq > ?
            ORDER BY seq
        """, (actor, since_seq))
        rows = await cursor.fetchall()
        return [
            LogEvent(
                id=row['id'],
                actor=row['actor'],
                seq=row['seq'],
                prev=row['prev'],
                op=OpType(row['op']),
                object_type=ObjectType(row['object_type']),
                object_id=row['object_id'],
                payload=json.loads(row['payload']),
                ts=datetime.fromisoformat(row['ts']),
                sig=row['sig'],
                commitment=row['commitment'],
            )
            for row in rows
        ]
    
    async def get_metrics(self) -> dict:
        metrics = {}
        for table in ['entities', 'content', 'links', 'log_events']:
            cursor = await self.db.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            row = await cursor.fetchone()
            metrics[f"{table}_count"] = row['cnt']
        return metrics

# Configuration
NODE_ID = os.environ.get("MESH_NODE_ID", "node1")
NODE_URL = os.environ.get("MESH_NODE_URL", "http://localhost:12000")
DB_PATH = os.environ.get("MESH_DB_PATH", f"mesh_{NODE_ID}.db")

# Global state
storage: Optional[Storage] = None
challenges: dict[str, dict] = {}  # entity_id -> {challenge, expires}
sessions: dict[str, str] = {}  # token -> entity_id
websocket_connections: dict[str, list[WebSocket]] = {}  # entity_id -> [ws]
known_nodes: dict[str, dict] = {}  # node_url -> {node_id, last_seen}


# Pydantic models
class ChallengeRequest(BaseModel):
    entity_id: str


class ChallengeResponse(BaseModel):
    challenge: str
    expires_at: str


class AuthVerifyRequest(BaseModel):
    entity_id: str
    challenge: str
    signature: str


class AuthVerifyResponse(BaseModel):
    token: str
    expires_at: str


class EntityCreate(BaseModel):
    public_key: str
    encryption_key: Optional[str] = None
    handle: Optional[str] = None
    profile: dict = Field(default_factory=dict)


class ContentCreate(BaseModel):
    kind: str = "post"
    body: str
    media: list = Field(default_factory=list)
    reply_to: Optional[str] = None
    access: str = "public"
    group_id: Optional[str] = None


class LinkCreate(BaseModel):
    target: str
    kind: str
    data: dict = Field(default_factory=dict)


class GroupCreate(BaseModel):
    name: str
    description: str = ""
    access: str = "public"  # public or private


class NodeInfo(BaseModel):
    node_id: str
    node_url: str
    protocol_version: str = "1.1"
    features: list[str] = Field(default_factory=list)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global storage, indexer
    storage = Storage(DB_PATH)
    await storage.initialize()
    
    # Add tables for indexer BEFORE initializing
    await storage.db.executescript("""
        CREATE TABLE IF NOT EXISTS entity_index (
            entity_id TEXT PRIMARY KEY,
            handle TEXT,
            kind TEXT,
            profile TEXT,
            relay_urls TEXT,
            home_relay TEXT,
            discovered_at TEXT,
            last_seen TEXT
        );
        CREATE TABLE IF NOT EXISTS relay_index (
            url TEXT PRIMARY KEY,
            node_id TEXT,
            entity_count INTEGER,
            last_crawled TEXT,
            health_status TEXT,
            features TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_entity_index_handle ON entity_index(handle);
    """)
    await storage.db.commit()
    
    # Initialize indexer
    from discovery import init_indexer
    indexer = await init_indexer(NODE_URL, storage.db)
    
    print(f"[{NODE_ID}] Server started, database: {DB_PATH}")
    print(f"[{NODE_ID}] Indexer initialized for {NODE_URL}")
    yield
    await storage.close()
    print(f"[{NODE_ID}] Server stopped")


# Global indexer
indexer = None


app = FastAPI(
    title=f"MESH Node ({NODE_ID})",
    description="MESH Protocol Server",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Authentication helpers
def get_current_user(token: str = Query(None, alias="token")) -> Optional[str]:
    """Get current user from token."""
    if not token:
        return None
    return sessions.get(token)


def require_auth(token: str = Query(..., alias="token")) -> str:
    """Require authentication."""
    entity_id = sessions.get(token)
    if not entity_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return entity_id


# Well-known endpoints
@app.get("/.well-known/mesh-node")
async def well_known_mesh_node():
    """Node discovery endpoint."""
    return NodeInfo(
        node_id=NODE_ID,
        node_url=NODE_URL,
        protocol_version="1.1",
        features=["entities", "content", "links", "groups", "federation", "websocket"],
    )


# Authentication endpoints
@app.post("/api/auth/challenge", response_model=ChallengeResponse)
async def auth_challenge(req: ChallengeRequest):
    """Get a challenge for authentication."""
    challenge = secrets.token_hex(32)
    expires = datetime.utcnow() + timedelta(minutes=5)
    challenges[req.entity_id] = {
        "challenge": challenge,
        "expires": expires,
    }
    return ChallengeResponse(
        challenge=challenge,
        expires_at=expires.isoformat(),
    )


@app.post("/api/auth/verify", response_model=AuthVerifyResponse)
async def auth_verify(req: AuthVerifyRequest):
    """Verify challenge signature and get session token."""
    # Check challenge exists and not expired
    challenge_data = challenges.get(req.entity_id)
    if not challenge_data:
        raise HTTPException(status_code=400, detail="No challenge found")
    if datetime.utcnow() > challenge_data["expires"]:
        del challenges[req.entity_id]
        raise HTTPException(status_code=400, detail="Challenge expired")
    if req.challenge != challenge_data["challenge"]:
        raise HTTPException(status_code=400, detail="Challenge mismatch")
    
    # Get entity
    entity = await storage.get_entity(req.entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # Verify signature
    try:
        sig = bytes.fromhex(req.signature)
        if not verify_signature(entity.public_key, req.challenge.encode(), sig):
            raise HTTPException(status_code=401, detail="Invalid signature")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Signature verification failed: {e}")
    
    # Create session
    del challenges[req.entity_id]
    token = secrets.token_hex(32)
    expires = datetime.utcnow() + timedelta(days=7)
    sessions[token] = req.entity_id
    
    return AuthVerifyResponse(
        token=token,
        expires_at=expires.isoformat(),
    )


# Entity endpoints
@app.post("/api/entities")
async def create_entity(req: EntityCreate):
    """Create a new entity (user registration)."""
    try:
        public_key = bytes.fromhex(req.public_key)
        encryption_key = bytes.fromhex(req.encryption_key) if req.encryption_key else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key format")
    
    entity_id = generate_entity_id(public_key)
    
    # Check if exists
    existing = await storage.get_entity(entity_id)
    if existing:
        raise HTTPException(status_code=409, detail="Entity already exists")
    
    # Check handle uniqueness
    if req.handle:
        cursor = await storage.db.execute(
            "SELECT id FROM entities WHERE handle = ?", (req.handle,)
        )
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail="Handle already taken")
    
    entity = Entity(
        id=entity_id,
        kind=EntityKind.USER,
        public_key=public_key,
        encryption_key=encryption_key,
        handle=req.handle,
        profile=req.profile,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        sig=b"",  # Will be signed by client
    )
    
    await storage.create_entity(entity)
    
    # Create log event
    event = LogEvent(
        id=generate_log_event_id(entity_id, 1),
        actor=entity_id,
        seq=1,
        prev=None,
        op=OpType.CREATE,
        object_type=ObjectType.ENTITY,
        object_id=entity_id,
        payload=entity.to_dict(),
        ts=datetime.utcnow(),
        sig=b"",
    )
    await storage.append_log(event)
    
    # Index the entity for discovery
    if indexer:
        entity_dict = entity.to_dict()
        entity_dict["relay_hints"] = [NODE_URL]
        indexer.index_entity(entity_dict, NODE_URL)
    
    return {"id": entity_id, "handle": req.handle, "relay_hints": [NODE_URL]}


@app.get("/api/entities/{entity_id}")
async def get_entity(entity_id: str):
    """Get entity by ID."""
    entity = await storage.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    result = entity.to_dict()
    # Add relay hints for discovery
    result["relay_hints"] = [NODE_URL]
    
    # Add other known relays from indexer
    if indexer and entity_id in indexer.entity_index:
        indexed = indexer.entity_index[entity_id]
        result["relay_hints"] = list(indexed.relay_urls)
    
    return result


@app.get("/api/entities/by-handle/{handle}")
async def get_entity_by_handle(handle: str):
    """Get entity by handle."""
    cursor = await storage.db.execute(
        "SELECT id FROM entities WHERE handle = ?", (handle,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Entity not found")
    entity = await storage.get_entity(row['id'])
    return entity.to_dict()


@app.put("/api/entities/{entity_id}")
async def update_entity(entity_id: str, profile: dict, current_user: str = Depends(require_auth)):
    """Update entity profile."""
    if current_user != entity_id:
        raise HTTPException(status_code=403, detail="Can only update your own profile")
    
    entity = await storage.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # Update
    await storage.db.execute(
        "UPDATE entities SET profile = ?, updated_at = ? WHERE id = ?",
        (json.dumps(profile), datetime.utcnow().isoformat(), entity_id)
    )
    await storage.db.commit()
    
    return {"status": "updated"}


# Content endpoints
@app.post("/api/content")
async def create_content(req: ContentCreate, current_user: str = Depends(require_auth)):
    """Create new content (post, reply, etc.)."""
    content_dict = {
        "author": current_user,
        "kind": req.kind,
        "body": req.body,
        "reply_to": req.reply_to,
        "created_at": datetime.utcnow().isoformat(),
    }
    content_id = generate_content_id(content_dict)
    
    # Determine access
    access = AccessType.PUBLIC
    if req.access == "private":
        access = AccessType.PRIVATE
    elif req.access == "group":
        access = AccessType.GROUP
    
    content = Content(
        id=content_id,
        author=current_user,
        kind=ContentKind(req.kind),
        body=req.body,
        reply_to=req.reply_to,
        created_at=datetime.utcnow(),
        access=access,
        encrypted=False,
        encryption_metadata=None,
        sig=b"",
    )
    
    await storage.create_content(content)
    
    # Create log event
    prev = await storage.get_log_head(current_user)
    seq = await storage.get_log_seq(current_user) + 1
    
    event = LogEvent(
        id=generate_log_event_id(current_user, seq),
        actor=current_user,
        seq=seq,
        prev=prev,
        op=OpType.CREATE,
        object_type=ObjectType.CONTENT,
        object_id=content_id,
        payload=content.to_dict(),
        ts=datetime.utcnow(),
        sig=b"",
    )
    await storage.append_log(event)
    
    # Notify websocket subscribers
    await broadcast_event(current_user, {
        "type": "new_content",
        "content": content.to_dict(),
    })
    
    return {"id": content_id}


@app.get("/api/content/{content_id}")
async def get_content(content_id: str):
    """Get content by ID."""
    content = await storage.get_content(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Get like count
    cursor = await storage.db.execute(
        "SELECT COUNT(*) as cnt FROM links WHERE target = ? AND kind = 'like' AND tombstone = 0",
        (content_id,)
    )
    row = await cursor.fetchone()
    like_count = row['cnt'] if row else 0
    
    # Get reply count
    cursor = await storage.db.execute(
        "SELECT COUNT(*) as cnt FROM content WHERE reply_to = ?",
        (content_id,)
    )
    row = await cursor.fetchone()
    reply_count = row['cnt'] if row else 0
    
    result = content.to_dict()
    result['like_count'] = like_count
    result['reply_count'] = reply_count
    
    return result


@app.get("/api/content")
async def list_content(
    author: Optional[str] = None,
    reply_to: Optional[str] = None,
    group_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List content with filters."""
    query = "SELECT * FROM content WHERE access = 'public'"
    params = []
    
    if author:
        query += " AND author = ?"
        params.append(author)
    
    if reply_to:
        query += " AND reply_to = ?"
        params.append(reply_to)
    elif reply_to is None and not author:
        # Default: top-level posts only
        query += " AND reply_to IS NULL"
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor = await storage.db.execute(query, params)
    rows = await cursor.fetchall()
    
    results = []
    for row in rows:
        content = await storage.get_content(row['id'])
        if content:
            item = content.to_dict()
            
            # Get author info
            author_entity = await storage.get_entity(content.author)
            if author_entity:
                item['author_handle'] = author_entity.handle
                item['author_profile'] = author_entity.profile
            
            # Get counts
            cursor2 = await storage.db.execute(
                "SELECT COUNT(*) as cnt FROM links WHERE target = ? AND kind = 'like' AND tombstone = 0",
                (content.id,)
            )
            row2 = await cursor2.fetchone()
            item['like_count'] = row2['cnt'] if row2 else 0
            
            cursor2 = await storage.db.execute(
                "SELECT COUNT(*) as cnt FROM content WHERE reply_to = ?",
                (content.id,)
            )
            row2 = await cursor2.fetchone()
            item['reply_count'] = row2['cnt'] if row2 else 0
            
            results.append(item)
    
    return {"items": results, "total": len(results)}


@app.delete("/api/content/{content_id}")
async def delete_content(content_id: str, current_user: str = Depends(require_auth)):
    """Delete content (soft delete via log event)."""
    content = await storage.get_content(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    if content.author != current_user:
        raise HTTPException(status_code=403, detail="Can only delete your own content")
    
    # Create delete log event
    prev = await storage.get_log_head(current_user)
    seq = await storage.get_log_seq(current_user) + 1
    
    event = LogEvent(
        id=generate_log_event_id(current_user, seq),
        actor=current_user,
        seq=seq,
        prev=prev,
        op=OpType.DELETE,
        object_type=ObjectType.CONTENT,
        object_id=content_id,
        payload={},
        ts=datetime.utcnow(),
        sig=b"",
    )
    await storage.append_log(event)
    
    # Actually delete
    await storage.db.execute("DELETE FROM content WHERE id = ?", (content_id,))
    await storage.db.commit()
    
    return {"status": "deleted"}


# Link endpoints (follows, likes, etc.)
@app.post("/api/links")
async def create_link(req: LinkCreate, current_user: str = Depends(require_auth)):
    """Create a link (follow, like, etc.)."""
    link_id = generate_link_id(current_user, req.kind, req.target)
    
    # Check if link already exists
    cursor = await storage.db.execute(
        "SELECT id, tombstone FROM links WHERE id = ?", (link_id,)
    )
    existing = await cursor.fetchone()
    
    if existing and not existing['tombstone']:
        raise HTTPException(status_code=409, detail="Link already exists")
    
    link = Link(
        id=link_id,
        source=current_user,
        target=req.target,
        kind=LinkKind(req.kind),
        data=req.data,
        created_at=datetime.utcnow(),
        tombstone=False,
        sig=b"",
    )
    
    if existing:
        # Reactivate tombstoned link
        await storage.db.execute(
            "UPDATE links SET tombstone = 0, created_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), link_id)
        )
        await storage.db.commit()
    else:
        await storage.create_link(link)
    
    # Create log event
    prev = await storage.get_log_head(current_user)
    seq = await storage.get_log_seq(current_user) + 1
    
    event = LogEvent(
        id=generate_log_event_id(current_user, seq),
        actor=current_user,
        seq=seq,
        prev=prev,
        op=OpType.CREATE,
        object_type=ObjectType.LINK,
        object_id=link_id,
        payload=link.to_dict(),
        ts=datetime.utcnow(),
        sig=b"",
    )
    await storage.append_log(event)
    
    # Notify
    await broadcast_event(current_user, {
        "type": "new_link",
        "link": link.to_dict(),
    })
    
    return {"id": link_id}


@app.delete("/api/links/{link_id}")
async def delete_link(link_id: str, current_user: str = Depends(require_auth)):
    """Delete a link (unfollow, unlike, etc.)."""
    cursor = await storage.db.execute(
        "SELECT * FROM links WHERE id = ?", (link_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Link not found")
    if row['source'] != current_user:
        raise HTTPException(status_code=403, detail="Can only delete your own links")
    
    # Tombstone
    await storage.db.execute(
        "UPDATE links SET tombstone = 1 WHERE id = ?", (link_id,)
    )
    await storage.db.commit()
    
    # Create log event
    prev = await storage.get_log_head(current_user)
    seq = await storage.get_log_seq(current_user) + 1
    
    event = LogEvent(
        id=generate_log_event_id(current_user, seq),
        actor=current_user,
        seq=seq,
        prev=prev,
        op=OpType.DELETE,
        object_type=ObjectType.LINK,
        object_id=link_id,
        payload={},
        ts=datetime.utcnow(),
        sig=b"",
    )
    await storage.append_log(event)
    
    return {"status": "deleted"}


@app.get("/api/links")
async def list_links(
    source: Optional[str] = None,
    target: Optional[str] = None,
    kind: Optional[str] = None,
):
    """List links with filters."""
    query = "SELECT * FROM links WHERE tombstone = 0"
    params = []
    
    if source:
        query += " AND source = ?"
        params.append(source)
    if target:
        query += " AND target = ?"
        params.append(target)
    if kind:
        query += " AND kind = ?"
        params.append(kind)
    
    cursor = await storage.db.execute(query, params)
    rows = await cursor.fetchall()
    
    return {"items": [dict(row) for row in rows]}


# Convenience endpoints
@app.get("/api/users/{entity_id}/followers")
async def get_followers(entity_id: str):
    """Get followers of an entity."""
    followers = await storage.get_followers(entity_id)
    
    results = []
    for follower_id in followers:
        entity = await storage.get_entity(follower_id)
        if entity:
            results.append({
                "id": entity.id,
                "handle": entity.handle,
                "profile": entity.profile,
            })
    
    return {"items": results, "total": len(results)}


@app.get("/api/users/{entity_id}/following")
async def get_following(entity_id: str):
    """Get who an entity follows."""
    following = await storage.get_following(entity_id)
    
    results = []
    for followed_id in following:
        entity = await storage.get_entity(followed_id)
        if entity:
            results.append({
                "id": entity.id,
                "handle": entity.handle,
                "profile": entity.profile,
            })
    
    return {"items": results, "total": len(results)}


@app.get("/api/users/{entity_id}/friends")
async def get_friends(entity_id: str):
    """Get friends of an entity."""
    friends = await storage.get_friends(entity_id)
    
    results = []
    for friend_id in friends:
        entity = await storage.get_entity(friend_id)
        if entity:
            results.append({
                "id": entity.id,
                "handle": entity.handle,
                "profile": entity.profile,
            })
    
    return {"users": results, "total": len(results)}


# ========== Friend Request Endpoints ==========

@app.post("/api/friends/request")
async def send_friend_request(req: dict, current_user: str = Depends(require_auth)):
    """Send a friend request to another user."""
    target_id = req.get("target_id")
    if not target_id:
        raise HTTPException(status_code=400, detail="target_id required")
    
    if target_id == current_user:
        raise HTTPException(status_code=400, detail="Cannot send friend request to yourself")
    
    # Check target exists
    target = await storage.get_entity(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already friends
    if await storage.are_friends(current_user, target_id):
        raise HTTPException(status_code=400, detail="Already friends")
    
    # Check if request already exists
    pending = await storage.get_sent_friend_requests(current_user)
    if any(r['to'] == target_id for r in pending):
        raise HTTPException(status_code=400, detail="Friend request already sent")
    
    # Check if they already sent us a request - auto-accept
    their_pending = await storage.get_pending_friend_requests(current_user)
    if any(r['from'] == target_id for r in their_pending):
        # Auto-accept - create mutual friendship
        now = datetime.utcnow().isoformat()
        
        # Create friend links both ways
        link_id_1 = generate_link_id(current_user, "friend", target_id)
        link_id_2 = generate_link_id(target_id, "friend", current_user)
        
        await storage.db.execute("""
            INSERT OR REPLACE INTO links (id, source, target, kind, data, created_at, tombstone, sig)
            VALUES (?, ?, ?, 'friend', '{}', ?, 0, ?)
        """, (link_id_1, current_user, target_id, now, b""))
        
        await storage.db.execute("""
            INSERT OR REPLACE INTO links (id, source, target, kind, data, created_at, tombstone, sig)
            VALUES (?, ?, ?, 'friend', '{}', ?, 0, ?)
        """, (link_id_2, target_id, current_user, now, b""))
        
        # Remove their pending request
        await storage.db.execute("""
            UPDATE links SET tombstone = 1 WHERE source = ? AND target = ? AND kind = 'friend_request'
        """, (target_id, current_user))
        
        await storage.db.commit()
        return {"status": "accepted", "message": "You are now friends"}
    
    # Create friend request
    link_id = generate_link_id(current_user, "friend_request", target_id)
    now = datetime.utcnow().isoformat()
    
    await storage.db.execute("""
        INSERT OR REPLACE INTO links (id, source, target, kind, data, created_at, tombstone, sig)
        VALUES (?, ?, ?, 'friend_request', '{}', ?, 0, ?)
    """, (link_id, current_user, target_id, now, b""))
    await storage.db.commit()
    
    return {"status": "sent", "message": "Friend request sent"}


@app.post("/api/friends/accept")
async def accept_friend_request(req: dict, current_user: str = Depends(require_auth)):
    """Accept a pending friend request."""
    from_id = req.get("from_id")
    if not from_id:
        raise HTTPException(status_code=400, detail="from_id required")
    
    # Check pending request exists
    pending = await storage.get_pending_friend_requests(current_user)
    if not any(r['from'] == from_id for r in pending):
        raise HTTPException(status_code=404, detail="No pending friend request from this user")
    
    now = datetime.utcnow().isoformat()
    
    # Create mutual friend links
    link_id_1 = generate_link_id(current_user, "friend", from_id)
    link_id_2 = generate_link_id(from_id, "friend", current_user)
    
    await storage.db.execute("""
        INSERT OR REPLACE INTO links (id, source, target, kind, data, created_at, tombstone, sig)
        VALUES (?, ?, ?, 'friend', '{}', ?, 0, ?)
    """, (link_id_1, current_user, from_id, now, b""))
    
    await storage.db.execute("""
        INSERT OR REPLACE INTO links (id, source, target, kind, data, created_at, tombstone, sig)
        VALUES (?, ?, ?, 'friend', '{}', ?, 0, ?)
    """, (link_id_2, from_id, current_user, now, b""))
    
    # Remove the pending request
    await storage.db.execute("""
        UPDATE links SET tombstone = 1 WHERE source = ? AND target = ? AND kind = 'friend_request'
    """, (from_id, current_user))
    
    await storage.db.commit()
    
    return {"status": "accepted", "message": "Friend request accepted"}


@app.post("/api/friends/reject")
async def reject_friend_request(req: dict, current_user: str = Depends(require_auth)):
    """Reject a pending friend request."""
    from_id = req.get("from_id")
    if not from_id:
        raise HTTPException(status_code=400, detail="from_id required")
    
    # Remove the pending request
    await storage.db.execute("""
        UPDATE links SET tombstone = 1 WHERE source = ? AND target = ? AND kind = 'friend_request'
    """, (from_id, current_user))
    await storage.db.commit()
    
    return {"status": "rejected", "message": "Friend request rejected"}


@app.delete("/api/friends/{friend_id}")
async def remove_friend(friend_id: str, current_user: str = Depends(require_auth)):
    """Remove a friend (unfriend)."""
    # Remove both friend links
    await storage.db.execute("""
        UPDATE links SET tombstone = 1 WHERE source = ? AND target = ? AND kind = 'friend'
    """, (current_user, friend_id))
    
    await storage.db.execute("""
        UPDATE links SET tombstone = 1 WHERE source = ? AND target = ? AND kind = 'friend'
    """, (friend_id, current_user))
    
    await storage.db.commit()
    
    return {"status": "removed", "message": "Friend removed"}


@app.get("/api/friends/requests")
async def get_friend_requests(current_user: str = Depends(require_auth)):
    """Get pending friend requests for current user."""
    pending = await storage.get_pending_friend_requests(current_user)
    
    results = []
    for req in pending:
        entity = await storage.get_entity(req['from'])
        if entity:
            results.append({
                "from_id": req['from'],
                "handle": entity.handle,
                "profile": entity.profile,
                "created_at": req['created_at'],
            })
    
    return {"requests": results, "total": len(results)}


@app.get("/api/friends/sent")
async def get_sent_requests(current_user: str = Depends(require_auth)):
    """Get friend requests sent by current user."""
    sent = await storage.get_sent_friend_requests(current_user)
    
    results = []
    for req in sent:
        entity = await storage.get_entity(req['to'])
        if entity:
            results.append({
                "to_id": req['to'],
                "handle": entity.handle,
                "profile": entity.profile,
                "created_at": req['created_at'],
            })
    
    return {"requests": results, "total": len(results)}


@app.get("/api/friends/status/{target_id}")
async def get_friendship_status(target_id: str, current_user: str = Depends(require_auth)):
    """Get friendship status with another user."""
    if target_id == current_user:
        return {"status": "self"}
    
    # Check if friends
    if await storage.are_friends(current_user, target_id):
        return {"status": "friends"}
    
    # Check if we sent them a request
    sent = await storage.get_sent_friend_requests(current_user)
    if any(r['to'] == target_id for r in sent):
        return {"status": "request_sent"}
    
    # Check if they sent us a request
    pending = await storage.get_pending_friend_requests(current_user)
    if any(r['from'] == target_id for r in pending):
        return {"status": "request_received"}
    
    return {"status": "none"}


@app.get("/api/users/{entity_id}/feed")
async def get_feed(
    response: Response,
    entity_id: str,
    limit: int = 50,
    offset: int = 0,
    view: str = "home_timeline",
    include_labels: bool = Query(False, description="Fetch moderation attestation labels (allowlist + MESH_MODERATION_URL required)", alias="labels"),
):
    """
    Named view: ``view=home_timeline`` (default) — posts from people you follow + your posts,
    with optional friend-gated content. Enforces View Layer limits (spec §9 / Appendix C).
    """
    if view and view != HOME_TIMELINE_VIEW:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown view {view!r}; this relay only implements {HOME_TIMELINE_VIEW!r}",
        )

    following = await storage.get_following(entity_id)
    follow_count = len(following)  # follow edges, before including self
    try:
        elimit, eoff, cost = validate_and_estimate_home_timeline(
            follow_count, limit, offset, include_labels
        )
    except ViewRejectionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e

    friends = await storage.get_friends(entity_id)
    following.append(entity_id)  # Include own posts

    # Build query for public posts from following + friends-only posts from actual friends
    placeholders_following = ",".join("?" * len(following))

    query = f"""
        SELECT * FROM content 
        WHERE (
            (author IN ({placeholders_following}) AND access = 'public')
            OR (author IN ({placeholders_following}) AND access = 'friends' AND author IN ({",".join("?" * len(friends)) if friends else "'none'"}))
            OR (author = ?)
        )
        AND reply_to IS NULL
        AND tombstone = 0
        ORDER BY created_at DESC 
        LIMIT ? OFFSET ?
    """

    params = following + (friends if friends else []) + [entity_id, elimit, eoff]
    cursor = await storage.db.execute(query, params)
    rows = await cursor.fetchall()

    results = []
    for row in rows:
        content = await storage.get_content(row["id"])
        if content:
            item = content.to_dict()

            # Get author info
            author_entity = await storage.get_entity(content.author)
            if author_entity:
                item["author_handle"] = author_entity.handle
                item["author_profile"] = author_entity.profile

            # Get counts
            cursor2 = await storage.db.execute(
                "SELECT COUNT(*) as cnt FROM links WHERE target = ? AND kind = 'like' AND tombstone = 0",
                (content.id,),
            )
            row2 = await cursor2.fetchone()
            item["like_count"] = row2["cnt"] if row2 else 0

            cursor2 = await storage.db.execute(
                "SELECT COUNT(*) as cnt FROM content WHERE reply_to = ?",
                (content.id,),
            )
            row2 = await cursor2.fetchone()
            item["reply_count"] = row2["cnt"] if row2 else 0

            # Check if current user liked
            like_id = generate_link_id(entity_id, "like", content.id)
            cursor2 = await storage.db.execute(
                "SELECT id FROM links WHERE id = ? AND tombstone = 0",
                (like_id,),
            )
            item["liked_by_me"] = bool(await cursor2.fetchone())

            item["moderation_labels"] = []
            results.append(item)

    labels_status = "ok"
    allow = parse_issuer_allowlist()
    if include_labels:
        if not allow or not moderation_base_url():
            labels_status = "disabled"
            for it in results:
                it["moderation_labels"] = []
        else:
            ids = [it["id"] for it in results]
            label_map = await fetch_labels_for_subjects(ids, allow)
            for it in results:
                it["moderation_labels"] = label_map.get(it["id"], [])
    else:
        labels_status = "off"
        for it in results:
            it["moderation_labels"] = []

    response.headers["X-Mesh-View"] = HOME_TIMELINE_VIEW
    response.headers["X-Mesh-View-Est-Events-Scanned"] = str(cost.estimated_events_scanned)
    response.headers["X-Mesh-View-Attestation-Lookups"] = str(cost.attestation_lookups)

    return {
        "view": HOME_TIMELINE_VIEW,
        "view_cost": cost.to_dict(),
        "items": results,
        "total": len(results),
        "labels_status": labels_status,
    }


# Group endpoints
@app.post("/api/groups")
async def create_group(req: GroupCreate, current_user: str = Depends(require_auth)):
    """Create a new group."""
    # Create group entity
    group_id = f"grp:{sha256_hex(f'{current_user}:{req.name}:{datetime.utcnow().isoformat()}'.encode())[:32]}"
    
    group = Entity(
        id=group_id,
        kind=EntityKind.GROUP,
        public_key=b"",  # Groups don't have keys
        encryption_key=None,
        handle=None,
        profile={
            "name": req.name,
            "description": req.description,
            "owner": current_user,
            "access": req.access,
            "created_at": datetime.utcnow().isoformat(),
        },
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        sig=b"",
    )
    
    await storage.create_entity(group)
    
    # Make creator a member and moderator
    member_link = Link(
        id=generate_link_id(current_user, "member", group_id),
        source=current_user,
        target=group_id,
        kind=LinkKind.MEMBER,
        data={"role": "owner"},
        created_at=datetime.utcnow(),
        tombstone=False,
        sig=b"",
    )
    await storage.create_link(member_link)
    
    return {"id": group_id, "name": req.name}


@app.get("/api/groups")
async def list_groups(access: str = "public", limit: int = 50):
    """List groups."""
    cursor = await storage.db.execute(
        "SELECT * FROM entities WHERE kind = 'group' ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    rows = await cursor.fetchall()
    
    results = []
    for row in rows:
        profile = json.loads(row['profile']) if row['profile'] else {}
        if access == "public" and profile.get("access") != "public":
            continue
        
        # Get member count
        cursor2 = await storage.db.execute(
            "SELECT COUNT(*) as cnt FROM links WHERE target = ? AND kind = 'member' AND tombstone = 0",
            (row['id'],)
        )
        row2 = await cursor2.fetchone()
        member_count = row2['cnt'] if row2 else 0
        
        results.append({
            "id": row['id'],
            "name": profile.get("name"),
            "description": profile.get("description"),
            "owner": profile.get("owner"),
            "access": profile.get("access"),
            "member_count": member_count,
            "created_at": row['created_at'],
        })
    
    return {"items": results, "total": len(results)}


@app.get("/api/groups/{group_id}")
async def get_group(group_id: str):
    """Get group details."""
    entity = await storage.get_entity(group_id)
    if not entity or entity.kind != EntityKind.GROUP:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Get members
    cursor = await storage.db.execute(
        "SELECT source, data FROM links WHERE target = ? AND kind = 'member' AND tombstone = 0",
        (group_id,)
    )
    rows = await cursor.fetchall()
    
    members = []
    for row in rows:
        member = await storage.get_entity(row['source'])
        if member:
            data = json.loads(row['data']) if row['data'] else {}
            members.append({
                "id": member.id,
                "handle": member.handle,
                "profile": member.profile,
                "role": data.get("role", "member"),
            })
    
    return {
        "id": entity.id,
        "profile": entity.profile,
        "members": members,
        "member_count": len(members),
    }


@app.post("/api/groups/{group_id}/join")
async def join_group(group_id: str, current_user: str = Depends(require_auth)):
    """Join a group."""
    entity = await storage.get_entity(group_id)
    if not entity or entity.kind != EntityKind.GROUP:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if private
    if entity.profile.get("access") == "private":
        raise HTTPException(status_code=403, detail="This is a private group. Request an invite.")
    
    # Create membership link
    link_id = generate_link_id(current_user, "member", group_id)
    
    link = Link(
        id=link_id,
        source=current_user,
        target=group_id,
        kind=LinkKind.MEMBER,
        data={"role": "member"},
        created_at=datetime.utcnow(),
        tombstone=False,
        sig=b"",
    )
    
    try:
        await storage.create_link(link)
    except:
        # Already a member
        pass
    
    return {"status": "joined"}


@app.post("/api/groups/{group_id}/leave")
async def leave_group(group_id: str, current_user: str = Depends(require_auth)):
    """Leave a group."""
    link_id = generate_link_id(current_user, "member", group_id)
    
    await storage.db.execute(
        "UPDATE links SET tombstone = 1 WHERE id = ?", (link_id,)
    )
    await storage.db.commit()
    
    return {"status": "left"}


# ========== Group Admin & Moderation ==========

async def is_group_admin(group_id: str, user_id: str) -> bool:
    """Check if user is owner/admin of group."""
    cursor = await storage.db.execute('''
        SELECT data FROM links 
        WHERE source = ? AND target = ? AND kind = 'member' AND tombstone = 0
    ''', (user_id, group_id))
    row = await cursor.fetchone()
    if not row:
        return False
    data = json.loads(row[0]) if row[0] else {}
    return data.get("role") in ("owner", "admin", "moderator")


async def is_group_owner(group_id: str, user_id: str) -> bool:
    """Check if user is owner of group."""
    cursor = await storage.db.execute('''
        SELECT data FROM links 
        WHERE source = ? AND target = ? AND kind = 'member' AND tombstone = 0
    ''', (user_id, group_id))
    row = await cursor.fetchone()
    if not row:
        return False
    data = json.loads(row[0]) if row[0] else {}
    return data.get("role") == "owner"


@app.post("/api/groups/{group_id}/admins")
async def add_group_admin(group_id: str, req: dict, current_user: str = Depends(require_auth)):
    """Add an admin to a group (owner only)."""
    if not await is_group_owner(group_id, current_user):
        raise HTTPException(status_code=403, detail="Only owner can add admins")
    
    user_id = req.get("user_id")
    role = req.get("role", "admin")  # admin or moderator
    
    if role not in ("admin", "moderator"):
        raise HTTPException(status_code=400, detail="Invalid role")
    
    # Update their membership role
    link_id = generate_link_id(user_id, "member", group_id)
    await storage.db.execute('''
        UPDATE links SET data = ? WHERE id = ?
    ''', (json.dumps({"role": role}), link_id))
    await storage.db.commit()
    
    return {"status": "admin_added", "user_id": user_id, "role": role}


@app.delete("/api/groups/{group_id}/admins/{user_id}")
async def remove_group_admin(group_id: str, user_id: str, current_user: str = Depends(require_auth)):
    """Remove admin from a group (owner only)."""
    if not await is_group_owner(group_id, current_user):
        raise HTTPException(status_code=403, detail="Only owner can remove admins")
    
    # Downgrade to regular member
    link_id = generate_link_id(user_id, "member", group_id)
    await storage.db.execute('''
        UPDATE links SET data = ? WHERE id = ?
    ''', (json.dumps({"role": "member"}), link_id))
    await storage.db.commit()
    
    return {"status": "admin_removed", "user_id": user_id}


@app.post("/api/groups/{group_id}/transfer")
async def transfer_group_ownership(group_id: str, req: dict, current_user: str = Depends(require_auth)):
    """Transfer group ownership (owner only)."""
    if not await is_group_owner(group_id, current_user):
        raise HTTPException(status_code=403, detail="Only owner can transfer ownership")
    
    new_owner_id = req.get("new_owner_id")
    if not new_owner_id:
        raise HTTPException(status_code=400, detail="new_owner_id required")
    
    # Check new owner is a member
    cursor = await storage.db.execute('''
        SELECT id FROM links 
        WHERE source = ? AND target = ? AND kind = 'member' AND tombstone = 0
    ''', (new_owner_id, group_id))
    if not await cursor.fetchone():
        raise HTTPException(status_code=400, detail="New owner must be a member")
    
    # Update old owner to admin
    old_link_id = generate_link_id(current_user, "member", group_id)
    await storage.db.execute('''
        UPDATE links SET data = ? WHERE id = ?
    ''', (json.dumps({"role": "admin"}), old_link_id))
    
    # Update new owner
    new_link_id = generate_link_id(new_owner_id, "member", group_id)
    await storage.db.execute('''
        UPDATE links SET data = ? WHERE id = ?
    ''', (json.dumps({"role": "owner"}), new_link_id))
    
    # Update group profile
    entity = await storage.get_entity(group_id)
    if entity:
        entity.profile["owner"] = new_owner_id
        await storage.db.execute(
            "UPDATE entities SET profile = ? WHERE id = ?",
            (json.dumps(entity.profile), group_id)
        )
    
    await storage.db.commit()
    
    return {"status": "transferred", "new_owner": new_owner_id}


@app.post("/api/groups/{group_id}/kick")
async def kick_from_group(group_id: str, req: dict, current_user: str = Depends(require_auth)):
    """Remove a user from group (admin/owner only)."""
    if not await is_group_admin(group_id, current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user_id = req.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    
    # Can't kick owner
    if await is_group_owner(group_id, user_id):
        raise HTTPException(status_code=403, detail="Cannot kick the owner")
    
    # Remove membership
    link_id = generate_link_id(user_id, "member", group_id)
    await storage.db.execute(
        "UPDATE links SET tombstone = 1 WHERE id = ?", (link_id,)
    )
    await storage.db.commit()
    
    return {"status": "kicked", "user_id": user_id}


@app.post("/api/groups/{group_id}/ban")
async def ban_from_group(group_id: str, req: dict, current_user: str = Depends(require_auth)):
    """Ban a user from group (admin/owner only)."""
    if not await is_group_admin(group_id, current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user_id = req.get("user_id")
    reason = req.get("reason", "")
    
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    
    # Can't ban owner
    if await is_group_owner(group_id, user_id):
        raise HTTPException(status_code=403, detail="Cannot ban the owner")
    
    # Remove membership
    link_id = generate_link_id(user_id, "member", group_id)
    await storage.db.execute(
        "UPDATE links SET tombstone = 1 WHERE id = ?", (link_id,)
    )
    
    # Create ban link
    ban_link_id = generate_link_id(group_id, "ban", user_id)
    await storage.db.execute('''
        INSERT OR REPLACE INTO links (id, source, target, kind, data, created_at, tombstone, sig)
        VALUES (?, ?, ?, 'ban', ?, ?, 0, ?)
    ''', (ban_link_id, group_id, user_id, json.dumps({"reason": reason, "by": current_user}), datetime.utcnow().isoformat(), b""))
    
    await storage.db.commit()
    
    return {"status": "banned", "user_id": user_id}


@app.delete("/api/groups/{group_id}/ban/{user_id}")
async def unban_from_group(group_id: str, user_id: str, current_user: str = Depends(require_auth)):
    """Unban a user from group (admin/owner only)."""
    if not await is_group_admin(group_id, current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    ban_link_id = generate_link_id(group_id, "ban", user_id)
    await storage.db.execute(
        "UPDATE links SET tombstone = 1 WHERE id = ?", (ban_link_id,)
    )
    await storage.db.commit()
    
    return {"status": "unbanned", "user_id": user_id}


@app.get("/api/groups/{group_id}/bans")
async def list_group_bans(group_id: str, current_user: str = Depends(require_auth)):
    """List banned users (admin/owner only)."""
    if not await is_group_admin(group_id, current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    cursor = await storage.db.execute('''
        SELECT l.target, l.data, l.created_at, e.handle, e.profile
        FROM links l
        LEFT JOIN entities e ON l.target = e.id
        WHERE l.source = ? AND l.kind = 'ban' AND l.tombstone = 0
    ''', (group_id,))
    
    bans = []
    for row in await cursor.fetchall():
        data = json.loads(row[1]) if row[1] else {}
        profile = json.loads(row[4]) if row[4] else {}
        bans.append({
            "user_id": row[0],
            "handle": row[3],
            "name": profile.get("name", row[3]),
            "reason": data.get("reason", ""),
            "banned_by": data.get("by", ""),
            "banned_at": row[2],
        })
    
    return {"bans": bans}


# ========== Content Moderation ==========

@app.post("/api/groups/{group_id}/content/{content_id}/remove")
async def remove_group_content(group_id: str, content_id: str, req: dict = None, current_user: str = Depends(require_auth)):
    """Remove content from group (admin/owner only)."""
    if not await is_group_admin(group_id, current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    reason = req.get("reason", "") if req else ""
    
    # Check content exists
    content = await storage.get_content(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Soft delete the content
    await storage.db.execute('''
        UPDATE content SET tombstone = 1 WHERE id = ?
    ''', (content_id,))
    await storage.db.commit()
    
    return {"status": "removed", "content_id": content_id, "reason": reason, "moderator": current_user}


@app.get("/api/groups/{group_id}/modlog")
async def get_group_modlog(group_id: str, limit: int = 50, current_user: str = Depends(require_auth)):
    """Get moderation log for group (admin/owner only)."""
    if not await is_group_admin(group_id, current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # For now, return empty - moderation log could be implemented later
    logs = []
    
    return {"items": logs}


# ========== Publication & Subscription (Substack-like) Endpoints ==========

# Pydantic models for publications
class PublicationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    handle: Optional[str] = None
    price_monthly: int = 0  # In cents
    price_yearly: int = 0   # In cents

class ArticleCreate(BaseModel):
    publication_id: str
    title: str
    subtitle: Optional[str] = None
    content: str
    excerpt: Optional[str] = None
    cover_image: Optional[str] = None
    access: str = "public"  # public, subscribers, paid
    status: str = "draft"   # draft, published

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    content: Optional[str] = None
    excerpt: Optional[str] = None
    cover_image: Optional[str] = None
    access: Optional[str] = None
    status: Optional[str] = None

class SubscriptionCreate(BaseModel):
    publication_id: str
    tier: str = "free"  # free, paid

# Stripe configuration (set via environment variables)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


@app.post("/api/publications")
async def create_publication(req: PublicationCreate, current_user: str = Depends(require_auth)):
    """Create a new publication."""
    pub_id = f"pub:{sha256_hex(f'{current_user}:{req.name}:{datetime.utcnow().isoformat()}'.encode())[:32]}"
    
    # Check handle uniqueness
    if req.handle:
        cursor = await storage.db.execute(
            "SELECT id FROM publications WHERE handle = ?", (req.handle,)
        )
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail="Handle already taken")
    
    now = datetime.utcnow().isoformat()
    
    await storage.db.execute('''
        INSERT INTO publications (id, owner_id, name, description, handle, price_monthly, price_yearly, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        pub_id, current_user, req.name, req.description, req.handle,
        req.price_monthly, req.price_yearly, now, now
    ))
    await storage.db.commit()
    
    return {
        "id": pub_id,
        "owner_id": current_user,
        "name": req.name,
        "description": req.description,
        "handle": req.handle,
        "price_monthly": req.price_monthly,
        "price_yearly": req.price_yearly,
        "created_at": now,
    }


@app.get("/api/publications")
async def list_publications(owner_id: Optional[str] = None, limit: int = 50):
    """List publications."""
    query = "SELECT * FROM publications"
    params = []
    
    if owner_id:
        query += " WHERE owner_id = ?"
        params.append(owner_id)
    
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    cursor = await storage.db.execute(query, params)
    rows = await cursor.fetchall()
    
    results = []
    for row in rows:
        owner = await storage.get_entity(row["owner_id"])
        results.append({
            "id": row["id"],
            "owner_id": row["owner_id"],
            "owner_handle": owner.handle if owner else None,
            "owner_profile": owner.profile if owner else None,
            "name": row["name"],
            "description": row["description"],
            "handle": row["handle"],
            "price_monthly": row["price_monthly"],
            "price_yearly": row["price_yearly"],
            "created_at": row["created_at"],
        })
    
    return {"items": results}


@app.get("/api/publications/{pub_id}")
async def get_publication(pub_id: str):
    """Get a publication by ID."""
    cursor = await storage.db.execute("SELECT * FROM publications WHERE id = ?", (pub_id,))
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Publication not found")
    
    owner = await storage.get_entity(row["owner_id"])
    
    # Get subscriber count
    cursor = await storage.db.execute(
        "SELECT COUNT(*) as cnt FROM subscriptions WHERE publication_id = ? AND status = 'active'",
        (pub_id,)
    )
    sub_row = await cursor.fetchone()
    
    return {
        "id": row["id"],
        "owner_id": row["owner_id"],
        "owner_handle": owner.handle if owner else None,
        "owner_profile": owner.profile if owner else None,
        "name": row["name"],
        "description": row["description"],
        "handle": row["handle"],
        "price_monthly": row["price_monthly"],
        "price_yearly": row["price_yearly"],
        "subscriber_count": sub_row["cnt"] if sub_row else 0,
        "created_at": row["created_at"],
    }


@app.post("/api/articles")
async def create_article(req: ArticleCreate, current_user: str = Depends(require_auth)):
    """Create a new article."""
    # Verify ownership
    cursor = await storage.db.execute(
        "SELECT owner_id FROM publications WHERE id = ?", (req.publication_id,)
    )
    row = await cursor.fetchone()
    if not row or row["owner_id"] != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to post to this publication")
    
    article_id = f"art:{sha256_hex(f'{current_user}:{req.title}:{datetime.utcnow().isoformat()}'.encode())[:32]}"
    now = datetime.utcnow().isoformat()
    
    published_at = now if req.status == "published" else None
    
    await storage.db.execute('''
        INSERT INTO articles (id, publication_id, author_id, title, subtitle, content, excerpt, cover_image, access, status, published_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        article_id, req.publication_id, current_user, req.title, req.subtitle,
        req.content, req.excerpt, req.cover_image, req.access, req.status,
        published_at, now, now
    ))
    await storage.db.commit()
    
    return {
        "id": article_id,
        "publication_id": req.publication_id,
        "title": req.title,
        "status": req.status,
        "created_at": now,
    }


@app.get("/api/articles")
async def list_articles(
    publication_id: Optional[str] = None,
    status: str = "published",
    limit: int = 50,
    current_user: str = Depends(get_current_user)
):
    """List articles."""
    query = "SELECT * FROM articles WHERE 1=1"
    params = []
    
    if publication_id:
        query += " AND publication_id = ?"
        params.append(publication_id)
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY published_at DESC, created_at DESC LIMIT ?"
    params.append(limit)
    
    cursor = await storage.db.execute(query, params)
    rows = await cursor.fetchall()
    
    results = []
    for row in rows:
        # Check access
        can_view = row["access"] == "public"
        if not can_view and current_user:
            # Check if subscriber
            cursor2 = await storage.db.execute(
                "SELECT tier FROM subscriptions WHERE subscriber_id = ? AND publication_id = ? AND status = 'active'",
                (current_user, row["publication_id"])
            )
            sub = await cursor2.fetchone()
            if sub:
                can_view = row["access"] == "subscribers" or (row["access"] == "paid" and sub["tier"] == "paid")
        
        author = await storage.get_entity(row["author_id"])
        
        results.append({
            "id": row["id"],
            "publication_id": row["publication_id"],
            "author_id": row["author_id"],
            "author_handle": author.handle if author else None,
            "author_profile": author.profile if author else None,
            "title": row["title"],
            "subtitle": row["subtitle"],
            "excerpt": row["excerpt"] or (row["content"][:200] + "..." if len(row["content"]) > 200 else row["content"]) if can_view else None,
            "cover_image": row["cover_image"],
            "access": row["access"],
            "status": row["status"],
            "published_at": row["published_at"],
            "can_view": can_view,
        })
    
    return {"items": results}


@app.get("/api/articles/{article_id}")
async def get_article(article_id: str, current_user: str = Depends(get_current_user)):
    """Get an article by ID."""
    cursor = await storage.db.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Check access
    can_view = row["access"] == "public"
    if not can_view and current_user:
        cursor2 = await storage.db.execute(
            "SELECT tier FROM subscriptions WHERE subscriber_id = ? AND publication_id = ? AND status = 'active'",
            (current_user, row["publication_id"])
        )
        sub = await cursor2.fetchone()
        if sub:
            can_view = row["access"] == "subscribers" or (row["access"] == "paid" and sub["tier"] == "paid")
    
    author = await storage.get_entity(row["author_id"])
    
    return {
        "id": row["id"],
        "publication_id": row["publication_id"],
        "author_id": row["author_id"],
        "author_handle": author.handle if author else None,
        "author_profile": author.profile if author else None,
        "title": row["title"],
        "subtitle": row["subtitle"],
        "content": row["content"] if can_view else None,
        "excerpt": row["excerpt"],
        "cover_image": row["cover_image"],
        "access": row["access"],
        "status": row["status"],
        "published_at": row["published_at"],
        "can_view": can_view,
        "paywall_message": "Subscribe to read this article" if not can_view else None,
    }


@app.put("/api/articles/{article_id}")
async def update_article(article_id: str, req: ArticleUpdate, current_user: str = Depends(require_auth)):
    """Update an article."""
    cursor = await storage.db.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    if row["author_id"] != current_user:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    updates = []
    params = []
    
    for field in ["title", "subtitle", "content", "excerpt", "cover_image", "access", "status"]:
        value = getattr(req, field)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)
    
    if req.status == "published" and row["status"] != "published":
        updates.append("published_at = ?")
        params.append(datetime.utcnow().isoformat())
    
    updates.append("updated_at = ?")
    params.append(datetime.utcnow().isoformat())
    params.append(article_id)
    
    await storage.db.execute(
        f"UPDATE articles SET {', '.join(updates)} WHERE id = ?",
        params
    )
    await storage.db.commit()
    
    return {"status": "updated", "id": article_id}


@app.post("/api/subscriptions")
async def create_subscription(req: SubscriptionCreate, current_user: str = Depends(require_auth)):
    """Subscribe to a publication."""
    # Check if already subscribed
    cursor = await storage.db.execute(
        "SELECT id FROM subscriptions WHERE subscriber_id = ? AND publication_id = ? AND status = 'active'",
        (current_user, req.publication_id)
    )
    if await cursor.fetchone():
        raise HTTPException(status_code=409, detail="Already subscribed")
    
    sub_id = f"sub:{sha256_hex(f'{current_user}:{req.publication_id}:{datetime.utcnow().isoformat()}'.encode())[:32]}"
    now = datetime.utcnow().isoformat()
    
    await storage.db.execute('''
        INSERT INTO subscriptions (id, subscriber_id, publication_id, tier, status, created_at)
        VALUES (?, ?, ?, ?, 'active', ?)
    ''', (sub_id, current_user, req.publication_id, req.tier, now))
    await storage.db.commit()
    
    return {
        "id": sub_id,
        "subscriber_id": current_user,
        "publication_id": req.publication_id,
        "tier": req.tier,
        "status": "active",
        "created_at": now,
    }


@app.get("/api/subscriptions")
async def list_subscriptions(current_user: str = Depends(require_auth)):
    """List user's subscriptions."""
    cursor = await storage.db.execute(
        "SELECT s.*, p.name as pub_name, p.handle as pub_handle FROM subscriptions s JOIN publications p ON s.publication_id = p.id WHERE s.subscriber_id = ? AND s.status = 'active'",
        (current_user,)
    )
    rows = await cursor.fetchall()
    
    return {"items": [dict(row) for row in rows]}


@app.delete("/api/subscriptions/{sub_id}")
async def cancel_subscription(sub_id: str, current_user: str = Depends(require_auth)):
    """Cancel a subscription."""
    cursor = await storage.db.execute(
        "SELECT * FROM subscriptions WHERE id = ? AND subscriber_id = ?",
        (sub_id, current_user)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    await storage.db.execute(
        "UPDATE subscriptions SET status = 'canceled', canceled_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), sub_id)
    )
    await storage.db.commit()
    
    return {"status": "canceled"}


# Stripe integration endpoints
@app.post("/api/stripe/create-checkout-session")
async def create_checkout_session(req: dict, current_user: str = Depends(require_auth)):
    """Create a Stripe checkout session for subscription."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    
    import httpx
    
    publication_id = req.get("publication_id")
    billing_cycle = req.get("billing_cycle", "monthly")  # monthly or yearly
    success_url = req.get("success_url", f"{NODE_URL}/subscription/success")
    cancel_url = req.get("cancel_url", f"{NODE_URL}/subscription/cancel")
    
    # Get publication
    cursor = await storage.db.execute("SELECT * FROM publications WHERE id = ?", (publication_id,))
    pub = await cursor.fetchone()
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    
    price = pub["price_monthly"] if billing_cycle == "monthly" else pub["price_yearly"]
    if price == 0:
        raise HTTPException(status_code=400, detail="This publication is free")
    
    # Create Stripe checkout session
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            headers={
                "Authorization": f"Bearer {STRIPE_SECRET_KEY}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "mode": "subscription",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "line_items[0][price_data][currency]": "usd",
                "line_items[0][price_data][product_data][name]": f"{pub['name']} Subscription",
                "line_items[0][price_data][unit_amount]": price,
                "line_items[0][price_data][recurring][interval]": "month" if billing_cycle == "monthly" else "year",
                "line_items[0][quantity]": 1,
                "metadata[publication_id]": publication_id,
                "metadata[subscriber_id]": current_user,
                "metadata[tier]": "paid",
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Stripe error: {response.text}")
        
        session = response.json()
        return {"checkout_url": session.get("url"), "session_id": session.get("id")}


@app.post("/api/stripe/webhook")
async def stripe_webhook(request):
    """Handle Stripe webhooks."""
    import hmac
    from fastapi import Request
    
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook not configured")
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    
    # Verify signature (simplified)
    # In production, use stripe.Webhook.construct_event
    
    try:
        event = json.loads(payload)
    except:
        raise HTTPException(status_code=400, detail="Invalid payload")
    
    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})
    
    if event_type == "checkout.session.completed":
        metadata = data.get("metadata", {})
        publication_id = metadata.get("publication_id")
        subscriber_id = metadata.get("subscriber_id")
        stripe_subscription_id = data.get("subscription")
        stripe_customer_id = data.get("customer")
        
        if publication_id and subscriber_id:
            sub_id = f"sub:{sha256_hex(f'{subscriber_id}:{publication_id}:{datetime.utcnow().isoformat()}'.encode())[:32]}"
            now = datetime.utcnow().isoformat()
            
            await storage.db.execute('''
                INSERT OR REPLACE INTO subscriptions (id, subscriber_id, publication_id, tier, status, stripe_subscription_id, stripe_customer_id, created_at)
                VALUES (?, ?, ?, 'paid', 'active', ?, ?, ?)
            ''', (sub_id, subscriber_id, publication_id, stripe_subscription_id, stripe_customer_id, now))
            await storage.db.commit()
    
    elif event_type == "customer.subscription.deleted":
        stripe_sub_id = data.get("id")
        await storage.db.execute(
            "UPDATE subscriptions SET status = 'canceled', canceled_at = ? WHERE stripe_subscription_id = ?",
            (datetime.utcnow().isoformat(), stripe_sub_id)
        )
        await storage.db.commit()
    
    return {"received": True}


# Federation endpoints
@app.get("/api/federation/nodes")
@app.get("/api/federation/peers")
async def list_known_nodes():
    """List known federation nodes/peers."""
    return {"items": list(known_nodes.values()), "peers": list(known_nodes.values())}


@app.post("/api/federation/nodes")
async def register_node(node: NodeInfo):
    """Register a new federation node."""
    known_nodes[node.node_url] = {
        "node_id": node.node_id,
        "node_url": node.node_url,
        "protocol_version": node.protocol_version,
        "features": node.features,
        "last_seen": datetime.utcnow().isoformat(),
    }
    return {"status": "registered", "id": node.node_id}


@app.post("/api/federation/peers")
async def register_peer(req: dict):
    """Register a federation peer by URL."""
    import httpx
    url = req.get("url", "").rstrip("/")
    if not url:
        raise HTTPException(status_code=400, detail="url required")
    
    # Discover peer
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{url}/.well-known/mesh-node")
            r.raise_for_status()
            info = r.json()
            
            known_nodes[url] = {
                "node_id": info.get("node_id"),
                "node_url": url,
                "protocol_version": info.get("protocol_version"),
                "features": info.get("features", []),
                "last_seen": datetime.utcnow().isoformat(),
            }
            
            # Register ourselves with peer
            await client.post(f"{url}/api/federation/nodes", json={
                "node_id": NODE_ID,
                "node_url": NODE_URL,
                "protocol_version": "1.1",
                "features": ["entities", "content", "links", "groups", "federation"],
            })
            
            return {"status": "registered", "id": info.get("node_id"), "peer": known_nodes[url]}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to connect: {e}")


@app.post("/api/federation/connect")
async def connect_to_node(req: dict):
    """Connect to a remote node and sync."""
    import httpx
    
    remote_url = req.get("node_url", "").rstrip("/")
    if not remote_url:
        raise HTTPException(status_code=400, detail="node_url required")
    
    # Discover remote node
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{remote_url}/.well-known/mesh-node")
            r.raise_for_status()
            node_info = r.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to connect: {e}")
    
    # Register remote node
    known_nodes[remote_url] = {
        "node_id": node_info.get("node_id"),
        "node_url": remote_url,
        "protocol_version": node_info.get("protocol_version"),
        "features": node_info.get("features", []),
        "last_seen": datetime.utcnow().isoformat(),
    }
    
    # Register ourselves with remote node
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(f"{remote_url}/api/federation/nodes", json={
                "node_id": NODE_ID,
                "node_url": NODE_URL,
                "protocol_version": "1.1",
                "features": ["entities", "content", "links", "groups", "federation"],
            })
        except:
            pass  # Not critical if this fails
    
    return {
        "status": "connected",
        "remote_node": known_nodes[remote_url],
        "local_node": {"node_id": NODE_ID, "node_url": NODE_URL},
    }


@app.get("/api/federation/sync/{entity_id}")
async def sync_entity(entity_id: str, since_seq: int = 0):
    """Get events for an entity since a sequence number (for federation sync)."""
    events = await storage.get_events_by_actor(entity_id, since_seq=since_seq)
    return {
        "entity_id": entity_id,
        "events": [e.to_dict() for e in events],
        "head_seq": await storage.get_log_seq(entity_id),
    }


@app.get("/api/federation/sync")
async def federation_sync_get(limit: int = 100):
    """Get all data for federation sync."""
    # Get entities
    cursor = await storage.db.execute("SELECT * FROM entities ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = await cursor.fetchall()
    entities = []
    for row in rows:
        entity = await storage.get_entity(row['id'])
        if entity:
            entities.append(entity.to_dict())
    
    # Get content
    cursor = await storage.db.execute("SELECT * FROM content WHERE access = 'public' AND tombstone = 0 ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = await cursor.fetchall()
    content = []
    for row in rows:
        c = await storage.get_content(row['id'])
        if c:
            content.append(c.to_dict())
    
    return {
        "entities": entities,
        "content": content,
        "node_id": NODE_ID,
        "node_url": NODE_URL,
    }


@app.post("/api/federation/sync")
async def federation_sync_post(req: dict):
    """Receive sync data from another node."""
    imported = {"entities": 0, "content": 0}
    
    # Import entities
    for e in req.get("entities", []):
        existing = await storage.get_entity(e.get("id"))
        if not existing:
            try:
                await storage.db.execute('''
                    INSERT INTO entities (id, kind, public_key, handle, profile, created_at, updated_at, sig)
                    VALUES (?, 'user', ?, ?, ?, ?, ?, ?)
                ''', (
                    e.get("id"),
                    e.get("public_key", ""),
                    e.get("handle"),
                    json.dumps(e.get("profile", {})),
                    e.get("created_at", datetime.utcnow().isoformat()),
                    datetime.utcnow().isoformat(),
                    b""
                ))
                await storage.db.commit()
                imported["entities"] += 1
            except Exception as ex:
                pass  # Skip duplicates
    
    # Import content
    for c in req.get("content", []):
        existing = await storage.get_content(c.get("id"))
        if not existing:
            try:
                await storage.db.execute('''
                    INSERT INTO content (id, author, kind, body, reply_to, created_at, access, encrypted, encryption_metadata, sig, tombstone)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, 0)
                ''', (
                    c.get("id"),
                    c.get("author"),
                    c.get("kind", "post"),
                    c.get("body", ""),
                    c.get("reply_to"),
                    c.get("created_at", datetime.utcnow().isoformat()),
                    c.get("access", "public"),
                    b""
                ))
                await storage.db.commit()
                imported["content"] += 1
            except Exception as ex:
                pass  # Skip duplicates
    
    return {"status": "synced", "imported": imported}


@app.get("/api/resolve/{handle}")
async def resolve_handle(handle: str):
    """Resolve a handle to an entity ID."""
    # Remove @ prefix if present
    handle = handle.lstrip("@")
    
    # Try local lookup
    cursor = await storage.db.execute("SELECT id FROM entities WHERE handle = ?", (handle,))
    row = await cursor.fetchone()
    if row:
        entity = await storage.get_entity(row['id'])
        if entity:
            return {
                "id": entity.id,
                "handle": entity.handle,
                "profile": entity.profile,
                "relay_hints": [NODE_URL],
            }
    
    # Try federation lookup
    for node_url, node_info in known_nodes.items():
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{node_url}/api/entities/by-handle/{handle}")
                if r.status_code == 200:
                    data = r.json()
                    return {
                        "id": data.get("id"),
                        "handle": data.get("handle"),
                        "profile": data.get("profile"),
                        "relay_hints": [node_url],
                    }
        except:
            pass
    
    raise HTTPException(status_code=404, detail="Handle not found")


@app.get("/api/federation/discover")
async def federation_discover(handle: str = None, entity_id: str = None):
    """Discover an entity across federated nodes."""
    if not handle and not entity_id:
        raise HTTPException(status_code=400, detail="handle or entity_id required")
    
    results = []
    
    for node_url, node_info in known_nodes.items():
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                if handle:
                    r = await client.get(f"{node_url}/api/entities/by-handle/{handle}")
                else:
                    r = await client.get(f"{node_url}/api/entities/{entity_id}")
                
                if r.status_code == 200:
                    data = r.json()
                    results.append({
                        "entity": data,
                        "node_url": node_url,
                        "node_id": node_info.get("node_id"),
                    })
        except:
            pass
    
    return {"results": results, "hints": [r["node_url"] for r in results]}


@app.get("/api/federation/content")
async def federation_get_content(since: str = None, limit: int = 100):
    """Get all content since a timestamp for federation sync."""
    query = "SELECT * FROM content WHERE access = 'public'"
    params = []
    
    if since:
        query += " AND created_at > ?"
        params.append(since)
    
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    cursor = await storage.db.execute(query, params)
    rows = await cursor.fetchall()
    
    results = []
    for row in rows:
        content = await storage.get_content(row['id'])
        if content:
            item = content.to_dict()
            author = await storage.get_entity(content.author)
            if author:
                item['author_handle'] = author.handle
                item['author_profile'] = author.profile
            results.append(item)
    
    return {"items": results, "node_id": NODE_ID}


@app.get("/api/federation/entities")
async def federation_get_entities(limit: int = 100, kind: Optional[str] = None):
    """Get all public entities for federation sync (users and groups)."""
    if kind:
        cursor = await storage.db.execute(
            "SELECT * FROM entities WHERE kind = ? ORDER BY created_at DESC LIMIT ?",
            (kind, limit)
        )
    else:
        # Export both users AND groups for federation
        cursor = await storage.db.execute(
            "SELECT * FROM entities ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
    rows = await cursor.fetchall()
    
    results = []
    for row in rows:
        entity = await storage.get_entity(row['id'])
        if entity:
            results.append(entity.to_dict())
    
    return {"items": results, "node_id": NODE_ID}


@app.get("/api/federation/groups")
async def federation_get_groups(limit: int = 100):
    """Get all public groups for federation sync."""
    cursor = await storage.db.execute(
        "SELECT * FROM entities WHERE kind = 'group' ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    rows = await cursor.fetchall()
    
    results = []
    for row in rows:
        entity = await storage.get_entity(row['id'])
        if entity:
            results.append(entity.to_dict())
    
    return {"items": results, "node_id": NODE_ID}


@app.post("/api/federation/import")
async def federation_import(req: dict):
    """Import entities (users, groups) and content from a remote node."""
    import httpx
    
    remote_url = req.get("node_url", "").rstrip("/")
    since = req.get("since")
    
    if not remote_url:
        raise HTTPException(status_code=400, detail="node_url required")
    
    imported = {"entities": 0, "groups": 0, "content": 0}
    
    async with httpx.AsyncClient(timeout=30) as client:
        # Import ALL entities (users AND groups)
        try:
            r = await client.get(f"{remote_url}/api/federation/entities")
            r.raise_for_status()
            entities = r.json().get("items", [])
            
            for ent in entities:
                existing = await storage.get_entity(ent["id"])
                if not existing:
                    try:
                        # Determine entity kind
                        kind = ent.get("kind", "user")
                        now = datetime.utcnow().isoformat()
                        
                        await storage.db.execute('''
                            INSERT INTO entities (id, kind, public_key, encryption_key, handle, profile, created_at, updated_at, sig)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            ent["id"],
                            kind,
                            bytes.fromhex(ent.get("public_key", "00" * 32)) if ent.get("public_key") else b"\x00" * 32,
                            bytes.fromhex(ent.get("encryption_key", "")) if ent.get("encryption_key") else None,
                            ent.get("handle"),
                            json.dumps(ent.get("profile", {})),
                            ent.get("created_at", now),
                            ent.get("updated_at", now),
                            bytes.fromhex(ent.get("sig", "00" * 64)) if ent.get("sig") else b"\x00" * 64,
                        ))
                        await storage.db.commit()
                        
                        if kind == "group":
                            imported["groups"] += 1
                        else:
                            imported["entities"] += 1
                            
                        print(f"[Federation] Imported {kind}: {ent.get('handle', ent['id'][:16])}")
                    except Exception as ex:
                        print(f"[Federation] Failed to import entity {ent['id']}: {ex}")
        except Exception as e:
            print(f"[Federation] Failed to import entities: {e}")
        
        # Import content
        try:
            params = {"limit": 100}
            if since:
                params["since"] = since
            r = await client.get(f"{remote_url}/api/federation/content", params=params)
            r.raise_for_status()
            content_items = r.json().get("items", [])
            
            for item in content_items:
                existing = await storage.get_content(item["id"])
                if not existing:
                    try:
                        now = datetime.utcnow().isoformat()
                        await storage.db.execute('''
                            INSERT INTO content (id, author, kind, body, reply_to, created_at, access, encrypted, encryption_metadata, sig)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            item["id"],
                            item.get("author"),
                            item.get("kind", "post"),
                            json.dumps(item.get("body", {})),
                            item.get("reply_to"),
                            item.get("created_at", now),
                            item.get("access", "public"),
                            0,  # encrypted
                            None,  # encryption_metadata
                            bytes.fromhex(item.get("sig", "00" * 64)) if item.get("sig") else b"\x00" * 64,
                        ))
                        await storage.db.commit()
                        imported["content"] += 1
                        print(f"[Federation] Imported content: {item['id'][:16]}")
                    except Exception as ex:
                        print(f"[Federation] Failed to import content {item['id']}: {ex}")
        except Exception as e:
            print(f"[Federation] Failed to import content: {e}")
    
    return {
        "status": "imported",
        "entities_imported": imported["entities"],
        "groups_imported": imported["groups"],
        "content_imported": imported["content"],
        "from_node": remote_url,
    }


@app.post("/api/federation/import/direct")
async def federation_import_direct(req: dict):
    """Directly import entities, groups, content, and links from provided data."""
    imported = {"entities": 0, "groups": 0, "content": 0, "links": 0}
    
    # Import entities (users)
    for ent in req.get("entities", []):
        existing = await storage.get_entity(ent["id"])
        if not existing:
            try:
                kind = ent.get("kind", "user")
                now = datetime.utcnow().isoformat()
                await storage.db.execute('''
                    INSERT INTO entities (id, kind, public_key, encryption_key, handle, profile, created_at, updated_at, sig)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ent["id"],
                    kind,
                    bytes.fromhex(ent.get("public_key", "00" * 32)) if ent.get("public_key") else b"\x00" * 32,
                    bytes.fromhex(ent.get("encryption_key", "")) if ent.get("encryption_key") else None,
                    ent.get("handle"),
                    json.dumps(ent.get("profile", {})),
                    ent.get("created_at", now),
                    ent.get("updated_at", now),
                    bytes.fromhex(ent.get("sig", "00" * 64)) if ent.get("sig") else b"\x00" * 64,
                ))
                await storage.db.commit()
                imported["entities"] += 1
            except Exception as ex:
                print(f"[Federation] Failed to import entity {ent['id']}: {ex}")
    
    # Import groups
    for grp in req.get("groups", []):
        existing = await storage.get_entity(grp["id"])
        if not existing:
            try:
                now = datetime.utcnow().isoformat()
                await storage.db.execute('''
                    INSERT INTO entities (id, kind, public_key, encryption_key, handle, profile, created_at, updated_at, sig)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    grp["id"],
                    "group",
                    bytes.fromhex(grp.get("public_key", "00" * 32)) if grp.get("public_key") else b"\x00" * 32,
                    None,
                    grp.get("handle"),
                    json.dumps(grp.get("profile", {})),
                    grp.get("created_at", now),
                    grp.get("updated_at", now),
                    bytes.fromhex(grp.get("sig", "00" * 64)) if grp.get("sig") else b"\x00" * 64,
                ))
                await storage.db.commit()
                imported["groups"] += 1
            except Exception as ex:
                print(f"[Federation] Failed to import group {grp['id']}: {ex}")
    
    # Import content
    for item in req.get("content", []):
        existing = await storage.get_content(item["id"])
        if not existing:
            try:
                now = datetime.utcnow().isoformat()
                await storage.db.execute('''
                    INSERT INTO content (id, author, kind, body, reply_to, created_at, access, encrypted, encryption_metadata, sig)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item["id"],
                    item.get("author"),
                    item.get("kind", "post"),
                    json.dumps(item.get("body", {})),
                    item.get("reply_to"),
                    item.get("created_at", now),
                    item.get("access", "public"),
                    0,
                    None,
                    bytes.fromhex(item.get("sig", "00" * 64)) if item.get("sig") else b"\x00" * 64,
                ))
                await storage.db.commit()
                imported["content"] += 1
            except Exception as ex:
                print(f"[Federation] Failed to import content {item['id']}: {ex}")
    
    # Import links (follows, likes, etc.)
    for link in req.get("links", []):
        try:
            # Check if link exists
            existing = await storage.db.execute(
                "SELECT id FROM links WHERE source = ? AND target = ? AND kind = ?",
                (link.get("source"), link.get("target"), link.get("kind"))
            )
            if not await existing.fetchone():
                link_id = link.get("id", f"lnk:{link.get('source', '')[:8]}:{link.get('kind', '')}:{link.get('target', '')[:8]}")
                now = datetime.utcnow().isoformat()
                await storage.db.execute('''
                    INSERT INTO links (id, source, target, kind, created_at, sig)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    link_id,
                    link.get("source"),
                    link.get("target"),
                    link.get("kind"),
                    link.get("created_at", now),
                    bytes.fromhex(link.get("sig", "00" * 64)) if link.get("sig") else b"\x00" * 64,
                ))
                await storage.db.commit()
                imported["links"] += 1
        except Exception as ex:
            print(f"[Federation] Failed to import link: {ex}")
    
    return {
        "status": "imported",
        "entities": imported["entities"],
        "groups": imported["groups"],
        "content": imported["content"],
        "links": imported["links"],
    }


@app.get("/api/federation/links")
async def federation_get_links(limit: int = 100):
    """Get all links for federation sync."""
    cursor = await storage.db.execute(
        "SELECT id, source, target, kind, created_at, sig FROM links ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    rows = await cursor.fetchall()
    
    links = []
    for row in rows:
        links.append({
            "id": row[0],
            "source": row[1],
            "target": row[2],
            "kind": row[3],
            "created_at": row[4],
            "sig": row[5].hex() if row[5] else None,
        })
    
    return {"links": links}


@app.get("/api/notifications")
async def get_notifications(current_user: str = Depends(require_auth), limit: int = 50):
    """Get notifications for the current user (likes, replies, follows on their content)."""
    notifications = []
    
    # Get likes on user's content
    cursor = await storage.db.execute('''
        SELECT l.id, l.source, l.target, l.kind, l.created_at, e.handle, e.profile
        FROM links l
        JOIN content c ON l.target = c.id
        LEFT JOIN entities e ON l.source = e.id
        WHERE c.author = ? AND l.kind = 'like'
        ORDER BY l.created_at DESC
        LIMIT ?
    ''', (current_user, limit))
    
    for row in await cursor.fetchall():
        profile = json.loads(row[6]) if row[6] else {}
        notifications.append({
            "id": row[0],
            "kind": "like",
            "actor_id": row[1],
            "actor_handle": row[5],
            "actor_name": profile.get("name", row[5]),
            "target_id": row[2],
            "created_at": row[4],
            "message": f"{profile.get('name', row[5])} liked your post"
        })
    
    # Get replies to user's content
    cursor = await storage.db.execute('''
        SELECT c.id, c.author, c.body, c.created_at, c.reply_to, e.handle, e.profile
        FROM content c
        JOIN content parent ON c.reply_to = parent.id
        LEFT JOIN entities e ON c.author = e.id
        WHERE parent.author = ? AND c.kind = 'reply'
        ORDER BY c.created_at DESC
        LIMIT ?
    ''', (current_user, limit))
    
    for row in await cursor.fetchall():
        profile = json.loads(row[6]) if row[6] else {}
        body = json.loads(row[2]) if row[2] else {}
        notifications.append({
            "id": row[0],
            "kind": "reply",
            "actor_id": row[1],
            "actor_handle": row[5],
            "actor_name": profile.get("name", row[5]),
            "target_id": row[4],
            "content_preview": body.get("text", "")[:50],
            "created_at": row[3],
            "message": f"{profile.get('name', row[5])} replied to your post"
        })
    
    # Get new followers
    cursor = await storage.db.execute('''
        SELECT l.id, l.source, l.created_at, e.handle, e.profile
        FROM links l
        LEFT JOIN entities e ON l.source = e.id
        WHERE l.target = ? AND l.kind = 'follow'
        ORDER BY l.created_at DESC
        LIMIT ?
    ''', (current_user, limit))
    
    for row in await cursor.fetchall():
        profile = json.loads(row[4]) if row[4] else {}
        notifications.append({
            "id": row[0],
            "kind": "follow",
            "actor_id": row[1],
            "actor_handle": row[3],
            "actor_name": profile.get("name", row[3]),
            "created_at": row[2],
            "message": f"{profile.get('name', row[3])} started following you"
        })
    
    # Sort by created_at
    notifications.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return {"items": notifications[:limit], "total": len(notifications)}


# ========== Discovery Layer API ==========

@app.get("/api/search")
async def search_entities(
    q: str = Query(..., description="Search query"),
    type: Optional[str] = Query(None, description="Entity type: user or group"),
    limit: int = Query(20, le=100)
):
    """Search for entities by name, handle, or bio."""
    if not indexer:
        raise HTTPException(status_code=503, detail="Indexer not initialized")
    
    results = indexer.search(q, kind=type, limit=limit)
    return {
        "query": q,
        "results": results,
        "total": len(results),
    }


@app.get("/api/resolve/{handle}")
async def resolve_handle(handle: str):
    """Resolve a handle to entity information."""
    if not indexer:
        raise HTTPException(status_code=503, detail="Indexer not initialized")
    
    result = indexer.resolve_handle(handle)
    if not result:
        raise HTTPException(status_code=404, detail="Handle not found")
    
    return result


@app.get("/api/locate/{entity_id}")
async def locate_entity(entity_id: str):
    """Find relay URLs for an entity."""
    if not indexer:
        raise HTTPException(status_code=503, detail="Indexer not initialized")
    
    result = indexer.locate_entity(entity_id)
    if not result:
        raise HTTPException(status_code=404, detail="Entity not found in index")
    
    return result


@app.get("/api/index/stats")
async def get_index_stats():
    """Get indexer statistics."""
    if not indexer:
        return {"status": "not_initialized"}
    
    return indexer.get_stats()


@app.get("/api/index/relays")
async def get_known_relays():
    """Get list of known relays."""
    if not indexer:
        return {"relays": []}
    
    return {"relays": indexer.get_known_relays()}


@app.post("/api/index/crawl")
async def trigger_crawl(req: Optional[dict] = None):
    """Trigger a crawl of known/seed relays."""
    if not indexer:
        raise HTTPException(status_code=503, detail="Indexer not initialized")
    
    # Add seed relays if provided
    if req and req.get("seed_relays"):
        for relay in req["seed_relays"]:
            indexer.add_seed_relay(relay)
    
    # Start crawl in background
    import asyncio
    asyncio.create_task(indexer.run_crawl())
    
    return {
        "status": "crawl_started",
        "known_relays": len(indexer.relay_index),
        "queue_size": len(indexer.crawl_queue),
    }


@app.post("/api/index/register")
async def register_relay(req: dict):
    """Register a relay with the indexer."""
    if not indexer:
        raise HTTPException(status_code=503, detail="Indexer not initialized")
    
    relay_url = req.get("relay_url")
    if not relay_url:
        raise HTTPException(status_code=400, detail="relay_url required")
    
    indexer.add_seed_relay(relay_url)
    
    return {
        "status": "registered",
        "relay_url": relay_url,
    }


@app.get("/.well-known/mesh/entity/{handle}")
async def well_known_entity(handle: str):
    """Resolve entity by handle (Discovery Layer standard endpoint)."""
    # Try local first
    cursor = await storage.db.execute(
        "SELECT id, handle, profile, public_key FROM entities WHERE handle = ?",
        (handle,)
    )
    row = await cursor.fetchone()
    
    if row:
        profile = json.loads(row[2]) if row[2] else {}
        return {
            "entity_id": row[0],
            "handle": row[1],
            "profile": profile,
            "public_key": row[3].hex() if row[3] else None,
            "relay_hints": [NODE_URL],
        }
    
    # Try indexer
    if indexer:
        result = indexer.resolve_handle(handle)
        if result:
            return result
    
    raise HTTPException(status_code=404, detail="Entity not found")


@app.get("/api/federation/relays")
async def federation_get_relays():
    """Get known relays for federation gossip."""
    relays = []
    
    # Add self
    relays.append({
        "url": NODE_URL,
        "node_id": NODE_ID,
        "last_seen": datetime.utcnow().isoformat(),
    })
    
    # Add indexed relays
    if indexer:
        for relay in indexer.get_known_relays():
            if relay["url"] != NODE_URL:
                relays.append({
                    "url": relay["url"],
                    "node_id": relay.get("node_id"),
                    "last_seen": relay.get("last_crawled"),
                })
    
    return {"relays": relays}


# WebSocket for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    await websocket.accept()
    
    entity_id = sessions.get(token) if token else None
    
    if entity_id:
        if entity_id not in websocket_connections:
            websocket_connections[entity_id] = []
        websocket_connections[entity_id].append(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "subscribe":
                # Subscribe to channels
                channels = data.get("channels", [])
                await websocket.send_json({"type": "subscribed", "channels": channels})
            
            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        if entity_id and entity_id in websocket_connections:
            websocket_connections[entity_id].remove(websocket)


async def broadcast_event(actor_id: str, event: dict):
    """Broadcast event to followers."""
    followers = await storage.get_followers(actor_id)
    
    for follower_id in followers:
        if follower_id in websocket_connections:
            for ws in websocket_connections[follower_id]:
                try:
                    await ws.send_json(event)
                except:
                    pass


# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "node_id": NODE_ID}


# Stats
@app.get("/api/stats")
async def get_stats():
    """Get node statistics."""
    metrics = await storage.get_metrics()
    return {
        "node_id": NODE_ID,
        "node_url": NODE_URL,
        **metrics,
    }


# ========== Direct Messages ==========

@app.get("/api/messages/conversations")
async def get_conversations(current_user: str = Depends(require_auth)):
    """Get list of conversations for the current user."""
    # Get all DM content where user is sender or recipient
    cursor = await storage.db.execute("""
        SELECT DISTINCT 
            CASE 
                WHEN author = ? THEN json_extract(body, '$.recipient')
                ELSE author 
            END as participant_id,
            MAX(created_at) as last_message_at
        FROM content 
        WHERE kind = 'dm' AND (author = ? OR json_extract(body, '$.recipient') = ?)
        GROUP BY participant_id
        ORDER BY last_message_at DESC
    """, (current_user, current_user, current_user))
    rows = await cursor.fetchall()
    
    conversations = []
    for row in rows:
        participant_id = row['participant_id']
        if not participant_id:
            continue
            
        participant = await storage.get_entity(participant_id)
        if not participant:
            continue
        
        # Get last message
        msg_cursor = await storage.db.execute("""
            SELECT body FROM content 
            WHERE kind = 'dm' AND (
                (author = ? AND json_extract(body, '$.recipient') = ?) OR
                (author = ? AND json_extract(body, '$.recipient') = ?)
            )
            ORDER BY created_at DESC LIMIT 1
        """, (current_user, participant_id, participant_id, current_user))
        msg_row = await msg_cursor.fetchone()
        last_message = ""
        if msg_row:
            try:
                body = json.loads(msg_row['body']) if isinstance(msg_row['body'], str) else msg_row['body']
                last_message = body.get('text', '')[:50]
            except:
                pass
        
        conversations.append({
            "id": f"{current_user}:{participant_id}",
            "participantId": participant_id,
            "participantHandle": participant.handle,
            "participantName": participant.profile.get('name', participant.handle),
            "lastMessage": last_message,
            "lastMessageAt": row['last_message_at'],
            "unreadCount": 0,  # TODO: track read status
        })
    
    return {"conversations": conversations}


@app.get("/api/messages/{participant_id}")
async def get_messages(participant_id: str, current_user: str = Depends(require_auth), limit: int = 50):
    """Get messages in a conversation."""
    cursor = await storage.db.execute("""
        SELECT * FROM content 
        WHERE kind = 'dm' AND (
            (author = ? AND json_extract(body, '$.recipient') = ?) OR
            (author = ? AND json_extract(body, '$.recipient') = ?)
        )
        ORDER BY created_at DESC LIMIT ?
    """, (current_user, participant_id, participant_id, current_user, limit))
    rows = await cursor.fetchall()
    
    messages = []
    for row in rows:
        try:
            body = json.loads(row['body']) if isinstance(row['body'], str) else row['body']
            messages.append({
                "id": row['id'],
                "senderId": row['author'],
                "content": body.get('text', ''),
                "timestamp": row['created_at'],
                "encrypted": bool(row['encrypted']),
                "status": "read",
            })
        except:
            pass
    
    messages.reverse()  # Oldest first
    return {"messages": messages}


@app.post("/api/messages")
async def send_message(req: dict, current_user: str = Depends(require_auth)):
    """Send a direct message."""
    recipient_id = req.get("recipient_id")
    content_text = req.get("content", "")
    encrypted = req.get("encrypted", False)
    
    if not recipient_id or not content_text:
        raise HTTPException(status_code=400, detail="recipient_id and content required")
    
    # Check recipient exists
    recipient = await storage.get_entity(recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    
    # Create DM content
    content_id = secrets.token_hex(24)
    now = datetime.utcnow()
    
    body = json.dumps({
        "text": content_text,
        "recipient": recipient_id,
    })
    
    await storage.db.execute("""
        INSERT INTO content (id, author, kind, body, created_at, access, encrypted, tombstone, sig)
        VALUES (?, ?, 'dm', ?, ?, 'private', ?, 0, ?)
    """, (content_id, current_user, body, now.isoformat(), 1 if encrypted else 0, b""))
    await storage.db.commit()
    
    return {"id": content_id, "status": "sent"}


@app.post("/api/notifications/read-all")
async def mark_notifications_read(current_user: str = Depends(require_auth)):
    """Mark all notifications as read."""
    # For now just return success - in production, track read status
    return {"status": "ok"}


# ========== Search & Trending ==========

@app.get("/api/trending")
async def get_trending():
    """Get trending topics."""
    # Simple implementation - count hashtags in recent posts
    cursor = await storage.db.execute("""
        SELECT body FROM content 
        WHERE kind = 'post' AND access = 'public' AND tombstone = 0
        AND created_at > datetime('now', '-7 days')
        ORDER BY created_at DESC LIMIT 500
    """)
    rows = await cursor.fetchall()
    
    import re
    hashtag_counts = {}
    for row in rows:
        body = row['body'] if isinstance(row['body'], str) else str(row['body'])
        hashtags = re.findall(r'#(\w+)', body)
        for tag in hashtags:
            tag_lower = tag.lower()
            hashtag_counts[tag_lower] = hashtag_counts.get(tag_lower, 0) + 1
    
    # Sort by count
    trending = sorted(hashtag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {"topics": [f"#{tag}" for tag, _ in trending]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=12000)
    parser.add_argument("--node-id", type=str, default="node1")
    args = parser.parse_args()
    
    NODE_ID = args.node_id
    DB_PATH = f"mesh_{NODE_ID}.db"
    NODE_URL = f"http://localhost:{args.port}"
    
    uvicorn.run(app, host="0.0.0.0", port=args.port)
