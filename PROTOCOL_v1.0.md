# FABRIC Protocol Specification v1.0

**FABRIC: Federated Architecture for Broadcast, Relationships, Identity, and Content**

A practical decentralized social protocol with semantic clarity, honest tradeoffs, and production-ready design.

---

## Changelog (v1.0)

### Breaking changes from WITNESS v0.3
- **Renamed**: WITNESS → FABRIC (reflects architectural shift)
- **Split**: "Everything is a Witness" → 7 semantic types
- **Replaced**: Vector clocks → Hybrid Logical Clocks (HLC)
- **Changed**: Fork-only threading → Canonical threads + optional forks
- **Relaxed**: Strict provenance → Graduated enforcement
- **Simplified**: Three-phase expiry → Two-phase
- **Merged**: Boundary into ViewDefinition
- **Rebranded**: "Radically minimal" → "Practically coherent"

---

## 1. Design Principles

### 1.1 What We Learned

| Trap | Problem | Our Fix |
|------|---------|---------|
| "Everything is X" | Hides semantic differences | 7 distinct types |
| Fork-only threading | Fragments conversations | Canonical threads + optional forks |
| Strict provenance | Brittleness, bootstrap hell | Graduated enforcement |
| Full vector clocks | O(n) at scale | Hybrid Logical Clocks |
| Complexity creep | Unusable spec | Cut to essentials |

### 1.2 Core Tenets

1. **Different things ARE different.** Posts, edges, reactions have different semantics. Don't hide it.

2. **Shared infrastructure, distinct types.** Signing, transport, timestamps are shared. Object semantics are not.

3. **Canonical by default, flexible by choice.** Threads have a canonical view. Forks exist for those who need them.

4. **Transparent but not brittle.** Provenance matters for ranked views, not for raw browsing.

5. **Scale-aware from day one.** HLC not vector clocks. Pull-based not push-heavy.

6. **Honest about tradeoffs.** We tell you what's guaranteed and what isn't.

---

## 2. Architecture Overview

### 2.1 Two Layers

```
┌─────────────────────────────────────────────────────┐
│                    VIEW LAYER                        │
│  ViewDefinitions + Boundaries → Materialized Feeds   │
└─────────────────────────┬───────────────────────────┘
                          │ computed from
┌─────────────────────────▼───────────────────────────┐
│                   OBJECT LAYER                       │
│  Identity │ Post │ Edge │ Reaction │ Message │ Label │
└─────────────────────────────────────────────────────┘
```

**Object Layer:** Signed, authoritative data objects with semantic types.

**View Layer:** Deterministic projections computed over object layer.

### 2.2 Seven Semantic Types

| Type | Authoritative By | Mutability | Primary Operation |
|------|------------------|------------|-------------------|
| **Identity** | Origin | Mutable (versioned) | Key management |
| **Post** | Author | Mutable (versioned) | Content publication |
| **Edge** | Source | Append-only log | Relationship changes |
| **Reaction** | Reactor | Append-only | Response to content |
| **Message** | Sender | Append-only, E2EE | Private communication |
| **Label** | Labeler | Append-only + supersede | Content metadata |
| **View** | Definer | Mutable (versioned) | Feed specification |

### 2.3 Shared Infrastructure

| Component | Implementation |
|-----------|----------------|
| Signing | Ed25519 |
| Hashing | SHA-256 |
| Timestamps | Hybrid Logical Clock (HLC) |
| Pointers | `{hash, locations[]}` |
| Capabilities | Signed delegation certificates |
| Transport | HTTPS + optional WebSocket |

---

## 3. Hybrid Logical Clocks

### 3.1 Why Not Vector Clocks

Vector clocks are elegant but don't scale:
- Size: O(n) in number of actors/devices
- Merge: O(n) comparison
- Pruning: Complex garbage collection

### 3.2 HLC Structure

