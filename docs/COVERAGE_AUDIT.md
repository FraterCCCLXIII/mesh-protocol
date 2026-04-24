# Simulator Coverage Audit

**Question: Do the simulators actually simulate all features documented in their specs?**

---

## HOLON v3 Simulator vs HOLON v3.2 Spec

### Spec Features (HOLON_v3.2_DRAFT.md)

| Section | Feature | Simulated? | Notes |
|---------|---------|:----------:|-------|
| **OBJECT LAYER** |
| §2 Entity | Entity creation | ✓ | `EntityKind`: user, org, group |
| §2.2 | Entity kinds | ⚠️ | Missing: bot, service, relay |
| §2.4 | Entity versioning | ✗ | No version tracking |
| §3 Content | Content creation | ✓ | `ContentKind`: post, article, media |
| §3.2 | Content kinds | ⚠️ | Missing: comment, poll, event, course |
| §3.5 | Access control | ⚠️ | Basic only, no tier-based access |
| §4 Link | Link creation | ✓ | `LinkKind`: follow, react, etc. |
| §4.2-4.5 | Link subkinds | ⚠️ | Basic relationship/interaction only |
| §4.6 | Signing rule | ✗ | No signature verification |
| §4.7 | Link tombstone | ✓ | Implemented |
| §5 Identity | Key-derived | ✗ | No cryptographic identity |
| §5.2 | Email-derived | ✗ | Not implemented |
| §5.4 | Key rotation | ✗ | Not implemented |
| §6 Encryption | E2EE | ✗ | Not implemented |
| §6.2-6.4 | Per-content/group/tier keys | ✗ | Not implemented |
| §7 Sync | Pull-based | ⚠️ | Basic subscribe only |
| §7.4 | Multi-relay | ✗ | Single storage only |
| §8 Groups | Group entity | ✓ | Groups exist |
| §8.2 | Group policies | ✗ | No policy enforcement |
| §8.3 | Membership flow | ⚠️ | Basic join only |
| §9 Paid Content | Tiers | ✗ | Not implemented |
| §9.2 | Subscriptions | ✗ | Not implemented |
| **STRUCTURE LAYER** |
| §11-15 | Holonic nesting | ✗ | No parent/child relationships |
| §16 | Context isolation | ✗ | No context enforcement |
| **VIEW LAYER** |
| §20 View | View definitions | ✓ | Basic views work |
| §21 | Source types | ⚠️ | Only follows, context |
| §22 | Filters | ⚠️ | Basic filters only |
| §23 | Ranking | ⚠️ | Simple formula only |
| §26 | Boundaries | ✗ | No deterministic verification |
| §27 | View execution | ⚠️ | Basic execution |
| §28 | View subscription | ✗ | Not implemented |
| §29 | View forking | ✗ | Not implemented |

### Coverage Summary: HOLON v3

- **Object Layer**: ~60% covered
- **Structure Layer**: ~10% covered  
- **View Layer**: ~40% covered
- **Overall**: ~35-40% of spec features

---

## HOLON v4 Simulator vs HOLON v4.0 Spec

### Spec Features (HOLON_v4.0_DRAFT.md)

