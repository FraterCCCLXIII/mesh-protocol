"""
HOLON Protocol v4.0 Simulator - Core Implementation

Implements the two-layer architecture:
- Data Layer: Entity, Content, Link
- Algorithm Layer: Views, Moderation, Reputation, Discovery

Based on HOLON_v4.0_DRAFT.md
"""

import hashlib
import json
import math
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable


# =============================================================================
# DATA LAYER
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
    COURSE = "course"


class LinkKind(Enum):
    FOLLOW = "follow"
    REACT = "react"
    SUBSCRIBE = "subscribe"
    MEMBER = "member"
    MODERATE = "moderate"
    LABEL = "label"
    DELEGATE = "delegate"
    VERIFY = "verify"
    ROTATE = "rotate"
    TIP = "tip"


class AccessType(Enum):
    PUBLIC = "public"
    FOLLOWERS = "followers"
    GROUP = "group"
    PRIVATE = "private"
    PAID = "paid"


@dataclass
class Entity:
    """An identity that can sign things."""
    id: str
    kind: EntityKind
    handle: str | None = None
    created: datetime = field(default_factory=lambda: datetime.now())
    profile: dict = field(default_factory=dict)
    parent: str | None = None  # For group nesting
    governance: dict | None = None  # For groups
    discoverable: bool = True
    keys: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": "entity",
            "id": self.id,
            "kind": self.kind.value,
            "handle": self.handle,
            "created": self.created.isoformat(),
            "profile": self.profile,
            "parent": self.parent,
            "governance": self.governance,
            "discoverable": self.discoverable,
        }

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))


@dataclass
class Content:
    """Something someone published."""
    id: str
    kind: ContentKind
    author: str
    created: datetime = field(default_factory=lambda: datetime.now())
    context: str | None = None
    body: dict = field(default_factory=dict)
    reply_to: str | None = None
    thread_root: str | None = None
    access: AccessType = AccessType.PUBLIC
    price: int | None = None  # For paid content (sats)

    def to_dict(self) -> dict:
        return {
            "type": "content",
            "id": self.id,
            "kind": self.kind.value,
            "author": self.author,
            "created": self.created.isoformat(),
            "context": self.context,
            "body": self.body,
            "reply_to": self.reply_to,
            "thread_root": self.thread_root,
            "access": self.access.value,
            "price": self.price,
        }

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_dict()))


@dataclass
class Link:
    """A directed relationship between two things."""
    id: str
    kind: LinkKind
    source: str
    target: str
    created: datetime = field(default_factory=lambda: datetime.now())
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
# ALGORITHM LAYER - VIEWS
# =============================================================================

@dataclass
class View:
    """A transparent, verifiable algorithm for content ranking."""
    id: str
    author: str
    name: str
    source: dict  # What content to consider
    filter: list = field(default_factory=list)  # Filter conditions
    rank: dict | None = None  # Ranking formula
    limit: int = 50
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "type": "view",
            "id": self.id,
            "author": self.author,
            "name": self.name,
            "source": self.source,
            "filter": self.filter,
            "rank": self.rank,
            "limit": self.limit,
            "description": self.description,
        }


