"""
HOLON v4 Implementation - Persistent Storage Layer

SQLite-based storage with async support:
- Entity storage with indexing
- Content storage with full-text search
- Link storage with graph queries
- View storage
"""

import json
import asyncio
import aiosqlite
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Any
from pathlib import Path
from enum import Enum


# =============================================================================
# DATA MODELS
# =============================================================================

class EntityKind(Enum):
    USER = "user"
    ORG = "org"
    GROUP = "group"
    RELAY = "relay"


class ContentKind(Enum):
    POST = "post"
    ARTICLE = "article"
    MEDIA = "media"


class LinkKind(Enum):
    FOLLOW = "follow"
    REACT = "react"
    SUBSCRIBE = "subscribe"
    MEMBER = "member"
    MODERATE = "moderate"
    LABEL = "label"
    DELEGATE = "delegate"
    VERIFY = "verify"
    TIP = "tip"


class AccessType(Enum):
    PUBLIC = "public"
    FOLLOWERS = "followers"
    GROUP = "group"
    PRIVATE = "private"
    PAID = "paid"


@dataclass
class Entity:
    id: str
    kind: EntityKind
    public_key: bytes
    encryption_key: bytes  # X25519 public key
    handle: Optional[str]
    profile: dict
    created_at: datetime
    updated_at: datetime
    sig: bytes
    
    def to_dict(self) -> dict:
        import base64
        return {
            "type": "entity",
            "id": self.id,
            "kind": self.kind.value,
            "public_key": base64.b64encode(self.public_key).decode(),
            "encryption_key": base64.b64encode(self.encryption_key).decode(),
            "handle": self.handle,
            "profile": self.profile,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Content:
    id: str
    kind: ContentKind
    author: str
    body: dict
    created_at: datetime
    context: Optional[str]
    reply_to: Optional[str]
    access: AccessType
    encrypted: bool
    encryption_metadata: Optional[dict]  # nonce, key_id, etc.
    sig: bytes
    
    def to_dict(self) -> dict:
        return {
            "type": "content",
            "id": self.id,
            "kind": self.kind.value,
            "author": self.author,
            "body": self.body,
            "created_at": self.created_at.isoformat(),
            "context": self.context,
            "reply_to": self.reply_to,
            "access": self.access.value,
            "encrypted": self.encrypted,
            "encryption_metadata": self.encryption_metadata,
        }


@dataclass
class Link:
    id: str
    kind: LinkKind
    source: str
    target: str
    data: dict
    created_at: datetime
    tombstone: bool
    sig: bytes
    
    def to_dict(self) -> dict:
        return {
            "type": "link",
            "id": self.id,
            "kind": self.kind.value,
            "source": self.source,
            "target": self.target,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "tombstone": self.tombstone,
        }


# =============================================================================
# SQLITE STORAGE
# =============================================================================

class Storage:
    """Async SQLite storage for HOLON protocol."""
    
    def __init__(self, db_path: str = "holon.db"):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None
    
    async def initialize(self):
        """Initialize database and create tables."""
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        
        await self.db.executescript("""
            -- Entities table
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                public_key BLOB NOT NULL,
                encryption_key BLOB NOT NULL,
                handle TEXT,
                profile TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sig BLOB NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_entities_handle ON entities(handle);
            CREATE INDEX IF NOT EXISTS idx_entities_kind ON entities(kind);
            
            -- Content table
            CREATE TABLE IF NOT EXISTS content (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                author TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                context TEXT,
                reply_to TEXT,
                access TEXT NOT NULL,
                encrypted INTEGER NOT NULL,
                encryption_metadata TEXT,
                sig BLOB NOT NULL,
                FOREIGN KEY (author) REFERENCES entities(id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_content_author ON content(author);
            CREATE INDEX IF NOT EXISTS idx_content_context ON content(context);
            CREATE INDEX IF NOT EXISTS idx_content_created ON content(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_content_reply_to ON content(reply_to);
            
            -- Full-text search for content
            CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
                id,
                text,
                content='content',
                content_rowid='rowid'
            );
            
            -- Links table
            CREATE TABLE IF NOT EXISTS links (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                tombstone INTEGER NOT NULL DEFAULT 0,
                sig BLOB NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_links_source ON links(source);
            CREATE INDEX IF NOT EXISTS idx_links_target ON links(target);
            CREATE INDEX IF NOT EXISTS idx_links_kind ON links(kind);
            CREATE INDEX IF NOT EXISTS idx_links_source_kind ON links(source, kind);
            CREATE INDEX IF NOT EXISTS idx_links_target_kind ON links(target, kind);
            
            -- Views table
            CREATE TABLE IF NOT EXISTS views (
                id TEXT PRIMARY KEY,
                author TEXT NOT NULL,
                name TEXT NOT NULL,
                source TEXT NOT NULL,
                filter TEXT NOT NULL,
                rank TEXT,
                params TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (author) REFERENCES entities(id)
            );
            
            -- Sync state (for multi-relay)
            CREATE TABLE IF NOT EXISTS sync_state (
                relay_url TEXT PRIMARY KEY,
                last_seq INTEGER NOT NULL,
                last_sync TEXT NOT NULL
            );
            
            -- Sequence counter
            CREATE TABLE IF NOT EXISTS sequence (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                seq INTEGER NOT NULL DEFAULT 0
            );
            
            INSERT OR IGNORE INTO sequence (id, seq) VALUES (1, 0);
        """)
        
        await self.db.commit()
    
    async def close(self):
        """Close database connection."""
        if self.db:
            await self.db.close()
    
    async def next_seq(self) -> int:
        """Get and increment sequence number."""
        async with self.db.execute(
            "UPDATE sequence SET seq = seq + 1 WHERE id = 1 RETURNING seq"
        ) as cursor:
            row = await cursor.fetchone()
            await self.db.commit()
            return row[0]
    
    # =========================================================================
    # ENTITY OPERATIONS
    # =========================================================================
    
    async def create_entity(self, entity: Entity) -> int:
        """Insert a new entity."""
        await self.db.execute("""
            INSERT INTO entities (id, kind, public_key, encryption_key, handle, 
                                  profile, created_at, updated_at, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entity.id,
            entity.kind.value,
            entity.public_key,
            entity.encryption_key,
            entity.handle,
            json.dumps(entity.profile),
            entity.created_at.isoformat(),
            entity.updated_at.isoformat(),
            entity.sig,
        ))
        await self.db.commit()
        return await self.next_seq()
    
    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID."""
        async with self.db.execute(
            "SELECT * FROM entities WHERE id = ?", (entity_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_entity(row)
        return None
    
    async def get_entity_by_handle(self, handle: str) -> Optional[Entity]:
        """Get entity by handle."""
        async with self.db.execute(
            "SELECT * FROM entities WHERE handle = ?", (handle.lower(),)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_entity(row)
        return None
    
    async def update_entity(self, entity: Entity) -> int:
        """Update an existing entity."""
        await self.db.execute("""
            UPDATE entities SET profile = ?, updated_at = ?, sig = ?
            WHERE id = ?
        """, (
            json.dumps(entity.profile),
            entity.updated_at.isoformat(),
            entity.sig,
            entity.id,
        ))
        await self.db.commit()
        return await self.next_seq()
    
    async def search_entities(self, query: str, limit: int = 20) -> List[Entity]:
        """Search entities by name/bio."""
        async with self.db.execute("""
            SELECT * FROM entities 
            WHERE handle LIKE ? OR profile LIKE ?
            LIMIT ?
        """, (f"%{query}%", f"%{query}%", limit)) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_entity(row) for row in rows]
    
    def _row_to_entity(self, row) -> Entity:
        return Entity(
            id=row['id'],
            kind=EntityKind(row['kind']),
            public_key=row['public_key'],
            encryption_key=row['encryption_key'],
            handle=row['handle'],
            profile=json.loads(row['profile']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            sig=row['sig'],
        )
    
    # =========================================================================
    # CONTENT OPERATIONS
    # =========================================================================
    
    async def create_content(self, content: Content) -> int:
        """Insert new content."""
        await self.db.execute("""
            INSERT INTO content (id, kind, author, body, created_at, context,
                                reply_to, access, encrypted, encryption_metadata, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            content.id,
            content.kind.value,
            content.author,
            json.dumps(content.body),
            content.created_at.isoformat(),
            content.context,
            content.reply_to,
            content.access.value,
            1 if content.encrypted else 0,
            json.dumps(content.encryption_metadata) if content.encryption_metadata else None,
            content.sig,
        ))
        
        # Index for full-text search
        text = content.body.get('text', '') + ' ' + content.body.get('title', '')
        if text.strip():
            await self.db.execute("""
                INSERT INTO content_fts (id, text) VALUES (?, ?)
            """, (content.id, text))
        
        await self.db.commit()
        return await self.next_seq()
    
    async def get_content(self, content_id: str) -> Optional[Content]:
        """Get content by ID."""
        async with self.db.execute(
            "SELECT * FROM content WHERE id = ?", (content_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_content(row)
        return None
    
    async def get_content_by_author(self, author_id: str, limit: int = 100) -> List[Content]:
        """Get content by author."""
        async with self.db.execute("""
            SELECT * FROM content WHERE author = ? 
            ORDER BY created_at DESC LIMIT ?
        """, (author_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_content(row) for row in rows]
    
    async def get_content_by_context(self, context_id: str, limit: int = 100) -> List[Content]:
        """Get content by context (group)."""
        async with self.db.execute("""
            SELECT * FROM content WHERE context = ?
            ORDER BY created_at DESC LIMIT ?
        """, (context_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_content(row) for row in rows]
    
    async def search_content(self, query: str, limit: int = 20) -> List[Content]:
        """Full-text search content."""
        # Use LIKE for simplicity (FTS5 requires special setup)
        async with self.db.execute("""
            SELECT * FROM content 
            WHERE body LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (f"%{query}%", limit)) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_content(row) for row in rows]
    
    async def get_replies(self, content_id: str) -> List[Content]:
        """Get replies to content."""
        async with self.db.execute("""
            SELECT * FROM content WHERE reply_to = ?
            ORDER BY created_at ASC
        """, (content_id,)) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_content(row) for row in rows]
    
    def _row_to_content(self, row) -> Content:
        return Content(
            id=row['id'],
            kind=ContentKind(row['kind']),
            author=row['author'],
            body=json.loads(row['body']),
            created_at=datetime.fromisoformat(row['created_at']),
            context=row['context'],
            reply_to=row['reply_to'],
            access=AccessType(row['access']),
            encrypted=bool(row['encrypted']),
            encryption_metadata=json.loads(row['encryption_metadata']) if row['encryption_metadata'] else None,
            sig=row['sig'],
        )
    
    # =========================================================================
    # LINK OPERATIONS
    # =========================================================================
    
    async def create_link(self, link: Link) -> int:
        """Insert a new link."""
        await self.db.execute("""
            INSERT INTO links (id, kind, source, target, data, created_at, tombstone, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            link.id,
            link.kind.value,
            link.source,
            link.target,
            json.dumps(link.data),
            link.created_at.isoformat(),
            1 if link.tombstone else 0,
            link.sig,
        ))
        await self.db.commit()
        return await self.next_seq()
    
    async def get_link(self, link_id: str) -> Optional[Link]:
        """Get link by ID."""
        async with self.db.execute(
            "SELECT * FROM links WHERE id = ?", (link_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_link(row)
        return None
    
    async def get_links_by_source(self, source_id: str, kind: Optional[LinkKind] = None) -> List[Link]:
        """Get links from a source entity."""
        if kind:
            query = "SELECT * FROM links WHERE source = ? AND kind = ? AND tombstone = 0"
            params = (source_id, kind.value)
        else:
            query = "SELECT * FROM links WHERE source = ? AND tombstone = 0"
            params = (source_id,)
        
        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_link(row) for row in rows]
    
    async def get_links_by_target(self, target_id: str, kind: Optional[LinkKind] = None) -> List[Link]:
        """Get links to a target."""
        if kind:
            query = "SELECT * FROM links WHERE target = ? AND kind = ? AND tombstone = 0"
            params = (target_id, kind.value)
        else:
            query = "SELECT * FROM links WHERE target = ? AND tombstone = 0"
            params = (target_id,)
        
        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_link(row) for row in rows]
    
    async def get_followers(self, entity_id: str) -> List[str]:
        """Get entity IDs that follow this entity."""
        async with self.db.execute("""
            SELECT source FROM links 
            WHERE target = ? AND kind = 'follow' AND tombstone = 0
        """, (entity_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row['source'] for row in rows]
    
    async def get_following(self, entity_id: str) -> List[str]:
        """Get entity IDs this entity follows."""
        async with self.db.execute("""
            SELECT target FROM links 
            WHERE source = ? AND kind = 'follow' AND tombstone = 0
        """, (entity_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row['target'] for row in rows]
    
    async def get_reaction_count(self, content_id: str) -> int:
        """Get reaction count for content."""
        async with self.db.execute("""
            SELECT COUNT(*) FROM links 
            WHERE target = ? AND kind = 'react' AND tombstone = 0
        """, (content_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0]
    
    async def tombstone_link(self, link_id: str) -> int:
        """Mark a link as tombstoned (soft delete)."""
        await self.db.execute(
            "UPDATE links SET tombstone = 1 WHERE id = ?", (link_id,)
        )
        await self.db.commit()
        return await self.next_seq()
    
    def _row_to_link(self, row) -> Link:
        return Link(
            id=row['id'],
            kind=LinkKind(row['kind']),
            source=row['source'],
            target=row['target'],
            data=json.loads(row['data']),
            created_at=datetime.fromisoformat(row['created_at']),
            tombstone=bool(row['tombstone']),
            sig=row['sig'],
        )
    
    # =========================================================================
    # GRAPH QUERIES
    # =========================================================================
    
    async def get_follows_of_follows(self, entity_id: str, limit: int = 20) -> List[str]:
        """Get entities followed by people you follow (excluding already followed)."""
        async with self.db.execute("""
            SELECT l2.target, COUNT(*) as overlap
            FROM links l1
            JOIN links l2 ON l1.target = l2.source
            WHERE l1.source = ? AND l1.kind = 'follow' AND l1.tombstone = 0
              AND l2.kind = 'follow' AND l2.tombstone = 0
              AND l2.target != ?
              AND l2.target NOT IN (
                  SELECT target FROM links WHERE source = ? AND kind = 'follow' AND tombstone = 0
              )
            GROUP BY l2.target
            ORDER BY overlap DESC
            LIMIT ?
        """, (entity_id, entity_id, entity_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [row['target'] for row in rows]
    
    async def get_group_members(self, group_id: str) -> List[str]:
        """Get members of a group."""
        async with self.db.execute("""
            SELECT source FROM links 
            WHERE target = ? AND kind = 'member' AND tombstone = 0
        """, (group_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row['source'] for row in rows]
    
    # =========================================================================
    # METRICS
    # =========================================================================
    
    async def get_metrics(self) -> dict:
        """Get storage metrics."""
        metrics = {}
        
        async with self.db.execute("SELECT COUNT(*) FROM entities") as cursor:
            metrics['entity_count'] = (await cursor.fetchone())[0]
        
        async with self.db.execute("SELECT COUNT(*) FROM content") as cursor:
            metrics['content_count'] = (await cursor.fetchone())[0]
        
        async with self.db.execute("SELECT COUNT(*) FROM links WHERE tombstone = 0") as cursor:
            metrics['link_count'] = (await cursor.fetchone())[0]
        
        async with self.db.execute("SELECT seq FROM sequence WHERE id = 1") as cursor:
            metrics['sequence'] = (await cursor.fetchone())[0]
        
        # Link breakdown
        async with self.db.execute("""
            SELECT kind, COUNT(*) as count FROM links 
            WHERE tombstone = 0 GROUP BY kind
        """) as cursor:
            rows = await cursor.fetchall()
            metrics['link_breakdown'] = {row['kind']: row['count'] for row in rows}
        
        return metrics
