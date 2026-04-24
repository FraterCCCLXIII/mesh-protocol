"""
HOLON Protocol Simulator - Core Implementation

Implements the Object Layer, Structure Layer, and View Layer
in-memory for simulation and testing.
"""

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable


# =============================================================================
# OBJECT LAYER
# =============================================================================

class EntityKind(Enum):
    USER = "user"
    ORG = "org"
    GROUP = "group"


class ContentKind(Enum):
    POST = "post"
    MEDIA = "media"
    STRUCTURED = "structured"


class LinkKind(Enum):
    RELATIONSHIP = "relationship"
    INTERACTION = "interaction"
    CREDENTIAL = "credential"


@dataclass
class Entity:
    id: str
    kind: EntityKind
    version: int = 1
    created: datetime = field(default_factory=datetime.utcnow)
    updated: datetime = field(default_factory=datetime.utcnow)
    data: dict = field(default_factory=dict)
    parent: str | None = None  # For Structure Layer

    def to_dict(self) -> dict:
        return {
            "type": "entity",
            "id": self.id,
            "kind": self.kind.value,
            "version": self.version,
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "data": self.data,
            "parent": self.parent,
        }

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))


@dataclass
class Content:
    id: str
    kind: ContentKind
    author: str
    created: datetime = field(default_factory=datetime.utcnow)
    context: str | None = None
    reply_to: str | None = None
    thread_root: str | None = None
    data: dict = field(default_factory=dict)
    access_type: str = "public"

    def to_dict(self) -> dict:
        return {
            "type": "content",
            "id": self.id,
            "kind": self.kind.value,
            "author": self.author,
            "created": self.created.isoformat(),
            "context": self.context,
            "reply_to": self.reply_to,
            "thread_root": self.thread_root,
            "data": self.data,
            "access": {"type": self.access_type},
        }

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))


@dataclass
class Link:
    id: str
    kind: LinkKind
    source: str
    target: str
    created: datetime = field(default_factory=datetime.utcnow)
    data: dict = field(default_factory=dict)
    tombstone: bool = False

    def to_dict(self) -> dict:
        return {
            "type": "link",
            "id": self.id,
            "kind": self.kind.value,
            "source": self.source,
            "target": self.target,
            "created": self.created.isoformat(),
            "data": self.data,
            "tombstone": self.tombstone,
        }

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))


# =============================================================================
# VIEW LAYER
# =============================================================================

@dataclass
class View:
    id: str
    author: str
    name: str
    source: dict
    filters: list = field(default_factory=list)
    sort: list = field(default_factory=list)
    limit: int = 100

    def to_dict(self) -> dict:
        return {
            "type": "view",
            "id": self.id,
            "author": self.author,
            "name": self.name,
            "source": self.source,
            "filter": self.filters,
            "sort": self.sort,
            "limit": self.limit,
        }


@dataclass
class ViewExecution:
    view_id: str
    boundary_timestamp: datetime
    results: list[str]
    result_hash: str
    computation_time_ms: float


# =============================================================================
# STORAGE
# =============================================================================

