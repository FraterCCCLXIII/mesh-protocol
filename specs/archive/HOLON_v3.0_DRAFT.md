# HOLON Protocol v3.0 (Draft)

**A Holonic Social Protocol with Programmable Views**

---

## The Paradigm Shift

> "Every node is simultaneously a whole and a part of a larger whole."

Previous protocols (including FABRIC v2.2) treat social objects as flat records in a global namespace. HOLON treats them as **nested, sovereign units** that can contain other units and belong to larger units.

Combined with **Programmable Views**, this enables:
- Transparent, auditable feed algorithms
- Context-aware trust and moderation
- Nested communities with local sovereignty
- Algorithm markets

---

## What's New in HOLON v3.0

| Feature | FABRIC v2.2 | HOLON v3.0 |
|---------|-------------|------------|
| Structure | Flat entities | Nested holons |
| Context | Single | Stack (inherited) |
| Reputation | Global + dimensions | Scoped per holon |
| Moderation | Global labels | Subsidiarity (local first) |
| Feeds | Client-computed | **Programmable Views** |
| Algorithms | Hidden | **Transparent, verifiable** |

---

## Part I: Holonic Structure

---

### 1. The Holon Primitive

Every entity is a **holon**: simultaneously a whole with its own identity, and a part of larger holons.

```
ent:alice (user holon)
    │
    ▼ part_of
ent:rust-devs (group holon)
    │
    ▼ part_of
ent:tech-community (org holon)
    │
    ▼ part_of
ent:fediverse (network holon)
```

**Key insight:** Users, groups, orgs, and networks are the same structural type at different scales.

### 2. The `part_of` Relationship

New Link subkind that establishes holonic containment:

```json
{
  "type": "link",
  "kind": "relationship",
  "source": "ent:rust-devs",
  "target": "ent:tech-community",
  "data": {
    "subkind": "part_of",
    "role": "subgroup",
    "inherits": ["moderation", "visibility"]
  },
  "sig": "ed25519:..."
}
```

**Properties:**
- `source` is contained within `target`
- `inherits` specifies which policies flow down
- Creates a directed acyclic graph (DAG) of containment

### 3. Context as Stack

Content exists within a **context stack**, not a single context:

```json
{
  "type": "content",
  "kind": "post",
  "author": "ent:alice",
  "context": ["ent:rust-devs", "ent:tech-community"],
  "data": { "text": "Check out this crate!" },
  "sig": "ed25519:..."
}
```

**Semantics:**
- Primary context: `ent:rust-devs` (where content "lives")
- Inherited context: `ent:tech-community` (parent holon)
- Content is visible in both contexts (unless restricted)

### 4. Holonic Entity Structure

Entities gain optional holonic fields:

```json
{
  "type": "entity",
  "id": "ent:rust-devs",
  "kind": "group",
  "version": 3,
  "data": {
    "name": "Rust Developers",
    "description": "A community for Rust programmers",
    
    "parent": "ent:tech-community",
    "children": ["ent:rust-beginners", "ent:rust-async"],
    
    "policies": {
      "moderation": "local_first",
      "visibility": "inherit",
      "membership": "open"
    }
  },
  "sig": "ed25519:..."
}
```

---

## Part II: Scoped Reputation

---

### 5. Reputation Per Holon

Reputation is no longer global. It's scoped to the holon where interactions occur:

```json
{
  "type": "snapshot",
  "kind": "reputation",
  "entity": "ent:alice",
  "data": {
    "scopes": {
      "ent:rust-devs": {
        "overall": 0.92,
        "dimensions": {"technical": 0.95, "helpfulness": 0.88}
      },
      "ent:politics-group": {
        "overall": 0.45,
        "dimensions": {"civility": 0.3, "accuracy": 0.6}
      },
      "global": {
        "overall": 0.71
      }
    }
  }
}
```

**Why this matters:**
- Alice is highly trusted for Rust advice
- Alice is controversial in political discussions
- These don't pollute each other
- Feeds can use context-appropriate trust

### 6. Trust Queries

When computing trust, specify the scope:

```
trust(ent:alice, scope=ent:rust-devs) → 0.92
trust(ent:alice, scope=ent:politics-group) → 0.45
trust(ent:alice, scope=global) → 0.71
trust(ent:alice, scope=inherit) → walks up context stack
```

---

## Part III: Subsidiarity Moderation

---

### 7. Local-First Moderation

Moderation decisions are made at the smallest competent level first:

```
Resolution order:
1. Thread-level (replies can be hidden by OP)
2. Group-level (group mods)
3. Org-level (org admins)
4. Network-level (relay operators)
5. Client-level (user preferences)
```

**Labels are scoped:**

