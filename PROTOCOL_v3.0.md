# FABRIC Protocol v3.0

**Federated Architecture for Broadcast, Relationships, Identity, and Content**

A production-ready protocol for decentralized social applications — with verifiable ordering, moderation primitives, and scalable storage.

---

## Changelog (v3.0)

### From v2.2
- **Added**: Author-signed ordering with `prev` chains (verifiable event ordering)
- **Added**: Moderation primitives (Labels, Reports, Trust Attestations)
- **Added**: Log/State separation (Events vs Snapshots)
- **Added**: Protocol-level spam resistance (proof-of-work, stake, rate tokens)
- **Added**: Schema registry specification
- **Added**: Attestor discovery protocol
- **Added**: Trust/reputation framework
- **Added**: Aggregation primitives (counters, rollups)
- **Breaking**: Events replace Links for high-volume operations
- **Breaking**: Snapshots replace mutable Entity state

---

## Part I: Core Architecture

---

## 1. The Four-Layer Model

FABRIC v3 separates concerns into four layers:

```
┌─────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                       │
│  Feeds, UIs, clients — built on primitives below            │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      MODERATION LAYER                        │
│  Labels, Reports, Trust Attestations, Reputation            │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                        STATE LAYER                           │
│  Snapshots (current state), Aggregates (counters)           │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                         LOG LAYER                            │
│  Events (immutable, append-only, author-signed ordering)    │
└─────────────────────────────────────────────────────────────┘
```

### 1.1 Log Layer (Events)

Immutable, append-only events with author-signed ordering:
- Posts, reactions, follows, messages
- Each event references its predecessor (`prev`)
- Cryptographically verifiable ordering

### 1.2 State Layer (Snapshots)

Mutable state derived from events:
- Entity profiles (name, bio, avatar)
- Aggregates (reaction counts, follower counts)
- Computed from log, can be reconstructed

### 1.3 Moderation Layer

Trust and safety primitives:
- Labels (content classification)
- Reports (user-generated flags)
- Trust attestations (vouching)
- Reputation scores

### 1.4 Application Layer

Built on the layers below:
- Feeds, timelines, discovery
- Client-specific rendering
- Business logic

---

## 2. Events (Log Layer)

### 2.1 Event Structure

Every event is immutable, append-only, and part of an author-signed chain:

```json
{
  "type": "event",
  "id": "evt:abc123",
  "kind": "post",
  "author": "ent:alice",
  "prev": "evt:xyz789",
  "seq": 42,
  "created": "2026-04-23T12:00:00Z",
  "data": {
    "text": "Hello, world!",
    "media": []
  },
  "pow": "0x00000f...",
  "sig": "ed25519:..."
}
```

**Key fields:**

| Field | Description |
|-------|-------------|
| `prev` | Hash of author's previous event (forms a chain) |
| `seq` | Author's local sequence number (monotonic) |
| `pow` | Optional proof-of-work (spam resistance) |
| `sig` | Signature covers all fields including `prev` and `seq` |

### 2.2 Author-Signed Ordering

Each author maintains their own event chain:

```
Author: Alice

evt:a1 (seq: 1, prev: null)
    │
    ▼
evt:a2 (seq: 2, prev: evt:a1)
    │
    ▼
evt:a3 (seq: 3, prev: evt:a2)
    │
    ▼
evt:a4 (seq: 4, prev: evt:a3)
```

**Properties:**

1. **Verifiable**: Anyone can verify the chain by checking signatures
2. **Tamper-evident**: Inserting/removing events breaks the chain
3. **Fork-detectable**: If Alice publishes two events with the same `prev`, it's a detectable fork
4. **Relay-independent**: Ordering is author-determined, not relay-determined

### 2.3 Event Kinds

