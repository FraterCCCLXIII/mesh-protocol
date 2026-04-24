# HOLON Protocol v3.2

**A Complete Social Protocol with Holonic Structure and Verifiable Views**

---

## Introduction

HOLON is a three-layer protocol for decentralized social applications. Each layer is independent and optional beyond the first.

| Layer | Name | Purpose | Required |
|-------|------|---------|----------|
| 1 | **Object Layer** | Social objects and identity | Yes |
| 2 | **Structure Layer** | Holonic nesting and context | No |
| 3 | **View Layer** | Programmable, verifiable feeds | No |

**Design philosophy:** Ship simple, layer complexity, verify everything.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR APPLICATION                          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  VIEW LAYER (optional)                                       │
│  Programmable feeds │ Boundaries │ Verification             │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  STRUCTURE LAYER (optional)                                  │
│  Holonic nesting │ Context │ Inheritance │ Local moderation │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  OBJECT LAYER (required)                                     │
│  Entity │ Content │ Link │ Identity │ Encryption │ Sync     │
└─────────────────────────────────────────────────────────────┘
```

---

# OBJECT LAYER

The foundation. Defines social objects, identity, and data sync.

---

## 1. Core Primitives

Three primitives describe all social data:

| Primitive | Purpose | Examples |
|-----------|---------|----------|
| **Entity** | Actors with identity | Users, organizations, groups |
| **Content** | Publishable data | Posts, articles, media, courses |
| **Link** | Directed relationships | Follow, react, subscribe, membership |

---

## 2. Entity

An Entity is an actor with cryptographic identity.

### 2.1 Entity Structure

```json
{
  "type": "entity",
  "id": "ent:alice",
  "kind": "user",
  "version": 1,
  "created": "2026-04-01T00:00:00Z",
  "updated": "2026-04-23T12:00:00Z",
  "data": {
    "name": "Alice",
    "bio": "Building decentralized systems",
    "avatar": "cid:bafybeif..."
  },
  "keys": {
    "signing": "ed25519:abc123...",
    "encryption": "x25519:def456..."
  },
  "sig": "ed25519:..."
}
```

### 2.2 Entity Kinds

| Kind | Purpose | Data Fields |
|------|---------|-------------|
| `user` | Individual person | name, bio, avatar |
| `org` | Organization or publication | name, description, logo, tiers |
| `group` | Community or team | name, description, visibility, join_policy, posting_policy |

### 2.3 Entity ID Format

```
ent:{identifier}

Examples:
ent:alice                    # Simple identifier
ent:did:key:z6Mk...          # DID-based
ent:email:alice@example.com  # Email-derived (provider custody)
```

### 2.4 Entity Versioning

Entities are mutable. `version` increments on each update.

**Conflict resolution:** Highest `version` wins. If tied, latest `updated` wins. If still tied, lexicographically lower `id` wins.

---

## 3. Content

Content is publishable data with an author.

### 3.1 Content Structure

```json
{
  "type": "content",
  "id": "cnt:post123",
  "kind": "post",
  "schema": "social.post.v1",
  "author": "ent:alice",
  "created": "2026-04-23T12:00:00Z",
  "context": "ent:rust-devs",
  "reply_to": "cnt:parent-post",
  "thread_root": "cnt:original-post",
  "access": {
    "type": "public"
  },
  "data": {
    "_display": {
      "summary": "Check out this new Rust crate!"
    },
    "text": "Check out this new Rust crate for async programming...",
    "media": [],
    "tags": ["rust", "async"]
  },
  "sig": "ed25519:..."
}
```

### 3.2 Content Kinds

| Kind | Purpose | Common Schemas |
|------|---------|----------------|
| `post` | Short-form content | social.post.v1 |
| `media` | Images, video, audio | media.image.v1, media.video.v1 |
| `structured` | Complex data | blog.article.v1, lms.course.v1 |

### 3.3 Content ID Format

```
cnt:{hash}

