# MESH Protocol - Discovery Layer Specification

**Version 1.0 - Hybrid Discovery via Social Graph**

## Overview

The Discovery Layer enables nodes to find entities (users, groups) across the federated network through three complementary mechanisms:

1. **Relay Hints** - Entities declare where they can be found
2. **Handle Resolution** - Human-readable handles resolve to relay URLs
3. **Social Graph Indexing** - Crawl the follow/member graph to discover entities

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DISCOVERY LAYER                                   │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │ Relay Hints │  │ Handle Resolution│  │ Social Graph Indexer   │ │
│  │             │  │                  │  │                        │ │
│  │ Entity.     │  │ @alice@node.com  │  │ Crawl follows/members  │ │
│  │ relay_hints │  │ → relay URL      │  │ to discover entities   │ │
│  └─────────────┘  └─────────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 1. Relay Hints

### 1.1 Entity Relay Hints

Every entity SHOULD include hints about where it can be found:

```typescript
interface Entity {
  id: string;
  kind: "user" | "group";
  // ... existing fields
  
  // NEW: Discovery hints
  relay_hints: RelayHint[];
  home_relay: string;           // Primary relay URL
  updated_at: timestamp;        // For cache invalidation
}

interface RelayHint {
  url: string;                  // Relay URL
  role: "home" | "backup" | "mirror";
  added_at: timestamp;
  expires_at?: timestamp;       // Optional expiry
}
```

### 1.2 Content Relay Hints

Content includes the author's relay hints for resolution:

```typescript
interface Content {
  // ... existing fields
  author_relay_hints?: string[];  // Copied from author at creation time
}
```

### 1.3 Relay Hint Propagation

When content is federated, relay hints travel with it:

```python
def federate_content(content: Content, author: Entity):
    """Add relay hints when federating content."""
    content.author_relay_hints = [h.url for h in author.relay_hints[:3]]
    return content
```

---

## 2. Handle Resolution

### 2.1 Handle Format

Handles follow the format: `@{local}@{domain}` or just `@{local}` for local users.

Examples:
- `@alice@mesh.example.com` - Full handle with domain
- `@alice` - Local handle (relative to current relay)

### 2.2 Resolution via Well-Known

```http
GET https://{domain}/.well-known/mesh/entity/{handle}

Response:
{
  "entity_id": "ent:abc123...",
  "handle": "alice",
  "relay_hints": [
    "https://relay1.example.com",
    "https://relay2.example.com"
  ],
  "public_key": "ed25519:...",
  "profile": {
    "name": "Alice",
    "avatar": "https://..."
  }
}
```

### 2.3 Resolution via DNS (Optional)

```
; DNS TXT record for handle resolution
_mesh-entity.alice.mesh.example.com TXT "relay=https://relay.example.com id=ent:abc123"

; DNS SRV for relay discovery
_mesh._tcp.mesh.example.com SRV 10 0 443 relay.mesh.example.com
```

### 2.4 Resolution Algorithm

```python
async def resolve_handle(handle: str, current_relay: str) -> Entity:
    """Resolve a handle to an entity."""
    
    if "@" not in handle or handle.count("@") == 1:
        # Local handle - query current relay
        local = handle.lstrip("@").split("@")[0]
        return await current_relay.get_entity_by_handle(local)
    
    # Full handle: @alice@example.com
    parts = handle.lstrip("@").split("@")
    local, domain = parts[0], parts[1]
    
    # Try well-known endpoint
    try:
        resp = await http.get(f"https://{domain}/.well-known/mesh/entity/{local}")
        if resp.ok:
            data = resp.json()
            # Try relay hints
            for relay_url in data["relay_hints"]:
                entity = await fetch_entity(relay_url, data["entity_id"])
                if entity:
                    return entity
    except:
        pass
    
    # Fallback: DNS resolution
    try:
        txt = await dns.resolve(f"_mesh-entity.{local}.{domain}", "TXT")
        # Parse and fetch
    except:
        pass
    
    raise EntityNotFound(handle)
```

---

## 3. Social Graph Indexing

### 3.1 Core Concept

The social graph (follows, memberships, replies) forms a natural discovery mechanism:

```
Alice follows Bob → Alice's relay learns about Bob's relay
Bob is member of Group1 → Bob's relay learns about Group1's relay
Carol replies to Alice → Carol's relay learns about Alice's relay
```

### 3.2 Indexer Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         INDEXER NODE                                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐│
│  │   Crawler   │────▶│  Link Queue │────▶│  Entity/Relay Index    ││
│  │             │     │             │     │                         ││
│  │ Follow graph│     │ BFS queue   │     │ entity_id → relay_urls ││
│  │ Member graph│     │ of links    │     │ handle → entity_id     ││
│  │ Reply graph │     │ to crawl    │     │ group_id → relay_urls  ││
│  └─────────────┘     └─────────────┘     └─────────────────────────┘│
│         │                                           │                │
│         ▼                                           ▼                │
│  ┌─────────────┐                          ┌─────────────────────────┐│
│  │Known Relays │                          │    Search API           ││
│  │             │                          │                         ││
│  │ Queue of    │                          │ GET /search?q=          ││
│  │ relays to   │                          │ GET /resolve/{handle}   ││
│  │ crawl       │                          │ GET /locate/{entity_id} ││
│  └─────────────┘                          └─────────────────────────┘│
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.3 Crawler Algorithm

