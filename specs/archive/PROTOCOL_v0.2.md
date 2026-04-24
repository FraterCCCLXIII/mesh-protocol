# WITNESS Protocol Specification v0.2

**WITNESS: Web of Interoperable Trust, Networks, Explanation, Signatures, and Streams**

A radically minimal decentralized social protocol built on cryptographic attestation semantics.

---

## Changelog (v0.2)

- Complete redesign from MESH v0.1
- Reduced from 4 primitives to 3: Witness, Pointer, Capability
- Added Explanation as mandatory metadata (not optional)
- Introduced Stream model (replaces Topic/Claim hybrid)
- Content/pointer separation (protocol handles attestations, not content)
- Capability certificates replace ACL whitelists
- Fork-based threading (Git model for conversations)
- Vector timestamps for multi-device operation
- Verifiable storage proofs for relay incentives

---

## 1. Core Philosophy

1. **Everything is a Witness**: A witness is a signed attestation that something exists, happened, or is endorsed. Posts, likes, follows, blocks, explanations — all witnesses.

2. **Content Lives Elsewhere**: The protocol handles *attestations about content*, not content itself. A post witness contains a pointer to content (IPFS, HTTP, inline), not the content. Relays are attestation servers, not content hosts.

3. **Streams, Not Logs**: A stream is a causal chain of witnesses. Streams can fork (replies), merge (aggregations), and filter (capabilities). Every actor has a personal stream; every conversation is a fork.

4. **Capabilities, Not ACLs**: Write access is proven by presenting a capability certificate, not by being on a list. Capabilities are portable, delegatable, and independently verifiable.

5. **Explanations Are Mandatory**: Every surfaced witness must have an explanation witness. "Why am I seeing this?" is not UX — it's protocol. Unexplained content cannot be rendered by compliant clients.

6. **Pull-First, Fork-Native**: Sync is pull-based (request what you want). Threading is fork-based (your reply is your fork of the conversation).

7. **Identity Is a Stream Head**: An identity is the current head of a personal stream. Key rotation, recovery, and delegation are all stream events.

8. **Verification Over Trust**: Any relay can serve any witness. Clients verify signatures, not relay identity. Relays are interchangeable caches.

9. **Multi-Device by Design**: Vector timestamps allow concurrent offline edits from multiple devices. No single sequence number.

10. **Protocol Defines Shape, Not Storage**: The protocol specifies data structures and verification rules. Storage location, retention policy, and hosting are out of scope.

---

## 2. Minimal Primitive Set

The protocol has exactly **3 primitives**:

| Primitive | Description |
|-----------|-------------|
| **Witness** | A signed attestation with type, pointer(s), vector timestamp, and explanation |
| **Pointer** | A content-addressed reference: `(hash, locations[])` |
| **Capability** | A signed delegation of authority: `(issuer, delegate, scope, expires)` |

### 2.1 Why Only Three?

**Witness** covers all social actions — it's the universal envelope.

**Pointer** separates content from attestation — enabling content-addressable everything.

**Capability** replaces identity documents, ACLs, group membership — all authority is explicit delegation.

Everything else — streams, forks, feeds, groups, DMs — emerges from these three.

---

## 3. Data Model

### 3.1 Pointer

A pointer is a content-addressed reference with location hints:

```json
{
  "hash": "sha256:3f8a7b2c...",
  "locations": [
    "ipfs://Qm...",
    "https://cdn.example.com/3f8a7b2c",
    "inline:<base64-content-if-small>"
  ]
}
```

**Rules:**
- `hash` is SHA-256 of canonical content bytes
- `locations` are hints; any location serving content with matching hash is valid
- Clients try locations in order, verify hash on receipt
- `inline:` prefix for small content (<1KB) embedded directly

### 3.2 Witness

A witness is a signed attestation:

