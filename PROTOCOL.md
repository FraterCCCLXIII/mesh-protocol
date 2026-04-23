# MESH Protocol Specification v0.1

**MESH: Minimal Extensible Social Hypergraph**

A next-generation decentralized social network protocol designed from first principles.

---

## 1. Core Philosophy

1. **Claims, not Events**: The atomic unit is a cryptographically signed *claim* — a statement made by an identity at a point in time. Everything else is derived.

2. **Content-Addressed DAG**: Claims reference each other by hash, forming a Merkle-DAG. This enables efficient sync, deduplication, and tamper-proof history.

3. **One Primitive, Many Uses**: Likes, follows, replies, memberships — all are just claims with different `type` fields. No special-case logic.

4. **Identity is Keys**: An identity IS a keypair. No usernames at the protocol level. Human-readable names are claims (self-asserted or attested).

5. **Local-First with Relay Assistance**: Every node stores its own claims. Relays are optional accelerators, not required infrastructure.

6. **Pull-Primary, Push-Optional**: Sync is pull-based (request what you need). Real-time updates via optional WebSocket subscriptions.

7. **Scopes, not ACLs**: Visibility is encoded as a *scope* — public, followers, group, or encrypted-to-keys. Simple, composable.

8. **Trust is Social**: Moderation is Web-of-Trust based. You trust who your trusted contacts trust. No global moderation authority.

9. **Sync is Set Reconciliation**: Nodes exchange Bloom filters of claim hashes, then transfer only missing claims. Bandwidth-efficient.

10. **Encryption is Opt-In Per-Claim**: Public content is plaintext. Private content uses NaCl box encryption to recipient keys.

---

## 2. Minimal Primitive Set

The protocol has exactly **4 primitives**:

| Primitive | Description |
|-----------|-------------|
| **Identity** | An Ed25519 keypair. The public key IS the identity. |
| **Claim** | A signed JSON object with content, type, and references. |
| **Reference** | A content-addressed link (hash) to another claim or identity. |
| **Scope** | Visibility metadata: `public`, `followers`, `group:<id>`, or `encrypted:<keys>`. |

### 2.1 Why These Four?

- **Identity**: You need actors.
- **Claim**: You need statements.
- **Reference**: You need to link statements (replies, reactions, threading).
- **Scope**: You need visibility control.

Everything else — feeds, comments, likes, groups, DMs — is built from these.

---

## 3. Data Model

### 3.1 Identity

```json
{
  "type": "identity",
  "pubkey": "ed25519:<base58-public-key>",
  "created_at": 1714000000
}
```

Identities are implicit — they exist when a claim is signed by a key. Optional identity metadata (display name, avatar) is published as claims.

### 3.2 Claim

```json
{
  "v": 1,
  "id": "<sha256-hash-of-canonical-content>",
  "pubkey": "ed25519:<base58-public-key>",
  "created_at": 1714000000,
  "type": "<claim-type>",
  "scope": "public",
  "content": { ... },
  "refs": ["<claim-hash>", "<claim-hash>"],
  "sig": "<ed25519-signature-base58>"
}
```

#### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `v` | int | Protocol version (currently 1) |
| `id` | string | SHA-256 hash of canonical JSON (excluding `id` and `sig`) |
| `pubkey` | string | Author's public key |
| `created_at` | int | Unix timestamp (seconds) |
| `type` | string | Claim type (see below) |
| `scope` | string | Visibility scope |
| `content` | object | Type-specific payload |
| `refs` | array | Referenced claim/identity hashes |
| `sig` | string | Ed25519 signature of `id` |

### 3.3 Core Claim Types

| Type | Purpose | Content Fields | Refs |
|------|---------|----------------|------|
| `post` | Public post | `text`, `media[]` | Optional: reply-to |
| `react` | Reaction | `emoji` | Target claim |
| `follow` | Follow | `action`: "follow"/"unfollow" | Target identity |
| `profile` | Profile data | `name`, `bio`, `avatar` | None |
| `group` | Create group | `name`, `rules` | None |
| `membership` | Join/leave group | `action`: "join"/"leave" | Target group |
| `dm` | Direct message | `ciphertext` | Recipient identity |
| `block` | Block user | None | Target identity |
| `attest` | Vouch for identity | `statement` | Target identity |