| Section | Feature | Simulated? | Notes |
|---------|---------|:----------:|-------|
| **DATA LAYER** |
| §1-3 | Three primitives | ✓ | Entity, Content, Link |
| §4 | Entity kinds | ✓ | user, org, group, relay |
| §4 | Content kinds | ✓ | post, article, media |
| §4 | Link kinds | ✓ | follow, react, subscribe, etc. |
| §5 | Identity & Keys | ⚠️ | No actual crypto |
| §5.3 | Key rotation | ✗ | Not implemented |
| §6 | Sync | ⚠️ | Basic subscribe |
| **DISCOVERY** |
| §7 | Discovery mechanisms | ✓ | All 5 levels |
| §8 | Handle resolution | ✓ | Implemented |
| §9 | Search | ✓ | Full-text search |
| §10 | Social graph discovery | ✓ | follows_of_follows, etc. |
| §11 | Context discovery | ✓ | Group-based |
| §12 | External verification | ✓ | verify links |
| §13 | Discovery views | ✓ | Rising stars, etc. |
| §14 | Contact import | ⚠️ | No hash lookup |
| §15 | QR code | ✗ | Not simulated |
| **ALGORITHM LAYER** |
| §16 | Views | ✓ | View definitions |
| §17 | Ranking formulas | ✓ | Full expression parsing |
| §17 | decay(), log(), cap() | ✓ | Implemented |
| §18 | Verification | ⚠️ | Hash-based, no boundary |
| §19 | Moderation as data | ✓ | Label links |
| §20 | Reputation | ✓ | Formula implemented |
| **ECONOMICS** |
| §21 | Relay economics | ✗ | Not simulated |
| §22 | Creator economics | ⚠️ | Tips tracked |
| §22 | Paid content | ⚠️ | Price field exists |
| §23 | View economics | ⚠️ | View subscriptions |
| **GOVERNANCE** |
| §24 | Context governance | ⚠️ | Basic moderators |
| §25 | Dispute resolution | ✗ | Not implemented |
| §26 | Protocol governance | ✗ | Not applicable |
| **MIGRATION** |
| §27 | Import from other protocols | ✗ | Not implemented |

### Coverage Summary: HOLON v4

- **Data Layer**: ~70% covered
- **Discovery**: ~85% covered ⭐
- **Algorithm Layer**: ~75% covered
- **Economics**: ~40% covered
- **Governance**: ~20% covered
- **Overall**: ~55-60% of spec features

---

## Relay v2 Simulator vs Relay_v2.md

### Spec Features (Relay_v2.md)

| Section | Feature | Simulated? | Notes |
|---------|---------|:----------:|-------|
| **TRUTH LAYER** |
| §0.2 | Identity | ✓ | actor_id from pubkey |
| §0.2 | Event | ✓ | Append-only, parents |
| §0.2 | State | ✓ | Versioned objects |
| §0.2 | Attestation | ✓ | Claims implemented |
| §0.2 | Snapshot | ⚠️ | Structure only, no Merkle |
| §0.8 | Verifiability profile | ✗ | Not implemented |
| **VIEW LAYER** |
| §0.3 | ViewDefinition | ✓ | sources + reduce |
| §0.6 | Boundary | ✓ | Full implementation |
| §0.6 | Determinism rules | ✓ | Same inputs = same output |
| §0.6.1 | Canonical form | ⚠️ | Basic canonicalization |
| §17.10 | Reducers | ✓ | chronological, engagement |
| §17.11 | Recompute/verify | ✓ | Full implementation |
| **WIRE PROTOCOL** |
| §4.1 | Canonical JSON | ⚠️ | Basic JSON only |
| §4.3 | actor_id multihash | ✓ | Implemented |
| §7 | Ed25519 signatures | ✗ | Not verified |
| §10 | Log events | ✓ | All types |
| §11 | State objects | ✓ | Version increment |
| §13.1 | Membership witness | ✗ | Not implemented |
| §13.4 | Action events | ✓ | request/commit/result |
| §18 | WebSocket | ✗ | Not implemented |
| §19 | HTTP signatures | ✗ | Not implemented |

### Coverage Summary: Relay v2

- **Truth Layer**: ~70% covered
- **View Layer**: ~80% covered ⭐
- **Wire Protocol**: ~40% covered
- **Overall**: ~55-60% of spec features

---

## Relay v1.4-1 Simulator vs Relay_v1.4.1.md

### Spec Features (Relay_v1.4.1.md)