The hash is computed from: author + created + kind + data
This ensures content-addressability.
```

### 3.4 The `_display` Convention

For forward compatibility, content SHOULD include `_display` in data:

```json
{
  "data": {
    "_display": {
      "title": "Optional title",
      "summary": "Plain text summary",
      "thumbnail": "cid:..."
    },
    // ... schema-specific fields
  }
}
```

Clients that don't understand a schema fall back to `_display`.

### 3.5 Access Control

| Type | Description | Encrypted |
|------|-------------|-----------|
| `public` | Anyone can read | No |
| `private` | Only specified entities | Yes |
| `group` | Only group members | Yes |
| `paid` | Only subscribers at tier | Yes |

**Public access:**
```json
{"access": {"type": "public"}}
```

**Private access:**
```json
{
  "access": {
    "type": "private",
    "recipients": ["ent:bob", "ent:carol"]
  },
  "encrypted": {
    "algorithm": "x25519-xsalsa20-poly1305",
    "recipient_keys": {
      "ent:bob": "encrypted_key_for_bob",
      "ent:carol": "encrypted_key_for_carol"
    },
    "ciphertext": "base64..."
  }
}
```

**Group access:**
```json
{
  "access": {
    "type": "group",
    "group": "ent:rust-devs"
  },
  "encrypted": {
    "ciphertext": "base64...",
    "group_key_version": 3
  }
}
```

**Paid access:**
```json
{
  "access": {
    "type": "paid",
    "entity": "ent:premium-news",
    "min_tier": "premium"
  },
  "encrypted": {
    "ciphertext": "base64...",
    "tier_key_version": 2
  }
}
```

---

## 4. Link

A Link is a directed relationship between objects.

### 4.1 Link Structure

```json
{
  "type": "link",
  "id": "lnk:follow123",
  "kind": "relationship",
  "source": "ent:alice",
  "target": "ent:bob",
  "created": "2026-04-23T12:00:00Z",
  "data": {
    "subkind": "follow"
  },
  "sig": "ed25519:..."
}
```

### 4.2 Link Kinds

| Kind | Purpose | Signed By |
|------|---------|-----------|
| `relationship` | Social connections | Source entity |
| `interaction` | Actions on content | Source entity |
| `credential` | Third-party attestations | Attestor (NOT source) |

### 4.3 Relationship Subkinds

| Subkind | Description | Source → Target |
|---------|-------------|-----------------|
| `follow` | Follow entity | User → User/Org/Group |
| `block` | Block entity | User → User |
| `mute` | Mute entity | User → User |
| `membership_request` | Request to join | User → Group |

### 4.4 Interaction Subkinds

| Subkind | Description | Source → Target |
|---------|-------------|-----------------|
| `react` | Reaction to content | User → Content |
| `bookmark` | Save content | User → Content |
| `report` | Report content | User → Content |
| `label` | Label content (moderation) | User/Service → Content |

### 4.5 Credential Subkinds

| Subkind | Description | Signed By |
|---------|-------------|-----------|
| `membership` | Confirmed group member | Group admin |
| `subscription` | Paid subscription | Payment attestor |
| `enrollment` | Course enrollment | Course provider |
| `certificate` | Achievement/completion | Issuer |
| `key_rotation` | Key rotation proof | Old key (exception) |

### 4.6 The Signing Rule

**Rule:** Who makes the claim signs the link.

- **Relationship:** Source signs ("I follow Bob")
- **Interaction:** Source signs ("I liked this post")
- **Credential:** Third party signs ("Alice is a member")

**Exception:** `key_rotation` credentials are signed by the old key to prove possession.

### 4.7 Link Lifecycle

Links are **append-only**. To "undo" a link, create a tombstone:

```json
{
  "type": "link",
  "kind": "relationship",
  "source": "ent:alice",
  "target": "ent:bob",
  "data": {
    "subkind": "follow",
    "tombstone": true
  }
}
```

---

## 5. Identity

### 5.1 Two Modes

| Mode | Control | Key Management | UX |
|------|---------|----------------|-----|
| **Provider custody** | Provider holds keys | Automatic | Email login |
| **Self-custody** | User holds keys | Manual | Key management |

### 5.2 Email-Derived Identity

For easy onboarding:
```
ent:email:alice@example.com
```

Provider generates and stores keys. User can migrate to self-custody later.

### 5.3 Key-Derived Identity

For self-custody:
```
ent:did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK
```

### 5.4 Key Rotation

Keys can be rotated with explicit deprecation:

```json
{
  "type": "link",
  "kind": "credential",
  "source": "ent:alice",
  "target": "ent:alice",
  "data": {
    "subkind": "key_rotation",
    "new_signing_key": "ed25519:new...",
    "new_encryption_key": "x25519:new...",
    "revoked_keys": ["ed25519:old..."],
    "effective_from": "2026-04-23T12:00:00Z"
  },
  "sig": "ed25519:old..."
}
```

Signed by the OLD key to prove possession.

---

## 6. Encryption

### 6.1 Algorithms

- **Key exchange:** X25519
- **Symmetric encryption:** XSalsa20-Poly1305
- **Signing:** Ed25519

### 6.2 Per-Content Keys

Each encrypted content has a unique content key:
1. Generate random content key
2. Encrypt content with content key
3. Encrypt content key to each recipient's public key

### 6.3 Group Keys

Groups have shared encryption keys:
- Key rotates when members leave (forward secrecy)
- New members receive current key
- Historical content uses historical keys

**Group key package:**
```json
{
  "group": "ent:rust-devs",
  "version": 3,
  "key_encrypted_to_members": {
    "ent:alice": "encrypted_group_key_for_alice",
    "ent:bob": "encrypted_group_key_for_bob"
  }
}
```

### 6.4 Tier Keys

Paid content uses tier-specific keys:
```json
{
  "publication": "ent:premium-news",
  "tier": "premium",
  "version": 2,
  "key_encrypted_to_subscribers": { ... }
}
```

---

## 7. Sync

### 7.1 Pull-Based Model

Clients pull data from relays using cursors.

### 7.2 Sequence Numbers

Relays assign sequence numbers to objects:

```json
{
  "op": "event",
  "object": { ... },
  "seq": 12345,
  "relay": "relay.example.com"
}
```

`seq` is relay-local, not author-signed.

### 7.3 Sync Queries

```
GET /content?author=ent:alice&after_seq=1000&limit=50
GET /links?source=ent:alice&kind=relationship&after_seq=500
```

### 7.4 Multi-Relay Sync

Clients track cursors per relay and deduplicate by object ID.

---

## 8. Groups

### 8.1 Group Entity

```json
{
  "type": "entity",
  "id": "ent:rust-devs",
  "kind": "group",
  "data": {
    "name": "Rust Developers",
    "description": "A community for Rust programmers",
    "visibility": "public",
    "join_policy": "open",
    "posting_policy": "members"
  },
  "keys": {
    "signing": "ed25519:...",
    "encryption": "x25519:..."
  }
}
```

### 8.2 Group Policies

| Policy | Options |
|--------|---------|
| `visibility` | `public`, `private` |
| `join_policy` | `open`, `approval`, `invite` |
| `posting_policy` | `anyone`, `members`, `mods`, `admins` |

### 8.3 Membership Flow

**Step 1: Request (for non-open groups)**
```json
{
  "type": "link",
  "kind": "relationship",
  "source": "ent:alice",
  "target": "ent:rust-devs",
  "data": {"subkind": "membership_request"},
  "sig": "ed25519:alice..."
}
```

**Step 2: Confirmation (credential)**
```json
{
  "type": "link",
  "kind": "credential",
  "source": "ent:alice",
  "target": "ent:rust-devs",
  "data": {
    "subkind": "membership",
    "role": "member",
    "granted_by": "ent:admin"
  },
  "sig": "ed25519:admin..."
}
```

### 8.4 Roles

| Role | Capabilities |
|------|--------------|
| `admin` | Full control, manage members |
| `mod` | Moderate content, approve members |
| `member` | Post and read |
| `readonly` | Read only |

---

## 9. Paid Content

### 9.1 Publication with Tiers

```json
{
  "type": "entity",
  "id": "ent:premium-news",
  "kind": "org",
  "data": {
    "name": "Premium Newsletter",
    "tiers": [
      {"id": "free", "price": 0},
      {"id": "premium", "price": {"amount": 10, "currency": "USD", "period": "month"}}
    ],
    "trusted_payment_attestors": ["ent:stripe-bridge"]
  }
}
```

### 9.2 Subscription Credential

```json
{
  "type": "link",
  "kind": "credential",
  "source": "ent:subscriber",
  "target": "ent:premium-news",
  "data": {
    "subkind": "subscription",
    "tier": "premium",
    "expires": "2026-05-01T00:00:00Z",
    "attestor": "ent:stripe-bridge"
  },
  "sig": "ed25519:stripe-bridge..."
}
```

### 9.3 Self-Attestation Fallback

For bootstrapping without external attestors:
```json
{
  "data": {
    "subkind": "subscription",
    "attestation_type": "self"
  },
  "sig": "ed25519:publication..."
}
```

Clients SHOULD show "verified by publisher" indicator.

---

## 10. Object Layer API

### 10.1 Entities

```
POST   /entities                Create entity
GET    /entities/{id}           Get entity
PATCH  /entities/{id}           Update entity
GET    /entities/{id}/keys      Get current keys
```

### 10.2 Content

```
POST   /content                 Create content
GET    /content/{id}            Get content
GET    /content?author={id}     List by author
GET    /content?context={id}    List by context
GET    /content?after_seq={n}   Sync cursor
```

### 10.3 Links

```
POST   /links                   Create link
GET    /links/{id}              Get link
GET    /links?source={id}       Links from entity
GET    /links?target={id}       Links to entity
```

### 10.4 Keys

```
GET    /keys/group/{id}         Get group key package
GET    /keys/tier/{pub}/{tier}  Get tier key (with credential)
```

---

## 11. Object Layer Summary

With just the Object Layer, you can build:
- Social networks (posts, follows, reactions)
- Blogs and newsletters (articles, subscriptions)
- Group chats (groups, encrypted messages)
- Learning platforms (courses, enrollments)
- Paid content (tiers, subscriptions)

**This is a complete, shippable protocol.**

---

# STRUCTURE LAYER

Optional. Adds holonic nesting, context inheritance, and local moderation.

---

## 12. The Holon Concept

A holon is an entity that is simultaneously:
- A **whole** with its own identity and sovereignty
- A **part** of a larger entity

```
ent:alice (user)
    ↓ part_of