@dataclass
class ViewBoundary:
    """A snapshot of view execution at a point in time."""
    view_id: str
    timestamp: datetime
    input_hash: str
    result_ids: list[str]
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

        # Indexes
        self._handles: dict[str, str] = {}  # handle -> entity_id
        self._links_by_source: dict[str, list[str]] = {}
        self._links_by_target: dict[str, list[str]] = {}
        self._links_by_kind: dict[LinkKind, list[str]] = {}
        self._content_by_author: dict[str, list[str]] = {}
        self._content_by_context: dict[str, list[str]] = {}
        self._children_by_parent: dict[str, list[str]] = {}
        self._verifications: dict[str, list[str]] = {}  # entity_id -> verification link ids

        # Sequence counter
        self._seq = 0

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    # Entity operations
    def create_entity(self, entity: Entity) -> int:
        self.entities[entity.id] = entity
        if entity.handle:
            self._handles[entity.handle.lower()] = entity.id
        if entity.parent:
            if entity.parent not in self._children_by_parent:
                self._children_by_parent[entity.parent] = []
            self._children_by_parent[entity.parent].append(entity.id)
        return self.next_seq()

    def get_entity(self, entity_id: str) -> Entity | None:
        return self.entities.get(entity_id)

    def resolve_handle(self, handle: str) -> str | None:
        """Resolve a handle to an entity ID."""
        return self._handles.get(handle.lower().lstrip("@"))

    def search_entities(self, query: str, limit: int = 20) -> list[Entity]:
        """Search entities by name/bio."""
        query_lower = query.lower()
        results = []
        for entity in self.entities.values():
            if not entity.discoverable:
                continue
            name = entity.profile.get("name", "").lower()
            bio = entity.profile.get("bio", "").lower()
            if query_lower in name or query_lower in bio:
                results.append(entity)
            if len(results) >= limit:
                break
        return results

    # Content operations
    def create_content(self, content: Content) -> int:
        self.content[content.id] = content

        if content.author not in self._content_by_author:
            self._content_by_author[content.author] = []
        self._content_by_author[content.author].append(content.id)

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

    def search_content(self, query: str, limit: int = 20) -> list[Content]:
        """Search content by text."""
        query_lower = query.lower()
        results = []
        for content in self.content.values():
            if content.access != AccessType.PUBLIC:
                continue
            text = content.body.get("text", "").lower()
            title = content.body.get("title", "").lower()
            if query_lower in text or query_lower in title:
                results.append(content)
            if len(results) >= limit:
                break
        return results

    # Link operations
    def create_link(self, link: Link) -> int:
        self.links[link.id] = link

        if link.source not in self._links_by_source:
            self._links_by_source[link.source] = []
        self._links_by_source[link.source].append(link.id)

        if link.target not in self._links_by_target:
            self._links_by_target[link.target] = []
        self._links_by_target[link.target].append(link.id)

        if link.kind not in self._links_by_kind:
            self._links_by_kind[link.kind] = []
        self._links_by_kind[link.kind].append(link.id)

        # Track verifications
        if link.kind == LinkKind.VERIFY:
            if link.source not in self._verifications:
                self._verifications[link.source] = []
            self._verifications[link.source].append(link.id)

        return self.next_seq()

    def get_links_by_source(self, source_id: str, kind: LinkKind | None = None) -> list[Link]:
        ids = self._links_by_source.get(source_id, [])
        links = [self.links[lid] for lid in ids if lid in self.links]
        if kind:
            links = [l for l in links if l.kind == kind]
        return [l for l in links if not l.tombstone]

    def get_links_by_target(self, target_id: str, kind: LinkKind | None = None) -> list[Link]:
        ids = self._links_by_target.get(target_id, [])
        links = [self.links[lid] for lid in ids if lid in self.links]
        if kind:
            links = [l for l in links if l.kind == kind]
        return [l for l in links if not l.tombstone]

    def get_followers(self, entity_id: str) -> list[str]:
        """Get entities that follow this entity."""
        follows = self.get_links_by_target(entity_id, LinkKind.FOLLOW)
        return [f.source for f in follows]

    def get_following(self, entity_id: str) -> list[str]:
        """Get entities this entity follows."""
        follows = self.get_links_by_source(entity_id, LinkKind.FOLLOW)
        return [f.target for f in follows]

    def get_members(self, group_id: str) -> list[str]:
        """Get members of a group."""
        memberships = self.get_links_by_target(group_id, LinkKind.MEMBER)
        return [m.source for m in memberships]

    def get_verifications(self, entity_id: str) -> list[Link]:
        """Get verification links for an entity."""
        ids = self._verifications.get(entity_id, [])
        return [self.links[lid] for lid in ids if lid in self.links]

    # View operations
    def create_view(self, view: View) -> int:
        self.views[view.id] = view
        return self.next_seq()

    def get_view(self, view_id: str) -> View | None:
        return self.views.get(view_id)

    # Graph traversal
    def get_children(self, entity_id: str) -> list[str]:
        return self._children_by_parent.get(entity_id, [])

    def get_descendants(self, entity_id: str, max_depth: int = 5) -> list[str]:
        descendants = []
        to_visit = [(entity_id, 0)]
        while to_visit:
            current, depth = to_visit.pop(0)
            if depth > 0:
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

        link_breakdown = {}
        for link in self.links.values():
            kind = link.kind.value
            link_breakdown[kind] = link_breakdown.get(kind, 0) + 1

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
            "handle_count": len(self._handles),
        }


