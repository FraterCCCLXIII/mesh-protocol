# FABRIC Protocol v2.2

**Federated Architecture for Broadcast, Relationships, Identity, and Content**

A minimal protocol for decentralized social applications — from blogs to learning platforms to encrypted communities.

---

## Changelog (v2.2)

### From v2.1
- **Fixed**: Membership model — `membership_request` (relationship) vs `membership` (credential)
- **Fixed**: Subscription moved from relationship to credential (was incorrectly listed)
- **Fixed**: Tier key architecture fully specified
- **Added**: Conflict resolution rules for multi-relay sync
- **Added**: Self-attestation fallback for payment bootstrapping
- **Added**: Entity versioning with explicit `version` field
- **Added**: Spam resistance recommendations
- **Added**: Schema registry guidance
- **Added**: Ordering fallback documentation
- **Clarified**: Known limitations section expanded

### From v2.0 (in v2.1)
- Key rotation with explicit deprecation
- `thread_root` field for efficient thread queries
- Group `history_policy`: `join_date_forward` (default) vs `full_access`
- Relay sequence numbers for sync
- Multi-relay merge guidance
- Payment attestation pattern
- `_display` convention for schema fallback rendering
- `tombstones_all` for batch tombstoning
- Links are append-only with tombstones
- `context` vs `access` distinction
- Credential signing rule (third-party signed)
- Collapsed to 3 Content kinds and 3 Link kinds

---

## 1. Core Model

### 1.1 Three Primitives, Three Kinds Each

| Primitive | Kinds | Purpose |
|-----------|-------|---------|
| **Entity** | `user`, `org`, `group` | Actors with identity |
| **Content** | `post`, `media`, `structured` | Publishable data |
| **Link** | `relationship`, `interaction`, `credential` | Connections between things |

Everything else is determined by `schema` (for Content) or `subkind` (for Links).

### 1.2 Entity

Actors in the system:

```json
{
  "type": "entity",
  "id": "ent:alice",
  "kind": "user",
  "version": 3,
  "seq": 12345,
  "created": "2026-04-23T12:00:00Z",
  "updated": "2026-04-25T08:00:00Z",
  "data": {
    "name": "Alice",
    "bio": "Building things",
    "avatar": "cid:bafybeif..."
  },
  "keys": {
    "signing": "ed25519:7xK4a2...",
    "encryption": "x25519:9bM3c8..."
  },
  "custody": "provider",
  "sig": "ed25519:..."
}
```

**Entity Versioning:**

Entities have an explicit `version` field (integer, starts at 1). Each update increments the version. This enables conflict resolution when the same entity is received from multiple relays with different states.

**Entity Kinds:**

| Kind | Description | Examples |
|------|-------------|----------|
| `user` | Individual person or bot | Alice, @newsbot |
| `org` | Organization or publication | Acme Inc, Alice's Newsletter |
| `group` | Community or team | Rust Developers, Project X Team |

### 1.3 Content

Publishable data:

```json
{
  "type": "content",
  "id": "cnt:post123",
  "kind": "post",
  "author": "ent:alice",
  "seq": 67890,
  "created": "2026-04-23T12:00:00Z",
  "schema": "social.post.v1",
  "data": {
    "_display": {
      "title": null,
      "summary": "Hello, decentralized world!",
      "thumbnail": null
    },
    "text": "Hello, decentralized world!",
    "media": []
  },
  "access": {"type": "public"},
  "sig": "ed25519:..."
}
```

**Content Kinds:**

| Kind | Description | Example Schemas |
|------|-------------|-----------------|
| `post` | Text-focused, threaded | `social.post.v1`, `blog.article.v1`, `social.comment.v1` |
| `media` | File-focused | `media.image.v1`, `media.video.v1`, `media.document.v1` |
| `structured` | Schema-driven data | `lms.course.v1`, `lms.lesson.v1`, `cooking.recipe.v1` |

### 1.4 Link

Relationships between entities or content:

```json
{
  "type": "link",
  "id": "lnk:follow456",
  "kind": "relationship",
  "source": "ent:alice",
  "target": "ent:bob",
  "seq": 11111,
  "created": "2026-04-23T12:00:00Z",
  "data": {
    "subkind": "follow"
  },
  "sig": "ed25519:..."
}
```

**Link Kinds and Subkinds:**

| Kind | Subkind | Description | Signed By |
|------|---------|-------------|-----------|
| `relationship` | `follow` | Subscribe to entity's content | Source |
| `relationship` | `membership_request` | Request to join group | Source (requester) |
| `relationship` | `block` | Block an entity | Source |
| `interaction` | `react` | Reaction to content (like, emoji) | Source |
| `interaction` | `reply` | Reply indicator (points to content) | Source |
| `interaction` | `progress` | Progress on content (for LMS) | Source |
| `interaction` | `bookmark` | Save for later | Source |
| `credential` | `membership` | Confirmed group membership | Group admin |
| `credential` | `subscription` | Paid subscription to entity | Payment attestor |
| `credential` | `key_rotation` | Rotate signing keys | Old key holder |
| `credential` | `enrollment` | Enrolled in course | Course provider |
| `credential` | `certificate` | Completed course/achievement | Issuer |

**Key distinction:** 
- `membership_request` is a **relationship** (source signs, "I want to join")
- `membership` is a **credential** (admin signs, "You are a member")

### 1.5 The Signing Rule: Who Signs What

**Critical distinction:**

| Kind | Signed By | Examples |
|------|-----------|----------|
| `relationship` | Source entity | Follow, block, membership_request |
| `interaction` | Source entity | React, reply, bookmark, progress |
| `credential` | Third party (NOT source) | Membership, subscription, enrollment, certificate |

**The rule:** If the link is an attestation from someone other than the source, it's a `credential`. If the source is making a claim about themselves, it's a `relationship` or `interaction`.

