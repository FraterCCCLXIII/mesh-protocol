# HOLON Protocol v3.1 (Draft)

**A Three-Layer Social Protocol with Holonic Structure and Verifiable Views**

---

## Design Philosophy

> "Ship simple. Layer complexity. Verify everything."

HOLON v3.1 separates three distinct concerns into optional, composable layers:

| Layer | Purpose | Complexity | When to Adopt |
|-------|---------|------------|---------------|
| **Layer 1: Core** | Social objects | Low | Immediately |
| **Layer 2: Holonic** | Nested structure | Medium | When communities grow |
| **Layer 3: Views** | Programmable feeds | High | When curation matters |

Each layer builds on the previous. You can ship with just Layer 1.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR APPLICATION                          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3: VIEW ENGINE (optional, Relay-powered)             │
│  Programmable feeds │ Boundaries │ Verification             │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: HOLONIC STRUCTURE (optional)                      │
│  part_of │ Context stack │ Inheritance │ Subsidiarity       │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: CORE PROTOCOL                                      │
│  Entity │ Content │ Link │ Identity │ Sync │ Encryption     │
└─────────────────────────────────────────────────────────────┘
```

---

# Layer 1: Core Protocol

**Status:** Required. Ship this first.

This is FABRIC v2.2, unchanged. A complete social protocol on its own.

---

## 1.1 Primitives

| Primitive | Purpose | Examples |
|-----------|---------|----------|
| **Entity** | Actors with identity | Users, orgs, groups |
| **Content** | Publishable data | Posts, articles, media |
| **Link** | Relationships | Follow, react, subscribe |

## 1.2 Entity

```json
{
  "type": "entity",
  "id": "ent:alice",
  "kind": "user",
  "version": 1,
  "data": {
    "name": "Alice",
    "bio": "Building things"
  },
  "keys": {
    "signing": "ed25519:...",
    "encryption": "x25519:..."
  },
  "sig": "ed25519:..."
}
```

**Kinds:** `user`, `org`, `group`

## 1.3 Content

```json
{
  "type": "content",
  "id": "cnt:post123",
  "kind": "post",
  "author": "ent:alice",
  "created": "2026-04-23T12:00:00Z",
  "schema": "social.post.v1",
  "data": {
    "text": "Hello world!",
    "media": []
  },
  "access": {"type": "public"},
  "sig": "ed25519:..."
}
```

**Kinds:** `post`, `media`, `structured`

## 1.4 Link

```json
{
  "type": "link",
  "id": "lnk:follow123",
  "kind": "relationship",
  "source": "ent:alice",
  "target": "ent:bob",
  "data": {"subkind": "follow"},
  "sig": "ed25519:..."
}
```

**Kinds:** `relationship`, `interaction`, `credential`

## 1.5 Identity & Encryption

- Email-derived or key-derived identifiers
- Provider custody or self-custody
- Key rotation with explicit deprecation
- Encryption as access layer (public, private, group, paid)

## 1.6 Sync

- Pull-based with sequence cursors
- Per-relay cursor tracking
- Client deduplication by object ID

## 1.7 What Layer 1 Delivers

With just Layer 1, you can build:
- Blogs
- Social networks
- Group chats
- Paid newsletters
- Learning platforms

**This is a complete protocol.** Layers 2 and 3 add power, not necessity.

---

# Layer 2: Holonic Structure

**Status:** Optional. Adopt when communities need nesting.

---

## 2.1 The Holon Concept

Every entity can be:
- A **whole** with its own identity and sovereignty
- A **part** of a larger entity

```
ent:alice (user)
    ↓ part_of
ent:rust-devs (group)
    ↓ part_of