ent:rust-devs (group)
    ↓ part_of
ent:tech-community (org)
```

**Key insight:** Users, groups, and organizations are the same structural type at different scales.

---

## 13. The `part_of` Relationship

### 13.1 Structure

```json
{
  "type": "link",
  "kind": "relationship",
  "source": "ent:rust-devs",
  "target": "ent:tech-community",
  "data": {
    "subkind": "part_of"
  },
  "sig": "ed25519:rust-devs-admin..."
}
```

### 13.2 Single Canonical Parent

**Simplification:** Each entity has at most ONE canonical parent.

This avoids:
- Conflicting inheritance from multiple parents
- Ambiguous context stack ordering
- Complex graph traversal

If an entity needs multiple associations, use secondary relationships (not `part_of`).

### 13.3 Validation Rules

- No cycles (DAG only)
- Maximum depth: 5 levels
- Parent must exist
- Signed by source entity admin

---

## 14. Context Stack

### 14.1 Definition

The context stack is the path from an entity to the root:

```
ent:rust-beginners → ent:rust-devs → ent:tech-community
```

### 14.2 Computation

```python
def get_context_stack(entity_id, max_depth=5):
    stack = [entity_id]
    current = entity_id
    for _ in range(max_depth):
        parent = get_parent(current)  # Follow part_of link
        if parent is None:
            break
        stack.append(parent)
        current = parent
    return stack