```
┌────────────────────────────────────────────────────┐
│                  64-bit HLC                         │
├──────────────────────────┬─────────────────────────┤
│   48 bits: wall clock    │   16 bits: counter      │
│   (milliseconds)         │   (logical increment)   │
└──────────────────────────┴─────────────────────────┘
```

### 3.3 HLC Algorithm

```python
def send_event(local_hlc, wall_clock):
    # On creating a new event
    l_new = max(local_hlc.l, wall_clock)
    if l_new == local_hlc.l:
        c_new = local_hlc.c + 1
    else:
        c_new = 0
    return HLC(l_new, c_new)

def receive_event(local_hlc, received_hlc, wall_clock):
    # On receiving an event
    l_new = max(local_hlc.l, received_hlc.l, wall_clock)
    if l_new == local_hlc.l == received_hlc.l:
        c_new = max(local_hlc.c, received_hlc.c) + 1
    elif l_new == local_hlc.l:
        c_new = local_hlc.c + 1
    elif l_new == received_hlc.l:
        c_new = received_hlc.c + 1
    else:
        c_new = 0
    return HLC(l_new, c_new)
```

### 3.4 Properties

- **Compact:** 64 bits total
- **Monotonic:** Always increases
- **Causal:** Preserves happens-before
- **Bounded drift:** Wall clock anchors prevent unbounded drift
- **Efficient sync:** "Give me everything after HLC X"

### 3.5 Wire Format

```json
{
  "hlc": "0x0001926a3b4c5d6e"
}
```

Or as structured:
```json
{
  "hlc": {"l": 1714000000000, "c": 42}
}
```

---

## 4. Object Types

### 4.1 Identity

The actor's cryptographic identity and metadata.

```json
{
  "type": "identity",
  "id": "fabric:id:sha256:...",
  "pubkey": "ed25519:7xK4a2...",
  "version": 3,
  "hlc": "0x0001926a3b4c5d6e",
  "content": {
    "name": "alice",
    "display_name": "Alice Smith",
    "bio": "Building the future",
    "avatar": {"hash": "sha256:...", "locations": ["ipfs://..."]}
  },
  "keys": {
    "active": ["ed25519:7xK4a2..."],
    "recovery": ["ed25519:9bM3c8..."],
    "devices": {
      "ed25519:device1...": {"name": "laptop", "added": "..."},
      "ed25519:device2...": {"name": "phone", "added": "..."}
    }
  },
  "origins": ["https://alice.example/fabric/"],
  "profiles": ["fabric.profile.auditable"],
  "sig": "ed25519:..."
}
```

**Semantics:**
- Mutable with version increments
- Origin is authoritative
- Device keys for multi-device (not vector clocks)

### 4.2 Post

Published content with optional threading.

```json
{
  "type": "post",
  "id": "fabric:post:sha256:...",
  "author": "ed25519:7xK4a2...",
  "version": 1,
  "hlc": "0x0001926a3b4c5d6e",
  "content": {
    "text": "Hello, decentralized world!",
    "media": [
      {"hash": "sha256:...", "locations": ["ipfs://..."], "mime": "image/png"}
    ]
  },
  "reply_to": null,
  "quote": null,
  "channel": null,
  "expires_at": null,
  "sig": "ed25519:..."
}
```

**Threading Model:**

```json
{
  "type": "post",
  "id": "fabric:post:sha256:reply...",
  "author": "ed25519:9aL3b7...",
  "content": {"text": "Great point!"},
  "reply_to": "fabric:post:sha256:original...",
  "sig": "ed25519:..."
}
```

**Semantics:**
- `reply_to` creates canonical thread structure
- Threads are traversable via reply chains
- Views can filter/sort, but structure is objective
- Edits increment version (audit trail preserved)

### 4.3 Edge

Relationships between entities (append-only log of changes).

```json
{
  "type": "edge",
  "id": "fabric:edge:sha256:...",
  "source": "ed25519:7xK4a2...",
  "target": "ed25519:9aL3b7...",
  "edge_type": "follow",
  "action": "create",
  "hlc": "0x0001926a3b4c5d6e",
  "sig": "ed25519:..."
}
```