# =============================================================================
# ALGORITHM LAYER - VIEW ENGINE
# =============================================================================

class ViewEngine:
    """Executes views with transparent ranking formulas."""

    def __init__(self, storage: Storage):
        self.storage = storage

    def execute(self, view: View, boundary_timestamp: datetime | None = None) -> ViewBoundary:
        start_time = time.time()
        boundary_timestamp = boundary_timestamp or datetime.now()

        # 1. Get source content
        candidates = self._get_source_content(view.source)

        # 2. Apply filters
        filtered = self._apply_filters(candidates, view.filter, boundary_timestamp)

        # 3. Compute input hash
        input_ids = sorted([c.id for c in filtered])
        input_hash = self._compute_hash(input_ids)

        # 4. Rank
        if view.rank:
            ranked = self._apply_ranking(filtered, view.rank)
        else:
            ranked = sorted(filtered, key=lambda c: c.created, reverse=True)

        # 5. Limit
        limited = ranked[:view.limit]

        # 6. Get result IDs and hash
        result_ids = [c.id for c in limited]
        result_hash = self._compute_hash(result_ids)

        computation_time = (time.time() - start_time) * 1000

        return ViewBoundary(
            view_id=view.id,
            timestamp=boundary_timestamp,
            input_hash=input_hash,
            result_ids=result_ids,
            result_hash=result_hash,
            computation_time_ms=computation_time,
        )

    def _get_source_content(self, source: dict) -> list[Content]:
        source_type = source.get("type", source.get("context"))

        if "context" in source:
            context_id = source["context"]
            content = list(self.storage.get_content_by_context(context_id))
            if source.get("include_children"):
                for child in self.storage.get_descendants(context_id):
                    content.extend(self.storage.get_content_by_context(child))
            return content

        elif source_type == "follows":
            entity_id = source.get("of")
            following = self.storage.get_following(entity_id)
            content = []
            for followed in following:
                content.extend(self.storage.get_content_by_author(followed))
            return content

        elif source_type == "author":
            author_id = source.get("author")
            return self.storage.get_content_by_author(author_id)

        elif source_type == "all":
            return list(self.storage.content.values())

        elif source_type == "union":
            content = []
            for sub_source in source.get("sources", []):
                content.extend(self._get_source_content(sub_source))
            return content

        elif source_type == "trending_content":
            # Get content with most reactions recently
            return sorted(
                self.storage.content.values(),
                key=lambda c: len(self.storage.get_links_by_target(c.id, LinkKind.REACT)),
                reverse=True
            )[:100]

        return []

    def _apply_filters(self, content: list[Content], filters: list, boundary_timestamp: datetime) -> list[Content]:
        result = content
        for f in filters:
            result = [c for c in result if self._matches_filter(c, f, boundary_timestamp)]
        return result

    def _matches_filter(self, content: Content, f: dict, boundary_timestamp: datetime) -> bool:
        field_name = f.get("field")
        op = f.get("op")
        value = f.get("value")

        # Get field value
        if field_name == "kind":
            field_value = content.kind.value
        elif field_name == "author":
            field_value = content.author
        elif field_name == "created":
            field_value = content.created
        elif field_name == "context":
            field_value = content.context
        elif field_name == "access":
            field_value = content.access.value
        elif field_name == "reactions":
            field_value = len(self.storage.get_links_by_target(content.id, LinkKind.REACT))
        elif field_name == "replies":
            field_value = len([c for c in self.storage.content.values() if c.reply_to == content.id])
        elif field_name == "labels":
            label_links = self.storage.get_links_by_target(content.id, LinkKind.LABEL)
            field_value = []
            for ll in label_links:
                field_value.extend(ll.data.get("labels", []))
        else:
            field_value = content.body.get(field_name)

        # Handle relative time
        if isinstance(value, str) and value.startswith("-"):
            match = re.match(r"-(\d+)([dhm])", value)
            if match:
                num, unit = int(match.group(1)), match.group(2)
                if unit == "d":
                    delta = timedelta(days=num)
                elif unit == "h":
                    delta = timedelta(hours=num)
                else:
                    delta = timedelta(minutes=num)
                value = boundary_timestamp - delta

        # Apply operator
        if op == "eq":
            return field_value == value
        elif op == "ne":
            return field_value != value
        elif op == "gt":
            return field_value > value if field_value else False
        elif op == "lt":
            return field_value < value if field_value else False
        elif op == "in":
            return field_value in value
        elif op == "contains":
            if isinstance(field_value, str):
                return value.lower() in field_value.lower()
            elif isinstance(field_value, list):
                return value in field_value
            return False
        elif op == "excludes":
            if isinstance(field_value, list):
                return value not in field_value
            return True

        return True

    def _apply_ranking(self, content: list[Content], rank: dict) -> list[Content]:
        formula = rank.get("formula", "")
        weights = rank.get("weights", {})

        def compute_score(c: Content) -> float:
            # Build context for formula evaluation
            reactions = len(self.storage.get_links_by_target(c.id, LinkKind.REACT))
            replies = len([x for x in self.storage.content.values() if x.reply_to == c.id])
            age_hours = (datetime.now() - c.created).total_seconds() / 3600

            author = self.storage.get_entity(c.author)
            author_followers = len(self.storage.get_followers(c.author)) if author else 0

            # Simple formula evaluation
            ctx = {
                "reactions": reactions,
                "replies": replies,
                "age_hours": age_hours,
                "author_followers": author_followers,
                "has_media": 1 if c.body.get("media") else 0,
            }
            ctx.update(weights)

            try:
                # Safe eval with limited context
                score = self._eval_formula(formula, ctx)
                return score
            except:
                return 0

        return sorted(content, key=compute_score, reverse=True)

    def _eval_formula(self, formula: str, ctx: dict) -> float:
        """Safely evaluate a ranking formula."""
        # Replace function calls
        formula = re.sub(r'decay\((\w+),\s*([\d.]+)\)',
                        lambda m: f"({ctx.get(m.group(1), 0)} * (0.5 ** ({ctx.get('age_hours', 0)} / {m.group(2)})))",
                        formula)
        formula = re.sub(r'log\(([^)]+)\)',
                        lambda m: f"math.log({m.group(1)} + 1)",
                        formula)
        formula = re.sub(r'cap\(([^,]+),\s*(\d+)\)',
                        lambda m: f"min({m.group(1)}, {m.group(2)})",
                        formula)

        # Replace variable names
        for name, value in ctx.items():
            formula = re.sub(rf'\b{name}\b', str(value), formula)

        # Evaluate
        return eval(formula, {"math": math, "min": min, "max": max})

    def _compute_hash(self, ids: list[str]) -> str:
        canonical = json.dumps(ids, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def verify(self, boundary: ViewBoundary) -> bool:
        """Verify a view boundary by recomputing."""
        view = self.storage.get_view(boundary.view_id)
        if not view:
            return False
        recomputed = self.execute(view, boundary.timestamp)
        return recomputed.result_hash == boundary.result_hash


# =============================================================================
# ALGORITHM LAYER - REPUTATION
# =============================================================================

class ReputationEngine:
    """Computes reputation scores (client-side, not stored)."""

    def __init__(self, storage: Storage):
        self.storage = storage

    def compute(self, entity_id: str, context: str | None = None) -> float:
        """Compute reputation score for an entity."""
        entity = self.storage.get_entity(entity_id)
        if not entity:
            return 0.0

        # Account age (days)
        account_age_days = (datetime.now() - entity.created).days

        # Followers (capped)
        followers = len(self.storage.get_followers(entity_id))
        followers_capped = min(followers, 10000)

        # Average reactions per post
        content = self.storage.get_content_by_author(entity_id)
        if content:
            total_reactions = sum(
                len(self.storage.get_links_by_target(c.id, LinkKind.REACT))
                for c in content
            )
            avg_reactions = total_reactions / len(content)
        else:
            avg_reactions = 0

        # Vouch score (other reputable accounts vouching)
        # Simplified: count verified external identities
        verifications = len(self.storage.get_verifications(entity_id))

        # Spam rate (content labeled as spam)
        spam_labels = 0
        for c in content:
            labels = self.storage.get_links_by_target(c.id, LinkKind.LABEL)
            for l in labels:
                if "spam" in l.data.get("labels", []):
                    spam_labels += 1
        spam_rate = spam_labels / max(len(content), 1)

        # Formula from v4.0 spec
        reputation = (
            math.log(account_age_days + 1) * 0.2 +
            math.log(followers_capped + 1) * 0.3 +
            avg_reactions * 0.3 +
            verifications * 0.2 -
            spam_rate * 2
        )

        return max(0, reputation)


# =============================================================================
# ALGORITHM LAYER - DISCOVERY
# =============================================================================

class DiscoveryEngine:
    """Implements discovery mechanisms from v4.0 spec."""

    def __init__(self, storage: Storage, reputation: ReputationEngine):
        self.storage = storage
        self.reputation = reputation

    def resolve_handle(self, handle: str) -> Entity | None:
        """Resolve a handle to an entity."""
        entity_id = self.storage.resolve_handle(handle)
        if entity_id:
            return self.storage.get_entity(entity_id)
        return None

    def search(self, query: str, types: list[str] = None, limit: int = 20) -> list[dict]:
        """Search across entities and content."""
        types = types or ["entity", "content"]
        results = []

        if "entity" in types:
            for entity in self.storage.search_entities(query, limit):
                results.append({
                    "type": "entity",
                    "id": entity.id,
                    "data": entity.to_dict(),
                })

        if "content" in types:
            for content in self.storage.search_content(query, limit - len(results)):
                results.append({
                    "type": "content",
                    "id": content.id,
                    "data": content.to_dict(),
                })

        return results[:limit]

    def follows_of_follows(self, entity_id: str, limit: int = 20) -> list[str]:
        """Find entities followed by people you follow."""
        following = set(self.storage.get_following(entity_id))
        candidates: dict[str, int] = {}

        for followed in following:
            for second_degree in self.storage.get_following(followed):
                if second_degree != entity_id and second_degree not in following:
                    candidates[second_degree] = candidates.get(second_degree, 0) + 1

        # Sort by overlap count
        sorted_candidates = sorted(candidates.items(), key=lambda x: -x[1])
        return [c[0] for c in sorted_candidates[:limit]]

    def similar_followers(self, entity_id: str, limit: int = 20) -> list[str]:
        """Find entities with similar follower patterns."""
        my_following = set(self.storage.get_following(entity_id))
        candidates: dict[str, int] = {}

        for followed in my_following:
            for other_follower in self.storage.get_followers(followed):
                if other_follower != entity_id:
                    candidates[other_follower] = candidates.get(other_follower, 0) + 1

        sorted_candidates = sorted(candidates.items(), key=lambda x: -x[1])
        return [c[0] for c in sorted_candidates[:limit]]

    def mutuals(self, entity_id: str) -> list[str]:
        """Find mutual follows."""
        following = set(self.storage.get_following(entity_id))
        followers = set(self.storage.get_followers(entity_id))
        return list(following & followers)

    def active_in_context(self, context_id: str, period_days: int = 7, limit: int = 20) -> list[str]:
        """Find users active in a context."""
        cutoff = datetime.now() - timedelta(days=period_days)
        content = self.storage.get_content_by_context(context_id)
        recent = [c for c in content if c.created > cutoff]

        # Count posts per author
        author_counts: dict[str, int] = {}
        for c in recent:
            author_counts[c.author] = author_counts.get(c.author, 0) + 1

        sorted_authors = sorted(author_counts.items(), key=lambda x: -x[1])
        return [a[0] for a in sorted_authors[:limit]]

    def suggested_contexts(self, entity_id: str, limit: int = 10) -> list[str]:
        """Suggest groups based on who you follow."""
        following = self.storage.get_following(entity_id)
        my_groups = set(g.target for g in self.storage.get_links_by_source(entity_id, LinkKind.MEMBER))

        group_scores: dict[str, int] = {}
        for followed in following:
            for membership in self.storage.get_links_by_source(followed, LinkKind.MEMBER):
                group = membership.target
                if group not in my_groups:
                    group_scores[group] = group_scores.get(group, 0) + 1

        sorted_groups = sorted(group_scores.items(), key=lambda x: -x[1])
        return [g[0] for g in sorted_groups[:limit]]

    def rising_stars(self, limit: int = 20) -> list[str]:
        """Find new accounts gaining followers quickly."""
        cutoff = datetime.now() - timedelta(days=30)
        new_accounts = [
            e for e in self.storage.entities.values()
            if e.kind == EntityKind.USER and e.created > cutoff
        ]

        # Score by follower count relative to age
        def growth_score(e: Entity) -> float:
            followers = len(self.storage.get_followers(e.id))
            age_days = max(1, (datetime.now() - e.created).days)
            return followers / math.log(age_days + 1)

        sorted_accounts = sorted(new_accounts, key=growth_score, reverse=True)
        return [e.id for e in sorted_accounts[:limit]]


# =============================================================================
# ALGORITHM LAYER - MODERATION
# =============================================================================

class ModerationEngine:
    """Moderation as transparent data."""

    def __init__(self, storage: Storage):
        self.storage = storage

    def get_labels(self, content_id: str) -> list[dict]:
        """Get all labels on content."""
        label_links = self.storage.get_links_by_target(content_id, LinkKind.LABEL)
        labels = []
        for link in label_links:
            labels.append({
                "labeler": link.source,
                "labels": link.data.get("labels", []),
                "created": link.created.isoformat(),
            })
        return labels

    def apply_moderation_view(self, content_ids: list[str], moderation_view: View) -> list[str]:
        """Filter content based on moderation view."""
        # The moderation view defines what to hide
        boundary = ViewEngine(self.storage).execute(moderation_view)
        hidden = set(boundary.result_ids)
        return [cid for cid in content_ids if cid not in hidden]

    def is_moderator(self, entity_id: str, context_id: str) -> bool:
        """Check if entity is a moderator in context."""
        group = self.storage.get_entity(context_id)
        if not group or not group.governance:
            return False
        return entity_id in group.governance.get("moderators", [])


# =============================================================================
# ID GENERATORS
# =============================================================================

def generate_entity_id(name: str = None) -> str:
    if name:
        return f"ent:{name.lower().replace(' ', '-')}"
    return f"ent:{uuid.uuid4().hex[:12]}"


def generate_content_id() -> str:
    return f"cnt:{uuid.uuid4().hex[:12]}"


def generate_link_id() -> str:
    return f"lnk:{uuid.uuid4().hex[:12]}"


def generate_view_id(name: str) -> str:
    return f"view:{name.lower().replace(' ', '-')}"
