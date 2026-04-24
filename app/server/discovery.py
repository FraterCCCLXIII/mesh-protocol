"""
MESH Protocol - Discovery Layer Implementation

Hybrid discovery via:
1. Relay hints (embedded in entities)
2. Handle resolution (well-known endpoints)
3. Social graph indexing (crawl follows/members to discover entities)
"""

import asyncio
import json
import httpx
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class RelayHint:
    """Hint about where an entity can be found."""
    url: str
    role: str = "backup"  # "home", "backup", "mirror"
    added_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expires_at: Optional[str] = None


@dataclass
class EntityIndex:
    """Indexed entity information."""
    entity_id: str
    handle: Optional[str]
    kind: str  # "user" or "group"
    profile: dict
    relay_urls: Set[str]
    home_relay: Optional[str] = None
    discovered_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_seen: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    indexing_preference: str = "public"  # "public", "unlisted", "private"
    
    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "handle": self.handle,
            "kind": self.kind,
            "profile": self.profile,
            "relay_urls": list(self.relay_urls),
            "home_relay": self.home_relay,
            "discovered_at": self.discovered_at,
            "last_seen": self.last_seen,
        }


@dataclass
class RelayIndex:
    """Indexed relay information."""
    url: str
    node_id: Optional[str] = None
    entity_count: int = 0
    content_count: int = 0
    last_crawled: Optional[str] = None
    health_status: str = "unknown"  # "healthy", "slow", "offline", "unknown"
    features: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "node_id": self.node_id,
            "entity_count": self.entity_count,
            "content_count": self.content_count,
            "last_crawled": self.last_crawled,
            "health_status": self.health_status,
            "features": self.features,
        }


@dataclass
class CrawlTask:
    """Task for the crawler queue."""
    relay_url: str
    depth: int = 0
    priority: int = 0  # Lower = higher priority


