# WITNESS Protocol Specification v0.3

**WITNESS: Web of Interoperable Trust, Networks, Explanation, Signatures, and Streams**

A radically minimal decentralized social protocol built on cryptographic attestation semantics, with formal verifiability guarantees.

---

## Changelog (v0.3)

### From v0.2
- **Added**: Two-layer architecture (Truth + View) from Relay 2.0
- **Added**: Explicit Boundary objects for deterministic View evaluation
- **Added**: Verifiability Profiles (minimal vs auditable)
- **Added**: Three-phase expiry model for ephemeral content
- **Added**: Commitment Hash for action binding (from Relay)
- **Added**: Private witness addressing with tag-based concealment
- **Added**: Snapshot Merkle proofs for verifiable partial storage
- **Refined**: Explanation → Provenance (more precise semantics)
- **Kept**: Fork-based threading (unique to WITNESS)
- **Kept**: Content/pointer separation (unique to WITNESS)
- **Kept**: Vector timestamps (unique to WITNESS)
- **Kept**: Capability certificates (improved from v0.2)

---

## 1. Core Philosophy

1. **Two Layers: Truth + View**: The protocol separates immutable facts (Truth) from derived projections (View). Truth is signed; Views are recomputable.

2. **Everything is a Witness**: A witness is a signed attestation. Posts, reactions, follows, actions — all witnesses in the Truth layer.

3. **Content Lives Elsewhere**: The protocol handles attestations about content, not content itself. Witnesses contain pointers; relays are attestation servers.

4. **Streams with Forks**: Conversations are fork-based. Your reply is your fork of the thread. You see only forks from accounts you trust.

5. **Provenance is Mandatory**: Every surfaced witness must have signed provenance metadata. "Why am I seeing this?" is protocol, not UX.

6. **Views Require Boundaries**: A View is deterministic only when evaluated over an explicit, finite Boundary. Without a Boundary, outputs are best-effort.

7. **Verifiability is Declared**: Implementations declare their verifiability profile upfront — whether State is derivable from Events or origin-attested only.

8. **Capabilities, Not ACLs**: Write access is proven by presenting a capability certificate. Capabilities are portable, delegatable, and independently verifiable.

9. **Expiry is Three-Phase**: Ephemeral content follows: Active → Expired-serving → Garbage-collected. "Expired" means operationally inactive, not "never existed."

10. **Multi-Device by Design**: Vector timestamps enable concurrent offline edits from multiple devices without conflicts.

---

## 2. Two-Layer Architecture

### 2.1 Truth Layer

The Truth layer contains cryptographically signed, content-addressed facts:

| Primitive | Description |
|-----------|-------------|
| **Identity** | Ed25519 keypair; public key IS the identity |
| **Witness** | Signed attestation with type, pointers, vector timestamp, provenance |
| **Pointer** | Content-addressed reference: `(hash, locations[])` |
| **Capability** | Signed delegation: `(issuer, delegate, scope, expires)` |
| **Snapshot** | Merkle-verifiable checkpoint of state at a boundary |

**Truth primitives are:**
- Immutable (witnesses) or versioned-authoritative (state)
- Cryptographically signed
- Content-addressed where applicable
- Independently verifiable

### 2.2 View Layer

The View layer contains deterministic projections over Truth:

| Concept | Description |
|---------|-------------|
| **ViewDefinition** | Signed specification: sources + reduce function + params |
| **Boundary** | Explicit constraint defining the dataset for evaluation |
| **Reducer** | Pure function that transforms inputs into ordered output |
| **Materialized View** | Cached output of a View at a specific Boundary |

**View properties:**
- Deterministic given same definition + same boundary
- Recomputable by any honest party
- Not authoritative — Truth is authoritative

### 2.3 Relationship