```json
{
  "type": "link",
  "kind": "interaction",
  "source": "ent:rust-devs-mod",
  "target": "cnt:problematic-post",
  "data": {
    "subkind": "label",
    "labels": [{"name": "off-topic", "confidence": 0.9}],
    "scope": "ent:rust-devs"
  }
}
```

This label applies within `ent:rust-devs` but doesn't propagate globally.

### 8. Moderation Inheritance

Parent holons can define policies that children inherit:

```json
{
  "type": "entity",
  "id": "ent:tech-community",
  "data": {
    "moderation_policy": {
      "banned_globally": ["ent:known-spammer"],
      "required_labels": ["spam"],
      "allow_override": true
    }
  }
}
```

Child holons can:
- Inherit parent policies
- Add stricter local policies
- Override (if `allow_override: true`)

---

## Part IV: Programmable Views (The Revolutionary Primitive)

---

### 9. Views as First-Class Objects

**This is the paradigm shift.**

A View is a portable, verifiable, subscribable feed definition:

```json
{
  "type": "view",
  "id": "view:quality-rust-feed",
  "author": "ent:curator",
  "name": "Quality Rust Content",
  "description": "High-signal Rust posts from trusted authors",
  
  "logic": {
    "source": {
      "type": "context_tree",
      "root": "ent:rust-devs",
      "depth": 2
    },
    "filter": [
      {"field": "kind", "op": "in", "value": ["post", "article"]},
      {"field": "trust(author, scope=context)", "op": ">", "value": 0.7}
    ],
    "sort": [
      {"field": "engagement_score", "order": "desc"},
      {"field": "created", "order": "desc"}
    ],
    "limit": 50
  },
  
  "verifiable": true,
  "cacheable": true,
  "update_frequency": "5m",
  
  "sig": "ed25519:curator..."
}
```

### 10. View Properties

| Property | Description |
|----------|-------------|
| `source` | Where to pull content from |
| `filter` | Conditions content must match |
| `sort` | Ordering rules |
| `limit` | Maximum results |
| `verifiable` | Anyone can recompute |
| `cacheable` | Results can be cached |

### 11. View Sources

```json
// My follows
{"type": "follows", "of": "me"}

// A specific holon
{"type": "context", "holon": "ent:rust-devs"}

// A holon tree (recursive)
{"type": "context_tree", "root": "ent:rust-devs", "depth": 3}

// Multiple holons
{"type": "union", "holons": ["ent:rust-devs", "ent:go-devs"]}

// Intersection
{"type": "intersection", "holons": ["ent:tech", "ent:my-follows"]}
```

### 12. View Filters

```json
// Trust threshold
{"field": "trust(author, scope=context)", "op": ">", "value": 0.5}

// Content type
{"field": "kind", "op": "in", "value": ["post", "article"]}

// Time range
{"field": "created", "op": ">", "value": "now-24h"}

// Label exclusion
{"field": "labels", "op": "excludes", "value": ["spam", "nsfw"]}

// Engagement threshold
{"field": "reaction_count", "op": ">", "value": 10}

// Custom function
{"field": "custom:quality_score(content)", "op": ">", "value": 0.7}
```

### 13. View Verification

Because Views are declarative, anyone can verify results:

```python
def verify_view_results(view, results, data_source):
    # Recompute the view from source data
    recomputed = execute_view(view.logic, data_source)
    
    # Compare
    return results == recomputed
```

**This kills black-box algorithms.** If a relay claims to show you a "quality feed," you can verify it.

### 14. View Subscription

Users can subscribe to Views like they subscribe to authors:

```json
{
  "type": "link",
  "kind": "relationship",
  "source": "ent:alice",
  "target": "view:quality-rust-feed",
  "data": {
    "subkind": "subscribe"
  }
}
```

**This enables:**
- Follow curators, not just authors
- Algorithm markets
- Transparent ranking

### 15. View Forking

Views can be forked and modified:

```json
{
  "type": "view",
  "id": "view:my-rust-feed",
  "author": "ent:alice",
  "forked_from": "view:quality-rust-feed",
  "changes": {
    "filter": [
      {"add": {"field": "author", "op": "in", "value": ["ent:favorite1", "ent:favorite2"]}}
    ]
  }
}
```

---

## Part V: Holonic Sync

---

### 16. Selective Sync

Clients don't sync the entire universe. They sync:
- Holons they belong to
- Holons they follow
- Summaries of parent holons

```
Sync strategy:
1. Full sync: My direct holons
2. Summary sync: Parent holons (aggregates only)
3. On-demand: Content from followed views
```

### 17. Holon Boundaries

Each holon can expose different interfaces:

| Interface | Audience | Content |
|-----------|----------|---------|
| Internal | Members | Full event log |
| Parent | Parent holon | Selected content + aggregates |
| Public | Anyone | Public content + aggregates |

---

## Part VI: Examples

---

### Example 1: Nested Community

