"""
MESH Protocol - Social Layer
Core primitives: Entity, Content, Link (from HOLON v4)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any


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


@dataclass
class Entity:
    """Identity primitive - users, groups, bots."""
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
    """Content primitive - posts, replies, media."""
    id: str
    author: str  # entity_id
    kind: ContentKind
    body: dict
    reply_to: Optional[str]  # content_id
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
    """Relationship primitive - follows, likes, memberships."""
    id: str
    source: str  # entity_id
    target: str  # entity_id or content_id
    kind: LinkKind
    data: dict
    created_at: datetime
    tombstone: bool  # Soft delete
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