```python
class SocialGraphCrawler:
    """Crawl the social graph to discover entities and relays."""
    
    def __init__(self, seed_relays: list[str]):
        self.known_relays: set[str] = set(seed_relays)
        self.known_entities: dict[str, EntityIndex] = {}
        self.crawl_queue: deque[CrawlTask] = deque()
        self.visited: set[str] = set()
    
    async def crawl(self, max_depth: int = 3):
        """BFS crawl of the social graph."""
        
        # Seed the queue with known relays
        for relay in self.known_relays:
            self.crawl_queue.append(CrawlTask(relay=relay, depth=0))
        
        while self.crawl_queue:
            task = self.crawl_queue.popleft()
            
            if task.relay in self.visited:
                continue
            if task.depth > max_depth:
                continue
                
            self.visited.add(task.relay)
            
            # Fetch entities from this relay
            entities = await self.fetch_entities(task.relay)
            
            for entity in entities:
                # Index the entity
                self.index_entity(entity, task.relay)
                
                # Discover new relays from relay_hints
                for hint in entity.relay_hints:
                    if hint.url not in self.known_relays:
                        self.known_relays.add(hint.url)
                        self.crawl_queue.append(
                            CrawlTask(relay=hint.url, depth=task.depth + 1)
                        )
            
            # Fetch links (follows, memberships) to discover more entities
            links = await self.fetch_links(task.relay)
            
            for link in links:
                # If target is on a different relay, queue it
                target_relay = await self.resolve_entity_relay(link.target)
                if target_relay and target_relay not in self.known_relays:
                    self.known_relays.add(target_relay)
                    self.crawl_queue.append(
                        CrawlTask(relay=target_relay, depth=task.depth + 1)
                    )
    
    def index_entity(self, entity: Entity, relay_url: str):
        """Add entity to the index."""
        if entity.id not in self.known_entities:
            self.known_entities[entity.id] = EntityIndex(
                entity_id=entity.id,
                handle=entity.handle,
                kind=entity.kind,
                profile=entity.profile,
                relay_urls=set(),
                discovered_at=now(),
            )
        
        self.known_entities[entity.id].relay_urls.add(relay_url)
        self.known_entities[entity.id].last_seen = now()
```

### 3.4 Index Data Structures

```typescript
interface EntityIndex {
  entity_id: string;
  handle: string;
  kind: "user" | "group";
  profile: {
    name: string;
    bio?: string;
    avatar?: string;
  };
  relay_urls: string[];        // All known relays for this entity
  home_relay?: string;         // Preferred relay
  discovered_at: timestamp;
  last_seen: timestamp;
  trust_score?: number;        // Based on attestations
}

interface RelayIndex {
  url: string;
  node_id: string;
  entity_count: number;
  content_count: number;
  last_crawled: timestamp;
  health_status: "healthy" | "slow" | "offline";
  features: string[];          // Supported protocol features
}
```

### 3.5 Incremental Updates

Instead of full crawls, use incremental updates:

```python
async def incremental_sync(relay_url: str, since: datetime):
    """Fetch only new/changed data since last sync."""
    
    # Get new entities
    new_entities = await relay.get(
        f"/api/federation/entities?since={since.isoformat()}"
    )
    
    # Get new links
    new_links = await relay.get(
        f"/api/federation/links?since={since.isoformat()}"
    )
    
    # Update index
    for entity in new_entities:
        self.index_entity(entity, relay_url)
    
    # Discover new relays from links
    for link in new_links:
        await self.maybe_discover_relay(link.target)
```

---

## 4. Search API

### 4.1 Endpoints

```http
# Search for entities
GET /api/search?q={query}&type={user|group}&limit=20

# Resolve handle to entity
GET /api/resolve/{handle}

# Locate entity by ID (find relays)
GET /api/locate/{entity_id}

# Get relay info
GET /api/relays
GET /api/relays/{relay_url}
```

### 4.2 Search Response

```json
{
  "query": "alice",
  "results": [
    {
      "entity_id": "ent:abc123",
      "handle": "alice",
      "kind": "user",
      "profile": {
        "name": "Alice Smith",
        "bio": "Decentralization enthusiast"
      },
      "relay_urls": [
        "https://relay1.example.com",
        "https://relay2.example.com"
      ],
      "relevance_score": 0.95
    }
  ],
  "total": 1,
  "took_ms": 12
}
```

### 4.3 Locate Response