```
ent:fediverse (network)
├── ent:tech-community (org)
│   ├── ent:rust-devs (group)
│   │   ├── ent:rust-beginners (subgroup)
│   │   └── ent:rust-async (subgroup)
│   └── ent:go-devs (group)
└── ent:creative-community (org)
    ├── ent:writers (group)
    └── ent:artists (group)
```

Alice posts in `ent:rust-beginners`:
- Visible in: rust-beginners, rust-devs, tech-community (based on policies)
- Moderated by: rust-beginners mods first, then rust-devs mods
- Reputation earned in: rust-beginners scope

### Example 2: Context-Aware Feed

```json
{
  "type": "view",
  "id": "view:my-tech-feed",
  "logic": {
    "source": {"type": "context_tree", "root": "ent:tech-community", "depth": 3},
    "filter": [
      {"field": "trust(author, scope=inherit)", "op": ">", "value": 0.6},
      {"field": "labels", "op": "excludes", "value": ["off-topic"]}
    ],
    "sort": [{"field": "relevance_score", "order": "desc"}]
  }
}
```

This feed:
- Pulls from all of tech-community's subholons
- Uses inherited trust (walks up context stack)
- Respects local moderation labels

### Example 3: Algorithm Market

Curator publishes a view:
```json
{
  "type": "view",
  "id": "view:curator-best-of-week",
  "author": "ent:trusted-curator",
  "name": "Best of the Week",
  "logic": { ... },
  "subscription_price": {"amount": 1, "currency": "USD", "period": "month"}
}
```

Users subscribe:
```json
{
  "type": "link",
  "kind": "credential",
  "source": "ent:subscriber",
  "target": "view:curator-best-of-week",
  "data": {
    "subkind": "subscription",
    "tier": "paid"
  }
}
```

---

## Part VII: Compatibility

---

### 18. Backwards Compatibility with FABRIC v2.2

HOLON v3.0 extends FABRIC v2.2. All v2.2 content is valid:

| v2.2 | HOLON v3.0 |
|------|------------|
| Entity | Entity (with optional holon fields) |
| Content | Content (with optional context stack) |
| Link | Link (with new `part_of` and `subscribe` subkinds) |
| — | View (new primitive) |

**Migration:**
- Flat entities become root-level holons
- Single context becomes single-element stack
- Global reputation becomes global scope

### 19. Optional Adoption

You can adopt HOLON features incrementally:
1. **Core only**: Just Entity, Content, Link (v2.2 compatible)
2. **+ Holons**: Add `part_of` relationships
3. **+ Scoped reputation**: Add scope to reputation
4. **+ Views**: Add programmable views

---

## Part VIII: Comparison

---

| Feature | HOLON v3.0 | FABRIC v2.2 | Relay 2.0 | Nostr | AT Protocol |
|---------|------------|-------------|-----------|-------|-------------|
| Nested structure | ✓ Native | ✗ | ✗ | ✗ | ✗ |
| Scoped reputation | ✓ | ✗ | ✗ | ✗ | ✗ |
| Subsidiarity moderation | ✓ | ✗ | Partial | ✗ | ✗ |
| Programmable views | ✓ | ✗ | ✗ | ✗ | ✗ |
| Verifiable feeds | ✓ | ✗ | ✗ | ✗ | ✗ |
| Algorithm markets | ✓ | ✗ | ✗ | ✗ | ✗ |

---

## Part IX: What Makes This Revolutionary

---

### 1. Programmable Views

No other protocol treats feeds as first-class, portable, verifiable objects. This alone enables:
- Transparent algorithms
- Algorithm markets
- User-owned curation
- Verifiable ranking

### 2. Holonic Structure

Nested sovereignty is how human communities actually work. This enables:
- Local moderation without global consensus
- Context-appropriate trust
- Natural scaling
- Organic federation

### 3. The Combination

Holons + Views together enable queries like:

```
"Show me AI discussions from people trusted within my professional network, 
ranked by engagement within that context, excluding content flagged by 
my local community's moderators."
```

No other protocol can express this.

---

## Part X: Summary

---

**HOLON v3.0 = FABRIC v2.2 + Holonic Structure + Programmable Views**

### New Primitives
1. `part_of` relationship (holonic containment)
2. `View` type (programmable, verifiable feeds)

### New Concepts
1. Context as stack (inherited from parent holons)
2. Scoped reputation (trust per holon)
3. Subsidiarity moderation (local first)

### What We Kept
- Entity, Content, Link (v2.2 core)
- All v2.2 features (encryption, groups, payments)
- Optional modules (spam, discovery, etc.)

### The Paradigm Shift
> Feeds are not client logic. They are portable, verifiable, subscribable objects.

> Communities are not flat. They are nested, sovereign units that can contain and be contained.

---

*Protocol version: 3.0 (Draft)*
*Status: Experimental*
*License: CC0 (Public Domain)*