```json
{
  "v": 2,
  "id": "sha256:<hash-of-canonical-witness>",
  "author": "ed25519:7xK4a2...",
  "vt": {"7xK4a2": 42, "9aL3b7": 17},
  "type": "post",
  "content": {
    "ptr": {"hash": "sha256:...", "locations": ["ipfs://..."]}
  },
  "refs": [],
  "explain": {
    "type": "author_stream",
    "issuer": "ed25519:7xK4a2..."
  },
  "cap": null,
  "sig": "ed25519:9d3f1a..."
}
```

#### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `v` | int | Protocol version (2) |
| `id` | string | SHA-256 hash of canonical witness (excluding `id`, `sig`) |
| `author` | string | Author's public key |
| `vt` | object | Vector timestamp: `{pubkey: counter}` per device/key |
| `type` | string | Witness type (see below) |
| `content` | object | Type-specific payload (usually contains pointers) |
| `refs` | array | Referenced witness IDs (for forks, replies, reactions) |
| `explain` | object | Why this witness exists (mandatory) |
| `cap` | object | Capability certificate if writing to non-self stream |
| `sig` | string | Ed25519 signature of `id` |

### 3.3 Vector Timestamp

Instead of a single sequence number, witnesses use vector timestamps:

```json
{
  "vt": {
    "ed25519:device1...": 42,
    "ed25519:device2...": 17
  }
}
```

**Semantics:**
- Each device/key increments its own counter
- Witness A causally precedes B if A's vector ≤ B's vector
- Concurrent witnesses (incomparable vectors) are both valid
- Clients merge concurrently using commutative semantics

**Why:** Enables offline multi-device operation without conflicts.

### 3.4 Explanation Object

Every witness must explain why it exists:

```json
{
  "explain": {
    "type": "followed_author",
    "issuer": "ed25519:viewer...",
    "via": "sha256:follow-witness-id"
  }
}
```

**Explanation Types:**

| Type | Meaning |
|------|---------|
| `author_stream` | I'm the author, this is my stream |
| `followed_author` | You follow this author |
| `reply_to_followed` | Reply to someone you follow |
| `mentioned` | You were mentioned |
| `capability_grant` | You have a capability to this stream |
| `indexer_surfaced` | An indexer you trust surfaced this |
| `peer_shared` | A peer explicitly shared this |
| `fork_of` | Fork of a witness you've seen |

**Critical Rule:** Compliant clients MUST NOT render witnesses without valid explanations. This makes algorithmic transparency a protocol invariant.

### 3.5 Capability Certificate

A capability is a signed delegation:

```json
{
  "type": "capability",
  "issuer": "ed25519:stream-owner...",
  "delegate": "ed25519:authorized-writer...",
  "scope": ["post", "react"],
  "stream": "sha256:stream-root-id",
  "expires_at": 1745536000,
  "sig": "ed25519:issuer-signature..."
}
```

**Usage:**
- To write to a stream you don't own, include the capability in `cap` field
- Relays verify capability chain before accepting
- Capabilities can be chained: A delegates to B, B delegates to C (if scope allows)

### 3.6 Core Witness Types

| Type | Purpose | Content | Refs |
|------|---------|---------|------|
| `genesis` | Create a stream | `name`, `rules` | None (this is stream root) |
| `post` | Public content | `ptr` to content | Optional: fork parent |
| `react` | Reaction | `emoji` | Target witness |
| `fork` | Reply/branch | `ptr` to content | Parent witness (creates new stream) |
| `follow` | Subscribe | None | Target stream root |
| `unfollow` | Unsubscribe | None | Target stream root |
| `delegate` | Issue capability | `scope`, `expires` | Delegate pubkey |
| `revoke` | Revoke capability | None | Capability witness |
| `keyrotate` | Rotate identity key | `new_key` | None |
| `recover` | Recover identity | `recovery_key` proof | None |
| `dm` | Encrypted message | `ciphertext`, `nonce`, `ephemeral` | Recipient stream |
| `label` | Content label | `labels[]`, `reason` | Target witness |
| `explain` | Standalone explanation | `why`, `for` | Target witness |
| `bundle` | Curated collection | `items[]` | None |