```

### 14.3 Content Context

Content specifies its primary context:

```json
{
  "type": "content",
  "context": "ent:rust-beginners",
  "data": { ... }
}
```

The full context stack is computed, not stored:
```
[ent:rust-beginners, ent:rust-devs, ent:tech-community]
```

---

## 15. Inheritance

### 15.1 The Rule: Child Overrides Parent

When policies conflict, **child wins**. No ambiguity.

### 15.2 What Is Inherited

| Policy | Inheritance |
|--------|-------------|
| `visibility` | Child can restrict, not expand |
| `moderation` | Child labels apply first, then parent |

### 15.3 What Is NOT Inherited

- Membership (each holon manages its own)
- Content (content lives in one context)
- Keys (each holon has its own keys)
- Reputation (see section 17)

### 15.4 Example

```
ent:tech-community
  visibility: public
  posting: members

    ↓ part_of

ent:rust-devs
  visibility: public (inherited, not overridden)
  posting: anyone (child overrides)
```

---

## 16. Subsidiarity Moderation

### 16.1 Principle

Moderation decisions happen at the smallest competent level first.

### 16.2 Resolution Order

```
1. Thread level (OP can hide replies)
2. Group level (group mods)
3. Parent level (parent org mods)
4. Relay level (relay operators)
5. Client level (user preferences)
```

### 16.3 Scoped Labels

Labels apply within a scope:

```json
{
  "type": "link",
  "kind": "interaction",
  "source": "ent:rust-devs-mod",
  "target": "cnt:off-topic-post",
  "data": {
    "subkind": "label",
    "labels": [{"name": "off-topic", "confidence": 0.9}],
    "scope": "ent:rust-devs"
  }
}
```

This label applies in `ent:rust-devs` but not globally.

### 16.4 Label Visibility

| Scope | Visible In |
|-------|------------|
| `ent:rust-beginners` | rust-beginners only |
| `ent:rust-devs` | rust-devs and all children |
| `global` | Everywhere |

---

## 17. Reputation: Not a Protocol Primitive

### 17.1 Design Decision

**HOLON does NOT define a `trust()` function in the protocol.**

### 17.2 Why

Computing scoped reputation requires either:
- Centralized oracle (defeats decentralization)
- Distributed consensus (too complex)
- Full local history (impractical storage)

### 17.3 Instead: Query Primitives

The protocol provides queryable signals:

```
GET /stats?entity=ent:alice&context=ent:rust-devs

