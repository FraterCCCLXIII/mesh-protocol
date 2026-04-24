# Unified Protocol Design: MESH v1.0

## Executive Summary

After testing HOLON v4, Relay v1.4.1, and Relay v2, the best protocol combines:

| From | What to Take | Why |
|------|--------------|-----|
| **HOLON v4** | Simple primitives, fast queries, group encryption | Developer UX, performance |
| **Relay v1.4.1** | Prev chain, commitment_hash, fork prevention | Integrity guarantees |
| **Relay v2** | Two-layer architecture, attestations, boundary determinism | Verification, extensibility |

---

## The Core Insight

The three protocols aren't competing approaches—they're **different layers** of the same system:

```
HOLON v4      = Simple data model (what to store)
Relay v1.4.1  = Integrity guarantees (how to trust it)
Relay v2      = Derived views (how to query it)
```

A unified protocol uses all three, properly layered.

---

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                              │
│        (Clients: mobile, web, desktop, bots, VR)                    │
│   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│   │   Mobile    │ │     Web     │ │   Desktop   │ │     Bot     │  │
│   └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                        VIEW LAYER (from Relay v2)                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  ViewDefinitions → Reducers → Materialized Feeds             │  │
│  │  • Boundary determinism (same input = same output)           │  │
│  │  • Cached views for performance                              │  │
│  │  • Client-defined algorithms                                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                    MODERATION LAYER (hybrid)                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Attestations (from Relay v2) + Labels + Reputation          │  │
│  │  • Third-party claims without modifying facts                │  │
│  │  • Composable trust networks                                 │  │
│  │  • Client-side filtering                                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                     SOCIAL LAYER (from HOLON v4)                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Three primitives: Entity, Content, Link                     │  │
│  │  • Entity = identity (user, group, bot)                      │  │
│  │  • Content = posts, replies, media                           │  │
│  │  • Link = relationships (follow, like, membership)           │  │
│  │  • Fast graph queries (0.10ms)                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                  INTEGRITY LAYER (from Relay v1.4.1)                │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Append-only log with prev chain                             │  │
│  │  • Every event references previous (fork prevention)         │  │
│  │  • commitment_hash for action verification                   │  │
│  │  • Sequence numbers for sync                                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                      PRIVACY LAYER (from HOLON v4)                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  • Ed25519 signatures (identity)                             │  │
│  │  • X25519 key exchange (DMs)                                 │  │
│  │  • AES-256-GCM encryption                                    │  │
│  │  • Group keys with rotation                                  │  │
│  │  • Access control (public/private/group)                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                       STORAGE LAYER (unified)                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  • SQLite with WAL mode (single node)                        │  │
│  │  • Content-addressed IDs (hash of content)                   │  │
│  │  • Indexes for fast queries                                  │  │
│  │  • Optional: PostgreSQL, distributed DB                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                      NETWORK LAYER (unified)                        │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  • HTTP API (request/response)                               │  │
│  │  • WebSocket (real-time subscriptions)                       │  │
│  │  • Federation (relay-to-relay sync via prev chain)           │  │
│  │  • Optional: libp2p, Bluetooth, sneakernet                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Primitives (6 total)

### Layer 1: Truth (Immutable Facts)

```typescript
// From HOLON v4 - simplified
interface Entity {
  id: string;              // hash(public_key)
  kind: "user" | "group" | "bot" | "service";
  public_key: bytes;       // Ed25519
  encryption_key?: bytes;  // X25519
  profile: object;         // Mutable via State
  sig: bytes;
}

interface Content {
  id: string;              // hash(author + body + created_at)
  author: string;          // entity_id
  kind: "post" | "reply" | "media" | "reaction";
  body: object;
  reply_to?: string;       // content_id
  created_at: timestamp;
  access: "public" | "private" | "group";
  sig: bytes;
}

interface Link {
  id: string;              // hash(source + kind + target)
  source: string;          // entity_id
  target: string;          // entity_id or content_id
  kind: "follow" | "like" | "member" | "block" | "pin";
  data?: object;
  tombstone: boolean;      // Soft delete
  sig: bytes;
}
```

### Layer 2: Integrity (From Relay v1.4.1)

```typescript
// Append-only event wrapper
interface LogEvent {
  id: string;              // hash(actor + seq)
  actor: string;           // entity_id
  seq: number;             // Monotonic sequence
  prev: string | null;     // Previous event ID (fork prevention)
  
  // The actual change
  op: "create" | "update" | "delete";
  object_type: "entity" | "content" | "link" | "state";
  object_id: string;
  payload: object;
  
  ts: timestamp;
  sig: bytes;
}

// For action verification
function commitment_hash(event_id, action_type, input_refs, params): string {
  return sha256(canonical_json({event_id, action_type, input_refs, params}));
}
```

### Layer 3: Derived (From Relay v2)