---

## 4. Streams

### 4.1 What Is a Stream?

A stream is a causal chain of witnesses sharing a common root. Every actor has a personal stream (rooted at their genesis witness). Streams can fork.

```
Stream: ed25519:alice (her personal stream)
    │
    ├── genesis (vt: {alice: 0})
    │
    ├── post (vt: {alice: 1})
    │
    ├── post (vt: {alice: 2})
    │       │
    │       └── [FORK by bob] ──> bob's reply stream
    │
    └── post (vt: {alice: 3, alice_phone: 1})  ← concurrent from two devices
```

### 4.2 Stream Identification

A stream is identified by its root witness ID:

```
stream:sha256:<root-witness-id>
```

For personal streams, the root is the genesis witness signed by the actor's key.

### 4.3 Forking

When Bob replies to Alice's post, Bob creates a **fork**:

```json
{
  "type": "fork",
  "author": "ed25519:bob...",
  "content": {
    "ptr": {"hash": "sha256:reply-content...", "locations": [...]}
  },
  "refs": ["sha256:alice-post-id"],
  "explain": {
    "type": "reply_to_followed",
    "via": "sha256:bob-follows-alice"
  }
}
```

**Fork semantics:**
- Bob's fork creates a new stream rooted at his fork witness
- The fork references Alice's post but lives in Bob's namespace
- Alice sees Bob's fork if she follows Bob (or someone who does shares it)
- Thread views are constructed by traversing forks

### 4.4 Thread Construction

To build a thread view from a root post:

1. Gather all `fork` witnesses referencing the root
2. Recursively gather forks of forks
3. Filter by your follow graph (only show forks from people you trust)
4. Sort by vector timestamp (or client preference)

**Key insight:** There's no "canonical thread." Each viewer constructs their own view based on which forks they can see. This is censorship-resistant threading.

### 4.5 Group Streams

A group is a stream where multiple actors have write capabilities:

```json
{
  "type": "genesis",
  "author": "ed25519:group-creator...",
  "content": {
    "name": "Rust Developers",
    "description": "Discussion about Rust"
  },
  "explain": {"type": "author_stream", "issuer": "ed25519:group-creator..."}
}
```

Members are added via capability delegation:

```json
{
  "type": "delegate",
  "author": "ed25519:group-creator...",
  "content": {
    "scope": ["post", "react"],
    "expires_at": null
  },
  "refs": ["ed25519:new-member..."],
  "explain": {"type": "author_stream", "issuer": "ed25519:group-creator..."}
}
```

---

## 5. Sync / Networking Model

### 5.1 Design Principles

- **Pull-based**: Clients request streams/witnesses they want
- **Content-addressed**: Witnesses identified by hash, fetchable from anywhere
- **Relay-agnostic**: Any relay serving valid witnesses is acceptable
- **Diff-based**: Efficient sync via vector timestamp comparison

### 5.2 Node Types

| Type | Role |
|------|------|
| **Client** | Owns keys, creates witnesses, constructs views |
| **Relay** | Stores/serves witnesses, enforces capability checks |
| **Indexer** | Aggregates streams, provides discovery, issues explanations |
| **Content Host** | Stores actual content (IPFS, CDN, personal server) |

### 5.3 Sync Protocol

#### 5.3.1 Stream State Request

Client requests current state of a stream:

```
GET /stream/<stream-id>/state
```

Response:
```json
{
  "stream_id": "sha256:...",
  "heads": ["sha256:witness1", "sha256:witness2"],
  "vector": {"ed25519:alice": 42, "ed25519:bob": 17}
}
```

`heads` are the current tips (may be multiple if concurrent). `vector` is the merged vector timestamp.

#### 5.3.2 Diff Request

Client provides their known vector, gets missing witnesses:

```
POST /stream/<stream-id>/diff
{
  "known_vector": {"ed25519:alice": 40, "ed25519:bob": 17}
}
```