class Storage:
    """In-memory storage for all protocol objects."""

    def __init__(self):
        self.entities: dict[str, Entity] = {}
        self.content: dict[str, Content] = {}
        self.links: dict[str, Link] = {}
        self.views: dict[str, View] = {}

        # Indexes for efficient queries
        self._links_by_source: dict[str, list[str]] = {}
        self._links_by_target: dict[str, list[str]] = {}
        self._content_by_author: dict[str, list[str]] = {}
        self._content_by_context: dict[str, list[str]] = {}
        self._children_by_parent: dict[str, list[str]] = {}

        # Sequence counter (simulates relay)
        self._seq = 0

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    # Entity operations
    def create_entity(self, entity: Entity) -> int:
        self.entities[entity.id] = entity
        if entity.parent:
            if entity.parent not in self._children_by_parent:
                self._children_by_parent[entity.parent] = []
            self._children_by_parent[entity.parent].append(entity.id)
        return self.next_seq()

    def get_entity(self, entity_id: str) -> Entity | None:
        return self.entities.get(entity_id)

    def update_entity(self, entity_id: str, data: dict) -> int | None:
        entity = self.entities.get(entity_id)
        if entity:
            entity.data.update(data)
            entity.version += 1
            entity.updated = datetime.utcnow()
            return self.next_seq()
        return None

    # Content operations
    def create_content(self, content: Content) -> int:
        self.content[content.id] = content

        # Index by author
        if content.author not in self._content_by_author:
            self._content_by_author[content.author] = []
        self._content_by_author[content.author].append(content.id)

        # Index by context
        if content.context:
            if content.context not in self._content_by_context:
                self._content_by_context[content.context] = []
            self._content_by_context[content.context].append(content.id)

        return self.next_seq()

    def get_content(self, content_id: str) -> Content | None:
        return self.content.get(content_id)

    def get_content_by_author(self, author_id: str) -> list[Content]:
        ids = self._content_by_author.get(author_id, [])
        return [self.content[cid] for cid in ids if cid in self.content]

    def get_content_by_context(self, context_id: str) -> list[Content]:
        ids = self._content_by_context.get(context_id, [])
        return [self.content[cid] for cid in ids if cid in self.content]

    # Link operations
    def create_link(self, link: Link) -> int:
        self.links[link.id] = link

        # Index by source
        if link.source not in self._links_by_source:
            self._links_by_source[link.source] = []
        self._links_by_source[link.source].append(link.id)

        # Index by target
        if link.target not in self._links_by_target:
            self._links_by_target[link.target] = []
        self._links_by_target[link.target].append(link.id)

        return self.next_seq()

    def get_link(self, link_id: str) -> Link | None:
        return self.links.get(link_id)

    def get_links_by_source(self, source_id: str, kind: LinkKind | None = None, subkind: str | None = None) -> list[Link]:
        ids = self._links_by_source.get(source_id, [])
        links = [self.links[lid] for lid in ids if lid in self.links]
        if kind:
            links = [l for l in links if l.kind == kind]
        if subkind:
            links = [l for l in links if l.data.get("subkind") == subkind]
        return [l for l in links if not l.tombstone]

    def get_links_by_target(self, target_id: str, kind: LinkKind | None = None, subkind: str | None = None) -> list[Link]:
        ids = self._links_by_target.get(target_id, [])
        links = [self.links[lid] for lid in ids if lid in self.links]
        if kind:
            links = [l for l in links if l.kind == kind]
        if subkind:
            links = [l for l in links if l.data.get("subkind") == subkind]
        return [l for l in links if not l.tombstone]

    # View operations
    def create_view(self, view: View) -> int:
        self.views[view.id] = view
        return self.next_seq()

    def get_view(self, view_id: str) -> View | None:
        return self.views.get(view_id)

    # Structure Layer: Context stack
    def get_context_stack(self, entity_id: str, max_depth: int = 5) -> list[str]:
        stack = [entity_id]
        current = entity_id
        for _ in range(max_depth):
            entity = self.entities.get(current)
            if not entity or not entity.parent:
                break
            stack.append(entity.parent)
            current = entity.parent
        return stack

    def get_children(self, entity_id: str) -> list[str]:
        return self._children_by_parent.get(entity_id, [])

    def get_descendants(self, entity_id: str, max_depth: int = 5) -> list[str]:
        """Get all descendants up to max_depth."""
        descendants = []
        to_visit = [(entity_id, 0)]
        while to_visit:
            current, depth = to_visit.pop(0)
            if depth > 0:  # Don't include the root
                descendants.append(current)
            if depth < max_depth:
                for child in self.get_children(current):
                    to_visit.append((child, depth + 1))
        return descendants

    # Metrics
    def get_metrics(self) -> dict:
        total_size = 0
        total_size += sum(e.size_bytes() for e in self.entities.values())
        total_size += sum(c.size_bytes() for c in self.content.values())
        total_size += sum(l.size_bytes() for l in self.links.values())

        # Link breakdown by subkind
        link_breakdown = {}
        for link in self.links.values():
            subkind = link.data.get("subkind", "unknown")
            link_breakdown[subkind] = link_breakdown.get(subkind, 0) + 1

        return {
            "entity_count": len(self.entities),
            "content_count": len(self.content),
            "link_count": len(self.links),
            "view_count": len(self.views),
            "total_objects": len(self.entities) + len(self.content) + len(self.links),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "sequence": self._seq,
            "link_breakdown": link_breakdown,
        }


# =============================================================================
# VIEW EXECUTION ENGINE
# =============================================================================