```
┌─────────────────────────────────────────────────────┐
│                    VIEW LAYER                        │
│  ┌─────────────┐   ┌──────────┐   ┌──────────────┐  │
│  │ViewDefinition│ + │ Boundary │ → │Materialized  │  │
│  │(sources,    │   │(explicit │   │View (ordered │  │
│  │ reduce)     │   │ pins)    │   │ witness list)│  │
│  └─────────────┘   └──────────┘   └──────────────┘  │
└────────────────────────┬────────────────────────────┘
                         │ fetches from
┌────────────────────────▼────────────────────────────┐
│                   TRUTH LAYER                        │
│  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐  │
│  │ Identity │ │ Witness  │ │Pointer │ │Capability│  │
│  │(keypairs)│ │(signed)  │ │(content│ │(delegated│  │
│  │          │ │          │ │ refs)  │ │ authority│  │
│  └──────────┘ └──────────┘ └────────┘ └──────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## 3. Verifiability Profiles

Implementations MUST declare at least one verifiability profile:

### 3.1 `witness.profile.minimal`

State MAY exist without a complete verifiable witness history:
- Origin-attested state is trusted
- Full audit trail not required
- Suitable for lightweight clients

### 3.2 `witness.profile.auditable`

State MUST be derivable from a finite set of Witness objects:
- Every state change has a corresponding witness
- Clients can reconstruct state from witnesses
- Full cryptographic audit possible

### 3.3 Declaration

```json
{
  "type": "genesis",
  "content": {
    "profiles": ["witness.profile.minimal", "witness.profile.auditable"]
  }
}
```

**Clients MUST:**
- Respect declared profiles when deciding verification depth
- Show "verified derivation" vs "origin-attested only" appropriately

---

## 4. Truth Layer Data Model

### 4.1 Pointer

A content-addressed reference with location hints:

```json
{
  "hash": "sha256:3f8a7b2c...",
  "locations": [
    "ipfs://Qm...",
    "https://cdn.example.com/3f8a7b2c",
    "inline:<base64-if-small>"
  ]
}
```

**Rules:**
- `hash` is SHA-256 of canonical content bytes
- `locations` are hints; any location serving matching hash is valid
- Clients try locations in order, verify hash on receipt
- `inline:` prefix for content <1KB embedded directly

### 4.2 Witness

A signed attestation in the Truth layer:

```json
{
  "v": 3,
  "id": "sha256:<hash-of-canonical-witness>",
  "author": "ed25519:7xK4a2...",
  "vt": {"ed25519:device1": 42, "ed25519:device2": 17},
  "type": "post",
  "content": {
    "ptr": {"hash": "sha256:...", "locations": ["ipfs://..."]}
  },
  "refs": [],
  "provenance": {
    "type": "author_stream",
    "issuer": "ed25519:7xK4a2...",
    "boundary": null
  },
  "expires_at": null,
  "cap": null,
  "sig": "ed25519:9d3f1a..."
}
```

#### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `v` | int | Protocol version (3) |
| `id` | string | SHA-256 hash of canonical witness (excluding `id`, `sig`) |
| `author` | string | Author's public key |
| `vt` | object | Vector timestamp: `{pubkey: counter}` per device |
| `type` | string | Witness type |
| `content` | object | Type-specific payload (usually contains pointers) |
| `refs` | array | Referenced witness IDs (for forks, replies, reactions) |
| `provenance` | object | Why this witness exists + optional boundary |
| `expires_at` | string | RFC 3339 expiry (null = no expiry) |
| `cap` | object | Capability certificate if writing to non-self stream |
| `sig` | string | Ed25519 signature of `id` |

### 4.3 Provenance Object

Every witness MUST have provenance metadata:

```json
{
  "provenance": {
    "type": "followed_author",
    "issuer": "ed25519:viewer...",
    "via": "sha256:follow-witness-id",
    "boundary": {
      "snapshot": "sha256:...",
      "as_of": "2026-04-22T00:00:00Z"
    }
  }
}
```

**Provenance Types:**

| Type | Meaning |
|------|---------|
| `author_stream` | Author's own stream |
| `followed_author` | From someone you follow |
| `reply_to_followed` | Reply to someone you follow |
| `mentioned` | You were mentioned |
| `capability_grant` | You have capability to this stream |
| `indexer_surfaced` | An indexer you trust surfaced this |
| `peer_shared` | A peer explicitly shared this |
| `fork_of` | Fork of a witness you've seen |
| `boundary_eval` | Result of View evaluation at stated boundary |

**Critical Rule:** Compliant clients MUST NOT render witnesses without valid provenance.

### 4.4 Capability Certificate

```json
{
  "type": "capability",
  "issuer": "ed25519:stream-owner...",
  "delegate": "ed25519:authorized-writer...",
  "scope": ["post", "react"],
  "stream": "sha256:stream-root-id",
  "expires_at": "2026-12-31T23:59:59Z",
  "revocable": true,
  "sig": "ed25519:issuer-signature..."
}
```

**Capability chains:**
- A delegates to B, B delegates to C (if scope allows)
- Verification walks the chain back to stream owner
- Revocation invalidates downstream delegations

### 4.5 Snapshot with Merkle Proof

A verifiable checkpoint of state:

```json
{
  "type": "snapshot",
  "id": "sha256:<merkle-root>",
  "author": "ed25519:origin...",
  "as_of": "2026-04-22T00:00:00Z",
  "scope": {
    "actors": ["ed25519:abc..."],
    "types": ["post"],
    "id_range": {"from": "sha256:...", "to": "sha256:..."}
  },
  "root_hash": "sha256:...",
  "state_count": 15234,
  "partial": false,
  "sig": "ed25519:..."
}
```

#### Merkle Tree Construction

1. Collect witnesses in snapshot membership after scope filtering
2. Sort by `id` in UTF-8 byte lexicographic order
3. Compute leaf hash for each: `SHA256(canonical JSON of witness)`
4. Build binary Merkle tree:
   - If odd count, append padding hash: `SHA256("witness.merkle.pad.v1")`
   - Parent = `SHA256(left || right)`
5. Root hash is the single remaining value

#### Membership Proof

```json
{
  "type": "snapshot.proof",
  "snapshot_id": "sha256:...",
  "witness_id": "sha256:...",
  "leaf_index": 42,
  "merkle_path": ["hex64...", "hex64..."],
  "path_bits": [0, 1, 0],
  "root_hash": "sha256:..."
}
```

**Verification:**
1. Compute leaf hash from witness
2. Walk path using path_bits (0=left child, 1=right child)
3. Compare final hash to root_hash

---

## 5. View Layer

### 5.1 Boundary Object

A Boundary defines the exact dataset for View evaluation:

```json
{
  "snapshot": "sha256:...",
  "event_ranges": [
    {
      "actor": "ed25519:abc...",
      "from": "sha256:witness-start",
      "to": "sha256:witness-end"
    }
  ],
  "state_scope": {
    "actors": ["ed25519:abc..."],
    "types": ["post"],
    "id_range": {"from": "sha256:...", "to": "sha256:..."}
  },
  "as_of": "2026-04-22T00:00:00Z"
}
```

**Finite Input Rule:**

A Boundary is valid for deterministic claims only if it describes a finite set of inputs. MUST include at least one of:

1. **`snapshot`** — fixes state membership set
2. **`event_ranges`** — per-actor inclusive ranges
3. **`id_range`** — closed lexicographic interval

**Without a valid Boundary:**
- View output is "latest available" / best-effort
- Not reproducible across deployments
- Not auditable

### 5.2 ViewDefinition

A signed specification for a View:

```json
{
  "type": "view.definition",
  "id": "sha256:...",
  "author": "ed25519:curator...",
  "version": 3,
  "content": {
    "sources": [
      {"kind": "actor_stream", "actor": "ed25519:alice..."},
      {"kind": "actor_stream", "actor": "ed25519:bob..."}
    ],
    "reduce": "witness.reduce.reverse_chronological.v1",
    "params": {}
  },
  "sig": "ed25519:..."
}
```

**Source Kinds:**

| Kind | Description |
|------|-------------|
| `actor_stream` | Witnesses from an actor's stream |
| `snapshot` | State set from a snapshot |
| `view` | Nested ViewDefinition (recursive) |
| `fork_tree` | All forks of a root witness |

### 5.3 Reducers

Reducers are pure functions. MUST NOT depend on:
- Current wall clock / Date.now
- Non-deterministic randomness
- External network calls
- Unspecified host/process state

**Required Reducers:**

| ID | Behavior |
|----|----------|
| `witness.reduce.chronological.v1` | Sort by (vt, id) ascending |
| `witness.reduce.reverse_chronological.v1` | Sort by (vt, id) descending |

**Determinism Rule:**

Two View evaluations are deterministically equivalent iff:
- Same ViewDefinition version
- Same Boundary
- Same resolved input witnesses
- Same fork/orphan resolution status

### 5.4 Recompute / Audit

Clients MUST be able to recompute any View:

1. Fetch ViewDefinition by id
2. Fetch all inputs per sources + Boundary
3. Apply reducer
4. Compare to any cached/served output

**If mismatch:**
- Served ordering is untrusted
- Client prefers own recompute

---

## 6. Three-Phase Expiry Model

For witnesses with `expires_at`:

### Phase A: Active

While not time-expired:
- Normal append, fetch, relay, listing
- Included in default range queries
- Part of live fan-out

### Phase B: Expired-Serving

After `expires_at` passes:
- MUST NOT treat as active for new traffic
- MUST NOT include in default listings
- MUST NOT relay via real-time channels
- MAY still serve on direct fetch (with expired flag)
- MAY include in queries with `include_expired=true`

```json
{
  "witness": { ... },
  "expired": true,
  "served_from_retention": true
}
```

### Phase C: Garbage-Collected

After retention period:
- MAY physically delete
- 404 on fetch is normal
- Absence is operational, not assertion that witness never existed

**Key Distinction:**
- Expiry governs operational availability
- Does NOT erase the signed fact from audit history
- Verifiers with copies can still validate signatures

---

## 7. Commitment Hash for Actions

When modeling request → commit → result flows:

### 7.1 Action Request

```json
{
  "type": "action.request",
  "author": "ed25519:requester...",
  "content": {
    "action_id": "witness.action.summarize.v1",
    "input_refs": ["sha256:post1...", "sha256:post2..."],
    "target": "ed25519:agent..."
  },
  "refs": ["ed25519:agent..."],
  "provenance": {"type": "author_stream", "issuer": "ed25519:requester..."}
}
```

### 7.2 Commitment Object

The agent commits to a specific computation:

```json
{
  "kind": "witness.action.commitment.v1",
  "request_witness_id": "sha256:request...",
  "action_id": "witness.action.summarize.v1",
  "input_refs": ["sha256:post1...", "sha256:post2..."],
  "agent_params": {"max_words": 120, "model": "gpt-4"}
}
```

**`commitment_hash`** = SHA-256 of canonical JSON of this object

### 7.3 Action Commit

```json
{
  "type": "action.commit",
  "author": "ed25519:agent...",
  "content": {
    "request_witness_id": "sha256:request...",
    "commitment_hash": "sha256:64-char-hex...",
    "agent_params": {"max_words": 120, "model": "gpt-4"}
  }
}
```

### 7.4 Action Result

```json
{
  "type": "action.result",
  "author": "ed25519:agent...",
  "content": {
    "commitment_hash": "sha256:64-char-hex...",
    "output_refs": ["sha256:summary-post..."]
  }
}
```

**Verification:**
1. Fetch all three witnesses
2. Verify signatures
3. Recompute commitment_hash from request + agent_params
4. Confirm hashes match across commit and result

---

## 8. Private Witness Addressing

For concealing requester-agent relationships:

### 8.1 Tag Computation

```json
{
  "kind": "witness.action.tag.v1",
  "requester": "ed25519:requester...",
  "agent": "ed25519:agent...",
  "salt": "base64url-encoded-16-bytes-minimum"
}
```

**`tag`** = SHA-256 of canonical JSON (64-char lowercase hex)

### 8.2 Private Action Request

```json
{
  "type": "action.request",
  "author": "ed25519:requester...",
  "content": {},
  "ext": ["witness.ext.private_action.v1"],
  "ext_payload": {
    "witness.ext.private_action.v1": {
      "tag": "64-char-hex...",
      "encrypted_payload": "base64-ciphertext..."
    }
  }
}
```

**Properties:**
- No plaintext `target` in content
- Observers see only tag + ciphertext
- Cannot infer requester-agent relationship from tag (preimage infeasible)
- Agent scans for matching tags using known (requester, salt) pairs

### 8.3 Commitment on Decrypted Data

The `commitment_hash` is computed over the decrypted, canonical inner request — same verification path as plaintext requests.

---

## 9. Streams and Forks (Retained from v0.2)

### 9.1 Stream Model

A stream is a causal chain of witnesses sharing a common root:

```
Stream: ed25519:alice (personal stream)
    │
    ├── genesis (vt: {alice: 0})
    │
    ├── post (vt: {alice: 1})
    │
    ├── post (vt: {alice: 2})
    │       │
    │       └── [FORK by bob] → bob's reply stream
    │
    └── post (vt: {alice: 3, alice_phone: 1})  ← concurrent devices