| Section | Feature | Simulated? | Notes |
|---------|---------|:----------:|-------|
| **IDENTIFIERS** |
| §4.2 | Content-addressed IDs | ✓ | Implemented |
| §4.3 | actor_id multihash | ✓ | SHA-256 |
| §4.3.1 | channel_id from genesis | ✓ | Implemented |
| **LOG EVENTS** |
| §10 | Append-only log | ✓ | prev chain |
| §10.2 | MVP event types | ✓ | follow.*, state.* |
| §10.2 | v1.3 types | ✓ | membership.* |
| §10.2 | v1.4 action types | ✓ | action.* |
| §10.5 | expires_at (v1.5) | ⚠️ | Field exists, not enforced |
| **STATE OBJECTS** |
| §11 | State versioning | ✓ | Version increment |
| §11.1 | Feed definitions | ✓ | sources + reduce |
| **CHANNELS** |
| §13 | Channel creation | ✓ | Genesis-based |
| §13.1 | Membership witness | ✗ | Not implemented |
| §13.4 | Action events | ✓ | Full chain |
| §13.4 | commitment_hash | ✓ | SHA-256 verification |
| §13.5 | Private actions (v1.5) | ✗ | Not implemented |
| **FEEDS** |
| §17.10 | Required reducers | ✓ | chronological, reverse |
| §17.11 | Recompute/verify | ✓ | Implemented |
| **VERIFICATION** |
| §7 | Ed25519 signatures | ✗ | Not verified |
| §19 | HTTP signatures | ✗ | Not implemented |
| §18 | WebSocket | ✗ | Not implemented |

### Coverage Summary: Relay v1.4-1

- **Identifiers**: ~90% covered ⭐
- **Log Events**: ~80% covered
- **State Objects**: ~85% covered
- **Channels**: ~60% covered
- **Feeds**: ~90% covered ⭐
- **Verification**: ~20% covered
- **Overall**: ~60-65% of spec features

---

# Summary: What's Missing?

## Common Gaps Across All Simulators

| Feature | Why Missing |
|---------|-------------|
| **Cryptographic signatures** | Would slow simulation, not testing crypto |
| **Actual encryption** | Same reason |
| **WebSocket/streaming** | Simulators are batch, not real-time |
| **HTTP API compliance** | Testing data model, not transport |
| **Multi-relay federation** | Complexity, would need network simulation |

## Per-Simulator Gaps

### HOLON v3 Missing (~60% gap)
- ❌ Structure Layer (holonic nesting)
- ❌ Encryption
- ❌ Key rotation
- ❌ Paid content tiers
- ❌ View boundaries/verification
- ❌ Multi-relay sync

### HOLON v4 Missing (~40% gap)
- ❌ Actual cryptography
- ❌ QR code discovery
- ❌ Relay economics simulation
- ❌ Dispute resolution
- ❌ Protocol governance
- ❌ Migration import

### Relay v2 Missing (~40% gap)
- ❌ Merkle proofs in snapshots
- ❌ Signature verification
- ❌ WebSocket
- ❌ HTTP signatures (RFC 9421)
- ❌ Membership witnesses

### Relay v1.4-1 Missing (~35% gap)
- ❌ Signature verification
- ❌ Private actions (v1.5)
- ❌ Membership witnesses
- ❌ WebSocket
- ❌ HTTP signatures

---

# Honest Assessment

| Simulator | Spec Coverage | What It Actually Tests |
|-----------|---------------|------------------------|
| **HOLON v3** | ~35-40% | Basic social primitives, simple views |
| **HOLON v4** | ~55-60% | Discovery, economics, transparent algorithms |
| **Relay v2** | ~55-60% | Truth/View layers, deterministic boundaries |
| **Relay v1.4-1** | ~60-65% | Wire protocol, action flows, feed verification |

## What The Simulators DO Test Well

| Simulator | Strengths |
|-----------|-----------|
| **HOLON v3** | Entity/Content/Link model, basic social graph |
| **HOLON v4** | Discovery engine, ranking formulas, reputation |
| **Relay v2** | Boundary-based determinism, attestations |
| **Relay v1.4-1** | prev chain, action.* flows, commitment_hash |

## What The Simulators DON'T Test

| Category | Not Tested |
|----------|------------|
| **Crypto** | Signatures, encryption, key derivation |
| **Network** | Multi-relay, federation, WebSocket |
| **Security** | Signature verification, replay attacks |
| **Scale** | Real storage, real network latency |

---

# Recommendation

**The simulators are useful for testing protocol semantics and data model behavior, but NOT for:**
- Cryptographic correctness
- Network protocol compliance
- Security properties
- Production performance

**For a production implementation, you'd need:**
1. Real Ed25519 signature verification
2. Actual encryption (X25519, AES-GCM)
3. Network layer (HTTP, WebSocket)
4. Persistence (database, not in-memory)
5. Multi-relay federation