### 3.4 Scope Values

| Scope | Meaning |
|-------|---------|
| `public` | Visible to anyone |
| `followers` | Visible to author's followers |
| `group:<claim-id>` | Visible to group members |
| `encrypted:<pubkey1,pubkey2,...>` | Encrypted to listed keys |

### 3.5 Canonical JSON

For hashing and signing, claims are serialized as:
- Keys sorted alphabetically
- No whitespace
- UTF-8 encoded
- `id` and `sig` fields excluded during hash computation

### 3.6 Example: A Post

```json
{
  "v": 1,
  "id": "sha256:3f8a7b...",
  "pubkey": "ed25519:7xK4a2...",
  "created_at": 1714000000,
  "type": "post",
  "scope": "public",
  "content": {
    "text": "Hello, decentralized world!",
    "media": []
  },
  "refs": [],
  "sig": "sig:9d3f1a..."
}
```

### 3.7 Example: A Reply

```json
{
  "v": 1,
  "id": "sha256:8b2c1f...",
  "pubkey": "ed25519:9aL3b7...",
  "created_at": 1714000060,
  "type": "post",
  "scope": "public",
  "content": {
    "text": "Welcome! Great to have you here."
  },
  "refs": ["sha256:3f8a7b..."],
  "sig": "sig:2e7c9a..."
}
```

### 3.8 Example: A Like

```json
{
  "v": 1,
  "id": "sha256:1c4d2e...",
  "pubkey": "ed25519:5bM2c8...",
  "created_at": 1714000120,
  "type": "react",
  "scope": "public",
  "content": {
    "emoji": "👍"
  },
  "refs": ["sha256:3f8a7b..."],
  "sig": "sig:7f1a3c..."
}
```

---

## 4. Sync / Networking Model

### 4.1 Design Principles

- **Pull-primary**: Nodes request claims they want. No unsolicited push.
- **Bloom-based reconciliation**: Efficient sync with minimal bandwidth.
- **Relay-assisted**: Relays cache and forward, but are not required.
- **DHT for discovery**: Find where claims live without central registry.

### 4.2 Node Types

| Type | Description | Required? |
|------|-------------|-----------|
| **User Node** | Stores user's own claims + claims they care about | Yes (at least one) |
| **Relay Node** | Caches claims, serves queries, optional WebSocket | No |
| **Bootstrap Node** | DHT entry point for peer discovery | Yes (a few public ones) |

### 4.3 Sync Protocol

#### 4.3.1 Claim Announcement

When a node creates a claim:
1. Compute claim hash
2. Sign claim
3. Store locally
4. Announce hash to DHT (key: pubkey, value: list of recent claim hashes)
5. Optionally push to subscribed relays

#### 4.3.2 Claim Retrieval

To get claims from an identity:
1. Query DHT for identity's pubkey → get list of claim hashes
2. Query DHT for each hash → get nodes that have it
3. Request claims from those nodes
4. Verify signature on receipt

#### 4.3.3 Bloom Filter Sync

For efficient sync between nodes:

```
Node A                          Node B
   |                               |
   |-- SYNC_REQUEST(my_bloom) ---> |
   |                               |
   |<-- SYNC_RESPONSE(missing) --- |
   |                               |
   |-- CLAIMS(missing_claims) ---> |
   |                               |
```

- `my_bloom`: Bloom filter of claim hashes Node A has
- `missing`: List of hashes Node B has that aren't in bloom
- Node A then requests those claims

#### 4.3.4 Subscription (Real-time)

Nodes can subscribe to updates:

```json
{
  "type": "subscribe",
  "filter": {
    "authors": ["ed25519:7xK4a2...", "ed25519:9aL3b7..."],
    "types": ["post", "react"],
    "since": 1714000000
  }
}
```

