# MESH Protocol Specification v1.1

**Modular Extensible Social Hybrid Protocol**

A next-generation decentralized social network protocol combining the best aspects of HOLON, Relay, Nostr, ActivityPub, SSB, and AT Protocol.

**v1.1 Changes:** Addresses multi-device support, fork resolution, view execution limits, moderation policy framework, and identity recovery.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Design Principles](#2-design-principles)
3. [Architecture](#3-architecture)
4. [Layer 1: Privacy Layer](#4-layer-1-privacy-layer)
5. [Layer 2: Storage Layer](#5-layer-2-storage-layer)
6. [Layer 3: Integrity Layer](#6-layer-3-integrity-layer)
7. [Layer 4: Social Layer](#7-layer-4-social-layer)
8. [Layer 5: Moderation Layer](#8-layer-5-moderation-layer)
9. [Layer 6: View Layer](#9-layer-6-view-layer)
10. [Layer 7: Network Layer](#10-layer-7-network-layer)
11. [Layer 8: Application Layer](#11-layer-8-application-layer)
12. [Multi-Device & Fork Resolution](#12-multi-device--fork-resolution) ← **NEW**
13. [Identity Recovery](#13-identity-recovery) ← **NEW**
14. [Derived Systems](#14-derived-systems)
15. [Sync Protocol](#15-sync-protocol)
16. [Security Model](#16-security-model)
17. [Scalability](#17-scalability)
18. [Comparison with Existing Protocols](#18-comparison-with-existing-protocols)
19. [Implementation Requirements](#19-implementation-requirements)
20. [Appendices](#20-appendices)

---

## 1. Overview

### 1.1 What is MESH?

MESH is a modular, layered protocol for decentralized social networking that provides:

- **Self-sovereign identity** via Ed25519 cryptographic keys
- **Append-only integrity** via prev-chain linked events
- **Multi-device support** via device keys and automatic merge ← **NEW**
- **End-to-end encryption** via X25519 + AES-256-GCM
- **Verifiable feeds** via deterministic view computation
- **Composable moderation** via third-party attestations
- **Optional identity recovery** via social recovery or custodial backup ← **NEW**
- **Horizontal scalability** via content-addressed data

### 1.2 Key Properties

| Property | Mechanism |
|----------|-----------|
| Decentralized | No required central servers |
| Self-sovereign | Users own their keys and data |
| Multi-device | Device keys with automatic merge |
| Censorship-resistant | Data replicates across relays |
| Privacy-preserving | E2EE for DMs and private groups |
| Verifiable | Deterministic feed computation |
| Recoverable | Optional social/custodial recovery |
| Scalable | Content-addressed, shardable |

### 1.3 Design Goals

1. **Simplicity** - Minimal primitive set (Entity, Content, Link)
2. **Integrity** - Provable append-only history
3. **Practicality** - Works with real-world usage patterns ← **EMPHASIZED**
4. **Privacy** - Encryption built-in, not bolted on
5. **Modularity** - Use only the layers you need
6. **Performance** - 6,000+ writes/sec, 5,000+ queries/sec

---

## 2. Design Principles

### 2.1 Core Principles

1. **Keys are identity** - Your Ed25519 keypair IS your identity
2. **Events are immutable** - Once written, events cannot be changed
3. **State is derived** - Current state is computed from event history
4. **Forks are normal** - Multi-device naturally creates forks; merge them ← **NEW**
5. **Attestations are separate** - Third-party claims never modify facts
6. **Views are deterministic** - Same inputs always produce same outputs
7. **Recovery is optional** - Users choose their security/convenience tradeoff ← **NEW**
8. **Layers are optional** - Clients choose which layers to implement

### 2.2 Tradeoffs Made

| Tradeoff | Choice | Rationale |
|----------|--------|-----------|
| Event logs vs state | Event logs | Auditability, sync simplicity |
| Push vs pull sync | Pull with subscriptions | Efficiency, offline support |
| Keys vs delegated identity | Keys with optional recovery | Self-sovereignty + practicality |
| Local-first vs relay-based | Hybrid | Flexibility, resilience |
| Single chain vs multi-head | **Multi-head with merge** | Multi-device support |
| Client-side vs protocol moderation | Client-side with attestations | Freedom, composability |
| E2EE default vs optional | Optional with easy E2EE | Performance, usability |

### 2.3 What MESH Does NOT Do

- **Consensus** - No blockchain, no global ordering
- **Payments** - No built-in cryptocurrency
- **Storage guarantees** - Relays may drop data
- **Forced recovery** - Recovery is opt-in, not mandatory
- **Content moderation** - Protocol provides tools, not policies

---

## 3. Architecture

### 3.1 Layer Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYER 8: APPLICATION                             │
│              (Mobile, Web, Desktop, Bots, VR)                       │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 7: NETWORK                                 │
│           (HTTP API, WebSocket, Federation, P2P)                    │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 6: VIEW                                    │
│        (ViewDefinitions, Reducers, Execution Limits)                │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 5: MODERATION                              │
│           (Attestations, Trust Networks, Conflict Resolution)       │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 4: SOCIAL                                  │
│              (Entity, Content, Link primitives)                     │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 3: INTEGRITY                               │
│         (LogEvent, Multi-Head DAG, Automatic Merge)                 │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 2: STORAGE                                 │
│            (SQLite/PostgreSQL, Indexes, Caching)                    │
├─────────────────────────────────────────────────────────────────────┤
│                    LAYER 1: PRIVACY                                 │
│     (Ed25519, X25519, AES-256-GCM, Device Keys, Recovery Keys)      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Layer 1: Privacy Layer

### 4.1 Overview

The Privacy Layer provides cryptographic primitives for identity, authentication, encryption, and recovery.

### 4.2 Identity Hierarchy ← **NEW SECTION**

MESH supports a hierarchical key structure for practical multi-device use:

```
                    ┌─────────────────┐
                    │   Root Key      │
                    │   (Ed25519)     │
                    │   KEEP OFFLINE  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Device 1 │  │ Device 2 │  │ Device 3 │
        │   Key    │  │   Key    │  │   Key    │
        └──────────┘  └──────────┘  └──────────┘
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Phone    │  │ Laptop   │  │ Desktop  │
        └──────────┘  └──────────┘  └──────────┘
```

**Key Types:**

| Key Type | Purpose | Storage | Compromise Impact |
|----------|---------|---------|-------------------|
| Root Key | Identity anchor | Offline/hardware | Total identity loss |
| Device Key | Day-to-day signing | On device | Revoke that device |
| Recovery Key | Account recovery | Trusted parties | Recovery possible |

### 4.3 Root Identity

The root identity is the canonical identity:

```typescript
interface RootIdentity {
  id: string;                    // ent:sha256(root_public_key)[:32]
  root_public_key: bytes;        // Ed25519 - KEEP PRIVATE KEY OFFLINE
  device_keys: DeviceKey[];      // Authorized device keys
  recovery_config?: RecoveryConfig;
  created_at: timestamp;
  sig: bytes;                    // Signed by root key
}

interface DeviceKey {
  device_id: string;
  public_key: bytes;             // Ed25519
  name: string;                  // "iPhone", "Laptop", etc.
  authorized_at: timestamp;
  expires_at?: timestamp;
  revoked: boolean;
  capabilities: string[];        // ["post", "follow", "dm", "admin"]
  sig: bytes;                    // Signed by root key
}
```

### 4.4 Device Key Authorization

To authorize a new device:

```python
def authorize_device(root_key: SigningKeyPair, device_public_key: bytes, name: str) -> DeviceKey:
    device = DeviceKey(
        device_id=generate_device_id(device_public_key),
        public_key=device_public_key,
        name=name,
        authorized_at=now(),
        revoked=False,
        capabilities=["post", "follow", "dm"],
    )
    device.sig = root_key.sign(canonical_json(device.to_dict()))
    return device
```

### 4.5 Signature Verification (Updated)

Signatures can come from root key OR authorized device key:

```python
def verify_event_signature(event: LogEvent, identity: RootIdentity) -> bool:
    # Try root key
    if verify_signature(identity.root_public_key, event_bytes, event.sig):
        return True
    
    # Try device keys
    for device in identity.device_keys:
        if device.revoked:
            continue
        if device.expires_at and device.expires_at < now():
            continue
        if verify_signature(device.public_key, event_bytes, event.sig):
            # Check capability
            if event_requires_capability(event) in device.capabilities:
                return True
    
    return False
```

### 4.6 Key Rotation

Device keys can be rotated without changing identity:

```python
def rotate_device_key(root_key: SigningKeyPair, old_device_id: str, new_device_public_key: bytes):
    # Revoke old
    revocation = DeviceKeyRevocation(
        device_id=old_device_id,
        revoked_at=now(),
        reason="rotation",
    )
    revocation.sig = root_key.sign(...)
    
    # Authorize new
    new_device = authorize_device(root_key, new_device_public_key, "Rotated Device")
    
    return revocation, new_device
```

---

## 5. Layer 2: Storage Layer

*[Same as v1.0 - see original spec]*

---

## 6. Layer 3: Integrity Layer

### 6.1 Overview

The Integrity Layer ensures append-only semantics while supporting **multi-device usage through a DAG structure with automatic merge**.

### 6.2 Multi-Head DAG (Key Change from v1.0) ← **MAJOR UPDATE**

**Problem with strict single-chain:**
- User posts from phone
- User posts from laptop before sync
- Result: FORK → terrible UX

**Solution: Allow multiple heads with automatic merge**

```
        Event 1 (laptop)
       /
Root ─┤
       \
        Event 2 (phone)
       
        ↓ Automatic merge
       
        Event 1 (laptop)
       /                \
Root ─┤                  ├─ Merge Event
       \                /
        Event 2 (phone)
```

### 6.3 LogEvent (Updated)

```typescript
interface LogEvent {
  id: string;                    // sha256(actor:device:local_seq)[:48]
  actor: string;                 // entity_id of author
  device_id: string;             // Which device created this ← NEW
  
  // DAG structure (changed from single prev)
  parents: string[];             // Previous event IDs (1 or more) ← CHANGED
  local_seq: number;             // Per-device sequence number ← CHANGED
  
  // Lamport timestamp for ordering
  lamport: number;               // max(parent.lamport) + 1 ← NEW
  
  op: "create" | "update" | "delete";
  object_type: "entity" | "content" | "link" | "state" | "attestation" | "view";
  object_id: string;
  payload: object;
  
  ts: timestamp;                 // Wall clock (informational only)
  sig: bytes;                    // Signed by device key
}
```

### 6.4 Fork Handling Strategies ← **NEW SECTION**

MESH defines three fork handling strategies. Implementations MUST support at least one:

#### Strategy 1: Automatic Merge (Recommended)

For most content, forks merge automatically:

```python
def auto_merge(heads: list[LogEvent]) -> LogEvent:
    """Create a merge event that combines multiple heads."""
    
    # Sort by lamport timestamp for deterministic ordering
    sorted_heads = sorted(heads, key=lambda e: (e.lamport, e.id))
    
    merge_event = LogEvent(
        id=generate_merge_id(sorted_heads),
        actor=heads[0].actor,
        device_id="merge",  # Special device ID for merges
        parents=[h.id for h in sorted_heads],
        local_seq=0,
        lamport=max(h.lamport for h in sorted_heads) + 1,
        op="merge",
        object_type="merge",
        object_id="",
        payload={
            "merged_heads": [h.id for h in sorted_heads],
            "strategy": "auto",
        },
        ts=now(),
        sig=b"",  # Merges are unsigned - deterministic from parents
    )
    
    return merge_event
```

**Merge Rules by Object Type:**

| Object Type | Merge Rule |
|-------------|------------|
| Content (post) | Both posts preserved, ordered by lamport |
| Content (edit) | Last-write-wins by lamport |
| Link (follow) | Union - if either says follow, follow |
| Link (unfollow) | Last-write-wins by lamport |
| Profile update | Last-write-wins by lamport |
| Attestation | Both preserved |

#### Strategy 2: Last-Write-Wins

For state that can't merge (e.g., profile bio):

```python
def last_write_wins(heads: list[LogEvent]) -> LogEvent:
    """Select the head with highest lamport timestamp."""
    winner = max(heads, key=lambda e: (e.lamport, e.id))
    
    # Other heads are "abandoned" - still valid, but not current
    return winner
```

#### Strategy 3: User Resolution

For rare conflicts that can't auto-resolve:

```python
def request_user_resolution(heads: list[LogEvent]) -> UserResolutionRequest:
    """Present conflict to user for manual resolution."""
    return UserResolutionRequest(
        conflict_type="unresolvable_fork",
        heads=heads,
        message="Your account has conflicting changes. Please choose which to keep.",
        options=[
            {"id": h.id, "summary": summarize_event(h)} 
            for h in heads
        ],
    )
```

**When to use each:**

| Scenario | Strategy | Example |
|----------|----------|---------|
| Both devices posted | Auto merge | Both posts appear in timeline |
| Both devices edited bio | LWW | Most recent bio wins |
| Conflicting block/unblock | User resolution | "Did you mean to block Alice?" |

### 6.5 Convergence Guarantee

With automatic merge, all devices eventually converge:

```python
def sync_and_merge(local_events: list, remote_events: list) -> list:
    # Combine all events
    all_events = set(local_events + remote_events)
    
    # Find all heads (events with no children)
    children = {e.id for e in all_events for p in e.parents}
    heads = [e for e in all_events if e.id not in children]
    
    # If multiple heads, merge them
    if len(heads) > 1:
        merge = auto_merge(heads)
        all_events.add(merge)
    
    return sorted(all_events, key=lambda e: e.lamport)
```

### 6.6 Offline Support

Devices can work offline and merge later:

```
Timeline:
─────────────────────────────────────────────────────►
   │
   │  Phone goes offline
   │  ├── Post A (phone, lamport=5)
   │  ├── Post B (phone, lamport=6)
   │
   │  Laptop continues online
   │  ├── Post C (laptop, lamport=5)
   │  ├── Post D (laptop, lamport=6)
   │
   │  Phone comes online
   │  ├── Sync discovers fork
   │  ├── Auto-merge creates merge event (lamport=7)
   │  └── All 4 posts preserved, ordered by lamport
   │
```

### 6.7 Preventing Malicious Forks

While forks from honest multi-device use are normal, malicious forks are detected:

```python
def detect_malicious_fork(events: list[LogEvent]) -> bool:
    """Detect if someone is intentionally creating many forks."""
    
    # Count forks per time window
    fork_events = [e for e in events if len(e.parents) > 1]
    
    # More than 10 forks per hour is suspicious
    recent_forks = [e for e in fork_events if e.ts > now() - hours(1)]
    if len(recent_forks) > 10:
        return True
    
    # Same device creating forks is impossible (local_seq is sequential)
    # Different devices creating occasional forks is normal
    
    return False
```

---

## 7. Layer 4: Social Layer

*[Same as v1.0 - see original spec]*

---

## 8. Layer 5: Moderation Layer

### 8.1 Overview

The Moderation Layer provides attestation-based moderation with **explicit conflict resolution and spam prevention**.

### 8.2 Core Principle

**Attestations NEVER modify facts.** They are separate claims that compose on top of the truth layer.

### 8.3 Attestation (Same as v1.0)

```typescript
interface Attestation {
  id: string;
  issuer: string;
  subject: string;
  type: "trust" | "label" | "badge" | "block" | "verify" | "flag";
  claim: object;
  evidence?: object;
  ts: timestamp;
  expires_at?: timestamp;
  revoked: boolean;
  sig: bytes;
}
```

### 8.4 Conflicting Attestations ← **NEW SECTION**

When attestations conflict, clients MUST resolve them:

```typescript
interface AttestationConflict {
  subject: string;
  attestations: Attestation[];
  conflict_type: "contradictory" | "severity_mismatch" | "trust_conflict";
}
```

**Resolution Strategies:**

#### 1. Trust-Weighted Resolution

```python
def resolve_by_trust(conflicts: list[Attestation], trust_network: TrustNetwork) -> Attestation:
    """Resolve conflict by trust weight."""
    
    def trust_score(att: Attestation) -> float:
        if att.issuer in trust_network.direct_trust:
            return trust_network.direct_trust[att.issuer]  # 0.0 - 1.0
        
        # Transitive trust (discounted)
        for trusted in trust_network.trusted_issuers:
            if att.issuer in get_trusted_by(trusted):
                return trust_network.direct_trust[trusted] * 0.5
        
        return 0.0
    
    # Highest trust wins
    return max(conflicts, key=trust_score)
```

#### 2. Recency Resolution

```python
def resolve_by_recency(conflicts: list[Attestation]) -> Attestation:
    """Most recent attestation wins."""
    return max(conflicts, key=lambda a: a.ts)
```

#### 3. Severity Resolution

```python
def resolve_by_severity(conflicts: list[Attestation]) -> Attestation:
    """Most severe attestation wins (safety-first)."""
    severity_order = {"block": 3, "flag": 2, "label": 1, "trust": 0}
    return max(conflicts, key=lambda a: severity_order.get(a.type, 0))
```

#### 4. Configurable Resolution

Users configure their preferred resolution:

```typescript
interface ModerationConfig {
  conflict_resolution: "trust_weighted" | "recency" | "severity" | "manual";
  
  // Trust weights
  trust_weights: {
    [issuer: string]: number;  // 0.0 - 1.0
  };
  
  // Auto-apply rules
  auto_block_threshold: number;     // e.g., 3 trusted issuers = auto-block
  auto_hide_threshold: number;      // e.g., 2 trusted flags = auto-hide
  
  // Manual review queue
  require_manual_review: string[];  // Attestation types requiring manual review
}
```

### 8.5 Spam Attestation Prevention ← **NEW SECTION**

Attestations themselves can be spammed. Prevention mechanisms:

#### 1. Rate Limiting

```python
ATTESTATION_LIMITS = {
    "per_issuer_per_hour": 100,
    "per_subject_per_hour": 50,
    "per_issuer_per_day": 1000,
}

def check_attestation_rate_limit(att: Attestation) -> bool:
    recent_by_issuer = count_attestations(issuer=att.issuer, since=hours_ago(1))
    if recent_by_issuer > ATTESTATION_LIMITS["per_issuer_per_hour"]:
        return False
    
    recent_on_subject = count_attestations(subject=att.subject, since=hours_ago(1))
    if recent_on_subject > ATTESTATION_LIMITS["per_subject_per_hour"]:
        return False
    
    return True
```

#### 2. Stake/Reputation Requirements

```python
def can_issue_attestation(issuer: str, att_type: str) -> bool:
    issuer_reputation = get_reputation(issuer)
    
    # Higher-impact attestations require more reputation
    required_reputation = {
        "label": 10,
        "flag": 50,
        "block": 100,
        "verify": 200,
    }
    
    return issuer_reputation >= required_reputation.get(att_type, 0)
```

#### 3. Attestation Challenges

```python
def challenge_attestation(att: Attestation, challenger: str, reason: str):
    """Allow challenging questionable attestations."""
    challenge = AttestationChallenge(
        attestation_id=att.id,
        challenger=challenger,
        reason=reason,
        ts=now(),
    )
    
    # If enough challenges, attestation is flagged for review
    challenges = get_challenges(att.id)
    if len(challenges) >= 3:
        flag_for_review(att)
```

### 8.6 Trust Bootstrapping ← **NEW SECTION**

New users need a way to bootstrap trust:

#### 1. Well-Known Trust Anchors

```python
WELL_KNOWN_ANCHORS = [
    "ent:mesh_foundation",      # Protocol foundation
    "ent:community_council",    # Elected moderators
    "ent:verified_orgs",        # Verified organizations
]

def default_trust_network() -> TrustNetwork:
    """Starting trust network for new users."""
    return TrustNetwork(
        trusted_issuers=WELL_KNOWN_ANCHORS,
        trust_depth=1,
        attestation_types=["label", "block", "flag"],
    )
```

#### 2. Social Trust Import

```python
def import_trust_from_follows(user_id: str) -> TrustNetwork:
    """Build trust network from who user follows."""
    following = get_following(user_id)
    
    # People you follow have base trust
    trust_weights = {f: 0.3 for f in following}
    
    # Mutual follows have higher trust
    followers = get_followers(user_id)
    for f in following:
        if f in followers:
            trust_weights[f] = 0.6
    
    return TrustNetwork(
        trusted_issuers=list(trust_weights.keys()),
        trust_weights=trust_weights,
    )
```

#### 3. Trust Discovery

```python
def discover_trusted_labelers(user_id: str) -> list[str]:
    """Find well-regarded labelers in user's network."""
    
    # Get who user's trusted contacts trust
    my_trusted = get_trust_network(user_id).trusted_issuers
    
    candidates = {}
    for trusted in my_trusted:
        their_trusted = get_trust_network(trusted).trusted_issuers
        for candidate in their_trusted:
            if candidate not in my_trusted:
                candidates[candidate] = candidates.get(candidate, 0) + 1
    
    # Sort by how many trusted contacts trust them
    return sorted(candidates.keys(), key=lambda c: candidates[c], reverse=True)[:10]
```

### 8.7 Moderation Policy Framework ← **NEW SECTION**

MESH doesn't define policies, but provides a framework for them:

```typescript
interface ModerationPolicy {
  id: string;
  name: string;                    // "Family Friendly", "Free Speech", etc.
  description: string;
  
  // What this policy considers violations
  violation_definitions: {
    [violation_type: string]: {
      description: string;
      severity: "low" | "medium" | "high" | "critical";
      auto_action?: "hide" | "warn" | "block";
    };
  };
  
  // Who enforces this policy
  enforcers: string[];             // entity_ids of authorized labelers
  
  // Appeals process
  appeals_contact?: string;
  appeals_process?: string;
}
```

**Example Policies:**

```json
{
  "id": "policy:mesh-default",
  "name": "MESH Default Policy",
  "violation_definitions": {
    "spam": {"severity": "medium", "auto_action": "hide"},
    "harassment": {"severity": "high", "auto_action": "warn"},
    "illegal_content": {"severity": "critical", "auto_action": "block"},
    "impersonation": {"severity": "high", "auto_action": "warn"}
  },
  "enforcers": ["ent:mesh_foundation", "ent:community_council"]
}
```

Users choose which policies to adopt:

```python
def apply_policies(content: Content, policies: list[str]) -> ModerationResult:
    """Apply selected moderation policies to content."""
    
    results = []
    for policy_id in policies:
        policy = get_policy(policy_id)
        attestations = get_attestations_from(policy.enforcers, subject=content.id)
        
        for att in attestations:
            if att.claim.get("violation_type") in policy.violation_definitions:
                violation = policy.violation_definitions[att.claim["violation_type"]]
                results.append(ModerationAction(
                    policy=policy_id,
                    violation=att.claim["violation_type"],
                    severity=violation["severity"],
                    action=violation.get("auto_action"),
                ))
    
    return aggregate_results(results)
```

---

## 9. Layer 6: View Layer

### 9.1 Overview

The View Layer provides deterministic feed computation with **explicit execution limits and cost controls**.

### 9.2 Execution Limits ← **NEW SECTION**

Views can be computationally expensive. Relays MUST enforce limits:

```typescript
interface ViewExecutionLimits {
  // Time limits
  max_execution_time_ms: number;     // e.g., 5000ms
  
  // Resource limits
  max_events_scanned: number;        // e.g., 100,000
  max_memory_mb: number;             // e.g., 100MB
  max_result_size: number;           // e.g., 1,000 events
  
  // Complexity limits
  max_sources: number;               // e.g., 100
  max_filters: number;               // e.g., 20
  max_attestation_lookups: number;   // e.g., 10,000
  
  // Rate limits
  executions_per_minute: number;     // e.g., 60
  executions_per_hour: number;       // e.g., 1,000
}

const DEFAULT_LIMITS: ViewExecutionLimits = {
  max_execution_time_ms: 5000,
  max_events_scanned: 100000,
  max_memory_mb: 100,
  max_result_size: 1000,
  max_sources: 100,
  max_filters: 20,
  max_attestation_lookups: 10000,
  executions_per_minute: 60,
  executions_per_hour: 1000,
};
```

### 9.3 View Cost Model ← **NEW SECTION**

Views have an estimated cost for planning:

```python
def estimate_view_cost(view_def: ViewDefinition) -> ViewCost:
    """Estimate computational cost of a view."""
    
    cost = ViewCost()
    
    # Source costs
    for source in view_def.sources:
        if source.kind == "actor":
            cost.events_to_scan += estimate_actor_events(source.actor_id)
        elif source.kind == "follows":
            following = len(get_following(source.actor_id))
            cost.events_to_scan += following * AVG_EVENTS_PER_USER
        elif source.kind == "all":
            cost.events_to_scan += TOTAL_EVENTS  # Very expensive!
    
    # Filter costs
    for filt in view_def.filters:
        if filt.require_attestations:
            cost.attestation_lookups += cost.events_to_scan
        if filt.exclude_attestations:
            cost.attestation_lookups += cost.events_to_scan
    
    # Reducer costs
    if view_def.reducer == "ranked":
        cost.complexity_multiplier = 2.0  # Scoring is expensive
    elif view_def.reducer == "custom":
        cost.complexity_multiplier = 5.0  # Unknown cost
    
    cost.total = (
        cost.events_to_scan * 0.001 +
        cost.attestation_lookups * 0.01
    ) * cost.complexity_multiplier
    
    return cost
```

### 9.4 View Execution Sandbox ← **NEW SECTION**

Custom reducers run in a sandbox:

```typescript
interface ViewSandbox {
  // Allowed operations
  allowed_operations: [
    "read_events",
    "read_attestations", 
    "sort",
    "filter",
    "aggregate",
  ];
  
  // Forbidden operations
  forbidden: [
    "network_access",
    "file_system",
    "exec",
    "eval",
  ];
  
  // Resource quotas
  max_cpu_ms: number;
  max_memory_bytes: number;
  max_iterations: number;
}
```

For WebAssembly-based custom reducers:

```python
def execute_custom_reducer(wasm_module: bytes, events: list, params: dict) -> list:
    """Execute custom reducer in WASM sandbox."""
    
    sandbox = WasmSandbox(
        memory_limit=100 * 1024 * 1024,  # 100MB
        fuel_limit=1_000_000,             # Instruction limit
        timeout_ms=5000,
    )
    
    try:
        result = sandbox.execute(wasm_module, {
            "events": events,
            "params": params,
        })
        return result
    except SandboxTimeout:
        raise ViewExecutionError("Custom reducer timed out")
    except SandboxMemoryExceeded:
        raise ViewExecutionError("Custom reducer exceeded memory limit")
```

### 9.5 View Abuse Prevention ← **NEW SECTION**

Preventing view-based DoS:

```python
def check_view_abuse(user_id: str, view_def: ViewDefinition) -> bool:
    """Check for view abuse patterns."""
    
    cost = estimate_view_cost(view_def)
    
    # Reject obviously expensive views
    if cost.total > MAX_VIEW_COST:
        raise ViewTooExpensive(f"View cost {cost.total} exceeds limit {MAX_VIEW_COST}")
    
    # Rate limit expensive views
    recent_expensive = count_expensive_views(user_id, since=minutes_ago(10))
    if recent_expensive > 10:
        raise RateLimited("Too many expensive views")
    
    # Track cumulative cost
    cumulative_cost = get_cumulative_cost(user_id, since=hours_ago(1))
    if cumulative_cost + cost.total > HOURLY_COST_LIMIT:
        raise CostLimitExceeded("Hourly view cost limit exceeded")
    
    return True
```

---

## 10. Layer 7: Network Layer

*[Same as v1.0 - see original spec]*

---

## 11. Layer 8: Application Layer

*[Same as v1.0 - see original spec]*

---

## 12. Multi-Device & Fork Resolution ← **NEW CHAPTER**

### 12.1 Overview

Real users have multiple devices. MESH handles this gracefully.

### 12.2 Device Registration Flow

```python
# On new device
async def register_new_device(root_key: bytes, device_name: str):
    # 1. Generate device keypair
    device_keys = SigningKeyPair.generate()
    
    # 2. Create authorization request
    auth_request = DeviceAuthRequest(
        device_public_key=device_keys.public_key_bytes(),
        device_name=device_name,
        requested_capabilities=["post", "follow", "dm"],
    )
    
    # 3. User approves on existing device (has root key)
    # This could be QR code, push notification, etc.
    
    # 4. Existing device creates DeviceKey signed by root
    device_key = authorize_device(root_key, device_keys.public_key_bytes(), device_name)
    
    # 5. Publish device key
    await relay.publish_device_key(device_key)
    
    # 6. New device can now sign events
    return device_keys, device_key
```

### 12.3 Posting from Multiple Devices

```python
async def post_from_device(device_keys: SigningKeyPair, device_id: str, text: str):
    # Get current local state
    local_seq = storage.get_device_seq(device_id)
    local_heads = storage.get_local_heads(my_entity_id)
    
    # Create event with parents = current heads
    event = LogEvent(
        id=generate_event_id(my_entity_id, device_id, local_seq + 1),
        actor=my_entity_id,
        device_id=device_id,
        parents=[h.id for h in local_heads],
        local_seq=local_seq + 1,
        lamport=max(h.lamport for h in local_heads) + 1,
        op="create",
        object_type="content",
        object_id=content.id,
        payload=content.to_dict(),
        ts=now(),
    )
    
    # Sign with device key
    event.sig = device_keys.sign(canonical_json(event.to_dict()))
    
    await relay.submit(event)
```

### 12.4 Sync and Merge Flow

```python
async def sync_and_merge():
    # 1. Fetch remote events
    remote_events = await relay.get_events(my_entity_id, since=last_sync)
    
    # 2. Merge with local events
    all_events = local_events + remote_events
    
    # 3. Find heads
    heads = find_heads(all_events)
    
    # 4. If multiple heads, merge
    if len(heads) > 1:
        merge_event = auto_merge(heads)
        await relay.submit(merge_event)
        heads = [merge_event]
    
    # 5. Update local state
    storage.set_local_heads(my_entity_id, heads)
```

### 12.5 Conflict Examples and Resolution

**Example 1: Both devices posted (no conflict)**
```
Phone: "Good morning!"  (lamport=5)
Laptop: "Just had coffee" (lamport=5)

Result: Both posts appear, ordered by (lamport, id)
```

**Example 2: Both devices edited profile (LWW)**
```
Phone: bio = "Developer" (lamport=5, ts=10:00)
Laptop: bio = "Engineer" (lamport=5, ts=10:01)

Result: "Engineer" wins (higher timestamp as tiebreaker)
```

**Example 3: Follow/unfollow conflict (needs resolution)**
```
Phone: follow(Alice) (lamport=5)
Laptop: unfollow(Alice) (lamport=5)

Result: User prompted - "Did you want to follow or unfollow Alice?"
```

---

## 13. Identity Recovery ← **NEW CHAPTER**

### 13.1 Overview

Lost keys mean lost identity by default. But MESH provides **optional** recovery mechanisms for users who want them.

### 13.2 Recovery Tradeoff Spectrum

```
MORE SECURE ◄──────────────────────────────────────► MORE CONVENIENT
    │                                                        │
    │  No recovery          Social recovery       Custodial  │
    │  (lost = lost)        (trusted friends)     (provider) │
    │                                                        │
    └────────────────────────────────────────────────────────┘
```

Users choose their position on this spectrum.

### 13.3 Recovery Configuration

```typescript
interface RecoveryConfig {
  // Which recovery methods are enabled
  methods: RecoveryMethod[];
  
  // Required threshold for recovery
  threshold: number;  // e.g., 3 of 5 guardians
  
  // Cooling off period before recovery completes
  recovery_delay_hours: number;  // e.g., 72 hours
  
  // Notification settings
  notify_on_recovery_attempt: boolean;
}

type RecoveryMethod = 
  | SocialRecovery
  | CustodialRecovery
  | HardwareBackup
  | PassphraseBackup;
```

### 13.4 Method 1: Social Recovery (Recommended)

Users designate trusted friends as "guardians":

```typescript
interface SocialRecovery {
  type: "social";
  guardians: Guardian[];
  threshold: number;        // How many needed
  
  // Each guardian gets an encrypted key share
  key_shares: {
    [guardian_id: string]: EncryptedKeyShare;
  };
}

interface Guardian {
  entity_id: string;
  name: string;
  relationship?: string;    // "friend", "family", "colleague"
  added_at: timestamp;
}
```

**Setup:**
```python
def setup_social_recovery(root_key: bytes, guardians: list[str], threshold: int):
    # 1. Split key using Shamir's Secret Sharing
    shares = shamir_split(root_key, total=len(guardians), threshold=threshold)
    
    # 2. Encrypt each share for its guardian
    encrypted_shares = {}
    for guardian_id, share in zip(guardians, shares):
        guardian = get_entity(guardian_id)
        encrypted = encrypt_for_recipient(share, guardian.encryption_key)
        encrypted_shares[guardian_id] = encrypted
    
    # 3. Publish recovery config (encrypted shares are public)
    config = RecoveryConfig(
        methods=[SocialRecovery(
            guardians=guardians,
            threshold=threshold,
            key_shares=encrypted_shares,
        )],
        recovery_delay_hours=72,
    )
    
    return config
```

**Recovery:**
```python
async def recover_via_social(user_id: str, new_device_key: bytes):
    # 1. User contacts guardians out-of-band
    # 2. Guardians approve recovery in their clients
    
    # Guardian approval flow
    async def guardian_approve(guardian_id: str, guardian_keys: SigningKeyPair):
        # Decrypt their share
        config = get_recovery_config(user_id)
        my_share = decrypt_for_recipient(
            config.key_shares[guardian_id],
            guardian_keys.encryption_private
        )
        
        # Create approval attestation
        approval = RecoveryApproval(
            user_id=user_id,
            guardian_id=guardian_id,
            share=my_share,  # Encrypted for user's new device
            approved_at=now(),
        )
        approval.sig = guardian_keys.sign(...)
        
        await relay.submit_recovery_approval(approval)
    
    # 3. Once threshold reached, recover
    approvals = await wait_for_approvals(user_id, threshold)
    
    # 4. Reconstruct key
    shares = [a.share for a in approvals]
    root_key = shamir_combine(shares)
    
    # 5. Cooling off period
    await wait(hours=config.recovery_delay_hours)
    
    # 6. Check for cancellation (user found their key)
    if recovery_cancelled(user_id):
        raise RecoveryCancelled()
    
    # 7. Complete recovery - authorize new device
    new_device = authorize_device(root_key, new_device_key, "Recovered Device")
    
    return new_device
```

### 13.5 Method 2: Custodial Recovery

For users who prefer convenience over full self-sovereignty:

```typescript
interface CustodialRecovery {
  type: "custodial";
  provider: string;         // entity_id of recovery provider
  provider_name: string;    // "MESH Foundation", "Acme Corp"
  
  // Provider holds encrypted key
  encrypted_key: bytes;
  
  // Verification method
  verification: "email" | "phone" | "id_document" | "multi_factor";
}
```

**How it works:**
1. User encrypts root key for provider's public key
2. Provider stores encrypted key
3. On recovery, provider verifies identity (email, phone, ID)
4. Provider returns encrypted key
5. User decrypts with their verification credentials

```python
def setup_custodial_recovery(root_key: bytes, provider_id: str, email: str):
    provider = get_entity(provider_id)
    
    # Derive encryption key from email + password (known only to user)
    recovery_password = prompt_user("Create recovery password")
    user_recovery_key = derive_key(email, recovery_password)
    
    # Double-encrypt: once for provider, once for user
    encrypted_for_provider = encrypt_for_recipient(root_key, provider.encryption_key)
    encrypted_for_user = encrypt_aes(encrypted_for_provider, user_recovery_key)
    
    # Provider stores encrypted_for_user
    # They can't decrypt without user's password
    
    return CustodialRecovery(
        provider=provider_id,
        encrypted_key=encrypted_for_user,
        verification="email",
    )
```

### 13.6 Method 3: Hardware Backup

For security-conscious users:

```typescript
interface HardwareBackup {
  type: "hardware";
  
  // Encrypted key stored on hardware device
  device_type: "yubikey" | "ledger" | "trezor" | "usb_drive";
  device_id?: string;
  
  // Backup locations
  locations: string[];      // "safe deposit box", "home safe", etc.
}
```

### 13.7 Method 4: Passphrase Backup

Mnemonic seed phrase (like Bitcoin):

```typescript
interface PassphraseBackup {
  type: "passphrase";
  
  // 24-word mnemonic
  word_count: 12 | 24;
  
  // Optional passphrase for extra security
  has_passphrase: boolean;
}
```

```python
def generate_mnemonic_backup(root_key: bytes) -> list[str]:
    # BIP39-style mnemonic
    entropy = root_key
    checksum = sha256(entropy)[:1]
    bits = entropy + checksum
    
    words = []
    for i in range(0, len(bits) * 8, 11):
        index = int.from_bytes(bits[i//8:(i+11)//8+1], 'big') >> (8 - (i % 8 + 11) % 8) & 0x7FF
        words.append(BIP39_WORDLIST[index])
    
    return words

def recover_from_mnemonic(words: list[str]) -> bytes:
    # Reverse the process
    ...
```

### 13.8 Recovery Security Measures

**Cooling Off Period:**
```python
RECOVERY_DELAY = timedelta(hours=72)

async def complete_recovery(recovery_id: str):
    recovery = get_recovery(recovery_id)
    
    if now() < recovery.initiated_at + RECOVERY_DELAY:
        raise RecoveryDelayNotPassed()
    
    if recovery.cancelled:
        raise RecoveryCancelled()
    
    # Complete recovery
    ...
```

**Notification:**
```python
async def notify_recovery_attempt(user_id: str, recovery_type: str):
    # Notify all devices
    for device in get_user_devices(user_id):
        await send_push_notification(device, {
            "type": "recovery_attempt",
            "message": f"Someone is trying to recover your account via {recovery_type}",
            "action": "Review and cancel if unauthorized",
        })
    
    # Notify guardians
    if recovery_type == "social":
        for guardian in get_guardians(user_id):
            await notify_entity(guardian, "Recovery attempt for your friend")
```

**Cancellation:**
```python
async def cancel_recovery(user_id: str, device_keys: SigningKeyPair):
    """Cancel recovery if user finds their key."""
    
    cancellation = RecoveryCancellation(
        user_id=user_id,
        cancelled_at=now(),
        reason="User found original key",
    )
    cancellation.sig = device_keys.sign(...)
    
    await relay.submit_cancellation(cancellation)
```

### 13.9 Recovery UX Guidelines

**Do:**
- ✓ Encourage social recovery setup during onboarding
- ✓ Show clear warnings about lost keys
- ✓ Make guardian selection easy ("Your most trusted contacts")
- ✓ Send reminders to update guardians periodically

**Don't:**
- ✗ Force recovery setup (some users want no recovery)
- ✗ Make recovery instant (allows attacks)
- ✗ Allow recovery without notification
- ✗ Store unencrypted keys anywhere

---

## 14. Derived Systems

*[Same as v1.0 - see original spec]*

---

## 15. Sync Protocol

### 15.1 Overview

MESH uses **DAG-based sync** that handles multi-device naturally.

### 15.2 Sync Algorithm (Updated for DAG)

```python
async def sync_actor(actor_id: str, relay: Relay):
    # 1. Get local heads (may be multiple)
    local_heads = storage.get_heads(actor_id)
    local_head_ids = {h.id for h in local_heads}
    
    # 2. Get remote heads
    remote_heads = await relay.get_heads(actor_id)
    remote_head_ids = {h.id for h in remote_heads}
    
    # 3. If same heads, in sync
    if local_head_ids == remote_head_ids:
        return
    
    # 4. Find missing events
    local_known = storage.get_all_event_ids(actor_id)
    remote_known = await relay.get_all_event_ids(actor_id)
    
    missing_local = remote_known - local_known
    missing_remote = local_known - remote_known
    
    # 5. Fetch missing events
    if missing_local:
        events = await relay.get_events(actor_id, event_ids=missing_local)
        for event in topological_sort(events):
            if verify_event(event):
                storage.store_event(event)
    
    # 6. Push events remote doesn't have
    if missing_remote:
        events = storage.get_events(actor_id, event_ids=missing_remote)
        await relay.submit_events(events)
    
    # 7. Merge if needed
    new_heads = storage.get_heads(actor_id)
    if len(new_heads) > 1:
        merge = auto_merge(new_heads)
        storage.store_event(merge)
        await relay.submit(merge)
```

---

## 16. Security Model

### 16.1 Updated Threat Model

**In Scope:**
- Impersonation (prevented by signatures)
- Tampering (prevented by signatures + DAG)
- Replay attacks (prevented by content-addressing)
- Eavesdropping on DMs (prevented by E2EE)
- **Key compromise on single device** (limited by device keys) ← **NEW**
- **Malicious fork attacks** (detected and rate-limited) ← **NEW**

**Out of Scope:**
- Root key compromise (total identity loss)
- Denial of service (relay responsibility)
- Spam (addressed by moderation layer)
- Sybil attacks (partially addressed by attestations)

### 16.2 Device Key Compromise Response

If a device is compromised:

```python
async def handle_device_compromise(root_key: SigningKeyPair, compromised_device_id: str):
    # 1. Revoke compromised device
    revocation = DeviceKeyRevocation(
        device_id=compromised_device_id,
        revoked_at=now(),
        reason="compromised",
    )
    revocation.sig = root_key.sign(...)
    await relay.publish_revocation(revocation)
    
    # 2. Events from compromised device after revocation are invalid
    # Clients MUST check revocation status when verifying
    
    # 3. Optionally: mark suspicious events
    suspicious = get_events_by_device(compromised_device_id, since=suspected_compromise_time)
    for event in suspicious:
        await mark_as_suspicious(event)
```

---

## 17. Scalability

*[Same as v1.0 - see original spec]*

---

## 18. Comparison with Existing Protocols

### 18.1 Updated Feature Comparison

| Feature | MESH v1.1 | Nostr | ActivityPub | SSB | AT Protocol |
|---------|:---------:|:-----:|:-----------:|:---:|:-----------:|
| Self-sovereign identity | ✓ | ✓ | ✗ | ✓ | ✗ |
| Multi-device support | ✓ | ✗ | ✓ | ✗ | ✓ |
| E2EE | ✓ | ✗ | ✗ | ✓ | ✗ |
| Fork handling | ✓ Auto | N/A | N/A | ✗ Manual | ✓ Auto |
| Identity recovery | ✓ Optional | ✗ | ✓ | ✗ | ✓ |
| Custom algorithms | ✓ | ✗ | ✗ | ✗ | ✓ |
| Execution limits | ✓ | N/A | N/A | N/A | ✓ |
| Attestations | ✓ | ✗ | ✗ | ✗ | ✓ |

---

## 19. Implementation Requirements

### 19.1 Updated Conformance Levels

**Level 1: Minimal**
- MUST implement Privacy Layer (signatures, device keys)
- MUST implement Storage Layer
- MUST implement Integrity Layer (DAG, auto-merge)
- MUST implement Social Layer
- MAY implement other layers

**Level 2: Standard**
- MUST implement all Level 1 requirements
- MUST implement Network Layer (HTTP API)
- MUST implement multi-device sync
- SHOULD implement Moderation Layer
- SHOULD implement View Layer with limits

**Level 3: Full**
- MUST implement all Level 2 requirements
- MUST implement social recovery
- MUST implement view execution sandbox
- MUST implement attestation conflict resolution
- MUST implement all sync optimizations

---

## 20. Appendices

### Appendix A: Multi-Device Test Vectors

**Device Key Authorization:**
```
Root Private Key: 9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60
Root Public Key: d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a
Device Public Key: 3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c

Device Key (JSON):
{
  "device_id": "dev:a1b2c3",
  "public_key": "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
  "name": "iPhone",
  "authorized_at": "2026-01-01T00:00:00Z",
  "revoked": false,
  "capabilities": ["post", "follow", "dm"],
  "sig": "..."
}
```

**Fork and Merge:**
```
Event A (device 1): id=evt_a, parents=[root], lamport=1
Event B (device 2): id=evt_b, parents=[root], lamport=1

Merge Event: id=evt_merge, parents=[evt_a, evt_b], lamport=2
```

### Appendix B: Recovery Test Vectors

**Shamir Split (3-of-5):**
```
Secret: 9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60

Share 1: 01:a1b2c3d4...
Share 2: 02:e5f6a7b8...
Share 3: 03:c9d0e1f2...
Share 4: 04:39404142...
Share 5: 05:73747576...

Any 3 shares reconstruct the secret.
```

### Appendix C: View Cost Examples

| View Type | Events Scanned | Attestation Lookups | Est. Time |
|-----------|:--------------:|:-------------------:|:---------:|
| My timeline (100 follows) | 10,000 | 0 | 50ms |
| My timeline + moderation | 10,000 | 10,000 | 200ms |
| Global trending | 1,000,000 | 0 | 2000ms |
| Global + moderation | 1,000,000 | 1,000,000 | REJECTED |

---

## Changelog

### v1.1 (2026-04-23)
- Added multi-device support with device keys
- Changed from single prev chain to multi-head DAG
- Added automatic fork merge strategies
- Added identity recovery (social, custodial, hardware, passphrase)
- Added view execution limits and cost model
- Added attestation conflict resolution
- Added trust bootstrapping
- Added moderation policy framework
- Added spam attestation prevention

### v1.0 (2026-04-23)
- Initial specification

---

## Authors

- MESH Protocol Working Group
- Based on HOLON, Relay, and community contributions

---

## License

This specification is released under CC0 1.0 Universal (Public Domain).