**Edge Types:**

| Type | Meaning |
|------|---------|
| `follow` | Subscribe to target's posts |
| `block` | Hide target, prevent interaction |
| `mute` | Hide target (private, no signal) |
| `member` | Join a group/channel |

**Semantics:**
- Append-only log of edge changes
- Current state = replay log
- `action`: `create` or `remove`

### 4.4 Reaction

Response to content (likes, emoji, bookmarks).

```json
{
  "type": "reaction",
  "id": "fabric:react:sha256:...",
  "author": "ed25519:7xK4a2...",
  "target": "fabric:post:sha256:...",
  "reaction_type": "like",
  "emoji": "❤️",
  "action": "create",
  "hlc": "0x0001926a3b4c5d6e",
  "sig": "ed25519:..."
}
```

**Semantics:**
- Append-only (create or remove, no edit)
- Aggregatable by clients
- `reaction_type`: `like`, `emoji`, `bookmark`, `repost`

### 4.5 Message

Private encrypted communication.

```json
{
  "type": "message",
  "id": "fabric:msg:sha256:...",
  "sender": "ed25519:7xK4a2...",
  "recipient": "ed25519:9aL3b7...",
  "hlc": "0x0001926a3b4c5d6e",
  "encryption": {
    "scheme": "x25519-xsalsa20-poly1305",
    "ephemeral_pubkey": "base64:...",
    "nonce": "base64:...",
    "ciphertext": "base64:..."
  },
  "sig": "ed25519:..."
}
```

**Semantics:**
- Append-only (immutable once sent)
- E2EE to recipient's key
- Sender signature proves authorship
- Conversation = messages where (sender, recipient) matches

### 4.6 Label

Metadata/moderation tags on content.

```json
{
  "type": "label",
  "id": "fabric:label:sha256:...",
  "labeler": "ed25519:moderator...",
  "target": "fabric:post:sha256:...",
  "labels": ["nsfw", "violence"],
  "reason": "Contains graphic content",
  "hlc": "0x0001926a3b4c5d6e",
  "supersedes": null,
  "sig": "ed25519:..."
}
```

**Semantics:**
- Append-only with supersession
- Multiple labelers can label same content
- Clients aggregate based on trusted labelers
- `supersedes`: replaces a previous label from same labeler

### 4.7 View

Feed/thread specification (computed over object layer).

```json
{
  "type": "view",
  "id": "fabric:view:sha256:...",
  "author": "ed25519:curator...",
  "version": 2,
  "hlc": "0x0001926a3b4c5d6e",
  "content": {
    "name": "Tech News",
    "sources": [
      {"kind": "author", "id": "ed25519:alice..."},
      {"kind": "author", "id": "ed25519:bob..."},
      {"kind": "channel", "id": "fabric:channel:tech"}
    ],
    "filter": {
      "types": ["post"],
      "exclude_replies": false
    },
    "sort": "reverse_chronological",
    "boundary": {
      "after_hlc": "0x0001926a3b4c5d6e",
      "limit": 100
    }
  },
  "sig": "ed25519:..."
}
```

**Semantics:**
- Mutable specification (version increments)
- Deterministic given same inputs + boundary
- Clients can recompute to verify
- `boundary` defines the finite input set

---

## 5. Threading Model

### 5.1 Canonical Threads (Default)

Threads are determined by `reply_to` chains:

```
Post A (root)
├── Post B (reply_to: A)
│   ├── Post D (reply_to: B)
│   └── Post E (reply_to: B)
└── Post C (reply_to: A)
    └── Post F (reply_to: C)
```

**Properties:**
- Objective structure (same for all viewers)
- Traversable via reply chains
- Sortable within thread (by HLC, votes, etc.)

### 5.2 Thread Views

Views can customize thread presentation:

```json
{
  "type": "view",
  "content": {
    "kind": "thread",
    "root": "fabric:post:sha256:...",
    "sort": "chronological",
    "filter": {
      "min_trust": 0.5,
      "exclude_blocked": true
    }
  }
}
```

### 5.3 Optional Fork Mode

For privacy-focused or censorship-resistant contexts:

```json
{
  "type": "post",
  "content": {"text": "My take on this..."},
  "reply_to": "fabric:post:sha256:original...",
  "fork_mode": true
}
```

**Fork semantics:**
- Post exists in author's stream only
- Not automatically visible in canonical thread
- Viewer must explicitly follow author to see
- Useful for: controversial replies, private annotations

**Default is canonical.** Forks are opt-in.

---

## 6. Provenance (Graduated Enforcement)

### 6.1 When Required

Provenance is **REQUIRED** for:
- Algorithmic/ranked feeds
- "For You" style recommendations
- Cross-origin aggregations
- Indexer-surfaced content

```json
{
  "provenance": {
    "type": "indexer_surfaced",
    "indexer": "ed25519:indexer...",
    "reason": "trending_in_network",
    "score": 0.85,
    "boundary": {"after_hlc": "...", "sources": [...]}
  }
}
```

### 6.2 When Optional

Provenance is **OPTIONAL** for:
- Chronological home timeline (you follow them)
- Direct profile viewing
- Thread expansion
- Search results

### 6.3 Degraded Rendering

When provenance is missing but expected:
- Show content with warning: "Source unverified"
- Lower visual prominence
- **Never invisible** (prevents censorship via provenance-stripping)

---

## 7. Capabilities

### 7.1 Capability Certificate

```json
{
  "type": "capability",
  "id": "fabric:cap:sha256:...",
  "issuer": "ed25519:owner...",
  "delegate": "ed25519:writer...",
  "scope": ["post", "react"],
  "resource": "fabric:channel:tech",
  "expires_at": "2026-12-31T23:59:59Z",
  "hlc": "0x0001926a3b4c5d6e",
  "sig": "ed25519:..."
}
```

### 7.2 Capability Chains

A can delegate to B, B can delegate to C (if scope allows):

```
Owner → Admin (full scope)
         └→ Moderator (label scope only)
              └→ Bot (auto-label scope)
```

**Verification:** Walk chain back to owner, verify all signatures.

### 7.3 Revocation

```json
{
  "type": "capability.revoke",
  "target": "fabric:cap:sha256:...",
  "reason": "access_removed",
  "hlc": "0x0001926a3b4c5d6e",
  "sig": "ed25519:issuer..."
}
```

---

## 8. Two-Phase Expiry

### 8.1 Phase A: Active

While `expires_at` is in the future or null:
- Normal operations
- Included in feeds and queries
- Synced and relayed

### 8.2 Phase B: Expired

After `expires_at` passes:
- Not included in default queries
- May still be fetched directly (with `expired: true` flag)
- May be garbage collected after retention period

**Key point:** "Expired" is operational status, not audit erasure.

---

## 9. Verifiability Profiles

### 9.1 `fabric.profile.minimal`

- Origin-attested state is trusted
- Full audit trail not required
- Suitable for lightweight clients, caches

### 9.2 `fabric.profile.auditable`

- Every state change has corresponding log entry
- State reconstructable from object history
- Full cryptographic audit possible

**Declaration:**
```json
{
  "profiles": ["fabric.profile.auditable"]
}
```

---

## 10. Sync Protocol

### 10.1 HLC-Based Diff

```
GET /sync?after_hlc=0x0001926a3b4c5d6e&types=post,edge&limit=100
```

Response:
```json
{
  "objects": [...],
  "latest_hlc": "0x0001926a3b4c5d6f",
  "has_more": true
}
```

### 10.2 Subscription (WebSocket)

```json
{
  "op": "subscribe",
  "filters": [
    {"type": "post", "authors": ["ed25519:alice..."]},
    {"type": "edge", "targets": ["ed25519:me..."]}
  ]
}
```

