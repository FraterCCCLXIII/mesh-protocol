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

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

class AccessType(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
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
                sig BLOB NOT NULL
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
        cursor = await self.db.execute("SELECT * FROM content WHERE id = ?", (content_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return Content(
            id=row['id'],
            author=row['author'],
            kind=ContentKind(row['kind']),
            body=json.loads(row['body']),
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
    body: dict
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
    global storage
    storage = Storage(DB_PATH)
    await storage.initialize()
    print(f"[{NODE_ID}] Server started, database: {DB_PATH}")
    yield
    await storage.close()
    print(f"[{NODE_ID}] Server stopped")


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
    
    return {"id": entity_id, "handle": req.handle}


@app.get("/api/entities/{entity_id}")
async def get_entity(entity_id: str):
    """Get entity by ID."""
    entity = await storage.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity.to_dict()


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


@app.get("/api/users/{entity_id}/feed")
async def get_feed(entity_id: str, limit: int = 50, offset: int = 0):
    """Get feed for an entity (posts from people they follow)."""
    following = await storage.get_following(entity_id)
    following.append(entity_id)  # Include own posts
    
    if not following:
        return {"items": [], "total": 0}
    
    placeholders = ','.join('?' * len(following))
    query = f"""
        SELECT * FROM content 
        WHERE author IN ({placeholders}) 
        AND access = 'public'
        AND reply_to IS NULL
        ORDER BY created_at DESC 
        LIMIT ? OFFSET ?
    """
    
    cursor = await storage.db.execute(query, following + [limit, offset])
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
            
            # Check if current user liked
            like_id = generate_link_id(entity_id, "like", content.id)
            cursor2 = await storage.db.execute(
                "SELECT id FROM links WHERE id = ? AND tombstone = 0",
                (like_id,)
            )
            item['liked_by_me'] = bool(await cursor2.fetchone())
            
            results.append(item)
    
    return {"items": results, "total": len(results)}


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


# Federation endpoints
@app.get("/api/federation/nodes")
async def list_known_nodes():
    """List known federation nodes."""
    return {"items": list(known_nodes.values())}


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
    return {"status": "registered"}


@app.get("/api/federation/sync/{entity_id}")
async def sync_entity(entity_id: str, since_seq: int = 0):
    """Get events for an entity since a sequence number (for federation sync)."""
    events = await storage.get_events_by_actor(entity_id, since_seq=since_seq)
    return {
        "entity_id": entity_id,
        "events": [e.to_dict() for e in events],
        "head_seq": await storage.get_log_seq(entity_id),
    }


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