```json
{
  "entity_id": "ent:abc123",
  "relay_urls": [
    {
      "url": "https://relay1.example.com",
      "role": "home",
      "last_seen": "2024-01-15T10:30:00Z",
      "health": "healthy"
    },
    {
      "url": "https://relay2.example.com", 
      "role": "backup",
      "last_seen": "2024-01-15T09:00:00Z",
      "health": "healthy"
    }
  ]
}
```

---

## 5. Relay-to-Relay Discovery

### 5.1 Relay Advertisement

Relays advertise themselves to indexers:

```http
POST /api/index/register
{
  "relay_url": "https://my-relay.example.com",
  "node_id": "node:xyz789",
  "features": ["entities", "content", "links", "groups", "e2ee"],
  "entity_count": 1500,
  "public": true
}
```

### 5.2 Relay Gossip

Relays share known relays with each other:

```http
GET /api/federation/relays

Response:
{
  "relays": [
    {
      "url": "https://relay1.example.com",
      "node_id": "node:abc",
      "last_seen": "2024-01-15T10:00:00Z"
    },
    {
      "url": "https://relay2.example.com",
      "node_id": "node:def",
      "last_seen": "2024-01-15T09:30:00Z"
    }
  ]
}
```

### 5.3 Bootstrap Relays

New nodes bootstrap from well-known relays:

```python
BOOTSTRAP_RELAYS = [
    "https://bootstrap1.mesh-protocol.org",
    "https://bootstrap2.mesh-protocol.org",
]

async def bootstrap_node():
    """Bootstrap a new node by connecting to known relays."""
    
    for relay in BOOTSTRAP_RELAYS:
        try:
            # Get list of known relays
            relays = await http.get(f"{relay}/api/federation/relays")
            
            # Register ourselves
            await http.post(f"{relay}/api/index/register", {
                "relay_url": MY_RELAY_URL,
                "node_id": MY_NODE_ID,
                "features": MY_FEATURES,
            })
            
            # Start syncing
            for known_relay in relays:
                await sync_with_relay(known_relay["url"])
                
            break  # Success
        except:
            continue  # Try next bootstrap relay
```

---

## 6. Privacy Considerations

### 6.1 Opt-Out of Indexing

Users can opt out of public indexing:

```typescript
interface Entity {
  // ...
  indexing_preference: "public" | "unlisted" | "private";
}
```

- `public` - Indexed and searchable
- `unlisted` - Not in search results, but resolvable by handle/ID
- `private` - Not indexed at all (discovery only via direct sharing)

### 6.2 Relay Privacy

Relays can choose not to federate their entity list:

```json
{
  "federation_policy": {
    "share_entities": false,
    "share_content": true,
    "share_links": false
  }
}
```

---

## 7. Implementation Requirements

### 7.1 Relay Requirements

**MUST:**
- Include `relay_hints` when creating entities
- Respond to `/.well-known/mesh/entity/{handle}`
- Expose `/api/federation/entities` endpoint
- Expose `/api/federation/relays` endpoint

**SHOULD:**
- Participate in relay gossip
- Accept entity location queries

### 7.2 Client Requirements

**MUST:**
- Try multiple relay hints when resolving entities
- Cache resolved entity locations

**SHOULD:**
- Use indexer for search when available
- Fallback to relay-by-relay search

### 7.3 Indexer Requirements

**MUST:**
- Respect `indexing_preference`
- Provide rate-limited search API
- Handle relay failures gracefully

**SHOULD:**
- Use incremental sync
- Maintain relay health status
- Provide relevance-ranked search

---

## 8. Example Flows

### 8.1 Alice Follows Bob (Different Relays)

```
1. Alice (relay1) wants to follow @bob@relay2.example.com

2. Client resolves handle:
   GET https://relay2.example.com/.well-known/mesh/entity/bob
   → Returns: { entity_id: "ent:bob123", relay_hints: ["https://relay2.example.com"] }

3. Client fetches Bob's entity:
   GET https://relay2.example.com/api/entities/ent:bob123
   → Returns full entity with profile

4. Client creates follow link on relay1:
   POST https://relay1.example.com/api/links
   { source: "ent:alice", target: "ent:bob123", kind: "follow" }

5. Relay1 now knows about relay2 (from Bob's relay_hints)
   → Adds relay2 to known relays for future sync
```

### 8.2 Discovering a Group

```
1. Alice sees a post mentioning @developers@relay3.example.com

2. Client resolves group:
   GET https://relay3.example.com/.well-known/mesh/entity/developers
   → Returns group entity with relay_hints

3. Client joins group:
   POST relay1/api/links { target: "grp:developers", kind: "member" }

4. Relay1 learns about relay3, starts syncing group content
```

### 8.3 Global Search

```
1. User searches for "mesh protocol"

2. Client queries indexer:
   GET https://indexer.example.com/api/search?q=mesh%20protocol

3. Indexer returns results from crawled relays:
   {
     results: [
       { entity_id: "grp:mesh-dev", handle: "mesh-developers", ... },
       { entity_id: "ent:alice", handle: "alice", bio: "mesh protocol dev", ... }
     ]
   }

4. Client fetches full entities from their relay_hints
```