```typescript
// Attestations - third-party claims
interface Attestation {
  id: string;
  issuer: string;          // Who made this claim
  subject: string;         // Who/what is it about
  type: "trust" | "label" | "badge" | "block";
  claim: object;
  expires_at?: timestamp;
  sig: bytes;
}

// View definitions - derived feeds
interface ViewDefinition {
  id: string;
  owner: string;
  version: number;         // Must increment
  
  sources: Source[];       // What to include
  filters: Filter[];       // What to exclude
  reducer: "chronological" | "ranked" | "grouped" | "custom";
  
  sig: bytes;
}

// Deterministic result
interface ViewResult {
  view_id: string;
  boundary_hash: string;   // hash(sorted event_ids + actor_heads)
  result_hash: string;     // hash(output)
  event_ids: string[];
  computed_at: timestamp;
}
```

### Layer 4: Privacy (From HOLON v4)

```typescript
interface GroupKey {
  group_id: string;
  version: number;
  key: bytes;              // AES-256 key
  members: string[];       // Who has access
  created_at: timestamp;
}

interface EncryptedContent {
  content_id: string;
  access_type: "dm" | "group";
  
  // For DMs
  recipient_key?: bytes;   // X25519 public key
  ephemeral_key?: bytes;   // Sender's ephemeral
  
  // For groups
  group_id?: string;
  key_version?: number;
  
  nonce: bytes;
  ciphertext: bytes;
}
```

---

## How They Compose

### Example: Creating a Post

```
1. PRIVACY LAYER
   - Sign content with Ed25519 key
   - If private: encrypt with group key

2. SOCIAL LAYER
   - Create Content object
   - Generate content_id = hash(author + body + ts)

3. INTEGRITY LAYER
   - Wrap in LogEvent
   - Set prev = current head
   - Increment seq
   - Compute commitment_hash

4. STORAGE LAYER
   - Write to SQLite with WAL
   - Update indexes

5. NETWORK LAYER
   - Broadcast to subscribers
   - Queue for federation

6. VIEW LAYER
   - Invalidate affected views
   - Update materialized feeds

7. APPLICATION LAYER
   - UI updates via WebSocket
```

### Example: Loading a Feed

```
1. APPLICATION LAYER
   - Request feed for user

2. VIEW LAYER
   - Check ViewDefinition
   - If cached + valid boundary: return cached
   - Else: execute reducer

3. MODERATION LAYER
   - Apply attestation filters
   - Filter blocked/muted

4. SOCIAL LAYER
   - Query Links (follows)
   - Query Content (posts from followed)

5. INTEGRITY LAYER
   - Verify signatures
   - Verify prev chain

6. Return to client
```

---

## Module Interfaces

Each layer exposes a clean interface. Clients choose which layers to use.

### Minimal Client (read-only)
```typescript
// Just Social + Storage
const client = mesh.connect({ layers: ["social", "storage"] });
const posts = await client.content.list({ author: "alice" });
```

### Standard Client (most apps)
```typescript
// Social + Integrity + Privacy + Storage
const client = mesh.connect({ 
  layers: ["social", "integrity", "privacy", "storage"] 
});

await client.post({ text: "Hello world" });  // Creates LogEvent with prev
await client.dm(bob, { text: "Secret" });    // E2EE with X25519
```

### Full Client (power users)
```typescript
// All layers
const client = mesh.connect({ layers: "all" });

// Custom views
await client.views.create({
  sources: [{ kind: "follows", actor: "me" }],
  filters: [{ attestations: { type: "block", from: ["trusted-labelers"] } }],
  reducer: "ranked",
});
```

---

## What Each Protocol Contributes

### From HOLON v4 ✓
- **Entity/Content/Link primitives** → Simple mental model
- **Fast graph queries** → 0.10ms lookups
- **Group encryption** → Private groups work
- **HTTP/WebSocket API** → Standard interfaces
- **Tombstone deletion** → Soft deletes

### From Relay v1.4.1 ✓
- **Prev chain** → Fork prevention, append-only
- **commitment_hash** → Action verification
- **Sequence numbers** → Efficient sync
- **Channel genesis** → Deterministic group creation
- **Log-based replication** → Federation

### From Relay v2 ✓
- **Two-layer architecture** → Truth vs Views
- **Attestations** → Third-party claims
- **Boundary determinism** → Verifiable feeds
- **ViewDefinitions** → Client-defined algorithms
- **Result caching** → Performance optimization

---

## File Structure