Response:
```json
{
  "witnesses": [
    { ... witness at alice:41 ... },
    { ... witness at alice:42 ... }
  ]
}
```

#### 5.3.3 Witness Fetch

Fetch specific witness by ID:

```
GET /witness/<witness-id>
```

Works on any relay that has it — content-addressed.

#### 5.3.4 Subscription (Real-time)

WebSocket subscription for new witnesses:

```json
{
  "type": "subscribe",
  "streams": ["sha256:stream1", "sha256:stream2"],
  "since_vector": {"ed25519:alice": 42}
}
```

Relay pushes new witnesses as they arrive.

### 5.4 Content Retrieval

Content is separate from witnesses. When a client sees a pointer:

```json
{"hash": "sha256:abc...", "locations": ["ipfs://Qm...", "https://..."]}
```

1. Try each location in order
2. Fetch bytes
3. Verify `sha256(bytes) == hash`
4. Cache locally

If all locations fail, client can query DHT or ask relays for alternative locations.

### 5.5 Transport

- **Primary**: QUIC (UDP, multiplexed, encrypted)
- **Fallback**: HTTPS
- **Encoding**: CBOR on wire, JSON for storage/debug

---

## 6. Identity & Auth

### 6.1 Identity Is a Stream

An identity is defined by its personal stream. The stream's genesis witness establishes the identity:

```json
{
  "type": "genesis",
  "author": "ed25519:7xK4a2...",
  "vt": {"ed25519:7xK4a2": 0},
  "content": {
    "name": "alice",
    "display_name": "Alice Smith"
  },
  "explain": {"type": "author_stream", "issuer": "ed25519:7xK4a2..."}
}
```

### 6.2 Key Hierarchy

```
Master Key (recovery, cold storage)
    │
    ├── Device Key 1 (laptop) ─── delegates via capability
    ├── Device Key 2 (phone) ─── delegates via capability
    └── Recovery Key (social recovery)
```

All keys appear in the same stream's vector timestamp. Delegation is explicit:

```json
{
  "type": "delegate",
  "author": "ed25519:master...",
  "content": {
    "scope": ["post", "react", "follow"],
    "expires_at": null
  },
  "refs": ["ed25519:device-key..."],
  "explain": {"type": "author_stream", "issuer": "ed25519:master..."}
}
```

### 6.3 Key Rotation

Rotation is a stream event:

```json
{
  "type": "keyrotate",
  "author": "ed25519:old-key...",
  "content": {
    "new_key": "ed25519:new-key...",
    "reason": "scheduled rotation"
  },
  "explain": {"type": "author_stream", "issuer": "ed25519:old-key..."}
}
```

After rotation:
- New witnesses use new key
- Old key can still sign revocations (for a grace period)
- Stream continues with new vector timestamp entries

### 6.4 Social Recovery

Recovery keys are pre-registered delegates with special scope:

```json
{
  "type": "delegate",
  "content": {
    "scope": ["recover"],
    "quorum": 3,
    "trustees": ["ed25519:friend1...", "ed25519:friend2...", "ed25519:friend3...", "ed25519:friend4...", "ed25519:friend5..."]
  }
}
```

Recovery requires M-of-N trustees signing a recovery witness.

### 6.5 Authentication

No sessions. Every witness is self-authenticating via signature. For relay write access:

1. Client signs witness
2. Relay verifies signature
3. If writing to non-self stream, relay verifies capability chain
4. Accept or reject

---

## 7. Derived Systems

### 7.1 Feed

**Construction:**
1. Collect `follow` witnesses from your stream
2. For each followed stream, fetch recent witnesses
3. Merge by vector timestamp
4. Filter by client preferences
5. Each displayed witness MUST have valid explanation

**Explanation chain:**
- Your post → `author_stream`
- Followed author's post → `followed_author`
- Reply to your post → `reply_to_followed`
- Indexer recommendation → `indexer_surfaced`