ent:tech-community (org)
```

## 2.2 The `part_of` Relationship

New Link subkind:

```json
{
  "type": "link",
  "kind": "relationship",
  "source": "ent:rust-devs",
  "target": "ent:tech-community",
  "data": {
    "subkind": "part_of",
    "inherits": ["visibility"]
  },
  "sig": "ed25519:..."
}
```

**Rules:**
- Creates a directed acyclic graph (DAG)
- No cycles allowed
- An entity can have multiple parents

## 2.3 Context Stack

Content exists within a context stack:

```json
{
  "type": "content",
  "kind": "post",
  "author": "ent:alice",
  "context": "ent:rust-devs",
  "data": {"text": "Check out this crate!"}
}
```

**Context resolution:**
1. Primary context: `ent:rust-devs`
2. Parent context: Follow `part_of` links upward
3. Full stack: `[ent:rust-devs, ent:tech-community, ...]`

**Limitation (v3.1):** Context stack is computed, not stored. Maximum depth: 5 levels.

## 2.4 Inheritance Rules

**Strict rule: Child overrides parent.**

When child and parent policies conflict:
- Child policy wins
- No ambiguity

| Inheritance | Behavior |
|-------------|----------|
| `visibility` | Child can restrict, not expand |
| `moderation` | Child labels apply first |
| `membership` | Not inherited (each holon manages its own) |

**What is NOT inherited:**
- Membership
- Content
- Keys
- Reputation (see section 2.6)

## 2.5 Subsidiarity Moderation

Moderation decisions happen at the smallest competent level first:

```
Resolution order:
1. Thread level (OP can moderate replies)
2. Group level (group mods)
3. Parent level (org admins)
4. Client level (user preferences)
```

**Labels are scoped:**

```json
{
  "type": "link",
  "kind": "interaction",
  "source": "ent:rust-devs-mod",
  "target": "cnt:off-topic-post",
  "data": {
    "subkind": "label",
    "labels": [{"name": "off-topic"}],
    "scope": "ent:rust-devs"
  }
}
```

This label applies in `ent:rust-devs` but not globally.

## 2.6 Reputation: NOT a Protocol Primitive

**Critical design decision:** HOLON does NOT define a `trust()` function in the protocol.

**Why:**
- Computing scoped reputation requires either:
  - A centralized oracle (defeats decentralization)
  - Distributed consensus (too slow/complex)
  - Full local history (impractical storage)
- Reputation is a **policy choice**, not a protocol primitive

**Instead, HOLON provides query primitives:**

```
// Client can query:
count(posts, author=ent:alice, context=ent:rust-devs)
count(reactions, target=ent:alice, context=ent:rust-devs, sentiment=positive)
count(labels, target=ent:alice, label=spam)

// Client computes trust locally:
trust = positive_reactions / total_reactions
```

**Result:** Reputation emerges from application logic, not protocol magic. Different clients can use different algorithms.

## 2.7 Holonic Entity Fields

Entities gain optional fields:

```json
{
  "type": "entity",
  "id": "ent:rust-devs",
  "kind": "group",
  "data": {
    "name": "Rust Developers",
    "parent": "ent:tech-community",
    "policies": {
      "visibility": "public",
      "join": "open",
      "posting": "members"
    }
  }
}
```

## 2.8 What Layer 2 Delivers

With Layers 1 + 2, you can build:
- Nested communities (subreddits within orgs)
- Local moderation without global consensus
- Context-aware content visibility
- Organic federation

---

# Layer 3: View Engine

**Status:** Optional. Adopt when transparent curation matters.

This layer is powered by concepts from Relay v2.

---

## 3.1 Views as First-Class Objects

A View is a **portable, verifiable, subscribable feed definition**:

```json
{
  "type": "view",
  "id": "view:quality-rust-feed",
  "author": "ent:curator",
  "name": "Quality Rust Content",
  "version": 1,
  
  "source": {
    "type": "context_tree",
    "root": "ent:rust-devs",
    "depth": 2
  },
  
  "filter": [
    {"field": "kind", "op": "in", "value": ["post", "article"]},
    {"field": "created", "op": ">", "value": "now-7d"}
  ],
  
  "sort": [
    {"field": "reaction_count", "order": "desc"},
    {"field": "created", "order": "desc"}
  ],
  
  "limit": 50,
  
  "sig": "ed25519:curator..."
}
```

## 3.2 View Properties

| Property | Description | Required |
|----------|-------------|----------|
| `source` | Where to pull content from | Yes |
| `filter` | Conditions content must match | No |
| `sort` | Ordering rules | No |
| `limit` | Maximum results | No (default: 100) |

## 3.3 View Sources

```json
// Content from followed entities
{"type": "follows", "of": "ent:me"}