Relay pushes matching claims as they arrive.

### 4.4 Transport

- **Primary**: QUIC (UDP-based, multiplexed, encrypted)
- **Fallback**: WebSocket over HTTPS
- **Encoding**: CBOR for wire format (compact), JSON for storage/display

### 4.5 Addressing

```
mesh://<pubkey>/<claim-hash>
mesh://<pubkey>                   # All claims by this identity
mesh://relay.example.com/<hash>  # Claim via relay
```

---

## 5. Identity & Auth

### 5.1 Identity Model

**Identity = Ed25519 Keypair**

- Public key: 32 bytes, base58 encoded with `ed25519:` prefix
- Private key: 64 bytes, never leaves device (or secure enclave)

No usernames, no registration. Generate a keypair = have an identity.

### 5.2 Key Derivation

Use BIP-39 mnemonic (24 words) for human-recoverable seed:

```
seed = PBKDF2(mnemonic, "mesh-identity", 100000, SHA-512)
keypair = Ed25519.from_seed(seed[0:32])
```

### 5.3 Key Hierarchy (Optional)

For multi-device / key rotation:

```
Master Key (cold storage, recovery)
    └── Device Key 1 (signed by master)
    └── Device Key 2 (signed by master)
    └── App Key (limited permissions)
```

Device keys are authorized via `delegate` claims:

```json
{
  "type": "delegate",
  "content": {
    "delegate_to": "ed25519:<device-pubkey>",
    "permissions": ["post", "react", "follow"],
    "expires_at": 1745536000
  },
  "refs": [],
  "pubkey": "ed25519:<master-pubkey>",
  ...
}
```

### 5.4 Key Rotation

1. Create new keypair
2. Publish `rotate` claim from old key:
   ```json
   {
     "type": "rotate",
     "content": {
       "new_key": "ed25519:<new-pubkey>",
       "reason": "scheduled rotation"
     }
   }
   ```
3. New key publishes `accept_rotation` claim referencing the rotate claim
4. Followers update their local mapping

### 5.5 Human-Readable Names

Names are NOT protocol-level. They're claims:

**Self-asserted:**
```json
{
  "type": "profile",
  "content": {
    "name": "alice",
    "display_name": "Alice Smith"
  }
}
```

**Attested (more trustworthy):**
```json
{
  "type": "attest",
  "content": {
    "statement": "This is the real Alice Smith",
    "name": "alice"
  },
  "refs": ["ed25519:<alice-pubkey>"],
  "pubkey": "ed25519:<trusted-attestor>"
}
```

Clients can show names with trust indicators based on attestation count.

### 5.6 Authentication

Nodes authenticate via challenge-response:

```
Client                           Server
   |                                |
   |-- AUTH_INIT(my_pubkey) ------> |
   |                                |
   |<-- CHALLENGE(nonce, ts) ------ |
   |                                |
   |-- AUTH_RESPONSE(sig(nonce)) -> |
   |                                |
   |<-- AUTH_OK(session_token) ---- |
```

Session tokens are short-lived (1 hour) and scoped to specific operations.

---

## 6. Derived Systems

All social features are built from the 4 primitives. No special-case logic.

### 6.1 Feed

**Construction:**
1. Collect `follow` claims by user
2. Get followed identities' `post` claims (with `scope: public` or appropriate scope)
3. Sort by `created_at` descending
4. Apply client-side filters (muted words, blocked users)

**Caching:**
Relays can pre-compute feeds for users who opt-in.

### 6.2 Comments (Replies)

A reply is a `post` claim where `refs` contains the parent claim hash:

```json
{
  "type": "post",
  "content": { "text": "Great point!" },
  "refs": ["sha256:<parent-post-hash>"]
}
```

**Thread construction:**
1. Given root post hash
2. Query for all claims where `refs` contains root hash
3. Recursively build tree
4. Sort by `created_at` or votes