### 7.2 Comments (Forks)

Replies are forks. No centralized comment section.

**Your view of comments:**
1. Start from root post
2. Gather all `fork` witnesses referencing it
3. Filter to forks from followed accounts (or friends-of-friends)
4. Display as tree

**Key property:** You never see spam replies because you only see forks from your trust graph.

### 7.3 Reactions

A react witness:

```json
{
  "type": "react",
  "content": {"emoji": "❤️"},
  "refs": ["sha256:target-post"],
  "explain": {"type": "author_stream", "issuer": "..."}
}
```

Clients aggregate reacts from visible streams.

### 7.4 Groups

A group is a stream with shared write capabilities. The creator issues capabilities to members. Members post with their capability included.

**Group moderation:**
- Creator can revoke capabilities
- Members see only posts from active capability holders
- Revoked posts remain in stream but clients filter them

### 7.5 Direct Messages

E2EE using X25519 + XSalsa20-Poly1305:

```json
{
  "type": "dm",
  "content": {
    "ciphertext": "base64...",
    "nonce": "base64...",
    "ephemeral_pubkey": "base64..."
  },
  "refs": ["stream:sha256:recipient-stream"],
  "explain": {"type": "peer_shared", "issuer": "ed25519:sender..."}
}
```

DMs go to recipient's stream (if they accept) or a shared secret stream.

### 7.6 Bundles (Curated Collections)

A bundle is a signed list of pointers:

```json
{
  "type": "bundle",
  "content": {
    "title": "Best Rust articles this week",
    "items": [
      {"witness": "sha256:post1", "note": "Great intro"},
      {"witness": "sha256:post2", "note": "Deep dive"}
    ]
  },
  "explain": {"type": "author_stream", "issuer": "..."}
}
```

Bundles enable curation without centralized algorithms.

---

## 8. Moderation Model

### 8.1 Principles

- **No global moderation**: Protocol has no censorship mechanism
- **Fork-based filtering**: You only see forks from your trust graph
- **Label system**: Trusted labelers can tag content
- **Client enforcement**: Clients filter based on labels + trust

### 8.2 Labels

Anyone can issue labels:

```json
{
  "type": "label",
  "content": {
    "labels": ["nsfw", "spam"],
    "reason": "Explicit content"
  },
  "refs": ["sha256:target-witness"],
  "explain": {"type": "author_stream", "issuer": "ed25519:labeler..."}
}
```

**Label trust:**
- You follow labelers you trust
- Client aggregates labels from trusted labelers
- Display warnings or hide based on preferences

### 8.3 Spam Resistance

**Structural:**
- You only see witnesses from your follow graph (extended)
- New accounts have no reach until followed
- Fork model prevents spam from appearing in your thread view

**Optional mechanisms:**
- Relays can require proof-of-work for new streams
- Communities can require attention bonds (stake returned if accepted)
- Indexers can require social proof (N followers from established accounts)

### 8.4 Sybil Resistance

Sybil accounts exist but have no impact:
- Zero followers = zero reach
- Capability model requires explicit delegation
- Trust only flows from accounts you follow

---

## 9. Scalability Strategy

### 9.1 Single User (Local-Only)

- Client stores own stream + followed streams
- Can operate fully offline
- Sync when connected to any relay

**Storage:** ~50MB (5K witnesses @ 10KB average)
**Bandwidth:** ~5MB/day (diff sync)

### 9.2 Small Community (1,000 users)

- 2-3 community relays
- Each relay stores all community streams
- Clients diff-sync with nearest relay

**Storage per relay:** ~5GB
**Bandwidth per user:** ~20MB/day

### 9.3 Large Scale (1M users)