Response:
{
  "post_count": 47,
  "reaction_count_received": 312,
  "positive_reactions": 290,
  "labels_received": {"helpful": 5, "spam": 0}
}
```

### 17.4 Client-Side Trust

Clients compute trust locally:

```python
def compute_trust(entity, context, stats):
    if stats.post_count == 0:
        return 0.5  # Unknown
    ratio = stats.positive_reactions / stats.reaction_count_received
    if stats.labels_received.get("spam", 0) > 0:
        ratio *= 0.5
    return ratio
```

Different clients can use different algorithms.

---

## 18. Holonic Entity Fields

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
      "posting": "members"
    }
  }
}
```

---

## 19. Structure Layer API

```
GET    /entities/{id}/parent    Get canonical parent
GET    /entities/{id}/children  Get child holons
GET    /entities/{id}/context   Get full context stack
GET    /content?context_tree={id}  Content in holon + children
GET    /stats?entity={id}&context={id}  Query signals for trust
```

---

## 20. Structure Layer Summary

With Object Layer + Structure Layer:
- Nested communities (subreddits within orgs)
- Local moderation without global consensus
- Context-aware content visibility
- Organic federation of communities

---

# VIEW LAYER

Optional. Adds programmable, verifiable feeds.

---

## 21. Views as First-Class Objects

A View is a **portable, verifiable, subscribable feed definition**.

### 21.1 Why Views?

Current platforms:
- Algorithms are opaque
- Users can't verify what they're shown
- No way to share curation logic

With Views:
- Algorithms are transparent
- Results are verifiable
- Curation is shareable and forkable

---

## 22. View Structure