### 6.3 Likes / Reactions

A reaction is a `react` claim:

```json
{
  "type": "react",
  "content": { "emoji": "❤️" },
  "refs": ["sha256:<target-post-hash>"]
}
```

**Aggregation:**
Clients count `react` claims per target, grouped by emoji.

### 6.4 Groups

**Create group:**
```json
{
  "type": "group",
  "content": {
    "name": "Rust Developers",
    "description": "Discussion about Rust",
    "rules": "Be kind. No spam."
  }
}
```

The claim hash becomes the group ID.

**Join group:**
```json
{
  "type": "membership",
  "content": { "action": "join" },
  "refs": ["sha256:<group-claim-hash>"]
}
```

**Post to group:**
```json
{
  "type": "post",
  "scope": "group:sha256:<group-claim-hash>",
  "content": { "text": "Hello group!" }
}
```

**Moderation:**
Group creator can publish `moderate` claims:
```json
{
  "type": "moderate",
  "content": {
    "action": "remove",
    "reason": "spam"
  },
  "refs": ["sha256:<offending-post>", "sha256:<group-hash>"]
}
```

Clients interpret these when rendering group content.

### 6.5 Direct Messaging

**Encryption:** X25519 (Curve25519 Diffie-Hellman) + XSalsa20-Poly1305

**Key exchange:**
Ed25519 signing keys are converted to X25519 for encryption.

**Message structure:**
```json
{
  "type": "dm",
  "scope": "encrypted:ed25519:<recipient-pubkey>",
  "content": {
    "ciphertext": "<base64-encrypted-payload>",
    "nonce": "<base64-nonce>",
    "ephemeral_pubkey": "<base64-x25519-pubkey>"
  },
  "refs": ["ed25519:<recipient-pubkey>"]
}
```

**Decryption flow:**
1. Recipient converts their Ed25519 key to X25519
2. Derive shared secret: X25519(recipient_private, ephemeral_pubkey)
3. Decrypt: XSalsa20-Poly1305(ciphertext, nonce, shared_secret)

**Forward secrecy:**
Each message uses a fresh ephemeral keypair. Optionally, implement Double Ratchet for full forward secrecy.

**Group DMs:**
Encrypt to multiple keys. Each recipient can decrypt independently.

### 6.6 Reposts / Boosts

A repost is a claim that references the original:

```json
{
  "type": "repost",
  "content": {
    "comment": "This is brilliant!"
  },
  "refs": ["sha256:<original-post-hash>"]
}
```

### 6.7 Mentions

Mentions are inline in content with explicit refs:

```json
{
  "type": "post",
  "content": {
    "text": "Thanks @alice for the help!",
    "mentions": [
      { "name": "alice", "pubkey": "ed25519:7xK4a2..." }
    ]
  },
  "refs": ["ed25519:7xK4a2..."]
}
```

---

## 7. Moderation Model

### 7.1 Design Principles

- **No global moderation**: Protocol has no built-in censorship
- **Client-side filtering**: Users choose what to see
- **Social trust**: Trust propagates through follow graph
- **Opt-in shared lists**: Communities share blocklists

### 7.2 Trust Graph

Each user has a local trust score for every identity:

```
trust(A) = Σ (weight(B) × trust_assignment(B, A)) for B in followed
```

Where:
- `weight(B)` = how much you trust B (based on your interaction history)
- `trust_assignment(B, A)` = B's explicit trust claim about A (-1 to +1)

### 7.3 Block & Mute

**Block:** Publish a `block` claim
```json
{
  "type": "block",
  "refs": ["ed25519:<blocked-pubkey>"]
}
```

Effects (client-side):
- Blocked user's posts hidden from your feed
- Blocked user can't see your posts (if you choose)
- Your block is visible to others (signals distrust)

**Mute:** Client-local only, no claim published.

### 7.4 Shared Blocklists

Users can publish curated blocklists:

```json
{
  "type": "blocklist",
  "content": {
    "name": "Known Spam Accounts",
    "description": "Community-maintained spam list",
    "blocked": ["ed25519:...", "ed25519:..."]
  }
}
```

Others can subscribe by following the blocklist author and trusting their `blocklist` claims.

### 7.5 Spam Resistance

**Rate limiting (relay-enforced):**
- Relays can require proof-of-work for publishing
- Relays can limit claims per identity per time window

**Proof-of-work claim:**
```json
{
  "type": "pow",
  "content": {
    "target_claim": "sha256:<claim-hash>",
    "nonce": 12345678,
    "difficulty": 20
  }
}
```

Where `SHA256(target_claim + nonce)` has `difficulty` leading zero bits.

**Social proof:**
- New accounts with no trust graph connections are flagged
- Clients can require N followers from trusted accounts before showing content

### 7.6 Sybil Resistance

Combine multiple signals:
1. **Age**: Account age (first claim timestamp)
2. **Activity**: Consistent posting history
3. **Trust graph**: Connections to established accounts
4. **Attestations**: Vouches from trusted identities
5. **Proof-of-work**: Computational cost to create identity

Clients compute a "legitimacy score" and filter accordingly.

### 7.7 Content Labeling

Trusted labelers can publish content warnings:

```json
{
  "type": "label",
  "content": {
    "labels": ["nsfw", "violence"],
    "reason": "Contains graphic content"
  },
  "refs": ["sha256:<target-claim>"]
}
```

Clients filter based on user preferences + trusted labelers.

---

## 8. Scalability Strategy

### 8.1 Single User (1 node)

**Architecture:**
- User runs a node on their device (phone/laptop/Raspberry Pi)
- Node stores all user's claims + claims from followed accounts
- Connects to DHT for discovery
- Optionally uses 1-2 relays for availability

**Storage:** ~100 MB (10,000 claims @ 10 KB average)
**Bandwidth:** ~10 MB/day (sync with followed accounts)
**CPU:** Minimal (verify signatures, render feeds)

### 8.2 Small Community (1,000 users)

**Architecture:**
- Most users run personal nodes
- 2-3 community relays for caching and search
- DHT handles discovery
- Relays pre-compute popular feeds

**Storage per node:** ~1 GB (100,000 claims)
**Relay storage:** ~10 GB (all community claims)
**Bandwidth:** ~50 MB/day per user

### 8.3 Large Scale (1 million users)

**Architecture:**

```
┌─────────────────────────────────────────────────────────┐
│                     User Nodes                          │
│  (Personal devices, store own claims + followed)        │
└─────────────────────┬───────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
┌─────────▼─────────┐   ┌────────▼─────────┐
│   Regional Relays │   │  Specialized     │
│   (Geographic)    │   │  Relays (Topics) │
└─────────┬─────────┘   └────────┬─────────┘
          │                       │
          └───────────┬───────────┘
                      │
          ┌───────────▼───────────┐
          │    DHT Bootstrap      │
          │    Nodes (Discovery)  │
          └───────────────────────┘
```

**Sharding strategy:**
- Relays specialize by topic, geography, or time range
- DHT distributes claim hash → node mappings
- Popular content replicated across many nodes (natural caching)

**Feed computation:**
- Users can run their own feed algorithms
- Relays offer pre-computed feeds as a service
- Open-source feed algorithms prevent filter bubbles

**Storage:**
- User nodes: ~5 GB (followed content + local cache)
- Major relays: ~1 TB (partial index)
- No single node needs all data

**Bandwidth optimization:**
- Bloom filter sync reduces transfer 10-100x
- Content-addressed dedup
- CDN integration for media

### 8.4 Scaling Properties

| Aspect | How It Scales |
|--------|---------------|
| Storage | Distributed; each node stores what it cares about |
| Bandwidth | Pull-based; no broadcast storms |
| Discovery | DHT; O(log n) lookups |
| Feed computation | Parallelizable; relay-assisted |
| Verification | Parallel signature verification |

---

## 9. Failure Modes

