# FABRIC Protocol — Optional Modules

**Extensions that add power to the FABRIC v2.2 core**

---

## ⚠️ This is NOT the Core Protocol

**The core protocol is FABRIC v2.2** (see PROTOCOL.md).

This document specifies **optional modules** for advanced use cases. Implementations can adopt none, some, or all of these modules.

### Why Modular?

> "Protocols that win usually do less, not more." — HTTP, SMTP, Nostr

The core protocol (v2.2) is simple enough to implement in a weekend. These modules add power for those who need it, without burdening simple implementations.

### Design Principle

Each module:
- Is **independent** (no dependencies between modules)
- Is **backwards compatible** (v2.2-only implementations can ignore module fields)
- **Extends** the core (adds fields/types, doesn't change existing semantics)

---

## Module Summary

| Module | Purpose | Complexity | When to Use |
|--------|---------|------------|-------------|
| **fabric-ordering** | Author-signed prev chains | Medium | High-trust, audit trails |
| **fabric-moderation** | Labels, reports, vouches | Medium | Social networks, communities |
| **fabric-spam** | PoW, rate tokens | Medium | Public platforms |
| **fabric-reputation** | Trust scores, web of trust | High | Large communities |
| **fabric-discovery** | Schema/attestor registries | Low | Ecosystem interop |
| **fabric-aggregates** | Counters, rollups | Low | Performance at scale |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR APPLICATION                          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│              OPTIONAL MODULES (this document)                │
│  Pick what you need: ordering, moderation, spam, etc.       │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                 FABRIC v2.2 CORE (PROTOCOL.md)               │
│  Entity │ Content │ Link │ Sync │ Encryption │ API          │
└─────────────────────────────────────────────────────────────┘
```

---

# Module: fabric-ordering

**Author-signed content chains for verifiable ordering**

## When to Use

✅ Use when you need:
- Cryptographic proof of content ordering
- Fork detection (author equivocation)
- Audit trails
- Replay protection

❌ Don't use when:
- Simple timestamp ordering is sufficient
- Implementation simplicity is priority
- Content is ephemeral

## Specification

### Extended Content Fields

Add two optional fields to Content:

```json
{
  "type": "content",
  "id": "cnt:post123",
  "kind": "post",
  "author": "ent:alice",
  "created": "2026-04-23T12:00:00Z",
  
  "prev": "cnt:post122",
  "author_seq": 42,
  
  "data": { ... },
  "sig": "ed25519:..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `prev` | content_id \| null | ID of author's previous content |
| `author_seq` | integer | Author's monotonic sequence number |

### Chain Rules

1. First content: `author_seq: 1`, `prev: null`
2. Subsequent: `author_seq: N+1`, `prev: ID of seq N content`
3. Signature MUST cover `prev` and `author_seq`

### Fork Detection

If two content items have same `author` and `author_seq` but different `id`:

```
Fork detected:
  cnt:fork1 (author_seq: 5, prev: cnt:a4)
  cnt:fork2 (author_seq: 5, prev: cnt:a4)
```

**Resolution options:**
- Reject both (strict)
- Accept earlier timestamp (lenient)
- Mark author as untrusted

### Backwards Compatibility

Content WITHOUT these fields is valid v2.2 content. Implementations:
- MUST accept content with or without ordering fields
- SHOULD only enforce ordering when fields are present

---

# Module: fabric-moderation

**Labels, reports, and trust attestations for content safety**

## When to Use

✅ Use when you need:
- Content classification (NSFW, spam, etc.)
- User reporting mechanism
- Trust/vouch system
- Moderation tooling

❌ Don't use when:
- Private/small community (manual moderation sufficient)
- Client-side filtering is enough

## Specification

### Label Link

Labelers classify content:

```json
{
  "type": "link",
  "kind": "interaction",
  "source": "ent:labeler-service",
  "target": "cnt:post123",
  "data": {
    "subkind": "label",
    "labels": [
      {"name": "nsfw", "confidence": 0.95},
      {"name": "violence", "confidence": 0.3}
    ],
    "expires": "2026-05-23T12:00:00Z"
  },
  "sig": "ed25519:labeler-key..."
}
```

### Standard Labels

| Category | Labels |
|----------|--------|
| Content Warning | `nsfw`, `violence`, `gore`, `spoiler` |
| Factuality | `misleading`, `satire`, `opinion` |
| Spam | `spam`, `scam`, `phishing` |
| Custom | Any application-specific string |

### Report Link

Users report problematic content:

```json
{
  "type": "link",
  "kind": "interaction",
  "source": "ent:reporter",
  "target": "cnt:problematic-post",
  "data": {
    "subkind": "report",
    "reason": "harassment",
    "details": "Targeted harassment of user X"
  },
  "sig": "ed25519:reporter-key..."
}
```

### Report Reasons

| Reason | Description |
|--------|-------------|
| `spam` | Spam or scam |
| `harassment` | Targeted harassment |
| `hate_speech` | Hate speech |
| `violence` | Violent content |
| `illegal` | Illegal content |
| `copyright` | Copyright violation |
| `misinformation` | False information |
| `other` | See details field |

### Vouch Link (Trust Attestation)

Users vouch for other users:

```json
{
  "type": "link",
  "kind": "interaction",
  "source": "ent:alice",
  "target": "ent:bob",
  "data": {
    "subkind": "vouch",
    "scope": "general",
    "confidence": 0.8,
    "reason": "Known personally"
  },
  "sig": "ed25519:alice-key..."
}
```

### Vouch Scopes

| Scope | Meaning |
|-------|---------|
| `general` | General trustworthiness |
| `identity` | Identity is verified |
| `not_spam` | Not a spam account |
| `expertise:{topic}` | Expert in topic |

### Negative Vouch (Distrust)

Use negative confidence:

```json
{
  "data": {
    "subkind": "vouch",
    "confidence": -0.9,
    "reason": "Known scam account"
  }
}
```

### Client Configuration

Clients choose trusted labelers:

```json
{
  "trusted_labelers": ["ent:official-labeler"],
  "label_actions": {
    "nsfw": "blur",
    "spam": "hide",
    "violence": "warn"
  }
}
```

---

# Module: fabric-spam

**Proof-of-work and rate limiting for spam resistance**

## When to Use

✅ Use when you need:
- Public platform open to anonymous users
- Defense against spam floods
- Sybil resistance

❌ Don't use when:
- Closed community (invite-only)
- All users are authenticated/trusted

## Specification

### Proof-of-Work Field

Add optional `pow` field to Content:

```json
{
  "type": "content",
  "kind": "post",
  "data": { ... },
  "pow": {
    "algorithm": "sha256",
    "difficulty": 16,
    "nonce": 12345678
  },
  "sig": "ed25519:..."
}
```

### PoW Verification

```python
def verify_pow(content):
    data = serialize(content, exclude=["pow.nonce"])
    hash = sha256(data + str(content.pow.nonce))
    leading_zeros = count_leading_zeros(hash)
    return leading_zeros >= content.pow.difficulty
```

### Difficulty Guidelines

| Context | Recommended Difficulty |
|---------|------------------------|
| New account (< 7 days) | 18-20 |
| Anonymous (no email) | 16-18 |
| Low reputation | 14-16 |
| High volume posting | 12-14 |
| Established account | 0 (none required) |

### Rate Tokens (Alternative)

Instead of PoW, relays can issue rate tokens:

```json
{
  "type": "rate_allocation",
  "entity": "ent:alice",
  "tokens_per_hour": 100,
  "current_balance": 87
}
```

| Action | Cost |
|--------|------|
| Post | 5 |
| Reply | 3 |
| React | 1 |
| Follow | 2 |

---

# Module: fabric-reputation

**Trust propagation and reputation scores**

## When to Use

✅ Use when you need:
- Automated trust assessment
- Web of trust calculations
- Reputation-based filtering

❌ Don't use when:
- Simple vouch system is sufficient
- Don't want algorithmic trust

## Specification

### Reputation Snapshot

```json
{
  "type": "snapshot",
  "kind": "reputation",
  "entity": "ent:alice",
  "computed_by": "ent:reputation-service",
  "data": {
    "overall": 0.85,
    "dimensions": {
      "content_quality": 0.9,
      "trust_network": 0.85,
      "spam_score": 0.02
    },
    "confidence": 0.8
  },
  "sig": "ed25519:reputation-service..."
}
```

### Trust Propagation

Trust flows through the network:

```
Alice vouches for Bob (0.9)
Bob vouches for Carol (0.8)
→ Alice's transitive trust in Carol: 0.9 × 0.8 × 0.7 (decay) ≈ 0.5
```

### Reputation Inputs

| Input | Description |
|-------|-------------|
| Direct vouches | Vouches from followed users |
| Transitive trust | Web of trust calculation |
| Account age | Older = more trusted |
| Content engagement | Positive reactions |
| Label history | Past spam/abuse labels |
| Report history | Reports against user |

---

# Module: fabric-discovery

**Schema and attestor registries**

## When to Use

✅ Use when you need:
- Ecosystem-wide schema interop
- Dynamic attestor discovery
- Schema versioning

❌ Don't use when:
- Fixed schema set
- Hardcoded attestors

## Specification

### Schema Registry

Schemas published as Content:

```json
{
  "type": "content",
  "kind": "structured",
  "schema": "fabric.schema.v1",
  "data": {
    "schema_id": "social.post.v1",
    "version": "1.0.0",
    "fields": {
      "text": {"type": "string", "max_length": 10000},
      "media": {"type": "array"}
    }
  }
}
```

### Schema API

```
GET /schemas                    List schemas
GET /schemas/{schema_id}        Get schema
```

### Attestor Registry

```json
{
  "type": "snapshot",
  "kind": "attestor_registry",
  "data": {
    "payment_attestors": [
      {
        "id": "ent:stripe-bridge",
        "name": "Stripe Bridge",
        "endpoint": "https://...",
        "status": "active"
      }
    ]
  }
}
```

### Attestor API

```
GET /attestors                  List attestors
GET /attestors/{id}             Get attestor
```

---

# Module: fabric-aggregates

**Efficient counters and rollups**

## When to Use

✅ Use when you need:
- Reaction counts without fetching all reactions
- Follower counts
- Performance at scale

❌ Don't use when:
- Small scale (counting on read is fine)

## Specification

### Aggregate Snapshot

```json
{
  "type": "snapshot",
  "kind": "aggregate",
  "target": "cnt:post123",
  "data": {
    "reaction_count": 142,
    "reaction_breakdown": {"❤️": 100, "🔥": 30, "👀": 12},
    "reply_count": 23,
    "repost_count": 7
  },
  "updated": "2026-04-23T12:00:00Z"
}
```

### Aggregate API

```
GET /aggregates/{content_id}    Get content aggregates
GET /aggregates/entity/{id}     Get entity aggregates (followers, etc.)
```

### Verification

Aggregates can be verified by counting the underlying links:

```python
def verify_aggregate(aggregate, links):
    actual_count = len([l for l in links if matches(l, aggregate.target)])
    return aggregate.data.reaction_count == actual_count
```

---

# Adoption Guide

## Minimal Implementation (Core Only)

Just implement FABRIC v2.2. No modules needed.

**Capabilities:** Posts, follows, groups, encryption, payments.

## Social Network

Core + fabric-moderation

**Adds:** Labels, reports, basic trust.

## High-Trust Platform

Core + fabric-ordering + fabric-moderation

**Adds:** Verifiable ordering, full moderation.

## Large Public Platform

Core + all modules

**Adds:** Everything, maximum scalability and safety.

---

# Module Interaction

Modules are independent but can work together:

| Combination | Benefit |
|-------------|---------|
| ordering + moderation | Verifiable moderation history |
| moderation + reputation | Automated trust from vouches |
| spam + reputation | PoW reduced for high-reputation users |
| aggregates + moderation | Efficient abuse detection |

---

*Version: 1.0 (modules for FABRIC v2.2)*
*Status: Draft*
*License: CC0 (Public Domain)*