```
┌─────────────────────────────────────────────┐
│              Clients                        │
└─────────────────┬───────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼───┐    ┌────▼────┐   ┌────▼────┐
│ Relay │    │ Relay   │   │ Relay   │
│ Shard │    │ Shard   │   │ Shard   │
│  A-M  │    │  N-Z    │   │ Groups  │
└───────┘    └─────────┘   └─────────┘
    │             │             │
    └─────────────┼─────────────┘
                  │
         ┌────────▼────────┐
         │    Indexers     │
         │  (Discovery)    │
         └─────────────────┘
```

**Sharding:**
- Relays shard by stream ID prefix
- Indexers aggregate for discovery
- Content hosts scale independently

**Key properties:**
- No single relay needs all data
- Any relay can serve any stream (if they choose)
- Indexers are optional convenience

### 9.4 Verifiable Storage Proofs

Relays can prove they store a stream:

```
Client: "Prove you have stream X"
Relay: "Challenge me"
Client: "Give me witness with hash prefix 0x3f"
Relay: Returns matching witness
Client: Verifies
```

This enables:
- Reputation systems for relay reliability
- Payment for storage guarantees
- Detection of partial storage

---

## 10. Failure Modes

### 10.1 Key Loss

**Impact:** Lose control of stream

**Mitigations:**
- BIP-39 mnemonic backup
- Social recovery (M-of-N trustees)
- Hardware key support

**Graceful degradation:** Can start new identity, reference old one

### 10.2 Relay Failure

**Impact:** Can't sync some streams

**Mitigations:**
- Streams replicated across multiple relays
- Any relay can serve any stream
- Client caches locally

### 10.3 Content Host Failure

**Impact:** Pointers resolve to nothing

**Mitigations:**
- Multiple locations in pointer
- Content-addressable = any mirror works
- Popular content naturally replicated

### 10.4 Indexer Failure

**Impact:** Discovery harder

**Mitigations:**
- Indexers are optional
- Direct follow via out-of-band sharing
- Multiple competing indexers

### 10.5 Spam Attack

**Impact:** Attackers create many streams

**Mitigations:**
- No reach without follows
- Fork model isolates spam
- Proof-of-work for new streams (relay policy)

### 10.6 Capability Forgery

**Impact:** None — capabilities are cryptographically signed

**Verification:** Relay and client both verify capability chains

---

## 11. Comparison Table

| Aspect | WITNESS | MESH v0.1 | Parcha | Nostr | AT Protocol |
|--------|---------|-----------|--------|-------|-------------|
| **Primitives** | 3 | 4 | 3 | ~1 (event) | Many (Lexicon) |
| **Threading** | Fork-based | DAG refs | Pointers | e-tags | Record refs |
| **Content storage** | Separate (pointers) | Inline | Inline | Inline | PDS repos |
| **Sync** | Vector diff | Bloom filter | Range fetch | Subscription | MST diff |
| **Multi-device** | Vector clocks | Single seq | Single seq | No | Limited |
| **Explanation** | Mandatory | None | None | None | None |
| **ACL model** | Capabilities | Scope field | Whitelists | None | Labelers |
| **Moderation** | Fork-filter | Web-of-trust | Relay+client | Client | Labelers |
| **Identity** | Stream head | Keypair | Keypair | Keypair | DID |

### 11.1 Key Differentiators

**vs MESH v0.1:**
- Simpler (3 vs 4 primitives)
- Content/pointer separation
- Vector clocks for multi-device
- Mandatory explanations

**vs Parcha:**
- Fork-based threading > pointer-based
- Capabilities > whitelists
- Explanations built-in
- Vector clocks

**vs Nostr:**
- No relay dependency for discovery
- Fork model prevents spam visibility
- Explanations make algorithms transparent
- Multi-device support

**vs AT Protocol:**
- No central indexer (BGS)
- Simpler primitive set
- Content-addressable (not repo-bound)
- Explanations mandatory

---

## 12. Novel Contributions

### 12.1 Mandatory Explanation Objects

**No other protocol does this.**

Every witness that surfaces to a user must have a cryptographically signed explanation of why. This makes algorithmic transparency a protocol invariant, not a policy.

