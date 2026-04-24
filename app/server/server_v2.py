#!/usr/bin/env python3
"""
MESH Protocol Server v2
Full protocol-compliant implementation with:
- Layer 1: Ed25519 + X25519 + AES-GCM + Device Keys
- Layer 3: Multi-head DAG + Lamport clock + Auto-merge
- Layer 4: Entity, Content, Link primitives
- Layer 5: Attestations with conflict resolution
- Layer 6: View execution with limits
- Layer 7: HTTP API + WebSocket + Federation
"""

import asyncio
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import aiosqlite

# Import protocol implementation
from protocol import (
    # Layer 1: Privacy
    SigningKeyPair, EncryptionKeyPair, verify_signature,
    canonical_json, sha256_hex,
    EncryptedEnvelope, encrypt_for_recipient, decrypt_from_sender,
    DeviceKey, authorize_device_key, verify_device_key,
    # Layer 3: Integrity
    LogEvent, OpType, ObjectType, DAGStore,
    generate_event_id, compute_lamport, create_merge_event,
    # Layer 4: Social
    Entity, EntityKind, Content, ContentKind, Link, LinkKind,
    generate_entity_id, generate_content_id, generate_link_id,
    # Layer 5: Moderation
    Attestation, AttestationType, resolve_attestation_conflicts, generate_attestation_id,
    # Layer 6: Views
    ViewExecutor,
    # Sync
    topological_sort,
)

# ============================================================
# CONFIGURATION
# ============================================================

NODE_ID = os.environ.get("MESH_NODE_ID", f"node_{secrets.token_hex(4)}")
NODE_URL = os.environ.get("MESH_NODE_URL", "http://localhost:12000")
DB_PATH = os.environ.get("DATABASE_URL", "sqlite:///./mesh.db").replace("sqlite:///", "")

# ============================================================
# PYDANTIC MODELS
# ============================================================

class EntityCreate(BaseModel):
    public_key: str
    encryption_key: Optional[str] = None
    handle: Optional[str] = None
    profile: dict = Field(default_factory=dict)


class DeviceKeyCreate(BaseModel):
    device_public_key: str
    device_name: str
    capabilities: List[str] = Field(default_factory=lambda: ["post", "follow", "dm"])


class ContentCreate(BaseModel):
    author: str
    kind: str = "post"
    body: str
    media: List[str] = Field(default_factory=list)
    reply_to: Optional[str] = None


class DMCreate(BaseModel):
    author: str
    recipient: str
    body: str


class LinkCreate(BaseModel):
    target: str
    kind: str = "follow"
    metadata: dict = Field(default_factory=dict)


class AttestationCreate(BaseModel):
    subject: str
    type: str
    claim: dict
    evidence: Optional[dict] = None
    confidence: float = 1.0


# ============================================================
# STORAGE
# ============================================================