| Kind | Description | Data Fields |
|------|-------------|-------------|
| `post` | Social post | text, media, reply_to, thread_root |
| `article` | Long-form content | title, body, cover |
| `react` | Reaction | target, emoji |
| `follow` | Follow entity | target |
| `unfollow` | Unfollow entity | target |
| `block` | Block entity | target |
| `unblock` | Unblock entity | target |
| `membership_request` | Request to join group | group |
| `message` | Direct message | recipient, ciphertext |
| `profile_update` | Update profile state | changes |
| `key_rotation` | Rotate keys | new_key, revoked_keys |
| `label` | Apply label to content | target, label, confidence |
| `report` | Report content | target, reason |
| `vouch` | Trust attestation | target, scope, confidence |

### 2.4 Event Verification

```python
def verify_event(event, author_chain):
    # 1. Verify signature
    if not verify_signature(event.sig, event.author, event):
        return False
    
    # 2. Verify chain linkage
    if event.seq == 1:
        if event.prev is not None:
            return False  # First event must have null prev
    else:
        expected_prev = author_chain.get_event(event.seq - 1)
        if event.prev != hash(expected_prev):
            return False  # Chain broken
    
    # 3. Verify proof-of-work (if required)
    if requires_pow(event) and not verify_pow(event.pow, event):
        return False
    
    return True
```

### 2.5 Fork Detection

If an author publishes two events with the same `seq`:

```
evt:fork1 (seq: 5, prev: evt:a4)  ← Fork!
evt:fork2 (seq: 5, prev: evt:a4)  ← Fork!
```

**Detection:** Relays and clients MUST detect forks and:
1. Mark the author as potentially compromised
2. Reject both forked events (or use timestamp tiebreaker)
3. Optionally: Accept events only after fork is resolved

---

## 3. Snapshots (State Layer)

### 3.1 Snapshot Structure

Snapshots represent current state, derived from events:

```json
{
  "type": "snapshot",
  "id": "snap:alice-profile-v3",
  "entity": "ent:alice",
  "kind": "profile",
  "version": 3,
  "updated": "2026-04-23T12:00:00Z",
  "derived_from": "evt:alice-profile-update-3",
  "data": {
    "name": "Alice",
    "bio": "Building things",
    "avatar": "cid:bafybeif..."
  },
  "sig": "ed25519:..."
}
```

**Key fields:**

| Field | Description |
|-------|-------------|
| `version` | Snapshot version (increments on update) |
| `derived_from` | Event that produced this snapshot |
| `data` | Current state |

### 3.2 Snapshot Kinds

| Kind | Description | Derived From |
|------|-------------|--------------|
| `profile` | Entity profile data | `profile_update` events |
| `keys` | Current signing/encryption keys | `key_rotation` events |
| `group_config` | Group settings | Group admin events |
| `aggregate` | Counters and rollups | Multiple events |

### 3.3 Aggregates

Aggregates are special snapshots that summarize multiple events:

```json
{
  "type": "snapshot",
  "kind": "aggregate",
  "target": "cnt:post123",
  "updated": "2026-04-23T12:00:00Z",
  "data": {
    "reaction_count": 142,
    "reaction_breakdown": {"❤️": 100, "🔥": 30, "👀": 12},
    "reply_count": 23,
    "repost_count": 7
  },
  "merkle_root": "sha256:..."
}
```