**Examples:**
- Alice follows Bob → `relationship` (Alice signs)
- Alice likes a post → `interaction` (Alice signs)
- Alice requests to join Group → `relationship/membership_request` (Alice signs)
- Alice is confirmed as Group member → `credential/membership` (Group admin signs)
- Alice is subscribed to Newsletter → `credential/subscription` (payment attestor signs)
- Alice enrolled in Course → `credential/enrollment` (school signs)
- Alice completed Course → `credential/certificate` (school signs)

**The test:** Ask "who is making the claim?"
- If source claims something about themselves → relationship or interaction
- If someone else attests something about source → credential

---

## 2. Identity Model

### 2.1 Three Layers

```
┌─────────────────────────────────────────┐
│           IDENTIFIER LAYER               │
│  Stable ID (portable across providers)   │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│         AUTHENTICATION LAYER             │
│  How you prove identity                  │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│            CUSTODY LAYER                 │
│  Who holds the signing keys              │
└─────────────────────────────────────────┘
```

### 2.2 Identifier Generation

**Email-derived (recommended for easy onboarding):**
```
id = "ent:" + base58(sha256(lowercase(email) + "fabric.v2"))
```

**Key-derived (for anonymous/sovereign):**
```
id = "ent:" + base58(sha256(public_key))
```

### 2.3 Custody Modes

| Mode | Keys Held By | Recovery | UX |
|------|--------------|----------|-----|
| `provider` | Service provider | Email/password reset | Easy |
| `self` | User's device | Seed phrase / social recovery | Sovereign |
| `threshold` | Split across parties | M-of-N recovery | Balanced |

### 2.4 Key Rotation (Critical for Custody Migration)

When migrating custody or rotating keys, publish a key rotation credential:

```json
{
  "type": "link",
  "kind": "credential",
  "source": "ent:alice",
  "target": "ent:alice",
  "data": {
    "subkind": "key_rotation",
    "new_signing_key": "ed25519:newkey...",
    "new_encryption_key": "x25519:newenckey...",
    "revoked_keys": ["ed25519:oldkey..."],
    "effective_from": "2026-05-01T00:00:00Z",
    "reason": "custody_migration"
  },
  "sig": "ed25519:oldkey..."
}
```

**Verification Rules:**

1. Rotation MUST be signed by a currently-valid key
2. After `effective_from`, clients MUST reject signatures from `revoked_keys`
3. Content with `created` timestamp after `effective_from` MUST use the new key
4. Clients SHOULD warn users about content signed by revoked keys

**This solves the "permanent trust shadow" problem:** When Alice migrates from Provider A to self-custody, she rotates keys. Provider A can no longer impersonate her for future content.

### 2.5 Identity Portability

To move from Provider A to Provider B:

```
1. Export signed identity bundle from A (entity + key material)
2. Generate new keys at B (or import if self-custody)
3. Publish key_rotation credential (old key signs, points to new key)
4. Import followers/following lists to B
5. Announce migration (optional: publish redirect notice)
```

---

## 3. Access Control & Encryption

### 3.1 Access Types

Every content has an `access` field:

```json
// Public - anyone can read
{"access": {"type": "public"}}

// Unlisted - has URL but not in feeds
{"access": {"type": "unlisted"}}

// Private - specific users only (encrypted)
{"access": {"type": "private", "allow": ["ent:bob", "ent:carol"]}}

// Group - group members only (encrypted)
{"access": {"type": "group", "group": "ent:rust-devs"}}

// Paid - subscribers of a tier (encrypted)
{"access": {"type": "paid", "entity": "ent:newsletter", "min_tier": "premium"}}
```

### 3.2 Encryption Model

**For private content (specific users):**

```json
{
  "type": "content",
  "kind": "post",
  "access": {"type": "private", "allow": ["ent:bob"]},
  "encrypted": {
    "ciphertext": "base64...",
    "nonce": "base64...",
    "algorithm": "xchacha20-poly1305",
    "wrapped_keys": {
      "ent:bob": "base64..."
    }
  }
}
```

**Process:**
1. Generate random content key K (32 bytes)
2. Encrypt content with K using XChaCha20-Poly1305
3. For each recipient, wrap K with their X25519 public key
4. Store wrapped keys in `wrapped_keys` map

### 3.3 Group Encryption and History Policy

**The scalability problem:** Re-wrapping content keys for every new member is expensive at scale. A group with 10,000 posts and monthly joins means 10,000 re-wrap operations monthly.

**Solution:** Groups choose a `history_policy`:

```json
{
  "type": "entity",
  "kind": "group",
  "data": {
    "history_policy": "join_date_forward",  // DEFAULT
    ...
  }
}
```

| Policy | Behavior | Use Case |
|--------|----------|----------|
| `join_date_forward` | New members only see content posted AFTER they joined | Social communities, chat groups (default, scalable) |
| `full_access` | New members can see ALL historical content | Knowledge bases, team workspaces (expensive, small groups) |

#### 3.3.1 Join-Date-Forward (Default)