### 9.1 DHT Partition

**Problem:** Network partition splits DHT, nodes can't find each other.

**Mitigation:**
- Multiple bootstrap nodes in different regions
- Local cache of known peers
- Relay fallback for discovery

**Recovery:** Automatic healing when connectivity restored.

### 9.2 Key Loss

**Problem:** User loses private key, loses identity forever.

**Mitigation:**
- BIP-39 mnemonic backup (write it down!)
- Social recovery: N-of-M trusted contacts can attest to new key
- Hardware key support (Ledger, YubiKey)

**Partial recovery:**
- Can prove ownership of old key via trusted attestations
- Content history preserved (but not cryptographically linked to new key)

### 9.3 Relay Collapse

**Problem:** Major relays go offline, users can't sync.

**Mitigation:**
- User nodes can sync directly (P2P)
- Multiple relay options (no single point of failure)
- Clients auto-discover alternative relays

**Graceful degradation:**
- Local content always available
- Sync resumes when relays return or alternatives found

### 9.4 Spam Flood

**Problem:** Attacker generates millions of spam claims.

**Mitigation:**
- Proof-of-work requirement (adjustable difficulty)
- Trust-based filtering (new accounts hidden by default)
- Relay rate limiting

**Impact:** Spam exists in DHT but filtered by clients.

### 9.5 Sybil Attack

**Problem:** Attacker creates many fake identities to manipulate trust.

**Mitigation:**
- Trust derived from YOUR follows (attacker must compromise your social graph)
- Attestation from known-good identities
- Temporal signals (account age, activity patterns)

**Limitation:** If your close contacts are compromised, you're vulnerable.

### 9.6 Eclipse Attack

**Problem:** Attacker surrounds target node with malicious peers.