Effects:
- Can't secretly manipulate feeds
- Third parties can audit recommendations
- Users understand their information environment

### 12.2 Fork-Based Threading

Replies are forks, not references. Each participant owns their contribution. You construct threads from forks you trust.

Effects:
- No spam in your thread view (only see followed forks)
- No centralized thread owner
- Censorship-resistant conversations

### 12.3 Content/Pointer Separation

The protocol handles attestations. Content lives elsewhere.

Effects:
- Relays are trivially scalable (tiny attestations)
- Content can live on IPFS, CDN, personal server
- Migration is easy (just update pointers)

### 12.4 Capability Certificates

Authority is proven, not looked up.

Effects:
- No race conditions in membership
- Offline verification of write rights
- Delegatable, chainable, expirable

---

## 13. Radical Simplification

**The 50% reduction:** WITNESS has 3 primitives where MESH had 4 and other protocols have many more.

The key insight: **Scope** (from MESH) is subsumed by **Capability**. Instead of encoding visibility in each witness, visibility is determined by who has the capability to read. This unifies ACLs and scopes.

Additionally, **Claims** (MESH) become **Witnesses** with mandatory **Explanations**. The explanation isn't a separate primitive — it's a required field. This removes the "claim about a claim" complexity while maintaining auditability.

---

## 14. Implementation Notes

### 14.1 Wire Protocol

Same as MESH v0.1 but with:
- `DIFF_REQUEST` / `DIFF_RESPONSE` for vector-based sync
- `EXPLAIN_QUERY` to request explanation for any witness

### 14.2 Cryptographic Primitives

| Purpose | Algorithm |
|---------|-----------|
| Signing | Ed25519 |
| Encryption | X25519 + XSalsa20-Poly1305 |
| Hashing | SHA-256 |
| Key derivation | Argon2id |

### 14.3 Client Requirements

A compliant client MUST:
1. Verify all signatures before displaying
2. Verify capability chains for non-author witnesses
3. Reject witnesses without valid explanations
4. Display explanation metadata to users on request

---

## 15. Appendix: Example Flows

### 15.1 Alice Posts

```json
{
  "type": "post",
  "author": "ed25519:alice...",
  "vt": {"ed25519:alice": 42},
  "content": {
    "ptr": {
      "hash": "sha256:content-hash...",
      "locations": ["ipfs://Qm..."]
    }
  },
  "refs": [],
  "explain": {
    "type": "author_stream",
    "issuer": "ed25519:alice..."
  }
}
```

### 15.2 Bob Replies (Forks)

```json
{
  "type": "fork",
  "author": "ed25519:bob...",
  "vt": {"ed25519:bob": 17},
  "content": {
    "ptr": {
      "hash": "sha256:reply-hash...",
      "locations": ["https://bob.example/reply"]
    }
  },
  "refs": ["sha256:alice-post-id"],
  "explain": {
    "type": "reply_to_followed",
    "issuer": "ed25519:bob...",
    "via": "sha256:bob-follows-alice-witness"
  }
}
```

### 15.3 Carol Sees Both (Feed Construction)

Carol follows both Alice and Bob. Her client:

1. Fetches Alice's stream → sees Alice's post
2. Fetches Bob's stream → sees Bob's fork
3. Constructs thread: Alice's post with Bob's reply
4. Each has valid explanation (followed_author)

### 15.4 Dave Doesn't See Bob's Reply

Dave follows Alice but not Bob. His client:

1. Fetches Alice's stream → sees Alice's post
2. Doesn't fetch Bob's stream (not followed)
3. Thread shows only Alice's post

Dave is protected from spam/harassment in Bob's fork.

---

## 16. Future Extensions

- **Encrypted streams**: Full stream encryption with MLS
- **Gossip layer**: P2P propagation for resilience  
- **Payment rails**: Native micropayments for content
- **Verifiable computation**: ZK proofs over witness sets

---

*Protocol version: 0.2*
*Status: Draft*
*License: CC0 (Public Domain)*
