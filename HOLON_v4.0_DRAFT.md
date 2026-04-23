# HOLON Protocol v4.0

**Transparent Social Infrastructure**

---

## What We Learned

Before diving in, here's what simulation and design iteration taught us:

| Assumption | Reality | Impact |
|------------|---------|--------|
| Link explosion is catastrophic | Storage grows ~1.25x users | Relax, it's manageable |
| Views will be slow at scale | Sub-millisecond even at 10k users | Views are cheap |
| Three layers needed | Structure is just entity metadata | Merge to two layers |
| Technical challenges dominate | Social/economic challenges dominate | Reframe the problem |

**Key insight:** The hard problems aren't in the data model. They're in:
1. Who decides what you see? (Algorithms)
2. Who decides what's allowed? (Moderation)
3. Who pays for infrastructure? (Economics)

HOLON v4.0 focuses on these.

---

## Core Philosophy

1. **Two layers, not three** — Data and Algorithms
2. **Transparent by default** — Every algorithm is inspectable
3. **Forkable everything** — Don't like it? Copy and modify it
4. **Economics built-in** — Sustainability isn't an afterthought
5. **Governance is explicit** — Moderation rules are data, not code

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR APPLICATION                          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  ALGORITHM LAYER                                             │
│  Views │ Feeds │ Recommendations │ Moderation Rules          │
│  ────────────────────────────────────────────────────────── │
│  All algorithms are: inspectable, verifiable, forkable      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  DATA LAYER                                                  │
│  Entity │ Content │ Link                                    │
│  ────────────────────────────────────────────────────────── │
│  Just data. No hidden logic. Synced via relays.             │
└─────────────────────────────────────────────────────────────┘
```

---

# DATA LAYER

Everything is one of three things.

---

## 1. The Three Primitives

| Primitive | What it is | Examples |
|-----------|------------|----------|
| **Entity** | Something with identity | user, org, group, relay |
| **Content** | Something published | post, article, image, video, course |
| **Link** | A relationship | follow, react, subscribe, moderate |

That's it. Everything else is built from these.

---

## 2. Entity

An identity that can sign things.

```json
{
  "id": "ent:alice",
  "type": "entity",
  "kind": "user",
  "keys": {
    "sign": "ed25519:...",
    "encrypt": "x25519:..."
  },
  "profile": {
    "name": "Alice",
    "bio": "Building things"
  },
  "parent": null,
  "sig": "..."
}
```

### Entity Kinds

| Kind | Purpose | Parent |
|------|---------|--------|
| `user` | A person | None |
| `org` | An organization | None |
| `group` | A community | Optional (for nesting) |
| `relay` | A server | None |

### Nesting (Replaces Structure Layer)

Groups can nest inside other groups:

```
University (group)
├── Computer Science (group, parent=University)
│   ├── AI Club (group, parent=CS)
│   └── Systems Club (group, parent=CS)
└── Physics (group, parent=University)
```

That's all "holonic structure" ever was — a `parent` field.

---

## 3. Content

Something someone published.

```json
{
  "id": "cnt:abc123",
  "type": "content",
  "kind": "post",
  "author": "ent:alice",
  "created": "2026-04-23T12:00:00Z",
  "context": "ent:ai-club",
  "body": {
    "text": "Just published a new paper on...",
    "media": ["cid:bafybeif..."]
  },
  "reply_to": null,
  "access": "public",
  "sig": "..."
}
```

### Content Kinds

| Kind | Body Fields |
|------|-------------|
| `post` | text, media |
| `article` | title, body (markdown), media |
| `media` | url, mime_type, caption |
| `course` | title, modules (array) |

### Access Control

| Access | Who can read |
|--------|-------------|
| `public` | Anyone |
| `followers` | Author's followers |
| `group` | Group members (uses group key) |
| `private` | Specific recipients (uses their public keys) |

---

## 4. Link

A directed relationship between two things.

```json
{
  "id": "lnk:xyz789",
  "type": "link",
  "kind": "react",
  "source": "ent:bob",
  "target": "cnt:abc123",
  "created": "2026-04-23T12:05:00Z",
  "data": {
    "emoji": "🔥"
  },
  "sig": "..."
}
```

### Link Kinds

| Kind | Source → Target | Data |
|------|-----------------|------|
| `follow` | entity → entity | — |
| `react` | entity → content | emoji |
| `subscribe` | entity → entity | tier (optional) |
| `member` | entity → group | role |
| `moderate` | entity → content | action, reason |
| `label` | entity → content | labels[], scope |
| `delegate` | entity → entity | permissions[] |

### Deletion = Tombstone

```json
{
  "id": "lnk:xyz789",
  "tombstone": true,
  "sig": "..."
}
```

---

## 5. Identity & Keys

### Key Hierarchy

```
Root Key (cold storage)
└── signs → Device Keys (on each device)
              └── signs → all content from that device