```json
{
  "type": "view",
  "id": "view:quality-rust-feed",
  "author": "ent:curator",
  "version": 1,
  "name": "Quality Rust Content",
  "description": "High-signal posts from the Rust community",
  
  "source": {
    "type": "context",
    "holon": "ent:rust-devs"
  },
  
  "filter": [
    {"field": "kind", "op": "eq", "value": "post"},
    {"field": "created", "op": "gt", "value": {"relative": "-7d"}}
  ],
  
  "sort": [
    {"field": "reaction_count", "order": "desc"},
    {"field": "created", "order": "desc"}
  ],
  
  "limit": 50,
  
  "sig": "ed25519:curator..."
}
```

---

## 23. View Sources

### 23.1 Source Types

| Type | Description |
|------|-------------|
| `follows` | Content from followed entities |
| `context` | Content in a specific holon |
| `context_tree` | Content in holon + descendants |
| `union` | Combination of sources |

### 23.2 Examples

**From follows:**
```json
{"type": "follows", "of": "ent:me"}
```

**From holon:**
```json
{"type": "context", "holon": "ent:rust-devs"}
```

**From holon tree (requires Structure Layer):**
```json
{"type": "context_tree", "root": "ent:rust-devs", "depth": 2}
```

**Union:**
```json
{
  "type": "union",
  "sources": [
    {"type": "context", "holon": "ent:rust-devs"},
    {"type": "context", "holon": "ent:go-devs"}
  ]
}
```

---

## 24. View Filters

### 24.1 Filter Structure

```json
{"field": "<field_name>", "op": "<operator>", "value": "<value>"}
```

### 24.2 Fields

| Field | Type | Description |
|-------|------|-------------|
| `kind` | string | Content kind |
| `author` | entity_id | Content author |
| `created` | timestamp | Creation time |
| `reaction_count` | integer | Total reactions |
| `reply_count` | integer | Total replies |
| `labels` | array | Applied labels |

### 24.3 Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equals | `{"field": "kind", "op": "eq", "value": "post"}` |
| `ne` | Not equals | `{"field": "kind", "op": "ne", "value": "media"}` |
| `gt` | Greater than | `{"field": "reaction_count", "op": "gt", "value": 10}` |
| `lt` | Less than | `{"field": "created", "op": "lt", "value": "2026-04-20"}` |
| `in` | In list | `{"field": "kind", "op": "in", "value": ["post", "article"]}` |
| `contains` | Array contains | `{"field": "tags", "op": "contains", "value": "rust"}` |
| `excludes` | Array excludes | `{"field": "labels", "op": "excludes", "value": ["spam"]}` |

### 24.4 Relative Time

For time-based filters:

```json
{"field": "created", "op": "gt", "value": {"relative": "-7d"}}
```

| Format | Meaning |
|--------|---------|
| `-7d` | 7 days ago |
| `-24h` | 24 hours ago |
| `-30m` | 30 minutes ago |

Relative time is resolved against the **boundary timestamp** (see section 26), not current time.

---

## 25. View Sorting

### 25.1 Sort Structure

```json
{"field": "<field_name>", "order": "asc|desc"}
```

### 25.2 Multi-Field Sort

```json
"sort": [
  {"field": "reaction_count", "order": "desc"},
  {"field": "created", "order": "desc"}
]
```

First field is primary, second is tiebreaker.

### 25.3 Canonical Ordering

For deterministic results, add final tiebreaker:

```json
"sort": [
  {"field": "reaction_count", "order": "desc"},
  {"field": "created", "order": "desc"},
  {"field": "id", "order": "asc"}
]
```

Content ID ensures unique ordering.

---

## 26. Boundaries and Verification

### 26.1 The Problem

Without boundaries, the same view can produce different results at different times or from different relays.

### 26.2 The Solution: Boundaries

A **boundary** defines exactly what data a view was computed over:

```json
{
  "type": "boundary",
  "id": "bnd:abc123",
  "computed_at": "2026-04-23T12:00:00Z",
  "sources": [
    {
      "relay": "relay.example.com",
      "holon": "ent:rust-devs",
      "from_seq": 10000,
      "to_seq": 15000
    }
  ]
}
```

### 26.3 View Execution

A **view execution** ties a view to a boundary and results:

```json
{
  "type": "view_execution",
  "id": "vex:def456",
  "view": "view:quality-rust-feed",
  "boundary": "bnd:abc123",
  "results": ["cnt:post1", "cnt:post2", "cnt:post3"],
  "result_hash": "sha256:789abc...",
  "computed_at": "2026-04-23T12:00:00Z"
}
```

### 26.4 Result Hashing

The `result_hash` is computed from:

```python
def compute_result_hash(results):
    # Canonical JSON serialization
    canonical = json.dumps(results, sort_keys=True, separators=(',', ':'))
    return sha256(canonical.encode()).hexdigest()
```

### 26.5 Verification

Anyone can verify a view execution:

```python
def verify_execution(execution, view, boundary, data_source):
    # 1. Fetch bounded data
    data = data_source.fetch(boundary)
    
    # 2. Execute view
    results = execute_view(view, data, boundary.computed_at)
    
    # 3. Compare hashes
    computed_hash = compute_result_hash(results)
    return computed_hash == execution.result_hash
```

---

## 27. View Execution Model

### 27.1 Determinism Requirements

For verifiability, views MUST be deterministic:

| Requirement | Rule |
|-------------|------|
| No external calls | View logic cannot fetch external data |
| No randomness | No random functions |
| No current time | Use boundary timestamp |
| Canonical ordering | Include ID in sort for uniqueness |

### 27.2 Execution Steps

```python
def execute_view(view, data, boundary_timestamp):
    # 1. Select from source
    candidates = select_from_source(view.source, data)
    
    # 2. Apply filters (with boundary_timestamp for relative time)
    filtered = apply_filters(candidates, view.filter, boundary_timestamp)
    
    # 3. Sort
    sorted_results = apply_sort(filtered, view.sort)
    
    # 4. Limit
    limited = sorted_results[:view.limit]
    
    # 5. Return IDs
    return [content.id for content in limited]
```

### 27.3 Aggregate Fields

Fields like `reaction_count` require aggregates. These MUST be:
- Included in the boundary (as snapshot)
- Or computed from bounded link data

```json
{
  "type": "boundary",
  "sources": [...],
  "aggregates": {
    "cnt:post1": {"reaction_count": 42, "reply_count": 5},
    "cnt:post2": {"reaction_count": 17, "reply_count": 2}
  }
}
```

---

## 28. View Subscription

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

**Benefits:**
- Follow curators, not just authors
- Transparent curation
- Portable across clients

---

## 29. View Forking

Users can fork and modify views:

```json
{
  "type": "view",
  "id": "view:my-rust-feed",
  "author": "ent:alice",
  "forked_from": "view:quality-rust-feed",
  
  "source": {"type": "context", "holon": "ent:rust-devs"},
  
  "filter": [
    {"field": "kind", "op": "eq", "value": "post"},
    {"field": "created", "op": "gt", "value": {"relative": "-7d"}},
    {"field": "author", "op": "in", "value": ["ent:favorite1", "ent:favorite2"]}
  ],
  
  "sort": [{"field": "created", "order": "desc"}],
  "limit": 20
}
```

---

## 30. Caching

### 30.1 Cache Hints

Views can specify caching behavior:

```json
{
  "type": "view",
  "cache": {
    "ttl_seconds": 300,
    "stale_while_revalidate_seconds": 60
  }
}
```

### 30.2 Cache Keys

Cache key = `(view_id, boundary_hash)`

Different boundaries produce different cache entries.

---

## 31. View Layer API

```
POST   /views                   Create view
GET    /views/{id}              Get view definition
GET    /views/{id}/execute      Execute view (returns execution with boundary)
POST   /views/{id}/verify       Verify an execution
GET    /views?author={id}       Views by author
GET    /views?subscribed={id}   Views subscribed by entity
```

### 31.1 Execute Response

```json
{
  "execution": {
    "id": "vex:abc123",
    "view": "view:quality-rust-feed",
    "boundary": { ... },
    "results": ["cnt:post1", "cnt:post2"],
    "result_hash": "sha256:..."
  },
  "content": [
    {"id": "cnt:post1", "data": { ... }},
    {"id": "cnt:post2", "data": { ... }}
  ]
}
```

