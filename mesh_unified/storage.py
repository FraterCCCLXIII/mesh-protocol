"""
MESH Protocol - Storage Layer
SQLite with WAL mode, optimized for performance
"""

import aiosqlite
from datetime import datetime
from typing import Optional, List

from .primitives import Entity, Content, Link, EntityKind, ContentKind, LinkKind, AccessType
from .integrity import LogEvent, OpType, ObjectType
from .attestations import Attestation, AttestationType
from .views import ViewDefinition, ViewResult, Source, Filter, ReducerType, SourceKind


class Storage:
    """SQLite storage with WAL mode for high performance."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None
    
    async def initialize(self):
        """Initialize database with optimized settings."""
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        
        # Enable WAL mode for performance (key optimization!)
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA synchronous=NORMAL")
        await self.db.execute("PRAGMA cache_size=-64000")  # 64MB cache
        await self.db.execute("PRAGMA temp_store=MEMORY")
        
        # Create tables
        await self.db.executescript("""
            -- Social Layer
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
            
            -- Integrity Layer
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
            
            -- Moderation Layer
            CREATE TABLE IF NOT EXISTS attestations (
                id TEXT PRIMARY KEY,
                issuer TEXT NOT NULL,
                subject TEXT NOT NULL,
                type TEXT NOT NULL,
                claim TEXT NOT NULL,
                evidence TEXT,
                ts TEXT NOT NULL,
                expires_at TEXT,
                revoked INTEGER NOT NULL DEFAULT 0,
                sig BLOB NOT NULL
            );
            
            -- View Layer
            CREATE TABLE IF NOT EXISTS view_definitions (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                version INTEGER NOT NULL,
                sources TEXT NOT NULL,
                filters TEXT NOT NULL,
                reducer TEXT NOT NULL,
                params TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sig BLOB NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS view_cache (
                view_id TEXT NOT NULL,
                view_version INTEGER NOT NULL,
                boundary_hash TEXT NOT NULL,
                result_hash TEXT NOT NULL,
                event_ids TEXT NOT NULL,
                computed_at TEXT NOT NULL,
                expires_at TEXT,
                PRIMARY KEY (view_id, view_version, boundary_hash)
            );
            
            -- Indexes for performance
            CREATE INDEX IF NOT EXISTS idx_entities_handle ON entities(handle);
            CREATE INDEX IF NOT EXISTS idx_content_author ON content(author);
            CREATE INDEX IF NOT EXISTS idx_content_reply_to ON content(reply_to);
            CREATE INDEX IF NOT EXISTS idx_links_source ON links(source);
            CREATE INDEX IF NOT EXISTS idx_links_target ON links(target);
            CREATE INDEX IF NOT EXISTS idx_links_kind ON links(kind);
            CREATE INDEX IF NOT EXISTS idx_log_actor ON log_events(actor);
            CREATE INDEX IF NOT EXISTS idx_log_actor_seq ON log_events(actor, seq);
            CREATE INDEX IF NOT EXISTS idx_attestations_subject ON attestations(subject);
            CREATE INDEX IF NOT EXISTS idx_attestations_issuer ON attestations(issuer);
        """)
        await self.db.commit()
    
    async def close(self):
        if self.db:
            await self.db.close()
    
    # =========================================================================
    # Social Layer Operations
    # =========================================================================
    
    async def create_entity(self, entity: Entity):
        """Create a new entity."""
        import json
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
        """Get entity by ID."""
        import json
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
            profile=json.loads(row['profile']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            sig=row['sig'],
        )
    
    async def create_content(self, content: Content):
        """Create new content."""
        import json
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
        """Get content by ID."""
        import json
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
        """Create a new link."""
        import json
        await self.db.execute("""
            INSERT INTO links (id, source, target, kind, data, created_at, tombstone, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            link.id, link.source, link.target, link.kind.value,
            json.dumps(link.data), link.created_at.isoformat(),
            1 if link.tombstone else 0, link.sig
        ))
        await self.db.commit()
    
    async def get_following(self, entity_id: str) -> List[str]:
        """Get list of entity IDs that entity_id follows."""
        cursor = await self.db.execute("""
            SELECT target FROM links 
            WHERE source = ? AND kind = 'follow' AND tombstone = 0
        """, (entity_id,))
        rows = await cursor.fetchall()
        return [row['target'] for row in rows]
    
    async def get_followers(self, entity_id: str) -> List[str]:
        """Get list of entity IDs that follow entity_id."""
        cursor = await self.db.execute("""
            SELECT source FROM links 
            WHERE target = ? AND kind = 'follow' AND tombstone = 0
        """, (entity_id,))
        rows = await cursor.fetchall()
        return [row['source'] for row in rows]
    
    # =========================================================================
    # Integrity Layer Operations
    # =========================================================================
    
    async def append_log(self, event: LogEvent):
        """Append event to log with prev chain validation."""
        import json
        
        # Get current head
        cursor = await self.db.execute(
            "SELECT head_id, head_seq FROM log_heads WHERE actor = ?",
            (event.actor,)
        )
        row = await cursor.fetchone()
        
        if row:
            # Not first event - must reference head
            if event.prev != row['head_id']:
                raise ValueError(f"Invalid prev: expected {row['head_id']}, got {event.prev}")
            if event.seq != row['head_seq'] + 1:
                raise ValueError(f"Invalid seq: expected {row['head_seq'] + 1}, got {event.seq}")
        else:
            # First event - must have null prev and seq=1
            if event.prev is not None:
                raise ValueError("First event must have prev=None")
            if event.seq != 1:
                raise ValueError("First event must have seq=1")
        
        # Insert event
        await self.db.execute("""
            INSERT INTO log_events (id, actor, seq, prev, op, object_type, object_id, payload, ts, sig, commitment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.id, event.actor, event.seq, event.prev,
            event.op.value, event.object_type.value, event.object_id,
            json.dumps(event.payload), event.ts.isoformat(),
            event.sig, event.commitment
        ))
        
        # Update head
        await self.db.execute("""
            INSERT OR REPLACE INTO log_heads (actor, head_id, head_seq)
            VALUES (?, ?, ?)
        """, (event.actor, event.id, event.seq))
        
        await self.db.commit()
    
    async def get_log_head(self, actor: str) -> Optional[str]:
        """Get the head event ID for an actor."""
        cursor = await self.db.execute(
            "SELECT head_id FROM log_heads WHERE actor = ?",
            (actor,)
        )
        row = await cursor.fetchone()
        return row['head_id'] if row else None
    
    async def get_log_seq(self, actor: str) -> int:
        """Get the current sequence number for an actor."""
        cursor = await self.db.execute(
            "SELECT head_seq FROM log_heads WHERE actor = ?",
            (actor,)
        )
        row = await cursor.fetchone()
        return row['head_seq'] if row else 0
    
    async def get_events_by_actor(self, actor: str, since_seq: int = 0) -> List[LogEvent]:
        """Get all events for an actor since a sequence number."""
        import json
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
    
    async def get_events_batch(self, event_ids: List[str]) -> List[LogEvent]:
        """Get multiple events by ID."""
        import json
        if not event_ids:
            return []
        placeholders = ','.join('?' * len(event_ids))
        cursor = await self.db.execute(f"""
            SELECT * FROM log_events WHERE id IN ({placeholders})
        """, event_ids)
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
    
    # =========================================================================
    # Moderation Layer Operations
    # =========================================================================
    
    async def put_attestation(self, att: Attestation):
        """Store an attestation."""
        import json
        await self.db.execute("""
            INSERT OR REPLACE INTO attestations 
            (id, issuer, subject, type, claim, evidence, ts, expires_at, revoked, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            att.id, att.issuer, att.subject, att.type.value,
            json.dumps(att.claim),
            json.dumps(att.evidence) if att.evidence else None,
            att.ts.isoformat(),
            att.expires_at.isoformat() if att.expires_at else None,
            1 if att.revoked else 0,
            att.sig
        ))
        await self.db.commit()
    
    async def get_attestations_for(self, subject: str) -> List[Attestation]:
        """Get all attestations about a subject."""
        import json
        cursor = await self.db.execute(
            "SELECT * FROM attestations WHERE subject = ?",
            (subject,)
        )
        rows = await cursor.fetchall()
        return [
            Attestation(
                id=row['id'],
                issuer=row['issuer'],
                subject=row['subject'],
                type=AttestationType(row['type']),
                claim=json.loads(row['claim']),
                evidence=json.loads(row['evidence']) if row['evidence'] else None,
                ts=datetime.fromisoformat(row['ts']),
                expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
                revoked=bool(row['revoked']),
                sig=row['sig'],
            )
            for row in rows
        ]
    
    async def get_attestations_by(self, issuer: str) -> List[Attestation]:
        """Get all attestations made by an issuer."""
        import json
        cursor = await self.db.execute(
            "SELECT * FROM attestations WHERE issuer = ?",
            (issuer,)
        )
        rows = await cursor.fetchall()
        return [
            Attestation(
                id=row['id'],
                issuer=row['issuer'],
                subject=row['subject'],
                type=AttestationType(row['type']),
                claim=json.loads(row['claim']),
                evidence=json.loads(row['evidence']) if row['evidence'] else None,
                ts=datetime.fromisoformat(row['ts']),
                expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
                revoked=bool(row['revoked']),
                sig=row['sig'],
            )
            for row in rows
        ]
    
    # =========================================================================
    # View Layer Operations
    # =========================================================================
    
    async def put_view_definition(self, view: ViewDefinition):
        """Store a view definition with version check."""
        import json
        
        # Check version increment
        cursor = await self.db.execute(
            "SELECT version FROM view_definitions WHERE id = ?",
            (view.id,)
        )
        row = await cursor.fetchone()
        if row and row['version'] >= view.version:
            raise ValueError(f"Version must increment: current={row['version']}, new={view.version}")
        
        await self.db.execute("""
            INSERT OR REPLACE INTO view_definitions
            (id, owner, version, sources, filters, reducer, params, created_at, updated_at, sig)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            view.id, view.owner, view.version,
            json.dumps([s.to_dict() for s in view.sources]),
            json.dumps([f.to_dict() for f in view.filters]),
            view.reducer.value,
            json.dumps(view.params),
            view.created_at.isoformat(),
            view.updated_at.isoformat(),
            view.sig
        ))
        await self.db.commit()
    
    async def get_view_definition(self, view_id: str) -> Optional[ViewDefinition]:
        """Get a view definition by ID."""
        import json
        cursor = await self.db.execute(
            "SELECT * FROM view_definitions WHERE id = ?",
            (view_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        
        sources_data = json.loads(row['sources'])
        filters_data = json.loads(row['filters'])
        
        return ViewDefinition(
            id=row['id'],
            owner=row['owner'],
            version=row['version'],
            sources=[Source(kind=SourceKind(s['kind']), actor_id=s.get('actor_id')) for s in sources_data],
            filters=[Filter(**f) for f in filters_data],
            reducer=ReducerType(row['reducer']),
            params=json.loads(row['params']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            sig=row['sig'],
        )
    
    # =========================================================================
    # Metrics
    # =========================================================================
    
    async def get_metrics(self) -> dict:
        """Get storage metrics."""
        metrics = {}
        for table in ['entities', 'content', 'links', 'log_events', 'attestations', 'view_definitions']:
            cursor = await self.db.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            row = await cursor.fetchone()
            metrics[f"{table}_count"] = row['cnt']
        return metrics