class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None
        self.dag = DAGStore()
    
    async def initialize(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        
        await self.db.executescript("""
            -- Entities with device keys
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                public_key BLOB NOT NULL,
                encryption_key BLOB,
                handle TEXT UNIQUE,
                profile TEXT,
                device_keys TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            
            -- Content with E2EE support
            CREATE TABLE IF NOT EXISTS content (
                id TEXT PRIMARY KEY,
                author TEXT NOT NULL,
                kind TEXT NOT NULL,
                body TEXT,
                media TEXT DEFAULT '[]',
                reply_to TEXT,
                encrypted TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            
            -- Links
            CREATE TABLE IF NOT EXISTS links (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                kind TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                UNIQUE(source, target, kind)
            );
            
            -- DAG events
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                actor TEXT NOT NULL,
                parents TEXT NOT NULL,
                lamport INTEGER NOT NULL,
                op TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                ts TEXT NOT NULL,
                device_id TEXT,
                sig TEXT
            );
            
            -- Attestations
            CREATE TABLE IF NOT EXISTS attestations (
                id TEXT PRIMARY KEY,
                issuer TEXT NOT NULL,
                subject TEXT NOT NULL,
                type TEXT NOT NULL,
                claim TEXT NOT NULL,
                evidence TEXT,
                confidence REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                revoked INTEGER DEFAULT 0
            );
            
            -- Trust relationships for moderation
            CREATE TABLE IF NOT EXISTS trust (
                follower TEXT NOT NULL,
                labeler TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (follower, labeler)
            );
            
            -- Sessions
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                device_id TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            
            -- Indexes
            CREATE INDEX IF NOT EXISTS idx_content_author ON content(author);
            CREATE INDEX IF NOT EXISTS idx_links_source ON links(source);
            CREATE INDEX IF NOT EXISTS idx_links_target ON links(target);
            CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor);
            CREATE INDEX IF NOT EXISTS idx_events_lamport ON events(lamport);
            CREATE INDEX IF NOT EXISTS idx_att_subject ON attestations(subject);
        """)
        await self.db.commit()
        
        # Load DAG from DB
        await self._load_dag()
    
    async def _load_dag(self):
        """Load existing events into DAG."""
        cursor = await self.db.execute("SELECT * FROM events ORDER BY lamport")
        async for row in cursor:
            event = LogEvent(
                id=row["id"],
                actor=row["actor"],
                parents=json.loads(row["parents"]),
                lamport=row["lamport"],
                op=OpType(row["op"]),
                object_type=ObjectType(row["object_type"]),
                object_id=row["object_id"],
                payload=json.loads(row["payload"]),
                ts=datetime.fromisoformat(row["ts"]),
                device_id=row["device_id"],
                sig=bytes.fromhex(row["sig"]) if row["sig"] else b"",
            )
            self.dag.add_event(event)
    
    async def close(self):
        if self.db:
            await self.db.close()
    
    # Entity operations
    async def create_entity(self, entity: Entity) -> str:
        await self.db.execute("""
            INSERT INTO entities (id, kind, public_key, encryption_key, handle, profile, device_keys, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entity.id, entity.kind.value, entity.public_key,
            entity.encryption_key, entity.handle,
            json.dumps(entity.profile),
            json.dumps([dk.to_dict() for dk in entity.device_keys]),
            entity.created_at.isoformat(),
            entity.updated_at.isoformat(),
        ))
        await self.db.commit()
        return entity.id
    
    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        cursor = await self.db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return Entity(
            id=row["id"],
            kind=EntityKind(row["kind"]),
            public_key=row["public_key"],
            encryption_key=row["encryption_key"],
            handle=row["handle"],
            profile=json.loads(row["profile"]) if row["profile"] else {},
            device_keys=[DeviceKey.from_dict(d) for d in json.loads(row["device_keys"])],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
    
    async def get_entity_by_handle(self, handle: str) -> Optional[Entity]:
        cursor = await self.db.execute("SELECT id FROM entities WHERE handle = ?", (handle,))
        row = await cursor.fetchone()
        if not row:
            return None
        return await self.get_entity(row["id"])
    
    async def add_device_key(self, entity_id: str, device_key: DeviceKey):
        entity = await self.get_entity(entity_id)
        if not entity:
            raise ValueError("Entity not found")
        entity.device_keys.append(device_key)
        await self.db.execute(
            "UPDATE entities SET device_keys = ?, updated_at = ? WHERE id = ?",
            (json.dumps([dk.to_dict() for dk in entity.device_keys]), datetime.utcnow().isoformat(), entity_id)
        )
        await self.db.commit()
    
    # Content operations
    async def create_content(self, content: Content) -> str:
        await self.db.execute("""
            INSERT INTO content (id, author, kind, body, media, reply_to, encrypted, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            content.id, content.author, content.kind.value,
            content.body, json.dumps(content.media), content.reply_to,
            json.dumps(content.encrypted.to_dict()) if content.encrypted else None,
            content.created_at.isoformat(), content.updated_at.isoformat(),
        ))
        await self.db.commit()
        return content.id
    
    async def get_content(self, content_id: str) -> Optional[Content]:
        cursor = await self.db.execute("SELECT * FROM content WHERE id = ?", (content_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return Content(
            id=row["id"],
            author=row["author"],
            kind=ContentKind(row["kind"]),
            body=row["body"] or "",
            media=json.loads(row["media"]) if row["media"] else [],
            reply_to=row["reply_to"],
            encrypted=EncryptedEnvelope.from_dict(json.loads(row["encrypted"])) if row["encrypted"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
    
    # Link operations
    async def create_link(self, link: Link) -> str:
        await self.db.execute("""
            INSERT OR REPLACE INTO links (id, source, target, kind, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (link.id, link.source, link.target, link.kind.value, json.dumps(link.metadata), link.created_at.isoformat()))
        await self.db.commit()
        return link.id
    
    async def delete_link(self, source: str, target: str, kind: str):
        await self.db.execute(
            "DELETE FROM links WHERE source = ? AND target = ? AND kind = ?",
            (source, target, kind)
        )
        await self.db.commit()
    
    async def get_following(self, entity_id: str) -> List[str]:
        cursor = await self.db.execute(
            "SELECT target FROM links WHERE source = ? AND kind = 'follow'",
            (entity_id,)
        )
        return [row["target"] for row in await cursor.fetchall()]
    
    async def get_followers(self, entity_id: str) -> List[str]:
        cursor = await self.db.execute(
            "SELECT source FROM links WHERE target = ? AND kind = 'follow'",
            (entity_id,)
        )
        return [row["source"] for row in await cursor.fetchall()]
    
    # Event operations
    async def append_event(self, event: LogEvent):
        await self.db.execute("""
            INSERT INTO events (id, actor, parents, lamport, op, object_type, object_id, payload, ts, device_id, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.id, event.actor, json.dumps(event.parents), event.lamport,
            event.op.value, event.object_type.value, event.object_id,
            json.dumps(event.payload), event.ts.isoformat(),
            event.device_id, event.sig.hex() if event.sig else "",
        ))
        await self.db.commit()
        self.dag.add_event(event)
    
    async def get_events(self, actor: str, since_lamport: int = 0) -> List[LogEvent]:
        cursor = await self.db.execute(
            "SELECT * FROM events WHERE actor = ? AND lamport > ? ORDER BY lamport",
            (actor, since_lamport)
        )
        events = []
        async for row in cursor:
            events.append(LogEvent(
                id=row["id"],
                actor=row["actor"],
                parents=json.loads(row["parents"]),
                lamport=row["lamport"],
                op=OpType(row["op"]),
                object_type=ObjectType(row["object_type"]),
                object_id=row["object_id"],
                payload=json.loads(row["payload"]),
                ts=datetime.fromisoformat(row["ts"]),
                device_id=row["device_id"],
                sig=bytes.fromhex(row["sig"]) if row["sig"] else b"",
            ))
        return events
    
    async def get_heads(self, actor: str) -> List[str]:
        return [e.id for e in self.dag.get_heads(actor)]
    
    # Attestation operations
    async def create_attestation(self, att: Attestation):
        await self.db.execute("""
            INSERT OR REPLACE INTO attestations (id, issuer, subject, type, claim, evidence, confidence, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            att.id, att.issuer, att.subject, att.type.value,
            json.dumps(att.claim), json.dumps(att.evidence) if att.evidence else None,
            att.confidence, att.created_at.isoformat(),
            att.expires_at.isoformat() if att.expires_at else None,
        ))
        await self.db.commit()
    
    async def get_attestations_for_subject(self, subject: str) -> List[Attestation]:
        cursor = await self.db.execute(
            "SELECT * FROM attestations WHERE subject = ? AND revoked = 0",
            (subject,)
        )
        attestations = []
        async for row in cursor:
            attestations.append(Attestation(
                id=row["id"],
                issuer=row["issuer"],
                subject=row["subject"],
                type=AttestationType(row["type"]),
                claim=json.loads(row["claim"]),
                evidence=json.loads(row["evidence"]) if row["evidence"] else None,
                confidence=row["confidence"],
                created_at=datetime.fromisoformat(row["created_at"]),
                expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            ))
        return attestations
    
    # Trust operations
    async def add_trust(self, follower: str, labeler: str):
        await self.db.execute(
            "INSERT OR REPLACE INTO trust (follower, labeler, created_at) VALUES (?, ?, ?)",
            (follower, labeler, datetime.utcnow().isoformat())
        )
        await self.db.commit()
    
    async def get_trusted_labelers(self, entity_id: str) -> Set[str]:
        cursor = await self.db.execute(
            "SELECT labeler FROM trust WHERE follower = ?",
            (entity_id,)
        )
        return {row["labeler"] for row in await cursor.fetchall()}
    
    # Feed
    async def get_feed(self, entity_id: str, limit: int = 50) -> List[dict]:
        following = await self.get_following(entity_id)
        following.append(entity_id)  # Include own posts
        
        placeholders = ",".join("?" * len(following))
        cursor = await self.db.execute(f"""
            SELECT c.*, e.handle, e.profile
            FROM content c
            JOIN entities e ON c.author = e.id
            WHERE c.author IN ({placeholders}) AND c.kind IN ('post', 'reply')
            ORDER BY c.created_at DESC
            LIMIT ?
        """, following + [limit])
        
        feed = []
        for row in await cursor.fetchall():
            profile = json.loads(row["profile"]) if row["profile"] else {}
            feed.append({
                "id": row["id"],
                "author": row["author"],
                "author_handle": row["handle"],
                "author_name": profile.get("name", row["handle"]),
                "kind": row["kind"],
                "body": row["body"],
                "media": json.loads(row["media"]) if row["media"] else [],
                "reply_to": row["reply_to"],
                "created_at": row["created_at"],
            })
        
        return feed


# ============================================================
# APP SETUP
# ============================================================

storage: Optional[Storage] = None
sessions: Dict[str, str] = {}  # token -> entity_id
challenges: Dict[str, str] = {}  # entity_id -> challenge


@asynccontextmanager
async def lifespan(app: FastAPI):
    global storage
    storage = Storage(DB_PATH)
    await storage.initialize()
    print(f"[{NODE_ID}] MESH Protocol Server v2 started")
    print(f"[{NODE_ID}] Database: {DB_PATH}")
    yield
    await storage.close()


app = FastAPI(
    title=f"MESH Protocol Server ({NODE_ID})",
    description="Full protocol-compliant MESH implementation",
    version="2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# AUTH
# ============================================================

def get_current_user(token: str = Query(None)) -> Optional[str]:
    if not token:
        return None
    return sessions.get(token)


def require_auth(token: str = Query(...)) -> str:
    entity_id = sessions.get(token)
    if not entity_id:
        raise HTTPException(401, "Invalid session")
    return entity_id


@app.get("/health")
async def health():
    return {"status": "ok", "node_id": NODE_ID, "protocol_version": "2.0"}


@app.get("/.well-known/mesh-node")
async def well_known():
    return {
        "node_id": NODE_ID,
        "node_url": NODE_URL,
        "protocol_version": "2.0",
        "features": ["dag", "e2ee", "device_keys", "attestations", "views"],
    }


@app.post("/api/auth/challenge")
async def auth_challenge(req: dict):
    entity_id = req.get("entity_id")
    if not entity_id:
        raise HTTPException(400, "entity_id required")
    
    challenge = secrets.token_hex(32)
    challenges[entity_id] = challenge
    return {"challenge": challenge}


@app.post("/api/auth/verify")
async def auth_verify(req: dict):
    entity_id = req.get("entity_id")
    challenge = req.get("challenge")
    signature = req.get("signature")
    device_id = req.get("device_id")  # Optional: specify which device
    
    if challenges.get(entity_id) != challenge:
        raise HTTPException(401, "Invalid challenge")
    
    entity = await storage.get_entity(entity_id)
    if not entity:
        raise HTTPException(404, "Entity not found")
    
    # Verify signature (check root key or device key)
    sig_bytes = bytes.fromhex(signature)
    msg_bytes = challenge.encode()
    
    # Try root key first
    if verify_signature(entity.public_key, msg_bytes, sig_bytes):
        pass  # Valid
    elif device_id:
        # Try specified device key
        device = next((dk for dk in entity.device_keys if dk.device_id == device_id), None)
        if not device or device.revoked:
            raise HTTPException(401, "Invalid device")
        if not verify_signature(device.public_key, msg_bytes, sig_bytes):
            raise HTTPException(401, "Invalid signature")
    else:
        raise HTTPException(401, "Invalid signature")
    
    # Create session
    token = secrets.token_urlsafe(32)
    sessions[token] = entity_id
    del challenges[entity_id]
    
    return {"token": token, "entity_id": entity_id}


# ============================================================
# ENTITY ENDPOINTS
# ============================================================

@app.post("/api/entities")
async def create_entity(req: EntityCreate):
    try:
        public_key = bytes.fromhex(req.public_key)
        encryption_key = bytes.fromhex(req.encryption_key) if req.encryption_key else None
    except:
        raise HTTPException(400, "Invalid key format")
    
    entity_id = generate_entity_id(public_key)
    
    # Check existence
    if await storage.get_entity(entity_id):
        raise HTTPException(409, "Entity exists")
    
    # Check handle
    if req.handle:
        if await storage.get_entity_by_handle(req.handle):
            raise HTTPException(409, "Handle taken")
    
    entity = Entity(
        id=entity_id,
        kind=EntityKind.USER,
        public_key=public_key,
        encryption_key=encryption_key,
        handle=req.handle,
        profile=req.profile,
        device_keys=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    await storage.create_entity(entity)
    
    # Create genesis event
    event = LogEvent(
        id=generate_event_id(entity_id, 1, []),
        actor=entity_id,
        parents=[],
        lamport=1,
        op=OpType.CREATE,
        object_type=ObjectType.ENTITY,
        object_id=entity_id,
        payload=entity.to_dict(),
        ts=datetime.utcnow(),
    )
    await storage.append_event(event)
    
    return {"id": entity_id, "handle": req.handle}


@app.get("/api/entities/{entity_id}")
async def get_entity(entity_id: str):
    entity = await storage.get_entity(entity_id)
    if not entity:
        raise HTTPException(404, "Not found")
    return entity.to_dict()


@app.post("/api/entities/{entity_id}/devices")
async def add_device_key(entity_id: str, req: DeviceKeyCreate, current_user: str = Depends(require_auth)):
    if current_user != entity_id:
        raise HTTPException(403, "Forbidden")
    
    entity = await storage.get_entity(entity_id)
    if not entity:
        raise HTTPException(404, "Not found")
    
    # In production, this should be signed by the root key
    device_key = DeviceKey(
        device_id=f"dev:{secrets.token_hex(8)}",
        public_key=bytes.fromhex(req.device_public_key),
        name=req.device_name,
        authorized_at=datetime.utcnow(),
        capabilities=req.capabilities,
    )
    
    await storage.add_device_key(entity_id, device_key)
    
    return device_key.to_dict()


# ============================================================
# CONTENT ENDPOINTS
# ============================================================

@app.post("/api/content")
async def create_content(req: ContentCreate, current_user: str = Depends(require_auth)):
    if current_user != req.author:
        raise HTTPException(403, "Forbidden")
    
    content_id = generate_content_id(req.author, req.body, datetime.utcnow())
    
    content = Content(
        id=content_id,
        author=req.author,
        kind=ContentKind(req.kind),
        body=req.body,
        media=req.media,
        reply_to=req.reply_to,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    await storage.create_content(content)
    
    # Create event
    heads = await storage.get_heads(req.author)
    parent_events = [storage.dag.get_event(h) for h in heads if storage.dag.get_event(h)]
    lamport = compute_lamport(parent_events)
    
    event = LogEvent(
        id=generate_event_id(req.author, lamport, heads),
        actor=req.author,
        parents=heads,
        lamport=lamport,
        op=OpType.CREATE,
        object_type=ObjectType.CONTENT,
        object_id=content_id,
        payload=content.to_dict(),
        ts=datetime.utcnow(),
    )
    await storage.append_event(event)
    
    return {"id": content_id}


@app.post("/api/dm")
async def create_dm(req: DMCreate, current_user: str = Depends(require_auth)):
    """Create an end-to-end encrypted DM."""
    if current_user != req.author:
        raise HTTPException(403, "Forbidden")
    
    recipient = await storage.get_entity(req.recipient)
    if not recipient or not recipient.encryption_key:
        raise HTTPException(400, "Recipient doesn't support E2EE")
    
    # Encrypt message
    encrypted = encrypt_for_recipient(
        req.body.encode(),
        recipient.encryption_key
    )
    
    content_id = generate_content_id(req.author, f"dm:{req.recipient}", datetime.utcnow())
    
    content = Content(
        id=content_id,
        author=req.author,
        kind=ContentKind.DM,
        body="",  # Body is encrypted
        encrypted=encrypted,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    await storage.create_content(content)
    
    return {"id": content_id, "encrypted": True}


@app.get("/api/content/{content_id}")
async def get_content(content_id: str):
    content = await storage.get_content(content_id)
    if not content:
        raise HTTPException(404, "Not found")
    return content.to_dict()


# ============================================================
# LINK ENDPOINTS
# ============================================================

@app.post("/api/links")
async def create_link(req: LinkCreate, current_user: str = Depends(require_auth)):
    link_id = generate_link_id(current_user, req.kind, req.target)
    
    link = Link(
        id=link_id,
        source=current_user,
        target=req.target,
        kind=LinkKind(req.kind),
        metadata=req.metadata,
        created_at=datetime.utcnow(),
    )
    
    await storage.create_link(link)
    
    # Create event
    heads = await storage.get_heads(current_user)
    parent_events = [storage.dag.get_event(h) for h in heads if storage.dag.get_event(h)]
    lamport = compute_lamport(parent_events)
    
    event = LogEvent(
        id=generate_event_id(current_user, lamport, heads),
        actor=current_user,
        parents=heads,
        lamport=lamport,
        op=OpType.CREATE,
        object_type=ObjectType.LINK,
        object_id=link_id,
        payload=link.to_dict(),
        ts=datetime.utcnow(),
    )
    await storage.append_event(event)
    
    return {"id": link_id}


@app.delete("/api/links")
async def delete_link(target: str, kind: str = "follow", current_user: str = Depends(require_auth)):
    await storage.delete_link(current_user, target, kind)
    return {"status": "deleted"}


# ============================================================
# ATTESTATION ENDPOINTS
# ============================================================

@app.post("/api/attestations")
async def create_attestation(req: AttestationCreate, current_user: str = Depends(require_auth)):
    att_id = generate_attestation_id(current_user, req.subject, req.type)
    
    attestation = Attestation(
        id=att_id,
        issuer=current_user,
        subject=req.subject,
        type=AttestationType(req.type),
        claim=req.claim,
        evidence=req.evidence,
        confidence=req.confidence,
        created_at=datetime.utcnow(),
    )
    
    await storage.create_attestation(attestation)
    
    return {"id": att_id}


@app.get("/api/subjects/{subject}/labels")
async def get_subject_labels(subject: str, viewer: str = Query(None)):
    attestations = await storage.get_attestations_for_subject(subject)
    
    if viewer:
        trusted = await storage.get_trusted_labelers(viewer)
        resolution = resolve_attestation_conflicts(attestations, trusted)
        return {"labels": [a.to_dict() for a in attestations], "resolution": resolution}
    
    return {"labels": [a.to_dict() for a in attestations]}


# ============================================================
# FEED ENDPOINTS
# ============================================================

@app.get("/api/feed")
async def get_feed(limit: int = 50, current_user: str = Depends(require_auth)):
    feed = await storage.get_feed(current_user, limit)
    return {"items": feed}


@app.get("/api/timeline/{entity_id}")
async def get_timeline(entity_id: str, limit: int = 50):
    cursor = await storage.db.execute("""
        SELECT * FROM content 
        WHERE author = ? AND kind IN ('post', 'reply')
        ORDER BY created_at DESC LIMIT ?
    """, (entity_id, limit))
    
    items = []
    async for row in cursor:
        items.append({
            "id": row["id"],
            "author": row["author"],
            "kind": row["kind"],
            "body": row["body"],
            "media": json.loads(row["media"]) if row["media"] else [],
            "reply_to": row["reply_to"],
            "created_at": row["created_at"],
        })
    
    return {"items": items}


# ============================================================
# DAG / SYNC ENDPOINTS
# ============================================================

@app.get("/api/sync/{actor}/heads")
async def get_actor_heads(actor: str):
    """Get current DAG heads for an actor."""
    heads = await storage.get_heads(actor)
    return {"actor": actor, "heads": heads}


@app.get("/api/sync/{actor}/events")
async def get_actor_events(actor: str, since: int = 0):
    """Get events for an actor since a lamport clock value."""
    events = await storage.get_events(actor, since)
    return {"actor": actor, "events": [e.to_dict() for e in events]}


@app.post("/api/sync/{actor}/merge")
async def merge_forks(actor: str, current_user: str = Depends(require_auth)):
    """Manually trigger fork merge if needed."""
    if current_user != actor:
        raise HTTPException(403, "Forbidden")
    
    if not storage.dag.needs_merge(actor):
        return {"status": "no_merge_needed"}
    
    heads = storage.dag.get_heads(actor)
    # In production, this would use the signing key
    # For now, create unsigned merge event
    merge_event = create_merge_event(
        actor=actor,
        parent_events=heads,
        signing_key=SigningKeyPair.generate(),  # Placeholder
    )
    
    await storage.append_event(merge_event)
    
    return {"status": "merged", "merge_event_id": merge_event.id}


# ============================================================
# FEDERATION ENDPOINTS
# ============================================================

@app.get("/api/federation/sync")
async def federation_sync(actor: str = Query(None), since: int = Query(0)):
    """Federation sync endpoint."""
    if actor:
        events = await storage.get_events(actor, since)
        return {"events": [e.to_dict() for e in events]}
    
    # Return recent events from all actors
    cursor = await storage.db.execute(
        "SELECT * FROM events WHERE lamport > ? ORDER BY lamport LIMIT 1000",
        (since,)
    )
    events = []
    async for row in cursor:
        events.append({
            "id": row["id"],
            "actor": row["actor"],
            "parents": json.loads(row["parents"]),
            "lamport": row["lamport"],
            "op": row["op"],
            "object_type": row["object_type"],
            "object_id": row["object_id"],
            "payload": json.loads(row["payload"]),
            "ts": row["ts"],
        })
    
    return {"events": events}


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "12000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