```
mesh-protocol/
├── spec/
│   ├── 00-overview.md
│   ├── 01-primitives.md          # Entity, Content, Link
│   ├── 02-integrity.md           # LogEvent, prev chain
│   ├── 03-privacy.md             # Encryption, keys
│   ├── 04-views.md               # ViewDefinition, reducers
│   ├── 05-attestations.md        # Third-party claims
│   ├── 06-network.md             # HTTP, WebSocket, federation
│   └── 07-storage.md             # SQLite, indexes
│
├── impl/
│   ├── core/
│   │   ├── crypto.py             # Ed25519, X25519, AES-GCM
│   │   ├── primitives.py         # Entity, Content, Link
│   │   └── canonical.py          # JSON canonicalization
│   │
│   ├── integrity/
│   │   ├── log.py                # LogEvent, prev chain
│   │   └── commitment.py         # commitment_hash
│   │
│   ├── privacy/
│   │   ├── dm.py                 # Direct messages
│   │   └── groups.py             # Group keys
│   │
│   ├── views/
│   │   ├── definitions.py        # ViewDefinition
│   │   ├── reducers.py           # Chronological, ranked, etc.
│   │   └── cache.py              # Materialized views
│   │
│   ├── moderation/
│   │   ├── attestations.py       # Third-party claims
│   │   └── filters.py            # Block, mute, labels
│   │
│   ├── storage/
│   │   ├── sqlite.py             # SQLite backend
│   │   └── indexes.py            # Query optimization
│   │
│   └── network/
│       ├── http.py               # REST API
│       ├── websocket.py          # Real-time
│       └── federation.py         # Relay-to-relay
│
├── clients/
│   ├── minimal/                  # Read-only, ~200 LOC
│   ├── standard/                 # Full features, ~500 LOC
│   └── full/                     # All layers, ~1000 LOC
│
└── tests/
    ├── adversarial/              # Security tests
    ├── integration/              # Feature tests
    └── load/                     # Scale tests
```

---

## Key Design Decisions

### 1. Prev Chain is Required (from Relay v1.4.1)
```
Every write MUST reference the previous event.
This gives us:
  ✓ Fork prevention
  ✓ Append-only guarantee
  ✓ Efficient sync (just send seq > N)
  ✓ Audit trail

Cost: One extra field per event (~32 bytes)
```

### 2. Views are Optional (from Relay v2)
```
Simple clients can skip the view layer.
Power users get:
  ✓ Custom algorithms
  ✓ Boundary determinism
  ✓ Cached feeds

Cost: Query latency (6ms vs 0.1ms)
Mitigation: Materialized views for common patterns
```

### 3. Attestations are Separate (from Relay v2)
```
Third-party claims NEVER modify facts.
This gives us:
  ✓ Labels without censorship
  ✓ Reputation without central authority
  ✓ Composable trust networks

How: Attestations are their own primitive
```

### 4. Encryption is Built-in (from HOLON v4)
```
Not an afterthought. First-class support for:
  ✓ DMs (X25519 + AES-GCM)
  ✓ Private groups (rotating group keys)
  ✓ Access control on content

How: Privacy layer below social layer
```

### 5. Storage is Pluggable
```
SQLite for single node (most use cases)
PostgreSQL for larger deployments
Distributed DB for massive scale

Interface is the same regardless.
```

---

## Migration Path

### If you built on HOLON v4:
```
Add:
  - LogEvent wrapper around writes (integrity layer)
  - prev chain tracking
  - Optional: ViewDefinitions for custom feeds

Keep:
  - Entity/Content/Link primitives
  - Group encryption
  - HTTP/WebSocket API
```

### If you built on Relay v1.4.1:
```
Add:
  - Attestations (moderation layer)
  - ViewDefinitions (view layer)
  - Group encryption (privacy layer)

Keep:
  - LogEvent with prev chain
  - commitment_hash
  - Channel genesis
```

### If you built on Relay v2:
```
Add:
  - prev chain to events (integrity layer)
  - Group encryption (privacy layer)
  - HTTP/WebSocket API (network layer)

Keep:
  - Two-layer architecture
  - Attestations
  - ViewDefinitions
```

---

## Performance Expectations

| Operation | Time | Layer |
|-----------|:----:|:-----:|
| Ed25519 sign | 0.12ms | Privacy |
| Ed25519 verify | 0.11ms | Privacy |
| Content write | 0.14ms | Storage (WAL) |
| Simple query | 0.10ms | Social |
| View execution | 5-10ms | View |
| commitment_hash | 0.01ms | Integrity |

| Scale | Nodes | Cost |
|-------|:-----:|:----:|
| 100K users | 1 | $20/mo |
| 1M users | 1-2 | $100/mo |
| 10M users | 5-10 | $2K/mo |
| 100M users | 50+ | $50K/mo |

---

## Summary

**The unified MESH protocol is:**

1. **Simple** - HOLON's 3 primitives at the core
2. **Trustworthy** - Relay v1.4.1's prev chain for integrity
3. **Flexible** - Relay v2's views for customization
4. **Private** - HOLON's encryption built-in
5. **Modular** - Use only what you need

**The key insight:** These aren't competing protocols. They're complementary layers that compose into a complete system.