---

## 32. View Layer Summary

With all three layers:
- **Transparent feeds:** Everyone can see the algorithm
- **Verifiable curation:** Results can be independently verified
- **Forkable ranking:** Anyone can modify existing views
- **Portable curation:** Views work across clients

---

# COMPARISON

---

## 33. Protocol Comparison

| Feature | HOLON v3.2 | Nostr | AT Protocol | ActivityPub |
|---------|------------|-------|-------------|-------------|
| **Object Layer** |
| Simple core | ✓ | ✓ | ✗ | ✗ |
| Email login | ✓ | ✗ | ✓ | Depends |
| Self-custody | ✓ | ✓ (required) | ✗ | ✗ |
| Key rotation | ✓ | ✗ | Limited | ✗ |
| Groups | ✓ | Limited | ✗ | ✓ |
| Paid content | ✓ | ✗ | ✗ | ✗ |
| **Structure Layer** |
| Nested holons | ✓ | ✗ | ✗ | ✗ |
| Local moderation | ✓ | ✗ | ✗ | ✓ |
| Context inheritance | ✓ | ✗ | ✗ | ✗ |
| **View Layer** |
| Programmable views | ✓ | ✗ | ✗ | ✗ |
| Verifiable feeds | ✓ | ✗ | ✗ | ✗ |
| View subscription | ✓ | ✗ | ✗ | ✗ |

---

# MIGRATION

---

## 34. From Other Protocols

### 34.1 From Nostr

| Nostr | HOLON |
|-------|-------|
| Event | Content |
| Kind 0 (metadata) | Entity |
| Kind 1 (note) | Content (kind: post) |
| Kind 3 (follows) | Link (relationship/follow) |
| Relay | Relay |

### 34.2 From ActivityPub

| ActivityPub | HOLON |
|-------------|-------|
| Actor | Entity |
| Note/Article | Content |
| Follow/Like | Link |
| Instance | Relay + optional parent holon |

---

# IMPLEMENTATION GUIDE

---

## 35. Adoption Path

### 35.1 Week 1: Object Layer

Implement:
- Entity CRUD
- Content CRUD
- Link CRUD
- Basic sync

**Result:** Functional social app

### 35.2 Month 1: Add Structure Layer (if needed)

Implement:
- `part_of` relationship
- Context stack computation
- Scoped labels

**Result:** Nested communities

### 35.3 Later: Add View Layer (if needed)

Implement:
- View definition storage
- View execution engine
- Boundary tracking
- Verification

**Result:** Transparent curation

---

## 36. Minimum Viable Implementation

### 36.1 Object Layer Only

Storage:
- Entities table
- Content table
- Links table

API:
- CRUD for each type
- Basic queries

Sync:
- Sequence-based pulling

### 36.2 What You Can Build

- Twitter clone
- Blog platform
- Group chat
- Newsletter with subscriptions
- Course platform

---

# SUMMARY

---

## 37. The Three Layers

| Layer | Adds | Complexity |
|-------|------|------------|
| **Object** | Social objects, identity, encryption | Low |
| **Structure** | Holonic nesting, local moderation | Medium |
| **View** | Programmable, verifiable feeds | High |

## 38. Key Design Decisions

1. **Layered adoption** — Start simple, add complexity as needed
2. **Single canonical parent** — No ambiguous inheritance
3. **Reputation is client-side** — Protocol provides signals, not scores
4. **Child overrides parent** — Clear conflict resolution
5. **Views are deterministic** — Same inputs = same outputs
6. **Boundaries enable verification** — Finite input sets for auditability

## 39. What Makes HOLON Different

1. **Holonic structure** — Communities nest like real organizations
2. **Verifiable views** — No black-box algorithms
3. **Progressive complexity** — Ship simple, grow sophisticated
4. **Complete from day one** — Object Layer alone is production-ready

---

*Protocol version: 3.2*
*Status: Draft*
*License: CC0 (Public Domain)*