// Content in a specific holon
{"type": "context", "holon": "ent:rust-devs"}

// Content in holon tree (with Layer 2)
{"type": "context_tree", "root": "ent:rust-devs", "depth": 2}

// Union of multiple sources
{"type": "union", "sources": [
  {"type": "context", "holon": "ent:rust-devs"},
  {"type": "context", "holon": "ent:go-devs"}
]}
```

## 3.4 View Filters

```json
// Content type
{"field": "kind", "op": "in", "value": ["post", "article"]}

// Time range
{"field": "created", "op": ">", "value": "now-24h"}

// Engagement threshold (uses aggregates)
{"field": "reaction_count", "op": ">", "value": 10}

// Exclude labeled content
{"field": "labels", "op": "excludes", "value": ["spam"]}

// Author filter
{"field": "author", "op": "in", "value": ["ent:trusted1", "ent:trusted2"]}
```

**Note:** No `trust()` function in filters. Clients pre-compute trusted author lists.

## 3.5 Boundaries (from Relay v2)

For verification, views execute against a **bounded input set**:

```json
{
  "type": "view_execution",
  "view": "view:quality-rust-feed",
  "boundary": {
    "snapshot_id": "snap:rust-devs-2026-04-23",
    "event_range": {
      "from_seq": 10000,
      "to_seq": 15000
    },
    "computed_at": "2026-04-23T12:00:00Z"
  },
  "results": ["cnt:post1", "cnt:post2", ...],
  "result_hash": "sha256:..."
}
```

**Boundary properties:**
- Defines exactly what data the view was computed over
- Anyone with the same boundary can recompute and verify
- Prevents "my feed is different than yours" disputes

## 3.6 Verification

```python
def verify_view_execution(execution, data_source):
    # 1. Fetch the bounded data
    data = data_source.fetch(execution.boundary)
    
    # 2. Recompute the view
    view = fetch_view(execution.view)
    recomputed = execute_view(view, data)
    
    # 3. Compare hashes
    return hash(recomputed) == execution.result_hash
```

## 3.7 View Execution Environment

**Determinism requirements:**
- Same view + same boundary = same results
- No external calls
- No randomness
- No current time (use boundary timestamp)

**Implementation options:**
- JSON-based declarative (as shown above)
- WASM sandbox (for complex logic)
- SQL-like DSL

**v3.1 specifies JSON-based only.** WASM is future work.

## 3.8 View Subscription

Users can subscribe to views:

```json
{
  "type": "link",
  "kind": "relationship",
  "source": "ent:alice",
  "target": "view:quality-rust-feed",
  "data": {"subkind": "subscribe"}
}
```

**This enables:**
- Follow curators, not just authors
- Algorithm markets
- Transparent ranking

## 3.9 View Forking

Users can fork and modify views:

```json
{
  "type": "view",
  "id": "view:my-rust-feed",
  "author": "ent:alice",
  "forked_from": "view:quality-rust-feed",
  "filter": [
    {"field": "kind", "op": "in", "value": ["post", "article"]},
    {"field": "created", "op": ">", "value": "now-7d"},
    {"field": "author", "op": "in", "value": ["ent:favorite1", "ent:favorite2"]}
  ]
}
```

## 3.10 Caching and TTL

Views can specify caching hints:

```json
{
  "type": "view",
  "id": "view:trending",
  "cache": {
    "ttl": "5m",
    "stale_while_revalidate": "1m"
  }
}
```

## 3.11 What Layer 3 Delivers

With all three layers:
- Transparent, auditable algorithms
- Verifiable feeds (no black boxes)
- Algorithm markets (subscribe to curators)
- Forkable curation (modify existing feeds)
- Decentralized recommendation

---

# Layer Integration

---

## How Layers Compose

| With | You Get |
|------|---------|
| Layer 1 only | Simple social network |
| Layer 1 + 2 | Nested communities with local moderation |
| Layer 1 + 3 | Verifiable feeds without nesting |
| Layer 1 + 2 + 3 | Full holonic social with transparent curation |

## Cross-Layer Queries

Layer 3 views can reference Layer 2 concepts:

```json
{
  "source": {"type": "context_tree", "root": "ent:rust-devs", "depth": 2}
}
```

If Layer 2 is not adopted, `context_tree` degrades to `context` (single holon).

---

# Relay v2 Integration

---

## Relay as the Computation Engine

HOLON defines **what** (social objects, structure, views).
Relay provides **how** (execution, boundaries, verification).

| HOLON Concept | Relay Equivalent |
|---------------|------------------|
| Content | Event / State |
| Link | Event |
| Credential | Attestation |
| View | ViewDefinition |
| View execution | Boundary-scoped computation |
| Aggregates | State snapshots |

## Mapping HOLON Views to Relay

A HOLON View compiles to a Relay ViewDefinition:

```
HOLON View (high-level, user-friendly)
         ↓ compile