When a new member joins:
1. Admin creates new key package version including new member
2. New content is encrypted to new group key
3. Old content remains encrypted to old group keys (new member can't read)
4. New member sees a "joined on [date]" marker in the timeline

This is how Signal groups work. It's:
- Scalable (no re-wrapping)
- Privacy-preserving (new members don't see old conversations)
- Simple to implement

```json
{
  "type": "content",
  "kind": "post",
  "access": {"type": "group", "group": "ent:rust-devs"},
  "encrypted": {
    "ciphertext": "base64...",
    "group_key_version": 3  // Only members with v3+ key can decrypt
  }
}
```

#### 3.3.2 Full Access (Opt-In)

For groups that need historical access (team knowledge bases, etc.):

```json
{
  "type": "entity",
  "kind": "group",
  "data": {
    "history_policy": "full_access"
  }
}
```

When a new member joins:
1. Admin creates new key package version (v4) including new member
2. Admin (or key server) re-wraps historical content keys to v4
3. New member can decrypt all historical content

**Scaling considerations:**
- Only use for small groups (<100 members, <1,000 posts)
- Consider lazy re-wrapping (re-wrap on access, not on join)
- Use a key server for large groups

**Content Key Registry (for full_access groups):**

```json
{
  "type": "content_key_registry",
  "group": "ent:rust-devs",
  "keys": {
    "ckey:cnt-abc123": {
      "wrapped_to_group_key_v3": "base64...",
      "wrapped_to_group_key_v4": "base64..."
    }
  }
}
```

#### 3.3.3 Group Key Package

```json
{
  "type": "key_package",
  "id": "kpkg:rust-devs-v3",
  "group": "ent:rust-devs",
  "version": 3,
  "created": "2026-04-23T12:00:00Z",
  "wrapped_group_key": {
    "ent:alice": "base64...",
    "ent:bob": "base64...",
    "ent:carol": "base64..."
  },
  "sig": "ed25519:admin..."
}
```

### 3.4 Paid Content Encryption

Same model as group encryption, but keys are released on payment verification.

```json
{
  "type": "content",
  "kind": "post",
  "schema": "blog.article.v1",
  "access": {
    "type": "paid",
    "entity": "ent:alice-newsletter",
    "min_tier": "premium"
  },
  "encrypted": {
    "ciphertext": "base64...",
    "content_key_id": "ckey:cnt-premium-article",
    "tier_key_ref": "tkey:alice-newsletter-premium-v2"
  }
}
```

---

## 4. Payment Attestation

### 4.1 The Problem

The protocol doesn't process payments. But it needs to verify that payment occurred.

### 4.2 Payment Attestation Service Pattern

```
┌─────────────┐     webhook      ┌─────────────────────┐
│   Stripe    │ ───────────────> │  Payment Attestation │
│  (or other) │                  │       Service        │
└─────────────┘                  └──────────┬──────────┘
                                            │
                                            │ signs & publishes
                                            ▼
                                 ┌─────────────────────┐
                                 │  Subscription Link   │
                                 │  (credential)        │
                                 └─────────────────────┘
```

### 4.3 Subscription Credential

```json
{
  "type": "link",
  "kind": "credential",
  "source": "ent:bob",
  "target": "ent:alice-newsletter",
  "seq": 22222,
  "created": "2026-04-01T00:00:00Z",
  "data": {
    "subkind": "subscription",
    "tier": "premium",
    "started": "2026-04-01T00:00:00Z",
    "expires": "2026-05-01T00:00:00Z",
    "payment_ref": "stripe:sub_abc123",
    "attestor": "ent:stripe-bridge"
  },
  "sig": "ed25519:stripe-bridge-key..."
}
```

### 4.4 Verification Flow

1. User requests paid content
2. Relay/client checks for valid subscription credential
3. Credential must be:
   - Signed by trusted attestor (publication trusts specific attestors)
   - Not expired (`expires` > now)
   - Correct tier (`tier` >= `min_tier`)
4. If valid, release content key to user

### 4.5 Attestation Service Implementation

```python
# Pseudocode for payment attestation service

@webhook("/stripe")
def handle_stripe_webhook(event):
    if event.type == "customer.subscription.created":
        # Look up FABRIC identity from Stripe customer email
        fabric_id = lookup_fabric_id(event.customer.email)
        publication = lookup_publication(event.subscription.product)
        
        # Create and sign subscription credential
        credential = {
            "type": "link",
            "kind": "credential",
            "source": fabric_id,
            "target": publication,
            "data": {
                "subkind": "subscription",
                "tier": get_tier(event.subscription.price),
                "started": event.subscription.start_date,
                "expires": event.subscription.current_period_end,
                "payment_ref": f"stripe:{event.subscription.id}",
                "attestor": MY_FABRIC_ID,
                "attestation_type": "third_party"
            }
        }
        credential["sig"] = sign(credential, MY_PRIVATE_KEY)
        
        # Publish to user's relay
        publish_to_relay(credential, fabric_id)
```

### 4.6 Self-Attestation Fallback (Bootstrap Mode)

**Problem:** Early adopters need attestors, but attestors need users. Bootstrapping is hard.

**Solution:** Publications can self-attest subscriptions with explicit marking:

```json
{
  "type": "link",
  "kind": "credential",
  "source": "ent:subscriber",
  "target": "ent:my-publication",
  "data": {
    "subkind": "subscription",
    "tier": "premium",
    "expires": "2026-05-01T00:00:00Z",
    "attestor": "ent:my-publication",
    "attestation_type": "self"
  },
  "sig": "ed25519:publication-key..."
}
```

**Key field:** `attestation_type`:
- `third_party`: Signed by independent attestor (cryptographically verifiable)
- `self`: Signed by publication itself (trust-based, not independently verifiable)

**Client behavior:**
- `third_party`: Show normal subscription status
- `self`: Show "Subscription verified by publisher" with subtle indicator
- Missing: Treat as `self` for backward compatibility

**Use cases:**
- Early-stage publications without attestor integration
- Small creators using manual subscription management
- Testing and development

**Trust model:** Self-attestation is trust-based. The publication claims the user is subscribed. Clients can:
- Always accept (trust publications)
- Warn users (show "not independently verified")
- Require third-party (strict mode for high-value content)

### 4.7 Tier Key Architecture

**Problem:** How does a verified subscriber get the decryption key for paid content?

**Solution:** Tier keys are held by the publication and released on credential verification.

```
┌─────────────────┐
│   Publication   │
│  (holds tier    │
│   keys)         │
└────────┬────────┘
         │
         │ 1. Subscriber presents credential
         │ 2. Publication verifies credential
         │ 3. Publication wraps content key to subscriber's key
         ▼
┌─────────────────┐
│   Subscriber    │
│  (receives      │
│   wrapped key)  │
└─────────────────┘
```

**Tier Key Package:**

```json
{
  "type": "tier_key_package",
  "id": "tkey:alice-newsletter-premium-v2",
  "publication": "ent:alice-newsletter",
  "tier": "premium",
  "version": 2,
  "created": "2026-04-01T00:00:00Z",
  "wrapped_tier_key": {
    "ent:subscriber1": "base64...",
    "ent:subscriber2": "base64..."
  },
  "sig": "ed25519:publication-key..."
}
```

**Content key release flow:**

1. Subscriber requests paid content
2. Client presents subscription credential to publication (or its relay)
3. Publication verifies:
   - Credential is valid (signed by trusted attestor or self)
   - Credential is not expired
   - Tier matches or exceeds content's `min_tier`
4. Publication wraps content key to subscriber's public key
5. Subscriber decrypts content

**Alternative: Lazy key wrapping**

For scalability, instead of pre-wrapping to all subscribers:

1. Store tier key encrypted only to publication
2. On valid credential presentation, wrap content key on-demand
3. Cache wrapped keys for repeat access

This trades latency for storage efficiency.

---

## 5. Threading Model

### 5.1 Thread Structure

Threads use `reply_to` for structure and `thread_root` for efficient querying:

```json
{
  "type": "content",
  "kind": "post",
  "schema": "social.post.v1",
  "data": {
    "text": "Great point!",
    "reply_to": "cnt:parent123",
    "thread_root": "cnt:original123"
  }
}
```

**Rules:**
- `reply_to`: Direct parent (for tree structure)
- `thread_root`: Original post that started the thread (for queries)
- If `reply_to` is null, `thread_root` should also be null (it's a root post)

### 5.2 Thread Query

```
GET /content?thread_root=cnt:original123&sort=chronological
```

Returns all content in the thread. Relay indexes `thread_root` for efficient lookup.

### 5.3 Thread Construction

```
cnt:original123 (root, thread_root: null)
├── cnt:reply1 (reply_to: original123, thread_root: original123)
│   ├── cnt:reply3 (reply_to: reply1, thread_root: original123)
│   └── cnt:reply4 (reply_to: reply1, thread_root: original123)
└── cnt:reply2 (reply_to: original123, thread_root: original123)
```

Clients can reconstruct the tree from `reply_to` relationships. The `thread_root` just makes the query efficient.

---

## 6. Links: Append-Only with Tombstones

### 6.1 Immutability Principle

Links are append-only. You cannot edit or delete a link. Instead, you publish a new link that tombstones the old one.

### 6.2 Tombstone Pattern

**Follow:**
```json
{"type": "link", "kind": "relationship", "id": "lnk:123", 
 "source": "ent:alice", "target": "ent:bob", 
 "data": {"subkind": "follow"}}
```

**Unfollow (tombstones the follow):**
```json
{"type": "link", "kind": "relationship", "id": "lnk:456", 
 "source": "ent:alice", "target": "ent:bob", 
 "data": {"subkind": "unfollow", "tombstones": "lnk:123"}}
```

### 6.3 Batch Tombstone Pattern

For cases where you want to resolve ALL prior links of a subkind (not just a specific one):

```json
{
  "type": "link",
  "kind": "relationship",
  "id": "lnk:789",
  "source": "ent:alice",
  "target": "ent:bob",
  "data": {
    "subkind": "unfollow",
    "tombstones_all": "relationship/follow"
  }
}
```

**`tombstones_all` format:** `{kind}/{subkind}`

This says: "Resolve ALL prior follow links between this source and target."

**Benefits:**
- Enables garbage collection (tombstoned links can be discarded)
- Reduces link accumulation over time
- Simplifies state computation (don't need to know specific link IDs)

**Use cases:**
- User unfollows after many follow/unfollow cycles
- Clear all reactions of a type
- Reset relationship state

### 6.4 Computing Current State

```python
def get_current_relationships(source, target):
    links = fetch_links(source=source, target=target, kind="relationship")
    links = sorted(links, key=lambda l: l.created)  # Chronological order
    
    # Build tombstone set
    tombstoned = set()
    tombstoned_all = {}  # {kind/subkind: timestamp}
    
    for link in links:
        if "tombstones" in link.data:
            tombstoned.add(link.data["tombstones"])
        if "tombstones_all" in link.data:
            tombstoned_all[link.data["tombstones_all"]] = link.created
    
    # Return non-tombstoned links
    result = []
    for link in links:
        # Skip if specifically tombstoned
        if link.id in tombstoned:
            continue
        # Skip if batch-tombstoned (and created before the tombstone)
        key = f"{link.kind}/{link.data.get('subkind', '')}"
        if key in tombstoned_all and link.created < tombstoned_all[key]:
            continue
        result.append(link)
    
    return result
```

### 6.5 Why Append-Only?

1. **Audit trail**: Can always see history of relationship changes
2. **Consistency**: No race conditions on updates
3. **Replication**: Append-only is easy to sync
4. **Signatures**: Each state change is independently signed

---

## 7. Schema System

### 7.1 Schema References

Content references a versioned schema:

```json
{
  "type": "content",
  "kind": "structured",
  "schema": "lms.course.v1",
  "data": { ... }
}
```

### 7.2 The `_display` Convention

Every content SHOULD include a `_display` object for fallback rendering:

```json
{
  "data": {
    "_display": {
      "title": "Introduction to Rust",
      "summary": "A comprehensive course on Rust programming",
      "thumbnail": "cid:bafybeif..."
    },
    // Schema-specific fields
    "modules": [...],
    "duration_hours": 20
  }
}
```

**Rules:**
- `_display.title`: Short title (optional, null if not applicable)
- `_display.summary`: 1-2 sentence description (required)
- `_display.thumbnail`: CID of preview image (optional)

**Client behavior:**
- If schema is known: Render with full schema support
- If schema is unknown: Render `_display` as a preview card
- If `_display` is missing: Show "Content requires [schema] support"

### 7.3 Core Schemas

**social.post.v1**
```json
{
  "text": "string, max 10000 chars",
  "media": "[{cid, mime, alt}]",
  "reply_to": "content id or null",
  "thread_root": "content id or null",
  "mentions": "[entity ids]",
  "tags": "[strings]"
}
```

**blog.article.v1**
```json
{
  "title": "string, required",
  "subtitle": "string",
  "body": "string (markdown)",
  "cover": "{cid, mime, alt}",
  "reading_time_minutes": "number",
  "canonical_url": "string"
}
```

**lms.course.v1**
```json
{
  "title": "string, required",
  "description": "string",
  "modules": [{
    "id": "string",
    "title": "string",
    "lessons": ["content ids"]
  }],
  "prerequisites": "[content ids]",
  "estimated_hours": "number"
}
```

**lms.lesson.v1**
```json
{
  "title": "string, required",
  "content": "string (markdown)",
  "video": "{cid, duration_seconds}",
  "quiz": [{
    "question": "string",
    "options": ["strings"],
    "correct_index": "number"
  }]
}
```

**media.image.v1**
```json
{
  "file": "{cid, mime, width, height, size_bytes}",
  "alt": "string",
  "caption": "string"
}
```

**media.video.v1**
```json
{
  "file": "{cid, mime, width, height, duration_seconds, size_bytes}",
  "thumbnail": "{cid, mime}",
  "captions": "[{lang, cid}]",
  "chapters": "[{time_seconds, title}]"
}
```

---

## 8. Sync Protocol

### 8.1 Relay Sequence Numbers

Every object stored by a relay gets a monotonically increasing sequence number:

```json
{
  "type": "content",
  "id": "cnt:abc123",
  "seq": 67890,
  ...
}
```

The `seq` is assigned by the relay, not the author. Different relays may assign different `seq` values to the same object.

### 8.2 Cursor-Based Sync

**Request:**
```
GET /content?author=ent:alice&after_seq=67800&limit=100
```

**Response:**
```json
{
  "items": [...],
  "cursor": "seq:67890",
  "has_more": false
}
```

**Next sync:**
```
GET /content?author=ent:alice&after_seq=67890&limit=100
```

### 8.3 Why Sequence Numbers?

1. **No clock sync**: Doesn't depend on client/server time agreement
2. **Monotonic**: Always increases, easy to track "what's new"
3. **Efficient**: Single integer comparison, indexed lookup
4. **Relay-local**: Each relay has its own sequence space

### 8.4 Cross-Relay Sync and Merge Strategy

**Key principle:** Sequence numbers are relay-local. Different relays assign different `seq` values to the same object.

When syncing from multiple relays, track `last_seq` per relay:

```json
{
  "sync_state": {
    "relay.example.com": {"last_seq": 67890},
    "relay.other.com": {"last_seq": 12345}
  }
}
```

**Client responsibilities:**

1. **Maintain per-relay cursors**: Each relay has its own sequence space
2. **Deduplicate by object ID**: Same object from different relays has same `id`
3. **Merge streams**: Combine objects from multiple relays into unified view
4. **Handle conflicts**: Same object may arrive with different `seq` from different relays (use object `id` as canonical identifier)

**Example merge logic:**

```python
def sync_from_relays(relays, sync_state):
    all_objects = {}
    
    for relay in relays:
        last_seq = sync_state.get(relay, 0)
        response = fetch(relay, after_seq=last_seq)
        
        for obj in response.items:
            # Deduplicate by object ID with conflict resolution
            if obj.id not in all_objects:
                all_objects[obj.id] = obj
            else:
                # Conflict: same ID from different relays
                all_objects[obj.id] = resolve_conflict(all_objects[obj.id], obj)
        
        # Update per-relay cursor
        sync_state[relay] = response.cursor
    
    return list(all_objects.values())
```

### 8.5 Conflict Resolution Rules

When the same object ID arrives from multiple relays with different content:

| Object Type | Resolution Rule |
|-------------|-----------------|
| **Entity** | Highest `version` wins |
| **Content** | Latest `created` timestamp wins; if equal, first-seen wins |
| **Link** | All versions kept (append-only, no conflict) |

**Entity conflict resolution:**

```python
def resolve_entity_conflict(existing, incoming):
    if incoming.version > existing.version:
        return incoming
    elif incoming.version == existing.version:
        # Same version but different content = data corruption or malicious
        # Keep existing, log warning
        log.warn(f"Entity {existing.id} version conflict")
        return existing
    else:
        return existing
```

**Content conflict resolution:**

```python
def resolve_content_conflict(existing, incoming):
    # Prefer later timestamp
    if incoming.created > existing.created:
        return incoming
    elif incoming.created == existing.created:
        # Tiebreaker: compare hashes, keep lower (deterministic)
        if hash(incoming) < hash(existing):
            return incoming
        return existing
    else:
        return existing
```

**Link conflict resolution:**

Links are append-only, so there's no true conflict. If the same link ID appears with different content, treat as data corruption and keep first-seen.

### 8.6 Why Relay-Local Sequences?

1. **Relay independence**: Relays don't need to coordinate
2. **No global ordering**: There is no single "true" order of events across the network
3. **Client choice**: Clients choose which relays to trust and how to merge
4. **Partition tolerance**: Network splits don't break sync

**Tradeoff:** Feeds are relay-relative. Different clients syncing from different relay sets may see different orderings. This is intentional — there's no global truth in a decentralized system.

### 8.7 Real-Time Subscriptions

```json
// WebSocket subscribe
{
  "op": "subscribe",
  "filters": [
    {"type": "content", "authors": ["ent:alice", "ent:bob"]},
    {"type": "link", "targets": ["ent:me"], "kinds": ["relationship", "interaction"]}
  ],
  "after_seq": 67890
}

// Server push
{
  "op": "event",
  "object": { ... },
  "seq": 67891
}
```

---

## 9. Groups

### 9.1 Group Entity

```json
{
  "type": "entity",
  "id": "ent:rust-devs",
  "kind": "group",
  "data": {
    "name": "Rust Developers",
    "description": "A community for Rust programmers",
    "avatar": "cid:bafybeif...",
    "visibility": "public",
    "join_policy": "open",
    "posting_policy": "members"
  },
  "keys": {
    "signing": "ed25519:...",
    "encryption": "x25519:..."
  }
}
```

**Visibility:**
- `public`: Anyone can see group and content
- `private`: Only members can see

**Join Policy:**
- `open`: Anyone can join
- `approval`: Requires admin approval
- `invite`: Invite only

**Posting Policy:**
- `members`: Any member can post
- `mods`: Only mods and admins
- `admins`: Only admins

### 9.2 Membership Flow

**Step 1: User requests to join (relationship)**

```json
{
  "type": "link",
  "kind": "relationship",
  "source": "ent:alice",
  "target": "ent:rust-devs",
  "data": {
    "subkind": "membership_request"
  },
  "sig": "ed25519:alice-key..."
}
```

**Step 2: Admin confirms membership (credential)**

```json
{
  "type": "link",
  "kind": "credential",
  "source": "ent:alice",
  "target": "ent:rust-devs",
  "data": {
    "subkind": "membership",
    "role": "member",
    "granted_by": "ent:admin-bob",
    "granted_at": "2026-04-23T12:00:00Z"
  },
  "sig": "ed25519:admin-bob-key..."
}
```

**Note:** The membership credential is signed by the admin (or group key), not by Alice. This is what makes it a credential — someone else attests that Alice is a member.

**For open groups (`join_policy: open`):**
- Skip the request step
- Admin (or automated system) immediately issues membership credential

**Roles:**
- `admin`: Full control, can issue memberships
- `mod`: Moderate content, can approve membership requests
- `member`: Post and read
- `readonly`: Read only

### 9.3 Posting to Groups

```json
{
  "type": "content",
  "kind": "post",
  "author": "ent:alice",
  "context": "ent:rust-devs",
  "access": {"type": "group", "group": "ent:rust-devs"},
  "data": {
    "text": "Check out this crate!"
  }
}
```

The `context` field indicates where the content "lives." The `access` field controls who can read it.

### 9.4 Context vs Access: When They Differ

**`context`**: Where content belongs (its "home")
**`access`**: Who can read it

Usually they're the same, but they can differ:

| context | access | Meaning |
|---------|--------|---------|
| `ent:group` | `{type: group, group: ent:group}` | Normal group post (most common) |
| `ent:group` | `{type: public}` | Announcement: posted to group, visible to everyone |
| `null` | `{type: group, group: ent:group}` | Personal post encrypted to group (sharing with specific audience) |
| `null` | `{type: private, allow: [...]}` | DM to specific users |

**Query implications:**

- `GET /content?context=ent:group` → All posts "in" the group (regardless of access)
- `GET /content?access.group=ent:group` → All posts readable by group members

**Why separate?**

1. **Announcements**: Post to your group feed but make it public for visibility
2. **Cross-posting**: Same content in your feed AND a group
3. **Selective sharing**: Personal content encrypted to a specific group's members

---

## 10. API Reference

### 10.1 Entities

```
POST   /entities                    Create entity
GET    /entities/{id}               Get entity
PATCH  /entities/{id}               Update entity data
GET    /entities/{id}/keys          Get current public keys
GET    /entities/{id}/key-history   Get key rotation history
```

### 10.2 Content

```
POST   /content                     Create content
GET    /content/{id}                Get content
GET    /content?author={id}         List by author
GET    /content?thread_root={id}    Get thread
GET    /content?context={id}        Get group content
GET    /content?after_seq={n}       Sync with cursor
```

### 10.3 Links

```
POST   /links                       Create link
GET    /links/{id}                  Get link
GET    /links?source={id}           Links from entity
GET    /links?target={id}           Links to entity
GET    /links?source={id}&target={id}&kind={kind}  Specific relationship
```

### 10.4 Keys (for encrypted content)

```
GET    /keys/group/{group_id}                    Get current group key package
GET    /keys/group/{group_id}/history            Get all key package versions
GET    /keys/content/{content_key_id}            Get wrapped content key
POST   /keys/group/{group_id}/rekey              Trigger group rekey (admin only)
```

### 10.5 Feeds

```
GET    /feed/home?after_seq={n}     Home feed (from follows)
GET    /feed/entity/{id}            Entity's public content
GET    /feed/group/{id}             Group feed (members only)
GET    /feed/explore                Discovery feed
```

---

## 11. Security Considerations

### 11.1 Key Rotation

- Rotate keys immediately when leaving provider custody
- Clients MUST check key rotation history before trusting signatures
- Content signed by revoked keys after `effective_from` is invalid

### 11.2 Group Key Management

- Rotate group key when members leave (forward secrecy)
- Re-wrap content keys when members join (historical access)
- Consider key server for large groups (performance)

### 11.3 Payment Security

- Only trust attestors explicitly listed by the publication
- Verify attestation signatures
- Check expiration on every access

### 11.4 Content Verification

- Always verify signatures before displaying content
- Verify `author` matches signing key's entity
- Check key rotation history for key validity at `created` time

---

## 12. Implementation Checklist

### 12.1 Minimal Implementation

- [ ] Entity CRUD
- [ ] Content CRUD (post kind only)
- [ ] Link CRUD (relationship kind only)
- [ ] Signature verification
- [ ] Sequence-based sync
- [ ] Basic feed (reverse chronological from follows)

### 12.2 Full Implementation

- [ ] All entity kinds
- [ ] All content kinds with schemas
- [ ] All link kinds and subkinds
- [ ] Key rotation
- [ ] Group encryption with historical access
- [ ] Payment attestation
- [ ] Thread queries
- [ ] WebSocket subscriptions
- [ ] `_display` fallback rendering

---

## 13. Examples

### 13.1 Simple Blog

```json
// Publication entity
{"type": "entity", "kind": "org", "id": "ent:alice-blog", "data": {"name": "Alice's Blog"}}

// Article
{"type": "content", "kind": "post", "schema": "blog.article.v1", 
 "author": "ent:alice-blog", "access": {"type": "public"},
 "data": {"_display": {"title": "My First Post", "summary": "..."}, "title": "My First Post", "body": "..."}}

// Reader follows
{"type": "link", "kind": "relationship", "source": "ent:bob", "target": "ent:alice-blog",
 "data": {"subkind": "follow"}}
```

### 13.2 Private Group

```json
// Group entity
{"type": "entity", "kind": "group", "id": "ent:secret-club",
 "data": {"name": "Secret Club", "visibility": "private", "join_policy": "invite"}}

// Membership (credential signed by admin)
{"type": "link", "kind": "credential", "source": "ent:alice", "target": "ent:secret-club",
 "data": {"subkind": "membership", "role": "admin", "granted_by": "ent:founder"},
 "sig": "ed25519:founder-key..."}

// Encrypted post
{"type": "content", "kind": "post", "author": "ent:alice", "context": "ent:secret-club",
 "access": {"type": "group", "group": "ent:secret-club"},
 "encrypted": {"ciphertext": "...", "content_key_id": "ckey:123", "group_key_version": 1}}
```

### 13.3 Paid Newsletter

```json
// Publication with tiers
{"type": "entity", "kind": "org", "id": "ent:premium-news",
 "data": {"name": "Premium Newsletter", "tiers": [
   {"id": "free", "price": 0},
   {"id": "premium", "price": {"amount": 10, "currency": "USD", "period": "month"}}
 ]}}

// Subscription (signed by payment attestor)
{"type": "link", "kind": "credential", "source": "ent:bob", "target": "ent:premium-news",
 "data": {"subkind": "subscription", "tier": "premium", "expires": "2026-05-01T00:00:00Z"},
 "sig": "ed25519:attestor-key..."}

// Paid article
{"type": "content", "kind": "post", "schema": "blog.article.v1",
 "author": "ent:premium-news", 
 "access": {"type": "paid", "entity": "ent:premium-news", "min_tier": "premium"},
 "encrypted": {"ciphertext": "...", "tier_key_ref": "tkey:premium-news-premium-v1"}}
```

### 13.4 Learning Platform

```json
// Course
{"type": "content", "kind": "structured", "schema": "lms.course.v1",
 "id": "cnt:rust-course", "author": "ent:coding-school",
 "data": {"_display": {"title": "Learn Rust", "summary": "..."}, 
         "title": "Learn Rust", "modules": [{"id": "m1", "title": "Basics", "lessons": ["cnt:lesson1"]}]}}

// Lesson
{"type": "content", "kind": "structured", "schema": "lms.lesson.v1",
 "id": "cnt:lesson1", "author": "ent:coding-school",
 "data": {"title": "Hello World", "content": "...", "video": {"cid": "..."}}}

// Enrollment
{"type": "link", "kind": "credential", "source": "ent:student", "target": "cnt:rust-course",
 "data": {"subkind": "enrollment", "enrolled_at": "2026-04-01T00:00:00Z"}}

// Progress
{"type": "link", "kind": "interaction", "source": "ent:student", "target": "cnt:lesson1",
 "data": {"subkind": "progress", "completed": true, "completed_at": "2026-04-02T00:00:00Z"}}
```

---

## 14. Comparison

| Feature | FABRIC v2.2 | AT Protocol | Nostr | ActivityPub |
|---------|-------------|-------------|-------|-------------|
| Core primitives | 3 | Many (Lexicon) | 1 (event) | Many (AS2) |
| Email login | ✓ Native | ✓ | ✗ | Depends |
| Self-custody option | ✓ | ✗ | ✓ Required | ✗ |
| Key rotation | ✓ | Limited | ✗ | ✗ |
| Private content | ✓ Native | ✗ | ✓ (NIP-04) | Limited |
| Group encryption | ✓ + history policy | ✗ | ✗ | ✗ |
| Paid content | ✓ Native | ✗ | ✗ | ✗ |
| Custom schemas | ✓ | ✓ | ✗ | Limited |
| Efficient sync | ✓ Seq numbers | ✓ | Relays | Varies |
| Conflict resolution | ✓ Explicit | Implicit | ✗ | ✗ |
| Self-attestation | ✓ | ✗ | ✗ | ✗ |

---

## 15. Known Tradeoffs and Risks

### 15.1 Sequence Numbers Are Relay-Local

**Tradeoff:** No global ordering. Feeds are relay-relative.

**Implication:** Different clients syncing from different relay sets may see different orderings. This is intentional — decentralized systems don't have global truth.

**Mitigation:** Use `created` timestamp for display ordering. Use `seq` only for sync cursors.

### 15.2 Group Key Management at Scale

**Tradeoff:** `full_access` history policy is expensive for large groups.

**Implication:** Re-wrapping content keys on every join doesn't scale past ~1,000 posts.

**Mitigation:** Default to `join_date_forward`. Use `full_access` only for small teams/knowledge bases. Consider lazy re-wrapping or key servers for large groups.

### 15.3 Link Explosion

**Tradeoff:** Everything is a Link — follows, reactions, subscriptions, credentials, progress.

**Implication:** Links will dominate storage. A user with 1,000 follows, 10,000 reactions, and 100 subscriptions has 11,100 links.

**Mitigation:** 
- Efficient indexing on (source, kind, subkind) and (target, kind, subkind)
- `tombstones_all` for garbage collection
- Consider link compaction in implementations

### 15.4 Ambitious Scope

**Tradeoff:** Protocol supports social, blogging, groups, messaging, payments, and LMS.

**Implication:** Hard to optimize for everything. Each use case has different performance characteristics.

**Mitigation:** The 3×3 model (3 primitives, 3 kinds each) provides a narrow foundation. Implementations can optimize for specific use cases while staying protocol-compliant.

### 15.5 No Global Moderation

**Tradeoff:** Moderation is relay-level and client-level, not protocol-level.

**Implication:** Spam and abuse are handled differently by different relays. No protocol-level block list.

**Mitigation:** This is intentional. Centralized moderation is a single point of failure/censorship. Trust networks and relay reputation emerge organically.

### 15.6 Timestamp-Based Ordering Is Gameable

**Tradeoff:** Content ordering uses `created` timestamp, which is author-controlled.

**Implication:** Malicious actors can backdate or future-date content to manipulate feed position.

**Mitigation options:**
1. **Soft ordering**: Use `(created, relay_first_seen, relay_id)` tuple for deterministic ordering
2. **Trust-weighted**: Discount timestamps from low-reputation sources
3. **Relay attestation**: Relays can add `received_at` timestamp as additional signal

**Recommendation:** Implementations SHOULD record `relay_received_at` alongside author's `created`. For display:
- Primary sort: `created` (author intent)
- Tiebreaker: `relay_received_at` (objective arrival)
- Suspicion: Flag content where `created` >> `relay_received_at`

### 15.7 Credential Trust Model Needs Discovery

**Tradeoff:** Credentials (subscriptions, memberships, certificates) require trusted attestors, but there's no protocol-level attestor discovery.

**Implication:** Each application invents its own trust system. No interoperability for attestor trust.

**Current model:** Publications explicitly list trusted attestors in their entity data.

**Future needs:**
- Attestor discovery protocol (how to find attestors for a domain)
- Revocation mechanism (how to invalidate a compromised attestor)
- Reputation system (how to assess attestor trustworthiness)

**Recommendation:** For v2.2, applications SHOULD:
- Publish trusted attestors in entity data: `data.trusted_attestors: ["ent:stripe-bridge", "ent:paypal-bridge"]`
- Check attestor against this list before accepting credentials
- Fall back to self-attestation with UI warning if no attestor matches

### 15.8 Spam Resistance Is Not Specified

**Tradeoff:** The protocol has no built-in spam resistance. Anyone can publish unlimited content.

**Implication:** First real deployment = spam flood without mitigations.

**Relay-level mitigations (RECOMMENDED):**
- Rate limiting by identity (X posts per hour)
- Rate limiting by IP (defense against Sybil)
- Proof-of-work for anonymous posts
- Deposit/stake requirements for new identities

**Client-level mitigations:**
- Web of trust scoring (content from follows-of-follows ranked higher)
- Reputation decay (new accounts start with low visibility)
- Mute/block propagation (share block lists with trusted peers)

**Protocol-level options (NOT in v2.2, future consideration):**
- `proof_of_work` field on content (hashcash-style)
- `stake` field referencing locked value
- `vouched_by` field for social proof

**Recommendation:** Relays MUST implement rate limiting. Clients SHOULD implement trust scoring. Protocol-level spam resistance is deferred to v3.

### 15.9 Schema Registry Is Out of Scope

**Tradeoff:** The protocol defines `_display` for fallback rendering but no schema registry.

**Implication:** Clients can't discover new schemas. Richer interop requires some centralization.

**Current model:** Schemas are convention-based namespaces (e.g., `social.post.v1`, `lms.course.v1`).

**Recommendation:**
1. Community-maintained schema registry (like npm for schemas)
2. Schema files are JSON Schema or similar
3. Clients can fetch schema definitions for rendering hints
4. Unknown schemas fall back to `_display` (always works)

**Governance question:** Who runs the registry? Options:
- Decentralized (schemas stored on FABRIC itself)
- Federated (multiple registries, clients choose)
- Centralized (single authoritative registry)

**For v2.2:** This is out of scope. `_display` ensures graceful degradation. Schema registry is a v3 concern.

---

## 16. Summary

**Three primitives:** Entity, Content, Link

**Three kinds each:**
- Entity: user, org, group
- Content: post, media, structured
- Link: relationship, interaction, credential

**Key innovations in v2.2:**
- Email login → self-custody migration path
- Key rotation with explicit deprecation
- Encryption as access layer (public/private/group/paid)
- History policy for groups (`join_date_forward` default)
- Payment attestation with self-attestation fallback
- Tier key architecture fully specified
- Entity versioning for conflict resolution
- Membership flow: request (relationship) → confirmed (credential)
- `_display` for schema fallback
- Append-only links with tombstones (including `tombstones_all`)
- Relay sequence numbers for efficient sync
- Explicit conflict resolution rules

**What we got right:**
- Simple enough to explain in 10 minutes
- Powerful enough for blogs, social networks, groups, newsletters, LMS
- Rigorous enough to actually implement
- Honest about tradeoffs and limitations

**What we deferred to v3:**
- Protocol-level spam resistance
- Schema registry
- Attestor discovery protocol
- Trust/reputation system

---

*Protocol version: 2.2*
*Status: Draft*
*License: CC0 (Public Domain)*