class ViewEngine:
    """Executes views against storage."""

    def __init__(self, storage: Storage):
        self.storage = storage

    def execute(self, view: View, boundary_timestamp: datetime | None = None) -> ViewExecution:
        start_time = time.time()
        boundary_timestamp = boundary_timestamp or datetime.utcnow()

        # 1. Get source content
        candidates = self._get_source_content(view.source)

        # 2. Apply filters
        filtered = self._apply_filters(candidates, view.filters, boundary_timestamp)

        # 3. Sort
        sorted_results = self._apply_sort(filtered, view.sort)

        # 4. Limit
        limited = sorted_results[:view.limit]

        # 5. Get IDs
        result_ids = [c.id for c in limited]

        # 6. Compute hash
        result_hash = self._compute_hash(result_ids)

        computation_time = (time.time() - start_time) * 1000

        return ViewExecution(
            view_id=view.id,
            boundary_timestamp=boundary_timestamp,
            results=result_ids,
            result_hash=result_hash,
            computation_time_ms=computation_time,
        )

    def _get_source_content(self, source: dict) -> list[Content]:
        source_type = source.get("type")

        if source_type == "context":
            holon = source.get("holon")
            return self.storage.get_content_by_context(holon)

        elif source_type == "context_tree":
            root = source.get("root")
            depth = source.get("depth", 2)
            content = list(self.storage.get_content_by_context(root))
            for descendant in self.storage.get_descendants(root, depth):
                content.extend(self.storage.get_content_by_context(descendant))
            return content

        elif source_type == "follows":
            entity = source.get("of")
            follows = self.storage.get_links_by_source(entity, LinkKind.RELATIONSHIP, "follow")
            content = []
            for follow in follows:
                content.extend(self.storage.get_content_by_author(follow.target))
            return content

        elif source_type == "union":
            content = []
            for sub_source in source.get("sources", []):
                content.extend(self._get_source_content(sub_source))
            return content

        return []

    def _apply_filters(self, content: list[Content], filters: list, boundary_timestamp: datetime) -> list[Content]:
        result = content
        for f in filters:
            result = [c for c in result if self._matches_filter(c, f, boundary_timestamp)]
        return result

    def _matches_filter(self, content: Content, f: dict, boundary_timestamp: datetime) -> bool:
        field = f.get("field")
        op = f.get("op")
        value = f.get("value")

        # Get field value
        if field == "kind":
            field_value = content.kind.value
        elif field == "author":
            field_value = content.author
        elif field == "created":
            field_value = content.created
        elif field == "context":
            field_value = content.context
        elif field == "reaction_count":
            # Count reactions (links targeting this content)
            reactions = self.storage.get_links_by_target(content.id, LinkKind.INTERACTION, "react")
            field_value = len(reactions)
        elif field == "reply_count":
            # Count replies (content with reply_to = this)
            field_value = len([c for c in self.storage.content.values() if c.reply_to == content.id])
        elif field == "labels":
            labels = self.storage.get_links_by_target(content.id, LinkKind.INTERACTION, "label")
            field_value = [l.data.get("labels", []) for l in labels]
            field_value = [label for sublist in field_value for label in sublist]  # Flatten
        else:
            field_value = content.data.get(field)

        # Handle relative time
        if isinstance(value, dict) and "relative" in value:
            relative = value["relative"]
            if relative.endswith("d"):
                delta = timedelta(days=int(relative[:-1].replace("-", "")))
            elif relative.endswith("h"):
                delta = timedelta(hours=int(relative[:-1].replace("-", "")))
            elif relative.endswith("m"):
                delta = timedelta(minutes=int(relative[:-1].replace("-", "")))
            else:
                delta = timedelta()
            value = boundary_timestamp - delta

        # Apply operator
        if op == "eq":
            return field_value == value
        elif op == "ne":
            return field_value != value
        elif op == "gt":
            return field_value > value
        elif op == "lt":
            return field_value < value
        elif op == "in":
            return field_value in value
        elif op == "contains":
            return value in field_value if field_value else False
        elif op == "excludes":
            if isinstance(field_value, list):
                return not any(v in field_value for v in value)
            return value not in field_value if field_value else True

        return True

    def _apply_sort(self, content: list[Content], sort: list) -> list[Content]:
        if not sort:
            return content

        def sort_key(c: Content):
            keys = []
            for s in sort:
                field = s.get("field")
                order = s.get("order", "asc")

                if field == "created":
                    val = c.created
                elif field == "reaction_count":
                    reactions = self.storage.get_links_by_target(c.id, LinkKind.INTERACTION, "react")
                    val = len(reactions)
                elif field == "reply_count":
                    val = len([x for x in self.storage.content.values() if x.reply_to == c.id])
                elif field == "id":
                    val = c.id
                else:
                    val = c.data.get(field, "")

                # For desc, negate numeric or reverse string
                if order == "desc":
                    if isinstance(val, (int, float)):
                        val = -val
                    elif isinstance(val, datetime):
                        val = datetime.max - val

                keys.append(val)
            return tuple(keys)

        return sorted(content, key=sort_key)

    def _compute_hash(self, result_ids: list[str]) -> str:
        canonical = json.dumps(result_ids, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def verify(self, execution: ViewExecution) -> bool:
        """Verify a view execution by recomputing."""
        view = self.storage.get_view(execution.view_id)
        if not view:
            return False

        recomputed = self.execute(view, execution.boundary_timestamp)
        return recomputed.result_hash == execution.result_hash


# =============================================================================
# ID GENERATORS
# =============================================================================

def generate_entity_id(name: str) -> str:
    return f"ent:{name.lower().replace(' ', '-')}"


def generate_content_id(author: str, kind: str) -> str:
    return f"cnt:{uuid.uuid4().hex[:12]}"


def generate_link_id() -> str:
    return f"lnk:{uuid.uuid4().hex[:12]}"


def generate_view_id(name: str) -> str:
    return f"view:{name.lower().replace(' ', '-')}"