**Mitigation:**
- Connect to multiple diverse peers
- Use relays as fallback
- Verify claims cryptographically (can't forge signatures)

### 9.7 Metadata Leakage

**Problem:** Network layer reveals who's communicating.

**Mitigation:**
- Optional Tor/I2P transport
- Relay mixing (post to relay, recipients pull)
- Timing obfuscation (delayed posts)

**Tradeoff:** Latency increases with stronger privacy.

### 9.8 Protocol Ossification

**Problem:** Hard to upgrade protocol once deployed.

**Mitigation:**
- Version field in claims (`v: 1`)
- Unknown fields ignored (forward compatibility)
- Extension mechanism via new claim types
- Soft forks (new claim types) preferred over hard forks

---

## 10. Comparison Table

| Aspect | MESH | Nostr | ActivityPub | AT Protocol |
|--------|------|-------|-------------|-------------|
| **Data model** | Claims (Merkle-DAG) | Events (flat log) | Objects + Activities | Records (MST) |
| **Identity** | Ed25519 keypair | secp256k1 keypair | WebFinger + HTTP | DID:PLC + handle |
| **Transport** | QUIC/DHT/WebSocket | WebSocket to relays | HTTPS (server-to-server) | HTTPS + XRPC |
| **Discovery** | DHT + optional relays | Relay-centric | Server-centric | BGS (central index) |
| **Sync** | Bloom filter reconciliation | Subscription filters | Push (Inbox/Outbox) | Repo sync (MST diff) |
| **Storage** | Local-first + relay cache | Relay-stored | Server-stored | PDS (user-controlled) |
| **Encryption** | NaCl box (opt-in) | NIP-04 (optional) | Not built-in | Not built-in |
| **Moderation** | Web-of-trust | Client-side | Server-side | Labelers + feeds |
| **Scalability** | DHT (logarithmic) | Relay sharding | Server federation | BGS aggregation |
| **Offline** | Full offline operation | Limited (relay-dependent) | No | Limited (need PDS) |
| **Complexity** | 4 primitives | Simple (NIPs add complexity) | High (many specs) | High (Lexicons) |
| **Single node cost** | Very low | Low (need relay) | High (full server) | Medium (need PDS) |
| **Million user cost** | Distributed | Relay scaling | Server scaling | BGS bottleneck |

### 10.1 Key Differentiators

**vs Nostr:**
- MESH uses DHT for discovery (no relay dependency)
- MESH has structured references (DAG vs flat events)
- MESH uses efficient Bloom sync vs subscription filters

**vs ActivityPub:**
- MESH is truly decentralized (no server required)
- MESH uses cryptographic identity (no WebFinger)
- MESH is local-first (works offline)

**vs AT Protocol:**
- MESH has no centralized indexer (BGS)
- MESH is simpler (4 primitives vs Lexicons)
- MESH uses DHT (no account server dependency)

---

## 11. Radical Simplification: "Everything is a Claim"

**The Insight:** Most protocols have separate concepts for:
- Posts
- Reactions
- Relationships (follow/block)
- Profile data
- Group membership
- Messages

MESH unifies ALL of these as **claims with different types**.

**Complexity reduction:**
- One data structure (not 6+)
- One sync mechanism (not different for each type)
- One verification path (check signature, done)
- One storage format
- One query model

**This reduces implementation complexity by ~50%** compared to protocols with specialized message types and handlers.

---

## 12. Novel Ideas

### 12.1 Probabilistic Eventual Consistency

Instead of guaranteeing all nodes see all claims, MESH accepts that:
- Claims propagate probabilistically through the network
- Nodes eventually converge but may have temporary inconsistencies
- Bloom filter sync naturally handles this (no ordering requirements)

**Why this matters:** Removes need for consensus protocols, vector clocks, or causal ordering. Claims are independent, idempotent, and commutative.

### 12.2 Trust Decay

Trust isn't static — it decays over time:

```
trust(A, t) = base_trust(A) × e^(-λ × (t - last_interaction))
```

Where:
- `base_trust(A)` = trust from initial follow/attest
- `λ` = decay constant
- `last_interaction` = last time you interacted with A's content

**Why this matters:** 
- Accounts that go dormant or get compromised naturally lose influence
- Active, engaged accounts maintain trust
- Reduces Sybil attack surface (dormant sock puppets lose trust)

### 12.3 Claim Expiry

Claims can have optional expiration:

```json
{
  "type": "post",
  "content": {
    "text": "This offer expires in 24 hours!",
    "expires_at": 1714086400
  }
}
```

**Why this matters:**
- Ephemeral content (stories)
- Reduces storage burden over time
- Privacy (content auto-deletes)

Nodes MAY garbage-collect expired claims. Clients SHOULD hide expired claims.

### 12.4 Verifiable Computation on Claims

Future extension: Publish claims that prove computation over other claims:

```json
{
  "type": "aggregation",
  "content": {
    "statement": "This post has 1,234 reactions",
    "proof": "<zk-snark-proof>",
    "inputs": ["sha256:...", "sha256:..."]
  }
}
```

**Why this matters:**
- Verified counts without downloading all reactions
- Privacy-preserving analytics
- Reduces client computation

---

## 13. Implementation Roadmap

### Phase 1: Core (MVP)
- [ ] Ed25519 identity generation
- [ ] Claim creation and signing
- [ ] Local storage (SQLite)
- [ ] Basic sync (request/response)
- [ ] CLI client

### Phase 2: Networking
- [ ] DHT implementation (Kademlia)
- [ ] Bloom filter sync
- [ ] Relay protocol
- [ ] WebSocket subscriptions

### Phase 3: Social Features
- [ ] Feed construction
- [ ] Reactions and replies
- [ ] Follow/block
- [ ] Profile claims
- [ ] E2EE DMs

### Phase 4: Scale
- [ ] Relay sharding
- [ ] Feed pre-computation
- [ ] Media handling (IPFS integration)
- [ ] Mobile clients

### Phase 5: Ecosystem
- [ ] Multiple client implementations
- [ ] Relay operator tools
- [ ] Trust/moderation tools
- [ ] Developer SDK

---

## 14. Appendix: Wire Protocol

### 14.1 Message Types

| Code | Name | Direction | Description |
|------|------|-----------|-------------|
| 0x01 | HELLO | Both | Protocol version, capabilities |
| 0x02 | AUTH_INIT | C→S | Start authentication |
| 0x03 | AUTH_CHALLENGE | S→C | Challenge nonce |
| 0x04 | AUTH_RESPONSE | C→S | Signed challenge |
| 0x05 | AUTH_OK | S→C | Authentication success |
| 0x10 | SYNC_REQUEST | C→S | Bloom filter of known claims |
| 0x11 | SYNC_RESPONSE | S→C | List of missing claim hashes |
| 0x12 | CLAIM_REQUEST | C→S | Request specific claims |
| 0x13 | CLAIM_RESPONSE | S→C | Requested claims |
| 0x14 | CLAIM_PUSH | Both | Push new claim |
| 0x20 | SUBSCRIBE | C→S | Subscribe to filter |
| 0x21 | UNSUBSCRIBE | C→S | Remove subscription |
| 0x22 | EVENT | S→C | New claim matching filter |
| 0x30 | QUERY | C→S | Query for claims |
| 0x31 | QUERY_RESULT | S→C | Query results |
| 0xFF | ERROR | Both | Error response |

### 14.2 CBOR Encoding

All wire messages are CBOR-encoded:

```
Message = {
  type: uint,       // Message type code
  id: uint,         // Request ID (for matching responses)
  payload: any      // Type-specific payload
}
```

---

## 15. Appendix: Cryptographic Details

### 15.1 Algorithms

| Purpose | Algorithm |
|---------|-----------|
| Signing | Ed25519 |
| Encryption | X25519 + XSalsa20-Poly1305 |
| Hashing | SHA-256 |
| Key derivation | PBKDF2-SHA512 |

### 15.2 Signature Verification

```python
def verify_claim(claim):
    # Extract fields for hashing
    hashable = {k: v for k, v in claim.items() if k not in ('id', 'sig')}
    canonical = canonical_json(hashable)
    computed_hash = sha256(canonical)
    
    # Verify hash matches
    assert claim['id'] == f"sha256:{base58(computed_hash)}"
    
    # Verify signature
    pubkey = decode_pubkey(claim['pubkey'])
    sig = decode_sig(claim['sig'])
    assert ed25519_verify(pubkey, computed_hash, sig)
```

### 15.3 Encryption

```python
def encrypt_dm(plaintext, recipient_pubkey, sender_privkey):
    # Generate ephemeral keypair
    ephemeral_priv, ephemeral_pub = x25519_generate()
    
    # Derive shared secret
    recipient_x25519 = ed25519_to_x25519_pub(recipient_pubkey)
    shared = x25519(ephemeral_priv, recipient_x25519)
    
    # Encrypt
    nonce = random_bytes(24)
    ciphertext = xsalsa20_poly1305_encrypt(plaintext, nonce, shared)
    
    return {
        'ciphertext': base64(ciphertext),
        'nonce': base64(nonce),
        'ephemeral_pubkey': base64(ephemeral_pub)
    }
```

---

## 16. Conclusion

MESH achieves:

✅ **Maximally decentralized**: No required central servers; DHT + local-first
✅ **Cheap to operate**: Single node runs on a Raspberry Pi
✅ **Horizontally scalable**: DHT + relay sharding to millions
✅ **Spam resistant**: Proof-of-work + Web-of-Trust + rate limiting
✅ **Rich social features**: All derived from 4 primitives
✅ **Simple to implement**: ~50% less code than comparable protocols

The key insight is **unification**: one data model (claims), one sync mechanism (Bloom filters), one trust model (Web-of-Trust). This reduces cognitive overhead and implementation complexity while maintaining flexibility.

MESH doesn't try to solve everything. It provides primitives and lets the ecosystem build.

---

*Protocol version: 0.1*
*Status: Draft*
*License: CC0 (Public Domain)*