```

### 9.2 Fork-Based Threading

When Bob replies to Alice's post:

```json
{
  "type": "fork",
  "author": "ed25519:bob...",
  "content": {
    "ptr": {"hash": "sha256:reply...", "locations": [...]}
  },
  "refs": ["sha256:alice-post-id"],
  "provenance": {
    "type": "reply_to_followed",
    "via": "sha256:bob-follows-alice"
  }
}
```

**Key Properties:**
- Bob's fork creates a new stream rooted at his witness
- Alice sees Bob's fork only if she follows Bob (or someone shares it)
- Thread views are constructed by traversing forks you trust

### 9.3 Thread Construction

1. Gather all `fork` witnesses referencing root
2. Recursively gather forks of forks
3. Filter by trust graph
4. Sort by vector timestamp

**No canonical thread** — each viewer constructs their own view.

---

## 10. Sync and Networking

### 10.1 Node Types

| Type | Role |
|------|------|
| **Client** | Owns keys, creates witnesses, constructs views |
| **Relay** | Stores/serves witnesses, enforces capability checks |
| **Indexer** | Aggregates streams, provides discovery |
| **Content Host** | Stores actual content (IPFS, CDN, etc.) |

### 10.2 Stream State Request

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

### 10.3 Vector Diff Sync

```
POST /stream/<stream-id>/diff
{
  "known_vector": {"ed25519:alice": 40}
}
```

Response: witnesses since that vector position.

### 10.4 Snapshot Fetch

```
GET /snapshot/<snapshot-id>
GET /snapshot/<snapshot-id>/proof/<witness-id>
```

---

## 11. Moderation Model

### 11.1 Fork-Based Filtering

You only see forks from your trust graph:
- No spam in your thread view
- No centralized moderation authority
- Each user constructs their own experience

### 11.2 Labels

Anyone can issue labels:

```json
{
  "type": "label",
  "content": {
    "labels": ["nsfw", "spam"],
    "reason": "Explicit content"
  },
  "refs": ["sha256:target-witness"]
}
```

Clients aggregate labels from trusted labelers.

### 11.3 Spam Resistance

- Zero reach without follows
- Fork model isolates spam
- Capability model requires explicit delegation
- Optional proof-of-work for new streams

---

## 12. Comparison: WITNESS v0.3 vs Alternatives

| Aspect | WITNESS v0.3 | Relay 2.0 | Nostr | AT Protocol |
|--------|--------------|-----------|-------|-------------|
| **Layers** | 2 (Truth+View) | 2 (Truth+View) | 1 (Events) | 1 (Records) |
| **Threading** | Fork-based | Pointer-based | e-tags | Record refs |
| **Content** | Pointers | Inline | Inline | PDS repos |
| **Boundaries** | Explicit | Explicit | None | Implicit |
| **Expiry** | Three-phase | Three-phase | None | None |
| **Provenance** | Mandatory | None | None | None |
| **Multi-device** | Vector clocks | Single seq | None | Limited |
| **Moderation** | Fork-filter | Labels+relay | Client | Labelers |

### 12.1 What WITNESS Adds

**vs Relay 2.0:**
- Fork-based threading (censorship-resistant conversations)
- Content/pointer separation (scalable relays)
- Mandatory provenance (algorithmic transparency)
- Vector timestamps (true multi-device)

**vs Nostr:**
- Two-layer architecture (Truth vs View)
- Explicit Boundaries (deterministic feeds)
- Fork-based threading (spam-free threads)
- Formal provenance (not just e-tags)

**vs AT Protocol:**
- No central indexer dependency
- Fork-based threading
- Content-addressable pointers
- Explicit verifiability profiles

---

## 13. Implementation Notes

### 13.1 Cryptographic Primitives

| Purpose | Algorithm |
|---------|-----------|
| Signing | Ed25519 |
| Hashing | SHA-256 |
| Encryption | X25519 + XSalsa20-Poly1305 |
| Key derivation | Argon2id |

### 13.2 Canonical JSON

- UTF-8 encoding
- Keys sorted lexicographically
- No whitespace
- NFC normalization for strings
- Numbers as integers (no floats in protocol)
- RFC 3339 for timestamps

### 13.3 Client Requirements

Compliant clients MUST:
1. Verify all signatures before displaying
2. Verify capability chains for non-author witnesses
3. Reject witnesses without valid provenance
4. Display provenance metadata on request
5. Respect verifiability profiles
6. Handle three-phase expiry correctly
7. Recompute Views when auditing

---

## 14. Novel Contributions (Summary)

### 14.1 From WITNESS

1. **Fork-Based Threading** — Replies are forks, not comments. Spam-free by construction.

2. **Mandatory Provenance** — Every surfaced witness must explain why. Algorithmic transparency as protocol invariant.

3. **Content/Pointer Separation** — Protocol handles attestations. Content lives elsewhere. Scalable relays.

4. **Vector Timestamps** — True multi-device operation without conflicts.

### 14.2 From Relay 2.0

5. **Two-Layer Architecture** — Truth (immutable facts) vs View (deterministic projections). Clean separation.

6. **Explicit Boundaries** — Views are deterministic only with finite pins. Honest about what's reproducible.

7. **Verifiability Profiles** — Declare upfront what guarantees you provide. Honest interop.

8. **Three-Phase Expiry** — Active → Expired-serving → GC. Operational expiry ≠ audit erasure.

9. **Commitment Hash** — Rigorous binding of request + agent_params for action verification.

10. **Private Addressing** — Tag-based concealment of relationships from observers.

11. **Merkle Snapshots** — Verifiable partial storage with membership proofs.

---

## 15. Future Extensions

- **Encrypted streams**: Full stream encryption with MLS
- **Gossip layer**: P2P propagation for resilience
- **Payment rails**: Native micropayments
- **ZK aggregation**: Verifiable computation over witness sets
- **Reducer registry**: Community-maintained pure functions

---

*Protocol version: 0.3*
*Status: Draft*
*License: CC0 (Public Domain)*