Relay ViewDefinition (low-level, executable)
         ↓ execute
Relay Boundary (finite input set)
         ↓ compute
Results (verifiable)
```

## Why This Split?

- **HOLON** stays approachable for product developers
- **Relay** provides formal verification for those who need it
- Most apps never touch Relay directly
- Power users can audit using Relay primitives

---

# API Reference

---

## Layer 1 API

```
POST   /entities                Create entity
GET    /entities/{id}           Get entity
GET    /content/{id}            Get content
POST   /content                 Create content
GET    /links?source={id}       Get links from entity
POST   /links                   Create link
```

## Layer 2 API

```
GET    /entities/{id}/parents   Get parent holons
GET    /entities/{id}/children  Get child holons
GET    /entities/{id}/context   Get full context stack
GET    /content?context={id}    Get content in holon
```

## Layer 3 API

```
POST   /views                   Create view
GET    /views/{id}              Get view definition
GET    /views/{id}/execute      Execute view (with boundary)
GET    /views/{id}/results      Get cached results
POST   /views/{id}/verify       Verify execution
GET    /views?subscribed        Get subscribed views
```

---

# Comparison

---

| Feature | HOLON v3.1 | FABRIC v2.2 | Relay v2 | Nostr | AT Protocol |
|---------|------------|-------------|----------|-------|-------------|
| Simple core | ✓ | ✓ | ✗ | ✓ | ✗ |
| Nested structure | ✓ (L2) | ✗ | ✗ | ✗ | ✗ |
| Programmable views | ✓ (L3) | ✗ | ✓ | ✗ | ✗ |
| Verifiable feeds | ✓ (L3) | ✗ | ✓ | ✗ | ✗ |
| Algorithm markets | ✓ (L3) | ✗ | ✗ | ✗ | ✗ |
| Layered adoption | ✓ | ✗ | ✗ | ✗ | ✗ |

---

# Migration Path

---

## From FABRIC v2.2

1. **Immediate:** All v2.2 content is valid Layer 1
2. **Optional:** Add `part_of` links for nesting (Layer 2)
3. **Optional:** Add Views for curation (Layer 3)

## For New Implementations

1. **Week 1:** Implement Layer 1 (ship basic social)
2. **Month 1:** Add Layer 2 if communities request nesting
3. **Later:** Add Layer 3 when algorithm transparency matters

---

# Summary

---

## The Three Layers

| Layer | Adds | Complexity |
|-------|------|------------|
| **1: Core** | Social objects | Low |
| **2: Holonic** | Nested structure | Medium |
| **3: Views** | Programmable feeds | High |

## Key Design Decisions

1. **Reputation is NOT a protocol primitive** — provide query primitives, let clients compute trust
2. **Child always overrides parent** — no ambiguous inheritance
3. **Views are deterministic** — same inputs = same outputs
4. **Boundaries enable verification** — finite input sets for auditability
5. **Relay powers Layer 3** — formal verification without burdening the core

## What Makes This Different

1. **Layered adoption** — ship simple, add complexity incrementally
2. **Holonic structure** — nested communities with local sovereignty
3. **Verifiable views** — no black-box algorithms
4. **Relay integration** — formal verification when needed

## The Paradigm Shift

> "Social systems should be structured like human communities: nested, local-first, transparent."

HOLON v3.1 makes this possible without overwhelming complexity.

---

*Protocol version: 3.1 (Draft)*
*Status: Experimental*
*License: CC0 (Public Domain)*
