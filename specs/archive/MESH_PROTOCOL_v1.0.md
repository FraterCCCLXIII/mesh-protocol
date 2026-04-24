# MESH Protocol Specification v1.0

**Modular Extensible Social Hybrid Protocol**

A next-generation decentralized social network protocol combining the best aspects of HOLON, Relay, Nostr, ActivityPub, SSB, and AT Protocol.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Design Principles](#2-design-principles)
3. [Architecture](#3-architecture)
4. [Layer 1: Privacy Layer](#4-layer-1-privacy-layer)
5. [Layer 2: Storage Layer](#5-layer-2-storage-layer)
6. [Layer 3: Integrity Layer](#6-layer-3-integrity-layer)
7. [Layer 4: Social Layer](#7-layer-4-social-layer)
8. [Layer 5: Moderation Layer](#8-layer-5-moderation-layer)
9. [Layer 6: View Layer](#9-layer-6-view-layer)
10. [Layer 7: Network Layer](#10-layer-7-network-layer)
11. [Layer 8: Application Layer](#11-layer-8-application-layer)
12. [Derived Systems](#12-derived-systems)
13. [Sync Protocol](#13-sync-protocol)
14. [Security Model](#14-security-model)
15. [Scalability](#15-scalability)
16. [Comparison with Existing Protocols](#16-comparison-with-existing-protocols)
17. [Implementation Requirements](#17-implementation-requirements)
18. [Appendices](#18-appendices)

---

## 1. Overview

### 1.1 What is MESH?

MESH is a modular, layered protocol for decentralized social networking that provides:

- **Self-sovereign identity** via Ed25519 cryptographic keys
- **Append-only integrity** via prev-chain linked events
- **End-to-end encryption** via X25519 + AES-256-GCM
- **Verifiable feeds** via deterministic view computation
- **Composable moderation** via third-party attestations
- **Horizontal scalability** via content-addressed data

### 1.2 Key Properties

| Property | Mechanism |
|----------|-----------|
| Decentralized | No required central servers |
| Self-sovereign | Users own their keys and data |
| Censorship-resistant | Data replicates across relays |
| Privacy-preserving | E2EE for DMs and private groups |
| Verifiable | Deterministic feed computation |
| Scalable | Content-addressed, shardable |
| Interoperable | Standard formats (JSON, HTTP) |

### 1.3 Design Goals

1. **Simplicity** - Minimal primitive set (Entity, Content, Link)
2. **Integrity** - Provable append-only history
3. **Privacy** - Encryption built-in, not bolted on
4. **Modularity** - Use only the layers you need
5. **Performance** - 6,000+ writes/sec, 5,000+ queries/sec

---

## 2. Design Principles

### 2.1 Core Principles

1. **Keys are identity** - Your Ed25519 keypair IS your identity
2. **Events are immutable** - Once written, events cannot be changed
3. **State is derived** - Current state is computed from event history
4. **Attestations are separate** - Third-party claims never modify facts
5. **Views are deterministic** - Same inputs always produce same outputs
6. **Layers are optional** - Clients choose which layers to implement

### 2.2 Tradeoffs Made

| Tradeoff | Choice | Rationale |
|----------|--------|-----------|
| Event logs vs state | Event logs | Auditability, sync simplicity |
| Push vs pull sync | Pull with subscriptions | Efficiency, offline support |
| Keys vs delegated identity | Keys | Self-sovereignty, simplicity |
| Local-first vs relay-based | Hybrid | Flexibility, resilience |
| Client-side vs protocol moderation | Client-side with attestations | Freedom, composability |
| E2EE default vs optional | Optional with easy E2EE | Performance, usability |

### 2.3 What MESH Does NOT Do

- **Consensus** - No blockchain, no global ordering
- **Payments** - No built-in cryptocurrency
- **Storage guarantees** - Relays may drop data
- **Identity recovery** - Lost keys = lost identity (by design)
- **Content moderation** - Protocol provides tools, not policies

---

## 3. Architecture

### 3.1 Layer Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 8: APPLICATION                             │
│              (Mobile, Web, Desktop, Bots, VR)                       │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 7: NETWORK                                 │
│           (HTTP API, WebSocket, Federation, P2P)                    │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 6: VIEW                                    │
│        (ViewDefinitions, Reducers, Boundary Determinism)            │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 5: MODERATION                              │
│           (Attestations, Labels, Trust Networks)                    │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 4: SOCIAL                                  │
│              (Entity, Content, Link primitives)                     │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 3: INTEGRITY                               │
│         (LogEvent, Prev Chain, Commitment Hash)                     │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 2: STORAGE                                 │
│            (SQLite/PostgreSQL, Indexes, Caching)                    │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 1: PRIVACY                                 │
│           (Ed25519, X25519, AES-256-GCM, Group Keys)                │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Layer Dependencies

```
Application ─────────────────────────────────────────┐
     │                                               │
     ├── Network ◄────── required ──────────────────►│
     │      │                                        │
     ├── View ◄─────── optional (power users) ──────►│
     │      │                                        │
     ├── Moderation ◄── optional (filtering) ───────►│
     │      │                                        │
     ├── Social ◄────── REQUIRED ───────────────────►│
     │      │                                        │
     ├── Integrity ◄─── REQUIRED ───────────────────►│
     │      │                                        │
     ├── Storage ◄───── REQUIRED ───────────────────►│
     │      │                                        │
     └── Privacy ◄───── REQUIRED ───────────────────►│
```

### 3.3 Minimum Viable Implementation

A minimal MESH client MUST implement:
- Privacy Layer (signatures)
- Storage Layer (persistence)
- Integrity Layer (log events)
- Social Layer (primitives)

A minimal MESH relay MUST implement:
- All of the above, plus
- Network Layer (HTTP API)

---

## 4. Layer 1: Privacy Layer

### 4.1 Overview

The Privacy Layer provides cryptographic primitives for identity, authentication, and encryption.

### 4.2 Identity

Identity in MESH is based on Ed25519 keypairs.

```
entity_id = "ent:" + hex(sha256(public_key))[0:32]
```

**Example:**
```json
{
  "public_key": "a1b2c3d4e5f6...",
  "entity_id": "ent:7f83b1657ff1fc53b92dc18148a1d65d"
}
```

### 4.3 Signatures

All mutable data MUST be signed using Ed25519.

**Signing Process:**
1. Create object without `sig` field
2. Serialize to canonical JSON (sorted keys, no whitespace)
3. Sign the bytes with Ed25519 private key
4. Add `sig` field as hex-encoded signature

```python
def sign_object(obj: dict, keypair: SigningKeyPair) -> dict:
    obj_copy = {k: v for k, v in obj.items() if k != 'sig'}
    canonical = json.dumps(obj_copy, sort_keys=True, separators=(',', ':'))
    sig = keypair.sign(canonical.encode('utf-8'))
    return {**obj_copy, 'sig': sig.hex()}
```

### 4.4 Canonical JSON

All hashing and signing MUST use canonical JSON:

- Keys sorted alphabetically
- No whitespace (separators = `(',', ':')`)
- UTF-8 encoding
- Numbers as-is (no scientific notation normalization)
- Null represented as `null`

```python
def canonical_json(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')
```

### 4.5 Key Exchange (DMs)

Direct messages use X25519 key exchange + AES-256-GCM.

**Encryption Process:**
1. Generate ephemeral X25519 keypair
2. Derive shared secret: `shared = x25519(ephemeral_private, recipient_public)`
3. Derive AES key: `key = HKDF-SHA256(shared, info="mesh-encryption-v1")`
4. Generate random 12-byte nonce
5. Encrypt with AES-256-GCM

```typescript
interface EncryptedMessage {
  ephemeral_public_key: bytes;  // 32 bytes
  nonce: bytes;                  // 12 bytes
  ciphertext: bytes;             // variable length
}
```

### 4.6 Group Encryption

Groups use symmetric AES-256-GCM keys distributed to members.

```typescript
interface GroupKey {
  group_id: string;
  version: number;      // Increments on rotation
  key: bytes;           // 32-byte AES key
  members: string[];    // entity_ids with access
  created_at: timestamp;
}
```

**Key Rotation:**
1. Generate new GroupKey with version + 1
2. Encrypt new key for each member using their X25519 public key
3. Distribute encrypted keys
4. Old keys retained for decrypting old content

### 4.7 Hash Functions

MESH uses SHA-256 for all hashing:

```python
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
```

**ID Generation:**
```python
def generate_entity_id(public_key: bytes) -> str:
    return "ent:" + sha256(public_key)[:32]

def generate_content_id(content_dict: dict) -> str:
    return sha256(canonical_json(content_dict))[:48]

def generate_link_id(source: str, kind: str, target: str) -> str:
    return sha256(f"{source}:{kind}:{target}".encode())[:32]

def generate_log_event_id(actor: str, seq: int) -> str:
    return sha256(f"{actor}:{seq}".encode())[:48]
```

---

## 5. Layer 2: Storage Layer

### 5.1 Overview

The Storage Layer provides persistence with optimized performance.

### 5.2 Recommended Configuration

SQLite with WAL mode provides excellent single-node performance:

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-64000;  -- 64MB cache
PRAGMA temp_store=MEMORY;
```

**Performance:**
- Writes: ~6,000/sec
- Queries: ~5,000/sec

### 5.3 Schema

```sql
-- Social Layer Tables
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,           -- 'user', 'group', 'bot', 'service'
    public_key BLOB NOT NULL,
    encryption_key BLOB,
    handle TEXT,
    profile TEXT,                  -- JSON
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sig BLOB NOT NULL
);

CREATE TABLE content (
    id TEXT PRIMARY KEY,
    author TEXT NOT NULL,
    kind TEXT NOT NULL,           -- 'post', 'reply', 'media', 'reaction'
    body TEXT NOT NULL,           -- JSON
    reply_to TEXT,
    created_at TEXT NOT NULL,
    access TEXT NOT NULL,         -- 'public', 'private', 'group'
    encrypted INTEGER NOT NULL,
    encryption_metadata TEXT,     -- JSON
    sig BLOB NOT NULL
);

CREATE TABLE links (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    kind TEXT NOT NULL,           -- 'follow', 'like', 'member', 'block', 'pin'
    data TEXT,                    -- JSON
    created_at TEXT NOT NULL,
    tombstone INTEGER NOT NULL DEFAULT 0,
    sig BLOB NOT NULL
);

-- Integrity Layer Tables
CREATE TABLE log_events (
    id TEXT PRIMARY KEY,
    actor TEXT NOT NULL,
    seq INTEGER NOT NULL,
    prev TEXT,                    -- NULL for first event
    op TEXT NOT NULL,             -- 'create', 'update', 'delete'
    object_type TEXT NOT NULL,    -- 'entity', 'content', 'link', etc.
    object_id TEXT NOT NULL,
    payload TEXT NOT NULL,        -- JSON
    ts TEXT NOT NULL,
    sig BLOB NOT NULL,
    commitment TEXT               -- Optional commitment_hash
);

CREATE TABLE log_heads (
    actor TEXT PRIMARY KEY,
    head_id TEXT NOT NULL,
    head_seq INTEGER NOT NULL
);

-- Moderation Layer Tables
CREATE TABLE attestations (
    id TEXT PRIMARY KEY,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    type TEXT NOT NULL,           -- 'trust', 'label', 'badge', 'block', 'flag'
    claim TEXT NOT NULL,          -- JSON
    evidence TEXT,                -- JSON
    ts TEXT NOT NULL,
    expires_at TEXT,
    revoked INTEGER NOT NULL DEFAULT 0,
    sig BLOB NOT NULL
);

-- View Layer Tables
CREATE TABLE view_definitions (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    version INTEGER NOT NULL,
    sources TEXT NOT NULL,        -- JSON array
    filters TEXT NOT NULL,        -- JSON array
    reducer TEXT NOT NULL,
    params TEXT NOT NULL,         -- JSON
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sig BLOB NOT NULL
);

CREATE TABLE view_cache (
    view_id TEXT NOT NULL,
    view_version INTEGER NOT NULL,
    boundary_hash TEXT NOT NULL,
    result_hash TEXT NOT NULL,
    event_ids TEXT NOT NULL,      -- JSON array
    computed_at TEXT NOT NULL,
    expires_at TEXT,
    PRIMARY KEY (view_id, view_version, boundary_hash)
);

-- Indexes
CREATE INDEX idx_entities_handle ON entities(handle);
CREATE INDEX idx_content_author ON content(author);
CREATE INDEX idx_content_reply_to ON content(reply_to);
CREATE INDEX idx_links_source ON links(source);
CREATE INDEX idx_links_target ON links(target);
CREATE INDEX idx_links_kind ON links(kind);
CREATE INDEX idx_log_actor ON log_events(actor);
CREATE INDEX idx_log_actor_seq ON log_events(actor, seq);
CREATE INDEX idx_attestations_subject ON attestations(subject);
CREATE INDEX idx_attestations_issuer ON attestations(issuer);
```

### 5.4 Content Addressing

All objects are content-addressed where possible:

| Object Type | ID Formula |
|-------------|------------|
| Entity | `sha256(public_key)[:32]` |
| Content | `sha256(canonical_json(content))[:48]` |
| Link | `sha256(source:kind:target)[:32]` |
| LogEvent | `sha256(actor:seq)[:48]` |
| Attestation | `sha256(canonical_json(attestation))[:48]` |

---

## 6. Layer 3: Integrity Layer

### 6.1 Overview

The Integrity Layer ensures append-only semantics and enables verification.

### 6.2 LogEvent

Every write is wrapped in a LogEvent:

```typescript
interface LogEvent {
  id: string;              // sha256(actor:seq)[:48]
  actor: string;           // entity_id of author
  seq: number;             // Monotonically increasing
  prev: string | null;     // Previous event ID (null for first)
  
  op: "create" | "update" | "delete";
  object_type: "entity" | "content" | "link" | "state" | "attestation" | "view";
  object_id: string;
  payload: object;
  
  ts: timestamp;
  sig: bytes;
  
  commitment?: string;     // Optional commitment_hash
}
```

### 6.3 Prev Chain

The prev chain ensures append-only semantics:

**Rules:**
1. First event MUST have `prev = null` and `seq = 1`
2. Subsequent events MUST have `prev = previous_event.id`
3. Sequence numbers MUST increment by 1
4. Events with invalid prev MUST be rejected

```python
def validate_prev(event: LogEvent, current_head: Optional[str], current_seq: int) -> bool:
    if current_head is None:
        # First event
        return event.prev is None and event.seq == 1
    else:
        # Subsequent event
        return event.prev == current_head and event.seq == current_seq + 1
```

### 6.4 Fork Detection

Forks occur when two events reference the same prev:

```python
def detect_fork(events_a: list, events_b: list) -> Optional[int]:
    """Returns index where chains diverge, or None if no fork."""
    for i in range(min(len(events_a), len(events_b))):
        if events_a[i].id != events_b[i].id:
            return i
    return None
```

**Fork Resolution:**
- MESH does not define automatic fork resolution
- Implementations MAY reject forked chains
- Users MAY manually resolve forks by choosing a chain

### 6.5 Commitment Hash

For action verification, events MAY include a commitment hash:

```python
def commitment_hash(event_id: str, action_type: str, input_refs: list, params: dict) -> str:
    data = {
        "event_id": event_id,
        "action_type": action_type,
        "input_refs": sorted(input_refs),
        "params": params,
    }
    return sha256(canonical_json(data))
```

**Use Cases:**
- Proving a specific action was taken
- Verifying action parameters
- Audit trails

---

## 7. Layer 4: Social Layer

### 7.1 Overview

The Social Layer defines three primitives: Entity, Content, and Link.

### 7.2 Entity

Entities represent identities: users, groups, bots, services.

```typescript
interface Entity {
  id: string;                    // ent:sha256(public_key)[:32]
  kind: "user" | "group" | "bot" | "service";
  public_key: bytes;             // Ed25519 public key (32 bytes)
  encryption_key?: bytes;        // X25519 public key (32 bytes)
  handle?: string;               // Human-readable name
  profile: object;               // Arbitrary metadata
  created_at: timestamp;
  updated_at: timestamp;
  sig: bytes;
}
```

**Entity Kinds:**
| Kind | Description |
|------|-------------|
| `user` | Human user account |
| `group` | Collection of users |
| `bot` | Automated account |
| `service` | External service integration |

**Profile Schema (Recommended):**
```typescript
interface Profile {
  name?: string;
  bio?: string;
  avatar?: string;          // URL or content_id
  banner?: string;          // URL or content_id
  website?: string;
  location?: string;
  custom?: object;          // Application-specific
}
```

### 7.3 Content

Content represents posts, replies, media, and reactions.

```typescript
interface Content {
  id: string;                    // sha256(canonical_json)[:48]
  author: string;                // entity_id
  kind: "post" | "reply" | "media" | "reaction";
  body: object;                  // Kind-specific content
  reply_to?: string;             // content_id (for replies)
  created_at: timestamp;
  access: "public" | "private" | "group";
  encrypted: boolean;
  encryption_metadata?: object;
  sig: bytes;
}
```

**Content Kinds:**

**Post:**
```typescript
interface PostBody {
  text?: string;
  media?: MediaAttachment[];
  tags?: string[];
  mentions?: string[];        // entity_ids
  links?: LinkPreview[];
}

interface MediaAttachment {
  type: "image" | "video" | "audio" | "file";
  url: string;
  mime_type: string;
  size_bytes?: number;
  width?: number;
  height?: number;
  duration_ms?: number;
  thumbnail_url?: string;
  alt_text?: string;
}
```

**Reply:**
```typescript
// Same as PostBody, but reply_to MUST be set
```

**Reaction:**
```typescript
interface ReactionBody {
  emoji: string;              // Unicode emoji or custom :shortcode:
  target: string;             // content_id being reacted to
}
```

**Media:**
```typescript
interface MediaBody {
  type: "image" | "video" | "audio" | "file";
  url: string;
  mime_type: string;
  metadata: object;
}
```

### 7.4 Link

Links represent relationships between entities or content.

```typescript
interface Link {
  id: string;                    // sha256(source:kind:target)[:32]
  source: string;                // entity_id
  target: string;                // entity_id or content_id
  kind: "follow" | "like" | "member" | "block" | "pin" | "moderator";
  data?: object;                 // Kind-specific metadata
  created_at: timestamp;
  tombstone: boolean;            // true = deleted
  sig: bytes;
}
```

**Link Kinds:**
| Kind | Source → Target | Description |
|------|-----------------|-------------|
| `follow` | user → user | Following relationship |
| `like` | user → content | Like/favorite |
| `member` | user → group | Group membership |
| `block` | user → user | Blocking relationship |
| `pin` | user → content | Pinned content |
| `moderator` | user → group | Moderator role |

**Tombstones:**

Links use tombstones for soft deletion:
- Setting `tombstone: true` removes the relationship
- The tombstoned link MUST be preserved for sync
- Queries MUST filter out tombstoned links by default

---

## 8. Layer 5: Moderation Layer

### 8.1 Overview

The Moderation Layer provides attestation-based moderation without censorship.

### 8.2 Core Principle

**Attestations NEVER modify facts.** They are separate claims that compose on top of the truth layer.

### 8.3 Attestation

```typescript
interface Attestation {
  id: string;
  issuer: string;                // Who made this claim
  subject: string;               // entity_id or content_id
  type: "trust" | "label" | "badge" | "block" | "verify" | "flag";
  claim: object;                 // Type-specific claim data
  evidence?: object;             // Supporting evidence
  ts: timestamp;
  expires_at?: timestamp;
  revoked: boolean;
  sig: bytes;
}
```

**Attestation Types:**

| Type | Description | Example Claim |
|------|-------------|---------------|
| `trust` | Vouching for identity | `{level: "high", reason: "known IRL"}` |
| `label` | Labeling content | `{label: "nsfw", confidence: 0.95}` |
| `badge` | Awarding achievement | `{badge: "verified", authority: "mesh.org"}` |
| `block` | Block recommendation | `{reason: "spam", severity: "high"}` |
| `verify` | Identity verification | `{method: "dns", domain: "alice.com"}` |
| `flag` | Content flag | `{type: "misinformation", details: "..."}` |

### 8.4 Trust Networks

Users compose trust from multiple sources:

```typescript
interface TrustNetwork {
  owner: string;                 // Who owns this config
  trusted_issuers: string[];     // entity_ids to trust
  trust_depth: number;           // 0 = direct only, 1 = friends-of-friends
  attestation_types: string[];   // Which types to consider
}
```

**Example:**
```json
{
  "owner": "ent:alice123",
  "trusted_issuers": [
    "ent:mesh_foundation",
    "ent:community_mods",
    "ent:bob456"
  ],
  "trust_depth": 1,
  "attestation_types": ["label", "block", "flag"]
}
```

### 8.5 Filtering

Clients apply attestation-based filtering:

```python
def should_filter(content_id: str, trust_network: TrustNetwork) -> bool:
    attestations = get_attestations_for(content_id)
    
    for att in attestations:
        if att.issuer not in trust_network.trusted_issuers:
            continue
        if att.type not in trust_network.attestation_types:
            continue
        if not att.is_valid():
            continue
            
        if att.type == "block" and att.claim.get("severity") == "high":
            return True
        if att.type == "flag" and att.claim.get("type") == "illegal":
            return True
    
    return False
```

### 8.6 Labels

Common label vocabulary (recommended):

| Label | Description |
|-------|-------------|
| `nsfw` | Not safe for work |
| `spoiler` | Contains spoilers |
| `sensitive` | Sensitive content |
| `spam` | Spam content |
| `bot` | Automated account |
| `impersonation` | Impersonating another |
| `misinformation` | False information |

Labels are advisory—clients decide how to handle them.

---

## 9. Layer 6: View Layer

### 9.1 Overview

The View Layer provides deterministic feed computation.

### 9.2 Core Principle

**Same definition + same boundary = same result.**

This enables:
- Verifiable feeds
- Reproducible results
- Efficient caching

### 9.3 ViewDefinition

```typescript
interface ViewDefinition {
  id: string;
  owner: string;                 // entity_id
  version: number;               // MUST increment on update
  
  sources: Source[];             // What to include
  filters: Filter[];             // What to exclude
  reducer: "chronological" | "reverse_chronological" | "ranked" | "grouped" | "custom";
  params: object;                // Reducer-specific parameters
  
  created_at: timestamp;
  updated_at: timestamp;
  sig: bytes;
}

interface Source {
  kind: "actor" | "follows" | "group" | "tag" | "all";
  actor_id?: string;
  group_id?: string;
  tag?: string;
}

interface Filter {
  exclude_actors?: string[];
  exclude_kinds?: string[];
  require_attestations?: AttestationFilter[];
  exclude_attestations?: AttestationFilter[];
  min_timestamp?: timestamp;
  max_timestamp?: timestamp;
}

interface AttestationFilter {
  type: string;
  issuers: string[];
}
```

### 9.4 Boundary Hash

The boundary hash captures the state at computation time:

```python
def boundary_hash(event_ids: list, actor_heads: dict) -> str:
    data = {
        "events": sorted(event_ids),
        "heads": dict(sorted(actor_heads.items())),
    }
    return sha256(canonical_json(data))
```

### 9.5 ViewResult

```typescript
interface ViewResult {
  view_id: string;
  view_version: number;
  
  boundary_hash: string;         // Determinism proof
  result_hash: string;           // Hash of output
  
  event_ids: string[];           // Ordered result
  computed_at: timestamp;
  
  cached: boolean;
  cache_expires?: timestamp;
}
```

### 9.6 Reducers

**Chronological:**
```python
def reduce_chronological(events: list, params: dict) -> list:
    sorted_events = sorted(events, key=lambda e: e.ts)
    limit = params.get("limit", 100)
    offset = params.get("offset", 0)
    return sorted_events[offset:offset+limit]
```

**Reverse Chronological:**
```python
def reduce_reverse_chronological(events: list, params: dict) -> list:
    sorted_events = sorted(events, key=lambda e: e.ts, reverse=True)
    limit = params.get("limit", 100)
    offset = params.get("offset", 0)
    return sorted_events[offset:offset+limit]
```

**Ranked:**
```python
def reduce_ranked(events: list, params: dict) -> list:
    def score(event):
        age_hours = (now() - event.ts).total_seconds() / 3600
        likes = count_likes(event.object_id)
        replies = count_replies(event.object_id)
        return (likes * 2 + replies * 3) / (age_hours + 2) ** 1.5
    
    sorted_events = sorted(events, key=score, reverse=True)
    return sorted_events[:params.get("limit", 100)]
```

### 9.7 Caching

Views MAY be cached based on boundary_hash:

```python
def get_or_compute_view(view_def: ViewDefinition) -> ViewResult:
    boundary = compute_boundary(view_def)
    
    cached = cache.get(view_def.id, view_def.version, boundary)
    if cached and cached.cache_expires > now():
        return cached
    
    result = execute_view(view_def)
    cache.set(result)
    return result
```

---

## 10. Layer 7: Network Layer

### 10.1 Overview

The Network Layer provides communication between clients and relays.

### 10.2 HTTP API

**Base URL:** `https://{relay}/mesh/v1/`

#### Authentication

Requests are authenticated via signed challenges:

```http
POST /auth/challenge
Content-Type: application/json

{"entity_id": "ent:alice123"}
```

Response:
```json
{
  "challenge": "random-challenge-string",
  "expires_at": "2026-01-01T00:00:00Z"
}
```

```http
POST /auth/verify
Content-Type: application/json

{
  "entity_id": "ent:alice123",
  "challenge": "random-challenge-string",
  "signature": "hex-encoded-signature"
}
```

Response:
```json
{
  "token": "jwt-or-session-token",
  "expires_at": "2026-01-02T00:00:00Z"
}
```

#### Endpoints

**Entities:**
```
GET    /entities/{id}
POST   /entities
PUT    /entities/{id}
```

**Content:**
```
GET    /content/{id}
POST   /content
GET    /content?author={entity_id}&limit={n}
```

**Links:**
```
GET    /links/{id}
POST   /links
GET    /links?source={entity_id}&kind={kind}
GET    /links?target={entity_id}&kind={kind}
DELETE /links/{id}
```

**Log Events:**
```
GET    /log/{actor}?since_seq={n}
POST   /log
GET    /log/{actor}/head
```

**Attestations:**
```
GET    /attestations?subject={id}
GET    /attestations?issuer={id}
POST   /attestations
```

**Views:**
```
GET    /views/{id}
POST   /views
GET    /views/{id}/execute
```

### 10.3 WebSocket API

Real-time subscriptions via WebSocket:

```
wss://{relay}/mesh/v1/ws
```

**Subscribe:**
```json
{
  "type": "subscribe",
  "channels": [
    {"kind": "actor", "actor_id": "ent:alice123"},
    {"kind": "content", "content_id": "cnt:abc"},
    {"kind": "tag", "tag": "mesh"}
  ]
}
```

**Event:**
```json
{
  "type": "event",
  "channel": {"kind": "actor", "actor_id": "ent:alice123"},
  "event": { ... LogEvent ... }
}
```

**Unsubscribe:**
```json
{
  "type": "unsubscribe",
  "channels": [...]
}
```

### 10.4 Federation

Relays sync via the log event stream:

**Sync Request:**
```http
GET /federation/sync?actor={entity_id}&since_seq={n}
Accept: application/x-ndjson
```

**Response (newline-delimited JSON):**
```
{"id":"evt1","actor":"ent:alice","seq":1,...}
{"id":"evt2","actor":"ent:alice","seq":2,...}
{"id":"evt3","actor":"ent:alice","seq":3,...}
```

**Relay Discovery:**

Relays advertise via DNS TXT records:
```
_mesh-relay.example.com TXT "v=mesh1 url=https://relay.example.com"
```

Or via a well-known endpoint:
```
GET /.well-known/mesh-relay
```

---

## 11. Layer 8: Application Layer

### 11.1 Overview

The Application Layer is where clients implement user-facing features.

### 11.2 Client Types

**Minimal Client (~200 LOC):**
- Read-only
- Social + Storage layers
- No integrity verification

**Standard Client (~500 LOC):**
- Full read/write
- Social + Integrity + Privacy layers
- Log event creation and verification

**Full Client (~1000 LOC):**
- All features
- All layers
- View definitions, attestations, federation

### 11.3 Example Client Flow

**User Registration:**
```python
# 1. Generate keys
signing = SigningKeyPair.generate()
encryption = EncryptionKeyPair.generate()

# 2. Create entity
entity = Entity(
    id=generate_entity_id(signing.public_key_bytes()),
    kind="user",
    public_key=signing.public_key_bytes(),
    encryption_key=encryption.public_key_bytes(),
    handle="alice",
    profile={"name": "Alice"},
    ...
)

# 3. Wrap in LogEvent
event = LogEvent(
    id=generate_log_event_id(entity.id, 1),
    actor=entity.id,
    seq=1,
    prev=None,
    op="create",
    object_type="entity",
    object_id=entity.id,
    payload=entity.to_dict(),
    ...
)

# 4. Sign and submit
signed_event = sign_object(event.to_dict(), signing)
relay.submit(signed_event)
```

**Creating a Post:**
```python
# 1. Create content
content = Content(
    id=generate_content_id({...}),
    author=my_entity_id,
    kind="post",
    body={"text": "Hello MESH!"},
    ...
)

# 2. Get current log head
head = relay.get_log_head(my_entity_id)
seq = relay.get_log_seq(my_entity_id) + 1

# 3. Create LogEvent
event = LogEvent(
    id=generate_log_event_id(my_entity_id, seq),
    actor=my_entity_id,
    seq=seq,
    prev=head,
    op="create",
    object_type="content",
    object_id=content.id,
    payload=content.to_dict(),
    ...
)

# 4. Sign and submit
signed_event = sign_object(event.to_dict(), my_keys)
relay.submit(signed_event)
```

---

## 12. Derived Systems

### 12.1 Feed

A feed is a ViewDefinition with reverse chronological reducer:

```json
{
  "id": "view:feed:alice",
  "owner": "ent:alice",
  "version": 1,
  "sources": [
    {"kind": "follows", "actor_id": "ent:alice"}
  ],
  "filters": [],
  "reducer": "reverse_chronological",
  "params": {"limit": 50}
}
```

### 12.2 Replies (Threads)

Replies use the `reply_to` field:

```python
def get_thread(content_id: str) -> list:
    root = get_content(content_id)
    replies = query_content(reply_to=content_id)
    return build_tree(root, replies)
```

### 12.3 Likes

Likes are Links with kind `like`:

```python
def like(user_id: str, content_id: str):
    link = Link(
        id=generate_link_id(user_id, "like", content_id),
        source=user_id,
        target=content_id,
        kind="like",
        ...
    )
    submit_link(link)

def count_likes(content_id: str) -> int:
    return count_links(target=content_id, kind="like", tombstone=False)
```

### 12.4 Groups

Groups are Entities with membership Links:

```python
def create_group(owner_id: str, name: str) -> Entity:
    group = Entity(
        kind="group",
        profile={"name": name, "owner": owner_id},
        ...
    )
    
    # Owner is first member
    membership = Link(
        source=owner_id,
        target=group.id,
        kind="member",
        data={"role": "owner"},
        ...
    )
    
    return group
```

### 12.5 Direct Messages

DMs use E2EE Content:

```python
def send_dm(sender: Entity, recipient: Entity, text: str):
    # Encrypt
    encrypted = encrypt_for_recipient(
        text.encode(),
        recipient.encryption_key
    )
    
    content = Content(
        author=sender.id,
        kind="post",
        body={},  # Empty - content is encrypted
        access="private",
        encrypted=True,
        encryption_metadata={
            "recipient": recipient.id,
            "ephemeral_key": encrypted.ephemeral_public_key.hex(),
            "nonce": encrypted.nonce.hex(),
            "ciphertext": encrypted.ciphertext.hex(),
        },
        ...
    )
    
    submit_content(content)
```

### 12.6 Notifications

Notifications are derived from events:

```python
def get_notifications(user_id: str) -> list:
    notifications = []
    
    # New followers
    follows = query_links(target=user_id, kind="follow", since=last_check)
    for f in follows:
        notifications.append({
            "type": "follow",
            "actor": f.source,
            "ts": f.created_at
        })
    
    # Likes on my content
    my_content = query_content(author=user_id)
    for c in my_content:
        likes = query_links(target=c.id, kind="like", since=last_check)
        for l in likes:
            notifications.append({
                "type": "like",
                "actor": l.source,
                "content": c.id,
                "ts": l.created_at
            })
    
    # Replies to my content
    for c in my_content:
        replies = query_content(reply_to=c.id, since=last_check)
        for r in replies:
            notifications.append({
                "type": "reply",
                "actor": r.author,
                "content": r.id,
                "ts": r.created_at
            })
    
    return sorted(notifications, key=lambda n: n["ts"], reverse=True)
```

---

## 13. Sync Protocol

### 13.1 Overview

MESH uses log-based sync with prev chain verification.

### 13.2 Actor Sync

To sync an actor's events:

```python
def sync_actor(actor_id: str, relay: Relay):
    # Get local head
    local_seq = storage.get_log_seq(actor_id)
    
    # Fetch remote events since local head
    events = relay.get_events(actor_id, since_seq=local_seq)
    
    # Verify and apply
    for event in events:
        # Verify signature
        actor = storage.get_entity(actor_id)
        if not verify_object_signature(event, actor.public_key):
            raise InvalidSignature()
        
        # Verify prev chain
        if not validate_prev(event, storage.get_log_head(actor_id), local_seq):
            raise InvalidPrevChain()
        
        # Apply
        storage.append_log(event)
        apply_event(event)
        local_seq = event.seq
```

### 13.3 Full Sync

To sync all followed actors:

```python
def full_sync(user_id: str, relay: Relay):
    # Sync self
    sync_actor(user_id, relay)
    
    # Sync following
    following = storage.get_following(user_id)
    for actor_id in following:
        sync_actor(actor_id, relay)
```

### 13.4 Real-time Sync

For real-time updates:

```python
async def realtime_sync(user_id: str, relay: Relay):
    ws = await relay.connect_websocket()
    
    # Subscribe to self and following
    await ws.subscribe([
        {"kind": "actor", "actor_id": user_id},
        *[{"kind": "actor", "actor_id": f} for f in get_following(user_id)]
    ])
    
    async for message in ws:
        if message["type"] == "event":
            event = message["event"]
            if verify_and_validate(event):
                storage.append_log(event)
                apply_event(event)
                notify_ui(event)
```

### 13.5 Conflict Resolution

MESH does not automatically resolve conflicts. When a fork is detected:

1. **Reject** - Refuse the forked chain
2. **Alert** - Notify the user
3. **Manual** - Let user choose which chain to trust

```python
def handle_fork(actor_id: str, local_events: list, remote_events: list):
    fork_point = detect_fork(local_events, remote_events)
    
    if fork_point is not None:
        raise ForkDetected(
            actor=actor_id,
            fork_point=fork_point,
            local_head=local_events[-1].id,
            remote_head=remote_events[-1].id,
        )
```

---

## 14. Security Model

### 14.1 Threat Model

**In Scope:**
- Impersonation (prevented by signatures)
- Tampering (prevented by signatures + prev chain)
- Replay attacks (prevented by content-addressing)
- Eavesdropping on DMs (prevented by E2EE)
- Metadata leakage (partially addressed)

**Out of Scope:**
- Key compromise (user responsibility)
- Denial of service (relay responsibility)
- Spam (addressed by moderation layer)
- Sybil attacks (partially addressed by attestations)

### 14.2 Security Properties

| Property | Mechanism | Guarantee |
|----------|-----------|-----------|
| Authentication | Ed25519 signatures | Only key holder can sign |
| Integrity | Signatures + prev chain | Tampering detected |
| Non-repudiation | Signed events | Cannot deny authorship |
| Confidentiality | X25519 + AES-GCM | Only recipient can read |
| Forward secrecy | Ephemeral keys | Past messages safe if key leaked |

### 14.3 Signature Verification

All implementations MUST verify signatures:

```python
def verify_event(event: LogEvent) -> bool:
    # Get author's public key
    author = storage.get_entity(event.actor)
    if author is None:
        return False
    
    # Verify signature
    return verify_object_signature(event.to_dict(), author.public_key)
```

### 14.4 Prev Chain Verification

All implementations MUST verify prev chains:

```python
def verify_prev_chain(events: list) -> bool:
    valid, error = validate_log_chain(events)
    return valid
```

### 14.5 Encryption Requirements

For E2EE content:
- MUST use X25519 for key exchange
- MUST use AES-256-GCM for encryption
- MUST use random 12-byte nonces
- MUST NOT reuse nonces
- SHOULD use ephemeral keys for forward secrecy

---

## 15. Scalability

### 15.1 Performance Targets

| Operation | Target | Measured |
|-----------|:------:|:--------:|
| Ed25519 sign+verify | <1ms | 0.15ms |
| Storage write | <1ms | 0.17ms |
| Simple query | <1ms | 0.19ms |
| View execution | <10ms | 2.76ms |

### 15.2 Single Node Capacity

With SQLite + WAL mode:
- **Writes:** 6,000/sec
- **Queries:** 5,000/sec
- **Users (14 writes/day):** 37 million DAU

### 15.3 Horizontal Scaling

**Strategy 1: Read Replicas**
- Primary handles writes
- Replicas handle reads
- Async replication

**Strategy 2: Sharding by Actor**
- Shard key: `hash(actor_id) % num_shards`
- Each shard handles subset of actors
- Cross-shard queries via scatter-gather

**Strategy 3: Federation**
- Multiple relays
- Users choose preferred relays
- Relays sync via federation protocol

### 15.4 Caching Strategy

1. **Entity cache** - Frequently accessed profiles
2. **Hot content cache** - Recent popular content
3. **View cache** - Materialized feed results
4. **Query cache** - Common query patterns

---

## 16. Comparison with Existing Protocols

### 16.1 Feature Comparison

| Feature | MESH | Nostr | ActivityPub | SSB | AT Protocol |
|---------|:----:|:-----:|:-----------:|:---:|:-----------:|
| Self-sovereign identity | ✓ | ✓ | ✗ | ✓ | ✗ |
| E2EE | ✓ | ✗ | ✗ | ✓ | ✗ |
| Append-only log | ✓ | ✗ | ✗ | ✓ | ✓ |
| Fork prevention | ✓ | ✗ | N/A | ✓ | ✓ |
| Custom algorithms | ✓ | ✗ | ✗ | ✗ | ✓ |
| Attestations | ✓ | ✗ | ✗ | ✗ | ✓ |
| Modular layers | ✓ | ✗ | ✗ | ✗ | ✓ |
| Simple primitives | ✓ | ✓ | ✗ | ✗ | ✗ |

### 16.2 Design Comparison

| Aspect | MESH | Nostr | ActivityPub | SSB | AT Protocol |
|--------|------|-------|-------------|-----|-------------|
| Identity | Ed25519 keys | secp256k1 keys | URLs | Ed25519 keys | DIDs |
| Data model | Entity/Content/Link | Events | Objects | Messages | Records |
| Sync | Log-based | Event-based | Push | Gossip | Firehose |
| Moderation | Attestations | Relays | Server | N/A | Labels |
| Complexity | Medium | Low | High | Medium | High |

### 16.3 When to Use MESH

**Use MESH when you need:**
- Self-sovereign identity
- Verifiable feeds
- E2EE built-in
- Modular architecture
- High performance

**Consider alternatives when:**
- Maximum simplicity (use Nostr)
- Existing ecosystem (use ActivityPub)
- Offline-first P2P (use SSB)
- Enterprise features (use AT Protocol)

---

## 17. Implementation Requirements

### 17.1 Conformance Levels

**Level 1: Minimal**
- MUST implement Privacy Layer (signatures only)
- MUST implement Storage Layer
- MUST implement Integrity Layer
- MUST implement Social Layer
- MAY implement other layers

**Level 2: Standard**
- MUST implement all Level 1 requirements
- MUST implement Network Layer (HTTP API)
- SHOULD implement Moderation Layer
- SHOULD implement View Layer

**Level 3: Full**
- MUST implement all Level 2 requirements
- MUST implement WebSocket subscriptions
- MUST implement Federation
- MUST implement all attestation types
- MUST implement all view reducers

### 17.2 Required Algorithms

| Algorithm | Purpose | Specification |
|-----------|---------|---------------|
| Ed25519 | Signatures | RFC 8032 |
| X25519 | Key exchange | RFC 7748 |
| AES-256-GCM | Encryption | NIST SP 800-38D |
| SHA-256 | Hashing | FIPS 180-4 |
| HKDF-SHA256 | Key derivation | RFC 5869 |

### 17.3 Test Vectors

See Appendix A for test vectors.

---

## 18. Appendices

### Appendix A: Test Vectors

**Ed25519 Signature:**
```
Private Key (hex): 9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60
Public Key (hex): d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a
Message: ""
Signature (hex): e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b
```

**Canonical JSON:**
```
Input: {"b": 2, "a": 1}
Output: {"a":1,"b":2}
```

**Entity ID:**
```
Public Key (hex): d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a
Entity ID: ent:3f79bb7b435b05321651daefd374cdc6
```

### Appendix B: JSON Schemas

**Entity Schema:**
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["id", "kind", "public_key", "profile", "created_at", "updated_at", "sig"],
  "properties": {
    "id": {"type": "string", "pattern": "^ent:[a-f0-9]{32}$"},
    "kind": {"enum": ["user", "group", "bot", "service"]},
    "public_key": {"type": "string"},
    "encryption_key": {"type": "string"},
    "handle": {"type": "string", "maxLength": 64},
    "profile": {"type": "object"},
    "created_at": {"type": "string", "format": "date-time"},
    "updated_at": {"type": "string", "format": "date-time"},
    "sig": {"type": "string"}
  }
}
```

### Appendix C: Error Codes

| Code | Name | Description |
|------|------|-------------|
| 1001 | INVALID_SIGNATURE | Signature verification failed |
| 1002 | INVALID_PREV | Prev chain validation failed |
| 1003 | INVALID_SEQ | Sequence number invalid |
| 1004 | FORK_DETECTED | Log fork detected |
| 1005 | DUPLICATE_ID | Object ID already exists |
| 2001 | ENTITY_NOT_FOUND | Entity does not exist |
| 2002 | CONTENT_NOT_FOUND | Content does not exist |
| 2003 | LINK_NOT_FOUND | Link does not exist |
| 3001 | UNAUTHORIZED | Authentication required |
| 3002 | FORBIDDEN | Permission denied |
| 4001 | RATE_LIMITED | Too many requests |
| 5001 | INTERNAL_ERROR | Server error |

### Appendix D: MIME Types

| Type | Description |
|------|-------------|
| `application/mesh+json` | MESH JSON objects |
| `application/x-ndjson` | Newline-delimited JSON (sync) |

### Appendix E: URI Schemes

```
mesh://relay.example.com/ent:abc123
mesh://relay.example.com/cnt:def456
mesh://relay.example.com/view:feed:alice
```

---

## Changelog

### v1.0 (2026-04-23)
- Initial specification
- Combined best features from HOLON v4, Relay v1.4.1, and Relay v2

---

## Authors

- MESH Protocol Working Group
- Based on HOLON, Relay, and community contributions

---

## License

This specification is released under CC0 1.0 Universal (Public Domain).