class SocialGraphIndexer:
    """
    Indexes entities and relays by crawling the social graph.
    
    Discovery flow:
    1. Start with seed relays
    2. Fetch entities from each relay
    3. Index entities and their relay_hints
    4. Fetch links (follows, members) to discover new relays
    5. Queue new relays for crawling
    6. Repeat with BFS
    """
    
    def __init__(self, my_relay_url: str, db=None):
        self.my_relay_url = my_relay_url
        self.db = db
        
        # In-memory indexes (can be persisted to DB)
        self.entity_index: Dict[str, EntityIndex] = {}
        self.handle_index: Dict[str, str] = {}  # handle -> entity_id
        self.relay_index: Dict[str, RelayIndex] = {}
        
        # Crawl state
        self.crawl_queue: deque[CrawlTask] = deque()
        self.visited_relays: Set[str] = set()
        self.crawl_in_progress = False
        
        # Settings
        self.max_depth = 3
        self.crawl_interval = 300  # 5 minutes
        self.request_timeout = 10
    
    async def initialize(self):
        """Initialize indexer, load from DB if available."""
        if self.db:
            await self._load_from_db()
        
        # Add self as known relay
        self.relay_index[self.my_relay_url] = RelayIndex(
            url=self.my_relay_url,
            health_status="healthy",
        )
    
    async def _load_from_db(self):
        """Load index from database."""
        try:
            # Load entity index
            cursor = await self.db.execute(
                "SELECT entity_id, handle, kind, profile, relay_urls, home_relay, discovered_at, last_seen "
                "FROM entity_index"
            )
            async for row in cursor:
                self.entity_index[row[0]] = EntityIndex(
                    entity_id=row[0],
                    handle=row[1],
                    kind=row[2],
                    profile=json.loads(row[3]) if row[3] else {},
                    relay_urls=set(json.loads(row[4])) if row[4] else set(),
                    home_relay=row[5],
                    discovered_at=row[6],
                    last_seen=row[7],
                )
                if row[1]:  # has handle
                    self.handle_index[row[1].lower()] = row[0]
            
            # Load relay index
            cursor = await self.db.execute(
                "SELECT url, node_id, entity_count, last_crawled, health_status, features "
                "FROM relay_index"
            )
            async for row in cursor:
                self.relay_index[row[0]] = RelayIndex(
                    url=row[0],
                    node_id=row[1],
                    entity_count=row[2] or 0,
                    last_crawled=row[3],
                    health_status=row[4] or "unknown",
                    features=json.loads(row[5]) if row[5] else [],
                )
        except Exception as e:
            logger.warning(f"Could not load index from DB: {e}")
    
    async def _save_entity_index(self, entity: EntityIndex):
        """Save entity to database."""
        if not self.db:
            return
        try:
            await self.db.execute("""
                INSERT OR REPLACE INTO entity_index 
                (entity_id, handle, kind, profile, relay_urls, home_relay, discovered_at, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entity.entity_id,
                entity.handle,
                entity.kind,
                json.dumps(entity.profile),
                json.dumps(list(entity.relay_urls)),
                entity.home_relay,
                entity.discovered_at,
                entity.last_seen,
            ))
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to save entity index: {e}")
    
    async def _save_relay_index(self, relay: RelayIndex):
        """Save relay to database."""
        if not self.db:
            return
        try:
            await self.db.execute("""
                INSERT OR REPLACE INTO relay_index
                (url, node_id, entity_count, last_crawled, health_status, features)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                relay.url,
                relay.node_id,
                relay.entity_count,
                relay.last_crawled,
                relay.health_status,
                json.dumps(relay.features),
            ))
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to save relay index: {e}")
    
    def add_seed_relay(self, relay_url: str):
        """Add a relay to crawl."""
        relay_url = relay_url.rstrip("/")
        if relay_url not in self.relay_index:
            self.relay_index[relay_url] = RelayIndex(url=relay_url)
        if relay_url not in self.visited_relays:
            self.crawl_queue.append(CrawlTask(relay_url=relay_url, depth=0))
    
    def index_entity(self, entity_data: dict, source_relay: str):
        """Index an entity discovered from a relay."""
        entity_id = entity_data.get("id")
        if not entity_id:
            return
        
        # Check indexing preference
        if entity_data.get("indexing_preference") == "private":
            return
        
        handle = entity_data.get("handle")
        kind = entity_data.get("kind", "user")
        profile = entity_data.get("profile", {})
        
        # Get relay hints
        relay_hints = entity_data.get("relay_hints", [])
        relay_urls = {source_relay}
        home_relay = source_relay
        
        for hint in relay_hints:
            if isinstance(hint, str):
                relay_urls.add(hint)
            elif isinstance(hint, dict):
                relay_urls.add(hint.get("url", ""))
                if hint.get("role") == "home":
                    home_relay = hint.get("url", source_relay)
        
        # Update or create index entry
        if entity_id in self.entity_index:
            entry = self.entity_index[entity_id]
            entry.relay_urls.update(relay_urls)
            entry.last_seen = datetime.utcnow().isoformat()
            if profile:
                entry.profile = profile
        else:
            entry = EntityIndex(
                entity_id=entity_id,
                handle=handle,
                kind=kind,
                profile=profile,
                relay_urls=relay_urls,
                home_relay=home_relay,
                indexing_preference=entity_data.get("indexing_preference", "public"),
            )
            self.entity_index[entity_id] = entry
        
        # Update handle index
        if handle:
            self.handle_index[handle.lower()] = entity_id
        
        # Queue relay hints for crawling
        for url in relay_urls:
            if url and url not in self.visited_relays:
                self.crawl_queue.append(CrawlTask(relay_url=url, depth=1))
        
        # Save to DB
        asyncio.create_task(self._save_entity_index(entry))
    
    async def crawl_relay(self, relay_url: str, depth: int = 0) -> bool:
        """Crawl a single relay to discover entities and links."""
        relay_url = relay_url.rstrip("/")
        logger.info(f"[Indexer] Crawling relay: {relay_url} (depth={depth})")
        
        if relay_url in self.visited_relays:
            return True
        
        self.visited_relays.add(relay_url)
        
        # Update relay index
        if relay_url not in self.relay_index:
            self.relay_index[relay_url] = RelayIndex(url=relay_url)
        
        relay_info = self.relay_index[relay_url]
        
        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            # Fetch relay info
            try:
                resp = await client.get(f"{relay_url}/.well-known/mesh-node")
                if resp.status_code == 200:
                    data = resp.json()
                    relay_info.node_id = data.get("node_id")
                    relay_info.features = data.get("features", [])
            except Exception as e:
                logger.debug(f"Could not fetch node info from {relay_url}: {e}")
            
            # Fetch entities
            try:
                resp = await client.get(f"{relay_url}/api/federation/entities?limit=500")
                if resp.status_code == 200:
                    data = resp.json()
                    entities = data.get("items", data.get("entities", []))
                    
                    relay_info.entity_count = len(entities)
                    
                    for entity in entities:
                        self.index_entity(entity, relay_url)
                        
                        # Discover new relays from relay_hints
                        for hint in entity.get("relay_hints", []):
                            hint_url = hint if isinstance(hint, str) else hint.get("url")
                            if hint_url and hint_url not in self.visited_relays and depth < self.max_depth:
                                self.crawl_queue.append(
                                    CrawlTask(relay_url=hint_url, depth=depth + 1)
                                )
                    
                    logger.info(f"[Indexer] Indexed {len(entities)} entities from {relay_url}")
            except Exception as e:
                logger.warning(f"Could not fetch entities from {relay_url}: {e}")
                relay_info.health_status = "offline"
                await self._save_relay_index(relay_info)
                return False
            
            # Fetch groups
            try:
                resp = await client.get(f"{relay_url}/api/federation/groups?limit=500")
                if resp.status_code == 200:
                    data = resp.json()
                    groups = data.get("groups", [])
                    
                    for group in groups:
                        self.index_entity(group, relay_url)
                    
                    logger.info(f"[Indexer] Indexed {len(groups)} groups from {relay_url}")
            except Exception as e:
                logger.debug(f"Could not fetch groups from {relay_url}: {e}")
            
            # Fetch links to discover more relays via social graph
            if depth < self.max_depth:
                try:
                    resp = await client.get(f"{relay_url}/api/federation/links?limit=1000")
                    if resp.status_code == 200:
                        data = resp.json()
                        links = data.get("links", [])
                        
                        # Look for targets we don't know about
                        for link in links:
                            target_id = link.get("target")
                            if target_id and target_id not in self.entity_index:
                                # Try to discover where this entity lives
                                await self._discover_entity_relay(target_id, client)
                except Exception as e:
                    logger.debug(f"Could not fetch links from {relay_url}: {e}")
            
            # Fetch known relays (gossip)
            try:
                resp = await client.get(f"{relay_url}/api/federation/relays")
                if resp.status_code == 200:
                    data = resp.json()
                    relays = data.get("relays", [])
                    
                    for relay in relays:
                        other_url = relay.get("url", relay) if isinstance(relay, dict) else relay
                        if other_url and other_url not in self.visited_relays and depth < self.max_depth:
                            self.crawl_queue.append(
                                CrawlTask(relay_url=other_url, depth=depth + 1)
                            )
            except Exception as e:
                logger.debug(f"Could not fetch relays from {relay_url}: {e}")
        
        relay_info.last_crawled = datetime.utcnow().isoformat()
        relay_info.health_status = "healthy"
        await self._save_relay_index(relay_info)
        
        return True
    
    async def _discover_entity_relay(self, entity_id: str, client: httpx.AsyncClient):
        """Try to discover which relay hosts an entity."""
        # Check known relays
        for relay_url in list(self.relay_index.keys())[:10]:  # Limit to 10 relays
            try:
                resp = await client.get(
                    f"{relay_url}/api/entities/{entity_id}",
                    timeout=5
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self.index_entity(data, relay_url)
                    return
            except:
                continue
    
    async def run_crawl(self):
        """Run a full crawl of the queue."""
        if self.crawl_in_progress:
            logger.info("[Indexer] Crawl already in progress")
            return
        
        self.crawl_in_progress = True
        crawled = 0
        
        try:
            while self.crawl_queue:
                task = self.crawl_queue.popleft()
                
                if task.relay_url in self.visited_relays:
                    continue
                
                if task.depth > self.max_depth:
                    continue
                
                await self.crawl_relay(task.relay_url, task.depth)
                crawled += 1
                
                # Rate limit
                await asyncio.sleep(0.5)
            
            logger.info(f"[Indexer] Crawl complete. Crawled {crawled} relays, "
                       f"indexed {len(self.entity_index)} entities")
        finally:
            self.crawl_in_progress = False
    
    async def start_background_crawl(self, interval: int = 300):
        """Start background crawling loop."""
        while True:
            try:
                # Reset visited for periodic re-crawl
                self.visited_relays.clear()
                
                # Re-queue known relays
                for relay_url in list(self.relay_index.keys()):
                    self.crawl_queue.append(CrawlTask(relay_url=relay_url, depth=0))
                
                await self.run_crawl()
            except Exception as e:
                logger.error(f"[Indexer] Background crawl error: {e}")
            
            await asyncio.sleep(interval)
    
    # Search API
    
    def search(self, query: str, kind: Optional[str] = None, limit: int = 20) -> List[dict]:
        """Search for entities by name, handle, or bio."""
        query_lower = query.lower()
        results = []
        
        for entity in self.entity_index.values():
            # Skip private entities in search
            if entity.indexing_preference == "private":
                continue
            
            # Filter by kind if specified
            if kind and entity.kind != kind:
                continue
            
            # Calculate relevance score
            score = 0
            
            # Handle match (highest priority)
            if entity.handle and query_lower in entity.handle.lower():
                score += 100
                if entity.handle.lower() == query_lower:
                    score += 50  # Exact match bonus
            
            # Name match
            name = entity.profile.get("name", "")
            if name and query_lower in name.lower():
                score += 50
                if name.lower() == query_lower:
                    score += 25
            
            # Bio match
            bio = entity.profile.get("bio", "")
            if bio and query_lower in bio.lower():
                score += 10
            
            if score > 0:
                result = entity.to_dict()
                result["relevance_score"] = score
                results.append(result)
        
        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return results[:limit]
    
    def resolve_handle(self, handle: str) -> Optional[dict]:
        """Resolve a handle to entity info."""
        handle_lower = handle.lower().lstrip("@")
        
        # Check if it's a full handle with domain
        if "@" in handle_lower:
            local, domain = handle_lower.split("@", 1)
            # For now, just search by local part
            # TODO: Implement cross-domain resolution
            handle_lower = local
        
        entity_id = self.handle_index.get(handle_lower)
        if entity_id and entity_id in self.entity_index:
            return self.entity_index[entity_id].to_dict()
        
        return None
    
    def locate_entity(self, entity_id: str) -> Optional[dict]:
        """Find relay URLs for an entity."""
        if entity_id in self.entity_index:
            entity = self.entity_index[entity_id]
            return {
                "entity_id": entity_id,
                "relay_urls": [
                    {
                        "url": url,
                        "role": "home" if url == entity.home_relay else "backup",
                        "last_seen": entity.last_seen,
                    }
                    for url in entity.relay_urls
                ]
            }
        return None
    
    def get_known_relays(self) -> List[dict]:
        """Get list of known relays."""
        return [relay.to_dict() for relay in self.relay_index.values()]
    
    def get_stats(self) -> dict:
        """Get indexer statistics."""
        return {
            "total_entities": len(self.entity_index),
            "total_users": sum(1 for e in self.entity_index.values() if e.kind == "user"),
            "total_groups": sum(1 for e in self.entity_index.values() if e.kind == "group"),
            "total_relays": len(self.relay_index),
            "healthy_relays": sum(1 for r in self.relay_index.values() if r.health_status == "healthy"),
        }


# Singleton indexer instance
_indexer: Optional[SocialGraphIndexer] = None


def get_indexer() -> SocialGraphIndexer:
    """Get the global indexer instance."""
    global _indexer
    if _indexer is None:
        raise RuntimeError("Indexer not initialized")
    return _indexer


async def init_indexer(my_relay_url: str, db=None, seed_relays: List[str] = None):
    """Initialize the global indexer."""
    global _indexer
    _indexer = SocialGraphIndexer(my_relay_url, db)
    await _indexer.initialize()
    
    if seed_relays:
        for relay in seed_relays:
            _indexer.add_seed_relay(relay)
    
    return _indexer