```

### Key Rotation

When a key is compromised:

```json
{
  "type": "link",
  "kind": "rotate",
  "source": "ent:alice",
  "target": "ent:alice",
  "data": {
    "old_key": "ed25519:abc...",
    "new_key": "ed25519:def...",
    "revoke_after": "2026-04-23T12:00:00Z"
  }
}
```

Content signed by the old key before `revoke_after` remains valid.

---

## 6. Sync

Relays store and sync data. Clients subscribe to what they need.

### Subscribe to entities

```json
{
  "op": "subscribe",
  "entities": ["ent:alice", "ent:bob"],
  "since": 12345
}
```

### Subscribe to contexts

```json
{
  "op": "subscribe",
  "contexts": ["ent:ai-club"],
  "since": 12345
}
```

### Relay response

```json
{
  "op": "events",
  "events": [...],
  "cursor": 12350
}
```

---

# ALGORITHM LAYER

**The innovation.** Every algorithm is transparent, verifiable, and forkable.

---

## 7. The Problem with Algorithms

On traditional platforms:
- You don't know why you see what you see
- You can't change it
- You can't verify it's doing what they claim

HOLON makes algorithms **data**, not hidden code.

---

## 8. Views

A View is a saved query that produces a feed.

```json
{
  "id": "view:trending-ai",
  "type": "view",
  "author": "ent:alice",
  "name": "Trending in AI",
  "source": {
    "context": "ent:ai-club",
    "include_children": true
  },
  "filter": [
    {"field": "kind", "op": "eq", "value": "post"},
    {"field": "created", "op": "gt", "value": "-24h"}
  ],
  "rank": {
    "formula": "reactions * 2 + replies + recency_bonus",
    "weights": {
      "reactions": 2,
      "replies": 1,
      "recency_hours": -0.1
    }
  },
  "limit": 50
}
```

### Anyone Can:

1. **Inspect** — See exactly how content is ranked
2. **Verify** — Re-run the algorithm, get the same results
3. **Fork** — Copy the view, modify the weights, publish your version
4. **Subscribe** — Use someone else's view as your feed

---

## 9. Ranking Formulas

Views use a simple expression language:

```
score = (reactions * w1) + (replies * w2) + (age_hours * w3) + (author_reputation * w4)
```

### Available Fields

| Field | Description |
|-------|-------------|
| `reactions` | Count of reaction links |
| `replies` | Count of reply content |
| `age_hours` | Hours since created |
| `author_followers` | Author's follower count |
| `author_reputation` | Computed trust score |
| `has_media` | 1 if contains media, 0 otherwise |
| `thread_depth` | How deep in a reply chain |

### Built-in Functions

| Function | Description |
|----------|-------------|
| `decay(hours, halflife)` | Exponential time decay |
| `log(x)` | Logarithm (for diminishing returns) |
| `cap(x, max)` | Cap a value |
| `boost_if(condition, amount)` | Conditional boost |

### Example: Hacker News-style

```json
{
  "formula": "(reactions - 1) / decay(age_hours, 2.5)",
  "description": "Points decay with age, half-life of 2.5 hours"
}
```

---

## 10. Verification

How do you know a feed wasn't manipulated?

### Boundaries

A boundary defines the inputs to a view at a point in time:

```json
{
  "view_id": "view:trending-ai",
  "timestamp": "2026-04-23T12:00:00Z",
  "input_hash": "sha256:abc123...",
  "result_ids": ["cnt:1", "cnt:2", "cnt:3", ...],
  "result_hash": "sha256:def456..."
}
```

### Verification Process

1. Get the boundary
2. Fetch all content matching the view's source/filter at that timestamp
3. Apply the ranking formula
4. Hash the results
5. Compare to `result_hash`

If they match, the feed wasn't manipulated.

---

## 11. Moderation as Data

Moderation rules are also transparent algorithms.

### Moderation View

```json
{
  "id": "view:ai-club-moderation",
  "type": "view",
  "author": "ent:ai-club",
  "name": "AI Club Moderation Policy",
  "source": {"context": "ent:ai-club"},
  "filter": [
    {"field": "labels", "op": "contains", "value": "spam"},
    {"field": "labeler_trust", "op": "gt", "value": 0.8}
  ],
  "action": "hide"
}
```

### How It Works

1. **Labelers** add labels to content (spam, nsfw, misinformation, etc.)
2. **Moderation views** filter based on labels
3. **Clients** apply the moderation view of the context they're in
4. **Users** can see what was hidden and why

### Key Properties

- **Transparent** — Rules are visible
- **Contextual** — Each community sets its own rules
- **Overridable** — Users can choose stricter or looser filtering
- **Auditable** — Every moderation action is a signed link

---

## 12. Reputation

Trust is computed, not stored.

### Inputs to Reputation

| Signal | Weight | Description |
|--------|--------|-------------|
| Account age | + | Older accounts more trusted |
| Follower count | + | (logarithmic, capped) |
| Content quality | + | Reactions on past content |
| Moderation history | - | Past content removed for spam/abuse |
| Vouches | + | Trusted accounts vouch for this one |

### Reputation Formula

```
reputation = (
  log(account_age_days + 1) * 0.2 +
  log(min(followers, 10000) + 1) * 0.3 +
  avg_reactions_per_post * 0.3 +
  vouch_score * 0.2 -
  spam_rate * 2
)
```

### Key Properties

- **Computed client-side** — Not stored in protocol
- **Context-specific** — Reputation in AI-club ≠ reputation globally
- **Inspectable** — Users can see how their reputation is calculated
- **Forkable** — Communities can use different formulas

---

# ECONOMICS

**Who pays for this?**

---

## 13. Relay Economics

Relays store and serve data. They need to be paid.

### Model 1: User-Paid

Users pay relays directly (subscription or per-request).

```json
{
  "type": "link",
  "kind": "subscribe",
  "source": "ent:alice",
  "target": "ent:relay-1",
  "data": {
    "tier": "premium",
    "payment": "ln:invoice..."
  }
}
```

### Model 2: Creator-Paid

Creators pay relays to host their content.

```json
{
  "type": "link",
  "kind": "host",
  "source": "ent:alice",
  "target": "ent:relay-1",
  "data": {
    "content_budget": "1000 sats/month"
  }
}
```

### Model 3: Community-Paid

Groups pay relays on behalf of members.

### Model 4: Advertiser-Paid

Views can include sponsored content (clearly marked).

**The protocol doesn't mandate a model.** Relays compete on price and service.

---

## 14. Creator Economics

Creators need to get paid for their work.

### Subscriptions

```json
{
  "type": "link",
  "kind": "subscribe",
  "source": "ent:bob",
  "target": "ent:alice",
  "data": {
    "tier": "supporter",
    "payment": "ln:invoice..."
  }
}
```

Alice publishes some content as `access: subscribers_only`.

### Tips

```json
{
  "type": "link",
  "kind": "tip",
  "source": "ent:bob",
  "target": "cnt:abc123",
  "data": {
    "amount": "1000 sats",
    "payment": "ln:invoice..."
  }
}
```

### Paid Content

```json
{
  "type": "content",
  "access": "paid",
  "price": "5000 sats",
  "preview": "First paragraph visible..."
}
```

---

## 15. View Economics

Good algorithms are valuable. Algorithm creators can be paid.

### View Subscriptions

```json
{
  "type": "link",
  "kind": "subscribe",
  "source": "ent:bob",
  "target": "view:best-ai-papers",
  "data": {
    "payment": "100 sats/month"
  }
}
```

### Why Pay for Views?

- **Curation takes effort** — Finding good content is work
- **Algorithms can be better or worse** — Good ones are worth paying for
- **Aligns incentives** — View authors are paid to serve users, not advertisers

---

# GOVERNANCE

**Who decides the rules?**

---

## 16. Context Governance

Every context (group/community) has governance rules.

```json
{
  "id": "ent:ai-club",
  "type": "entity",
  "kind": "group",
  "governance": {
    "moderation_view": "view:ai-club-moderation",
    "moderators": ["ent:alice", "ent:bob"],
    "appeals": "ent:ai-club-appeals-council",
    "rules_url": "https://ai-club.example/rules"
  }
}
```

### Governance Properties

| Property | Description |
|----------|-------------|
| `moderation_view` | Which view defines content filtering |
| `moderators` | Who can add labels in this context |
| `appeals` | Who handles appeals |
| `rules_url` | Human-readable rules |

---

## 17. Dispute Resolution

When moderation is contested:

1. **User appeals** — Creates an appeal link
2. **Appeals council reviews** — Can override moderator decision
3. **Fork if irreconcilable** — Community splits

```json
{
  "type": "link",
  "kind": "appeal",
  "source": "ent:charlie",
  "target": "lnk:moderation-action-123",
  "data": {
    "reason": "This was satire, not spam"
  }
}
```

### Key Principle

**No central authority.** If you disagree with a community's moderation:
1. Appeal within the community
2. Leave and join/create another community
3. Fork the community (copy members, different rules)

---

## 18. Protocol Governance

How does the protocol itself evolve?

### Extension Mechanism

New features are proposed as extensions:

```json
{
  "type": "content",
  "kind": "extension_proposal",
  "author": "ent:protocol-council",
  "body": {
    "name": "HOLON-EXT-001: Video Streaming",
    "spec_url": "https://...",
    "status": "draft"
  }
}
```

### Adoption

Extensions become standard when:
1. Multiple implementations exist
2. Significant usage (measured by relays)
3. No unresolved objections from major implementers

**There is no central committee.** Standards emerge from usage.

---

# MIGRATION

**How do you get here from existing networks?**

---

## 19. Import Existing Data

### From Twitter/X

```json
{
  "type": "content",
  "kind": "post",
  "author": "ent:alice",
  "body": {
    "text": "My old tweet",
    "imported_from": {
      "platform": "twitter",
      "id": "1234567890",
      "url": "https://twitter.com/alice/status/1234567890"
    }
  }
}
```

### From Nostr

Direct mapping:
- Nostr events → HOLON content
- Nostr pubkeys → HOLON entity keys
- Nostr follows → HOLON follow links

### From ActivityPub

- ActivityPub actors → HOLON entities
- ActivityPub objects → HOLON content
- ActivityPub activities → HOLON links

---

## 20. Social Graph Portability

Your follow list is yours. Export it anytime.

```json
{
  "type": "export",
  "format": "holon-social-graph-v1",
  "entities": [
    {"id": "ent:alice", "kind": "user", "profile": {...}},
    ...
  ],
  "follows": [
    {"source": "ent:me", "target": "ent:alice"},
    ...
  ]
}
```

Import into any HOLON client. Your social graph moves with you.

---

# IMPLEMENTATION GUIDE

---

## 21. Minimum Viable Implementation

To build a HOLON client, implement:

### Phase 1: Read-Only (1 week)

1. Connect to a relay
2. Fetch entities/content/links
3. Display a feed

### Phase 2: Write (1 week)

4. Generate keypair
5. Sign and publish content
6. Create follow/react links

### Phase 3: Views (1 week)

7. Execute view queries
8. Display ranked feeds
9. Allow view subscription

### Phase 4: Encryption (when needed)

10. Group key management
11. Private messages
12. Paid content unlock

---

## 22. Relay Implementation

A relay needs:

1. **Storage** — SQLite is fine for small scale, Postgres for large
2. **WebSocket API** — Subscribe/publish
3. **Query engine** — Execute view filters
4. **Signature verification** — Reject invalid signatures

### Recommended Stack

| Component | Small Scale | Large Scale |
|-----------|-------------|-------------|
| Database | SQLite | Postgres + TimescaleDB |
| Server | Single process | Horizontally scaled |
| Caching | None | Redis |
| CDN | None | Cloudflare/Fastly |

---

## 23. Scaling Characteristics

From simulation:

| Users | Objects | Storage | View P95 |
|-------|---------|---------|----------|
| 100 | ~120 | 0.03 MB | 0.2 ms |
| 1,000 | ~1,250 | 0.3 MB | 0.1 ms |
| 10,000 | ~12,500 | 3 MB | 0.5 ms |
| 100,000 | ~125,000 | 30 MB | 5 ms |

**Key findings:**
- Storage grows linearly (~1.25x user count)
- View computation is fast (sub-millisecond to low-millisecond)
- Link explosion is manageable (mostly from key rotation, not social activity)

---

# COMPARISON

---

## 24. vs Other Protocols

| Feature | Nostr | ActivityPub | AT Protocol | **HOLON** |
|---------|-------|-------------|-------------|-----------|
| Decentralized | ✓ | Partial | Partial | ✓ |
| Self-sovereign identity | ✓ | ✗ | ✓ | ✓ |
| Transparent algorithms | ✗ | ✗ | Partial | **✓** |
| Verifiable feeds | ✗ | ✗ | ✗ | **✓** |
| Forkable algorithms | ✗ | ✗ | ✗ | **✓** |
| Built-in encryption | ✗ | ✗ | ✗ | ✓ |
| Community nesting | ✗ | ✗ | ✗ | ✓ |
| Creator economics | ✗ | ✗ | ✗ | ✓ |

### HOLON's Unique Contribution

**Transparent, verifiable, forkable algorithms.**

Every other protocol treats algorithms as implementation details. HOLON makes them first-class citizens of the protocol.

---

# KNOWN LIMITATIONS

---

## 25. What HOLON Doesn't Solve

| Problem | Status | Notes |
|---------|--------|-------|
| Sybil attacks | Partial | Reputation helps but doesn't eliminate |
| Illegal content | External | Requires legal process, not protocol |
| Key loss | User responsibility | No recovery without backup |
| Relay collusion | Mitigated | Use multiple relays |
| Global consensus | Not attempted | Eventual consistency only |

---

## 26. Open Questions

1. **How do you bootstrap trust in a new network?**
   - Current answer: Import from existing networks, vouching
   
2. **How do you prevent algorithm gaming?**
   - Current answer: Transparent algorithms make gaming visible
   
3. **How do you handle legal takedown requests?**
   - Current answer: Relays comply individually, content may exist elsewhere
   
4. **What happens when communities fork?**
   - Current answer: Both continue to exist, users choose

---

# SUMMARY

---

## 27. What HOLON Is

A protocol for social applications where:

1. **You own your identity** — Keys, not accounts
2. **You own your data** — Portable, exportable
3. **You own your social graph** — Take it anywhere
4. **Algorithms are transparent** — See why you see what you see
5. **Algorithms are verifiable** — Prove feeds aren't manipulated
6. **Algorithms are forkable** — Don't like it? Change it
7. **Moderation is contextual** — Communities set their own rules
8. **Economics are built-in** — Creators and curators can be paid

---

## 28. What HOLON Isn't

- Not a blockchain (no global consensus needed)
- Not a company (no central operator)
- Not a complete solution (social problems need social solutions)

---

## 29. Get Started

1. **Read the spec** — You just did
2. **Run the simulator** — `python run_simulation.py --scenario small_network`
3. **Build a client** — Start with read-only, add features incrementally
4. **Join a relay** — Or run your own
5. **Contribute** — Spec improvements, implementations, feedback

---

## Changelog from v3.2

| Change | Rationale |
|--------|-----------|
| Merged Structure Layer into Data Layer | `parent` field is enough for nesting |
| Renamed "View Layer" to "Algorithm Layer" | Clearer purpose |
| Added ranking formula specification | Enable real algorithm transparency |
| Added Economics section | Sustainability is critical |
| Added Governance section | Moderation needs explicit rules |
| Added Migration section | Adoption requires import paths |
| Removed excessive JSON examples | Less verbose, more conceptual |
| Added simulation results | Ground the spec in reality |

---

*HOLON v4.0 DRAFT — Transparent Social Infrastructure*