### 10.3 Snapshot

```json
{
  "type": "snapshot",
  "id": "fabric:snap:sha256:...",
  "scope": {"authors": ["ed25519:..."], "types": ["post", "edge"]},
  "as_of_hlc": "0x0001926a3b4c5d6e",
  "root_hash": "sha256:...",
  "object_count": 15234
}
```

With Merkle proofs for membership verification.

---

## 11. Comparison

| Aspect | FABRIC v1.0 | WITNESS v0.3 | Relay 2.0 | Nostr |
|--------|-------------|--------------|-----------|-------|
| **Primitives** | 7 semantic types | 4 (everything witness) | Event + State | 1 (event) |
| **Timestamps** | HLC (64-bit) | Vector clocks | Single seq | Unix |
| **Threading** | Canonical + optional fork | Fork-only | Pointer-based | e-tags |
| **Provenance** | Graduated | Strict mandatory | None | None |
| **Expiry** | Two-phase | Three-phase | Three-phase | None |
| **Content** | Inline + pointers | Pointers only | Inline | Inline |
| **Complexity** | Medium | High | High | Low |
| **Scalability** | Good | Questionable | Good | Good |

---

## 12. What We Cut

| Removed | Why |
|---------|-----|
| Full vector clocks | O(n) scaling problem |
| "Everything is a witness" | Hides semantic differences |
| Fork-only threading | Fragments conversations |
| Strict provenance requirement | Brittleness, censorship vector |
| Three-phase expiry | Unnecessary complexity |
| Separate Boundary object | Merged into ViewDefinition |
| "Radically minimal" branding | It wasn't true |

---

## 13. What We Kept

| Kept | Why |
|------|-----|
| Two-layer architecture | Clean separation of truth vs views |
| Content-addressed pointers | Scalable content delivery |
| Capability-based auth | Flexible, delegatable |
| Verifiability profiles | Honest interop |
| Merkle snapshots | Verifiable partial storage |
| E2EE messaging | Privacy fundamental |
| Ed25519 + SHA-256 | Battle-tested crypto |

---

## 14. Migration from WITNESS

### 14.1 Object Mapping

| WITNESS | FABRIC |
|---------|--------|
| Witness (type: post) | Post |
| Witness (type: follow) | Edge (edge_type: follow) |
| Witness (type: react) | Reaction |
| Witness (type: fork) | Post with reply_to + fork_mode |
| Witness (type: dm) | Message |
| Witness (type: label) | Label |
| ViewDefinition | View |

### 14.2 Timestamp Migration

```python
def vector_to_hlc(vt: dict) -> int:
    # Take max timestamp from vector, add small counter
    max_ts = max(vt.values())
    return (max_ts << 16) | (len(vt) & 0xFFFF)
```

---

## 15. Implementation Checklist

### 15.1 Minimum Viable

- [ ] Identity creation and resolution
- [ ] Post create/read
- [ ] Edge create (follow)
- [ ] HLC generation
- [ ] Signature verification
- [ ] Basic sync (HLC-based diff)

### 15.2 Full Implementation

- [ ] All 7 object types
- [ ] Capability delegation
- [ ] Message encryption
- [ ] View computation
- [ ] Merkle snapshots
- [ ] WebSocket subscriptions
- [ ] Expiry handling

---

## 16. Conclusion

FABRIC is what WITNESS should have been: a **practically coherent** protocol that respects semantic differences while sharing infrastructure.

**Key improvements:**
1. **Semantic types** replace "everything is X"
2. **HLC** replaces vector clocks
3. **Canonical threading** replaces fork-only
4. **Graduated provenance** replaces strict requirements
5. **Simpler expiry** replaces three-phase

The result is a protocol that's:
- **Implementable** (clear semantics)
- **Scalable** (HLC, not vectors)
- **Usable** (canonical threads)
- **Honest** (about what's guaranteed)

---

*Protocol version: 1.0*
*Status: Draft*
*License: CC0 (Public Domain)*