**Properties:**
- Computed from events (can be verified)
- Cached for performance (don't need to count every time)
- `merkle_root` allows verification against event log

### 3.4 State Reconstruction

Snapshots can always be reconstructed from events:

```python
def reconstruct_profile(entity_id, event_log):
    profile = {}
    for event in event_log.get_events(author=entity_id, kind="profile_update"):
        profile.update(event.data.changes)
    return profile
```

This means:
- Snapshots are optimization, not source of truth
- Events are the canonical record
- State can be audited against log

---

## 4. Credentials (Unchanged from v2.2)

Credentials remain third-party signed attestations:

| Subkind | Description | Signed By |
|---------|-------------|-----------|
| `membership` | Confirmed group membership | Group admin |
| `subscription` | Paid subscription | Payment attestor |
| `enrollment` | Course enrollment | Course provider |
| `certificate` | Achievement/completion | Issuer |

Credentials are NOT events (they're not part of author's chain). They're standalone signed objects.

---

## Part II: Moderation Layer

---

## 5. Labels

### 5.1 Label Event

Labels are events that classify content:

```json
{
  "type": "event",
  "kind": "label",
  "author": "ent:labeler-service",
  "prev": "evt:...",
  "seq": 1234,
  "data": {
    "target": "cnt:post123",
    "labels": [
      {"name": "nsfw", "confidence": 0.95},
      {"name": "violence", "confidence": 0.3}
    ],
    "expires": "2026-05-23T12:00:00Z"
  },
  "sig": "ed25519:..."
}
```

### 5.2 Label Categories

| Category | Labels | Description |
|----------|--------|-------------|
| Content Warning | `nsfw`, `violence`, `gore`, `spoiler` | Content that needs warning |
| Factuality | `misleading`, `satire`, `opinion`, `verified` | Information quality |
| Legal | `illegal`, `copyright`, `doxxing` | Legal concerns |
| Spam | `spam`, `scam`, `phishing` | Malicious content |
| Custom | Any string | Application-specific |

### 5.3 Labeler Trust

Clients choose which labelers to trust:

```json
{
  "client_config": {
    "trusted_labelers": [
      {"id": "ent:official-labeler", "trust": 1.0},
      {"id": "ent:community-labeler", "trust": 0.7}
    ],
    "label_actions": {
      "nsfw": "blur",
      "spam": "hide",
      "violence": "warn"
    }
  }
}
```

### 5.4 Labeler Registration

Labelers publish their policies:

```json
{
  "type": "snapshot",
  "kind": "labeler_policy",
  "entity": "ent:official-labeler",
  "data": {
    "name": "Official Content Moderation",
    "description": "Automated and human-reviewed labels",
    "labels_provided": ["nsfw", "spam", "violence", "misleading"],
    "appeal_process": "https://...",
    "transparency_report": "https://..."
  }
}
```

---

## 6. Reports

### 6.1 Report Event

Users can report content:

```json
{
  "type": "event",
  "kind": "report",
  "author": "ent:reporter",
  "prev": "evt:...",
  "seq": 56,
  "data": {
    "target": "cnt:problematic-post",
    "target_author": "ent:poster",
    "reason": "harassment",
    "details": "This post contains targeted harassment",
    "evidence": ["cnt:context1", "cnt:context2"]
  },
  "sig": "ed25519:..."
}
```

### 6.2 Report Reasons

| Reason | Description |
|--------|-------------|
| `spam` | Spam or scam content |
| `harassment` | Targeted harassment |
| `hate_speech` | Hate speech |
| `violence` | Violent content |
| `illegal` | Illegal content |
| `copyright` | Copyright violation |
| `impersonation` | Impersonating someone |
| `misinformation` | False information |
| `other` | Other reason (see details) |

### 6.3 Report Processing

Reports are processed by:
1. **Relay operators** (can hide content on their relay)
2. **Labelers** (can apply labels based on reports)
3. **Group admins** (can take action in their groups)

Reports are visible to:
- The reporter (their own reports)
- Authorized moderators (aggregated, anonymized)
- NOT the reported user (to prevent retaliation)

---

## 7. Trust Attestations (Vouching)

### 7.1 Vouch Event

Users can vouch for other users:

```json
{
  "type": "event",
  "kind": "vouch",
  "author": "ent:alice",
  "prev": "evt:...",
  "seq": 78,
  "data": {
    "target": "ent:bob",
    "scope": "general",
    "confidence": 0.8,
    "reason": "Known personally for 5 years"
  },
  "sig": "ed25519:..."
}
```

### 7.2 Vouch Scopes

| Scope | Meaning |
|-------|---------|
| `general` | General trustworthiness |
| `identity` | Identity is verified |
| `expertise:{topic}` | Expert in topic |
| `not_spam` | Not a spam account |
| `original_content` | Creates original content |

### 7.3 Anti-Vouch (Distrust)

Negative attestations:

```json
{
  "type": "event",
  "kind": "vouch",
  "author": "ent:alice",
  "data": {
    "target": "ent:scammer",
    "scope": "general",
    "confidence": -0.9,
    "reason": "Known scam account"
  }
}
```

Negative confidence indicates distrust.

### 7.4 Web of Trust

Trust propagates through the network:

```
Alice trusts Bob (0.9)
Bob trusts Carol (0.8)
→ Alice has transitive trust in Carol (0.9 × 0.8 × decay = ~0.5)
```

**Trust computation:**

```python
def compute_trust(source, target, max_depth=3):
    if source == target:
        return 1.0
    
    # Direct trust
    direct = get_vouch(source, target)
    if direct:
        return direct.confidence
    
    # Transitive trust (with decay)
    if max_depth <= 0:
        return 0.0
    
    total = 0.0
    weight = 0.0
    for intermediate in get_vouched_by(source):
        t = compute_trust(intermediate.target, target, max_depth - 1)
        total += intermediate.confidence * t * 0.7  # 0.7 decay factor
        weight += abs(intermediate.confidence)
    
    return total / weight if weight > 0 else 0.0
```

---

## 8. Reputation Framework

### 8.1 Reputation Snapshot

Aggregated reputation for an entity:

```json
{
  "type": "snapshot",
  "kind": "reputation",
  "entity": "ent:alice",
  "computed_by": "ent:reputation-service",
  "updated": "2026-04-23T12:00:00Z",
  "data": {
    "overall": 0.85,
    "dimensions": {
      "content_quality": 0.9,
      "engagement": 0.7,
      "trust_network": 0.85,
      "account_age": 0.95,
      "spam_score": 0.02
    },
    "confidence": 0.8,
    "sample_size": 1234
  },
  "sig": "ed25519:..."
}
```

### 8.2 Reputation Inputs

| Input | Weight | Description |
|-------|--------|-------------|
| Account age | 0.1 | Older accounts more trusted |
| Web of trust | 0.3 | Vouches from trusted users |
| Content engagement | 0.2 | Positive reactions to content |
| Label history | 0.2 | Past labels (spam, etc.) |
| Report history | 0.2 | Past reports against user |

### 8.3 Reputation Services

Multiple reputation services can exist:
- Each publishes reputation snapshots
- Clients choose which to trust
- Decentralized: no single source of truth

---

## Part III: Spam Resistance

---

## 9. Proof-of-Work

### 9.1 PoW Field

Events can include proof-of-work:

```json
{
  "type": "event",
  "kind": "post",
  "data": { ... },
  "pow": {
    "algorithm": "sha256",
    "difficulty": 16,
    "nonce": 12345678,
    "hash": "0x0000f..."
  },
  "sig": "ed25519:..."
}
```

### 9.2 PoW Verification

```python
def verify_pow(event):
    # Compute hash of event without pow.hash
    event_data = serialize(event, exclude=["pow.hash"])
    computed_hash = sha256(event_data + event.pow.nonce)
    
    # Check difficulty (leading zeros)
    required_zeros = event.pow.difficulty
    if not computed_hash.startswith("0" * required_zeros):
        return False
    
    return computed_hash == event.pow.hash
```

### 9.3 PoW Requirements

Relays can require PoW based on:

| Condition | Required Difficulty |
|-----------|---------------------|
| New account (< 7 days) | 20 |
| Low reputation (< 0.3) | 18 |
| Anonymous (no email) | 16 |
| High volume (> 10/hour) | 14 |
| Established account | 0 (none) |

---

## 10. Stake-Based Posting

### 10.1 Stake Credential

Users can stake value to post:

```json
{
  "type": "credential",
  "kind": "stake",
  "source": "ent:alice",
  "data": {
    "amount": 100,
    "currency": "USDC",
    "locked_until": "2027-04-23T00:00:00Z",
    "contract": "eth:0x...",
    "attestor": "ent:stake-bridge"
  },
  "sig": "ed25519:stake-bridge..."
}
```

### 10.2 Stake Slashing

If a staked user is found to be spamming:
1. Labelers apply `spam` label with high confidence
2. Multiple reports confirm
3. Stake can be slashed (portion forfeited)

This creates economic disincentive for spam.

### 10.3 Stake Benefits

Staked users get:
- No PoW requirement
- Higher rate limits
- Priority relay processing
- Reputation boost

---

## 11. Rate Tokens

### 11.1 Token Allocation

Users receive rate tokens based on reputation:

```json
{
  "type": "snapshot",
  "kind": "rate_allocation",
  "entity": "ent:alice",
  "data": {
    "tokens_per_hour": 100,
    "current_balance": 87,
    "refill_rate": 10,
    "max_balance": 200
  }
}
```

### 11.2 Token Costs

| Action | Cost |
|--------|------|
| Post | 5 |
| Reply | 3 |
| React | 1 |
| Follow | 2 |
| Message | 5 |
| Report | 10 |

### 11.3 Token Earning

Users earn tokens by:
- Time (passive refill)
- Positive engagement on content
- Vouches from trusted users
- Completing challenges (CAPTCHA, etc.)

---

## Part IV: Discovery & Registries

---

## 12. Schema Registry

### 12.1 Schema Definition

Schemas are published as content:

```json
{
  "type": "content",
  "kind": "structured",
  "schema": "fabric.schema.v1",
  "author": "ent:schema-registry",
  "data": {
    "schema_id": "social.post.v1",
    "version": "1.0.0",
    "description": "Standard social post",
    "fields": {
      "text": {"type": "string", "required": true, "max_length": 10000},
      "media": {"type": "array", "items": {"type": "media_ref"}},
      "reply_to": {"type": "content_id", "required": false},
      "thread_root": {"type": "content_id", "required": false},
      "mentions": {"type": "array", "items": {"type": "entity_id"}},
      "tags": {"type": "array", "items": {"type": "string"}}
    },
    "display_hints": {
      "title_field": null,
      "summary_field": "text",
      "thumbnail_field": "media[0]"
    }
  }
}
```

### 12.2 Schema Discovery

```
GET /schemas                          List all schemas
GET /schemas/{schema_id}              Get schema definition
GET /schemas/{schema_id}/versions     List versions
GET /schemas?namespace={ns}           Filter by namespace
```

### 12.3 Schema Namespaces

| Namespace | Owner | Examples |
|-----------|-------|----------|
| `fabric.*` | Protocol | `fabric.schema.v1` |
| `social.*` | Community | `social.post.v1` |
| `media.*` | Community | `media.video.v1` |
| `lms.*` | Community | `lms.course.v1` |
| `{org}.*` | Organization | `acme.invoice.v1` |

### 12.4 Schema Governance

- Core schemas (`fabric.*`) require protocol upgrade
- Community schemas (`social.*`, `media.*`) via community consensus
- Org schemas (`{org}.*`) managed by organization

---

## 13. Attestor Discovery

### 13.1 Attestor Registry

```json
{
  "type": "snapshot",
  "kind": "attestor_registry",
  "data": {
    "payment_attestors": [
      {
        "id": "ent:stripe-bridge",
        "name": "Stripe Payment Bridge",
        "supported_processors": ["stripe"],
        "endpoint": "https://stripe-bridge.fabric.network",
        "public_key": "ed25519:...",
        "fee": "1%",
        "status": "active"
      },
      {
        "id": "ent:paypal-bridge",
        "name": "PayPal Payment Bridge",
        "supported_processors": ["paypal"],
        "endpoint": "https://paypal-bridge.fabric.network",
        "public_key": "ed25519:...",
        "fee": "1.5%",
        "status": "active"
      }
    ],
    "identity_attestors": [
      {
        "id": "ent:email-verifier",
        "name": "Email Verification Service",
        "verification_types": ["email"],
        "endpoint": "https://verify.fabric.network"
      }
    ]
  }
}
```

### 13.2 Attestor Discovery API

```
GET /attestors                        List all attestors
GET /attestors?type=payment           Filter by type
GET /attestors/{id}                   Get attestor details
GET /attestors/{id}/status            Get current status
```

### 13.3 Attestor Revocation

If an attestor is compromised:

```json
{
  "type": "event",
  "kind": "attestor_revocation",
  "author": "ent:fabric-governance",
  "data": {
    "attestor": "ent:compromised-attestor",
    "reason": "Private key compromised",
    "effective_from": "2026-04-23T12:00:00Z",
    "credentials_affected": "all_after:2026-04-20T00:00:00Z"
  }
}
```

---

## Part V: API & Sync

---

## 14. Event Sync

### 14.1 Chain-Based Sync

Sync an author's event chain:

```
GET /events?author=ent:alice&after_seq=100&limit=50
```

Response:
```json
{
  "events": [
    {"id": "evt:a101", "seq": 101, "prev": "evt:a100", ...},
    {"id": "evt:a102", "seq": 102, "prev": "evt:a101", ...}
  ],
  "chain_head": "evt:a150",
  "has_more": true
}
```

### 14.2 Chain Verification

Clients MUST verify the chain on sync:

```python
def sync_author_chain(author, last_known_seq):
    events = fetch_events(author, after_seq=last_known_seq)
    
    for event in events:
        # Verify signature
        if not verify_signature(event):
            raise InvalidSignature(event)
        
        # Verify chain linkage
        if event.seq > 1:
            expected_prev = local_chain.get(event.seq - 1)
            if event.prev != hash(expected_prev):
                raise ChainBroken(event)
        
        # Verify no forks
        existing = local_chain.get(event.seq)
        if existing and existing.id != event.id:
            raise ForkDetected(event, existing)
        
        local_chain.add(event)
```

### 14.3 Fork Resolution

If a fork is detected:

```json
{
  "type": "fork_report",
  "author": "ent:alice",
  "seq": 42,
  "events": [
    {"id": "evt:fork1", "hash": "sha256:...", "timestamp": "..."},
    {"id": "evt:fork2", "hash": "sha256:...", "timestamp": "..."}
  ],
  "reporter": "ent:relay-xyz"
}
```

Resolution options:
1. **Timestamp tiebreaker**: Accept earlier timestamp
2. **Relay consensus**: Accept version seen by most relays
3. **Author resolution**: Author publishes resolution event
4. **Reject both**: Mark author as untrusted until resolved

---

## 15. Snapshot Sync

### 15.1 Get Current State

```
GET /snapshots/{entity_id}/profile        Get current profile
GET /snapshots/{entity_id}/keys           Get current keys
GET /snapshots/{content_id}/aggregate     Get engagement counts
```

### 15.2 Verify Against Log

Snapshots can be verified:

```python
def verify_snapshot(snapshot, event_log):
    # Reconstruct state from events
    reconstructed = reconstruct_state(
        entity=snapshot.entity,
        kind=snapshot.kind,
        events=event_log
    )
    
    # Compare
    return snapshot.data == reconstructed
```

---

## 16. Full API Reference

### 16.1 Events

```
POST   /events                           Publish event
GET    /events/{id}                      Get event
GET    /events?author={id}&after_seq={n} Sync author chain
GET    /events?thread_root={id}          Get thread events
GET    /events?target={id}&kind=react    Get reactions
```

### 16.2 Snapshots

```
GET    /snapshots/{entity}/profile       Get profile
GET    /snapshots/{entity}/keys          Get current keys
GET    /snapshots/{content}/aggregate    Get aggregates
GET    /snapshots/{group}/config         Get group config
```

### 16.3 Credentials

```
POST   /credentials                      Issue credential
GET    /credentials/{id}                 Get credential
GET    /credentials?source={id}          Credentials for entity
GET    /credentials?target={id}          Credentials about entity
```

### 16.4 Moderation

```
GET    /labels?target={id}               Labels for content
GET    /reports?target={id}              Reports (moderator only)
GET    /vouches?target={id}              Vouches for entity
GET    /reputation/{entity}              Reputation snapshot
```

### 16.5 Discovery

```
GET    /schemas                          List schemas
GET    /schemas/{id}                     Get schema
GET    /attestors                        List attestors
GET    /attestors/{id}                   Get attestor
```

### 16.6 Keys

```
GET    /keys/group/{group}               Group key package
GET    /keys/tier/{pub}/{tier}           Tier key (with credential)
POST   /keys/tier/{pub}/{tier}/request   Request tier key
```

---

## Part VI: Migration & Compatibility

---

## 17. Migration from v2.2

### 17.1 Mapping

| v2.2 Concept | v3.0 Concept |
|--------------|--------------|
| Entity | Snapshot (kind: profile) |
| Content | Event (kind: post/article/etc) |
| Link (relationship) | Event (kind: follow/block/etc) |
| Link (interaction) | Event (kind: react/reply/etc) |
| Link (credential) | Credential (unchanged) |

### 17.2 Migration Path

1. **Events**: Convert all v2.2 Content and Links to Events
2. **Chains**: Build author chains from timestamps (best-effort)
3. **Snapshots**: Compute current state from events
4. **Credentials**: Keep unchanged

### 17.3 Compatibility Mode

Relays can serve both formats:

```
GET /v2/content/{id}    → v2.2 format
GET /v3/events/{id}     → v3.0 format
```

---

## 18. Breaking Changes

| Change | Impact | Migration |
|--------|--------|-----------|
| Links → Events | High | Convert, build chains |
| Entity → Snapshot | Medium | Compute from events |
| `seq` author-signed | High | Rebuild chains |
| New moderation types | Low | Additive |

---

## Part VII: Summary

---

## 19. What's New in v3.0

### 19.1 Verifiable Ordering

- Author-signed `prev` chains
- Fork detection
- Relay-independent ordering

### 19.2 Moderation Primitives

- Labels (content classification)
- Reports (user flagging)
- Vouches (trust attestations)
- Reputation (aggregated trust)

### 19.3 Spam Resistance

- Proof-of-work option
- Stake-based posting
- Rate tokens

### 19.4 Scalability

- Log/State separation (Events vs Snapshots)
- Aggregation primitives (counters, rollups)
- Efficient sync (chain-based)

### 19.5 Discovery

- Schema registry
- Attestor discovery
- Revocation mechanisms

---

## 20. Comparison

| Feature | FABRIC v3.0 | FABRIC v2.2 | Relay 2.0 | Nostr |
|---------|-------------|-------------|-----------|-------|
| Primitives | Events + Snapshots | 3 (Entity/Content/Link) | Events + State | Events |
| Ordering | Author-signed chains | Relay-assigned seq | Author-signed prev | Timestamp |
| Fork detection | ✓ | ✗ | ✓ | ✗ |
| Moderation | Labels, Reports, Vouches | None | Labels | NIP-56 |
| Spam resistance | PoW, Stake, Tokens | Relay-level | PoW | None |
| Schema registry | ✓ | ✗ | ✗ | ✗ |
| Aggregates | ✓ Native | Implementation | ✓ | ✗ |

---

## 21. Known Limitations (Remaining)

### 21.1 Not Addressed in v3.0

| Issue | Status | Reason |
|-------|--------|--------|
| Global consensus | Not addressed | Intentionally decentralized |
| Content persistence | Relay-dependent | No protocol-level pinning |
| Key recovery | User responsibility | Self-sovereignty tradeoff |

### 21.2 Future Considerations (v4)

- Content-addressed persistence (IPFS/Arweave integration)
- Zero-knowledge proofs for privacy
- Cross-protocol bridges

---

*Protocol version: 3.0*
*Status: Draft*
*License: CC0 (Public Domain)*
