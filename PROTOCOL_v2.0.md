# FABRIC Protocol v2.0

**Federated Architecture for Broadcast, Relationships, Identity, and Content**

A minimal protocol for decentralized social applications — from blogs to learning platforms to encrypted communities.

---

## Design Goals

1. **Three primitives, infinite applications** — Entity, Content, Link cover everything
2. **Email login to self-custody** — Easy onboarding, optional sovereignty  
3. **Encryption as access layer** — Any content can be public, private, group, or paid
4. **Schema flexibility** — Posts, articles, courses, videos all fit the same model
5. **Scale-ready** — Pull-based sync, content-addressed media, efficient timestamps

---

## 1. The Three Primitives

| Primitive | Purpose | Examples |
|-----------|---------|----------|
| **Entity** | Actors with identity | Users, organizations, groups, bots |
| **Content** | Publishable data | Posts, articles, courses, videos, images |
| **Link** | Relationships | Follow, react, reply, subscribe, enroll |

That's it. Everything else is a `kind` within these primitives.

### 1.1 Entity

Any actor in the system:

```json
{
  "type": "entity",
  "id": "ent:alice",
  "kind": "user",
  "created": "2026-04-23T12:00:00Z",
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

**Entity Kinds:**
- `user` — Individual person
- `org` — Organization or company
- `group` — Community or team
- `publication` — Newsletter or blog
- `bot` — Automated agent

### 1.2 Content

Anything publishable:

```json
{
  "type": "content",
  "id": "cnt:post123",
  "kind": "post",
  "author": "ent:alice",
  "created": "2026-04-23T12:00:00Z",
  "schema": "social.post.v1",
  "data": {
    "text": "Hello, decentralized world!",
    "media": [{"cid": "bafybeig...", "mime": "image/png"}]
  },
  "access": {"type": "public"},
  "sig": "ed25519:..."
}
```

**Content Kinds:**
- `post` — Short-form social post
- `article` — Long-form writing
- `comment` — Reply to other content
- `course` — Learning course structure
- `lesson` — Individual lesson
- `media` — Image, video, audio
- `document` — PDF, file

### 1.3 Link

Relationships between entities or content:

```json
{
  "type": "link",
  "id": "lnk:follow456",
  "kind": "follow",
  "source": "ent:alice",
  "target": "ent:bob",
  "created": "2026-04-23T12:00:00Z",
  "data": {},
  "sig": "ed25519:..."
}
```

**Link Kinds:**
- `follow` — Subscribe to entity's content
- `react` — Reaction to content (like, emoji)
- `reply` — Threaded reply
- `membership` — Member of group (with role)
- `subscription` — Paid subscription
- `enrollment` — Enrolled in course

---

## 2. Identity Model

### 2.1 Three Layers

```
┌─────────────────────────────────────────┐
│           IDENTIFIER LAYER               │
│  Stable ID (portable across providers)   │
│  Examples: email-derived, key-derived    │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│         AUTHENTICATION LAYER             │
│  How you prove you're that identity      │
│  Examples: password, passkey, key sig    │
└─────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────┐
│            CUSTODY LAYER                 │
│  Who holds the signing keys              │
│  Examples: self, provider, threshold     │
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

**Custom (for organizations):**
```
id = "ent:" + chosen_name  // Must be unique at registrar
```

### 2.3 Custody Modes

| Mode | Keys Held By | Recovery | UX |
|------|--------------|----------|-----|
| **Provider** | Service provider | Email/password reset | Easy (like normal apps) |
| **Self** | User's device | Seed phrase / social recovery | Sovereign but harder |
| **Threshold** | Split across parties | M-of-N recovery | Balance of both |

### 2.4 Easy Login Flow

```
1. User enters email
2. Provider derives identifier from email
3. Provider checks if entity exists
   - If new: create entity, generate keys, store encrypted
   - If exists: authenticate via password/passkey/magic link
4. User is logged in (provider holds keys)
5. Optional: user exports keys for self-custody
```

### 2.5 Anonymous Identity

```
1. User generates keypair locally
2. User derives identifier from public key
3. User creates entity (self-custodied)
4. No email, no recovery — that's the tradeoff
```

### 2.6 Identity Portability

To move from Provider A to Provider B:

```
1. Export signed identity bundle from A
2. Bundle includes: entity data, key material (if self-custody), follower list
3. Import to Provider B
4. B verifies signatures
5. Announce migration via signed statement
```

---

## 3. Access Control

### 3.1 Access Types

Every content has an `access` field:

```json
// Public - anyone can read
{"access": {"type": "public"}}

// Private - specific users only
{"access": {"type": "private", "allow": ["ent:bob", "ent:carol"]}}

// Group - group members only
{"access": {"type": "group", "group": "ent:rust-devs"}}

// Paid - subscribers of a tier
{"access": {"type": "paid", "tier": "premium", "entity": "ent:my-publication"}}

// Unlisted - has URL but not in feeds
{"access": {"type": "unlisted"}}
```

### 3.2 Encryption for Private Content

**Private to specific users:**
```
1. Generate random content key K
2. Encrypt content with K (XChaCha20-Poly1305)
3. For each allowed user U:
   - Encrypt K with U's public encryption key
   - Store as wrapped_keys[U.id] = encrypted_K
```

```json
{
  "type": "content",
  "id": "cnt:private123",
  "kind": "post",
  "author": "ent:alice",
  "access": {"type": "private", "allow": ["ent:bob"]},
  "encrypted": {
    "ciphertext": "base64...",
    "nonce": "base64...",
    "wrapped_keys": {
      "ent:bob": "base64..."
    }
  },
  "sig": "ed25519:..."
}
```

**Group encryption:**
```
1. Group has a group key (symmetric)
2. Group key is wrapped to each member's key
3. Content key is wrapped to group key
4. On membership change: rotate group key, re-wrap to new member set
```

**Paid content:**
```
1. Content key held by payment gateway or wrapped to tier key
2. On payment verification: 
   - Gateway releases content key, OR
   - Gateway wraps content key to subscriber's key
```

### 3.3 Key Distribution

```json
{
  "type": "key_package",
  "id": "key:group-abc-v3",
  "for": "ent:rust-devs",
  "version": 3,
  "wrapped_keys": {
    "ent:alice": "base64...",
    "ent:bob": "base64...",
    "ent:carol": "base64..."
  },
  "created": "2026-04-23T12:00:00Z",
  "sig": "ed25519:..."  // Signed by group admin
}
```

---

## 4. Content Schemas

### 4.1 Schema References

Content `schema` field references a versioned schema:

```json
{
  "type": "content",
  "kind": "post",
  "schema": "social.post.v1",
  "data": { ... }
}
```

### 4.2 Core Schemas

**social.post.v1**
```json
{
  "text": "string, required, max 10000 chars",
  "media": "[{cid, mime, alt?}], optional",
  "reply_to": "content id, optional",
  "quote": "content id, optional",
  "mentions": "[entity ids], optional",
  "tags": "[strings], optional"
}
```

**blog.article.v1**
```json
{
  "title": "string, required",
  "subtitle": "string, optional",
  "body": "string (markdown), required",
  "cover": "{cid, mime, alt}, optional",
  "canonical_url": "string, optional",
  "reading_time": "number (minutes), optional"
}
```

**lms.course.v1**
```json
{
  "title": "string, required",
  "description": "string, optional",
  "modules": [{
    "id": "string",
    "title": "string",
    "lessons": ["content ids"]
  }],
  "prerequisites": "[course ids], optional",
  "certificate": "{enabled, template}, optional"
}
```

**lms.lesson.v1**
```json
{
  "title": "string, required",
  "content": "string (markdown), required",
  "video": "{cid, duration}, optional",
  "quiz": "[{question, options, correct}], optional",
  "resources": "[{title, url}], optional"
}
```

**media.video.v1**
```json
{
  "title": "string, optional",
  "description": "string, optional",
  "video": "{cid, mime, duration, width, height}",
  "thumbnail": "{cid, mime}, optional",
  "captions": "[{lang, cid}], optional",
  "chapters": "[{time, title}], optional"
}
```

### 4.3 Custom Schemas

Anyone can define schemas. Convention:
```
namespace.kind.version

Examples:
- myapp.recipe.v1
- acme.invoice.v2
- edu.flashcard.v1
```

Unknown schemas: store data as opaque JSON, don't validate.

---

## 5. Media Handling

### 5.1 Content-Addressed Storage

All media uses content identifiers (CIDs):

```json
{
  "media": [
    {
      "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
      "mime": "image/jpeg",
      "size": 245678,
      "alt": "A sunset over mountains"
    }
  ]
}
```

### 5.2 Storage Backends

CIDs can resolve via:
- IPFS: `ipfs://bafybeig...`
- HTTP: `https://cdn.example.com/bafybeig...`
- S3-compatible: provider-specific

### 5.3 Media Encryption

For private media:
```
1. Encrypt media blob with content key
2. Store encrypted blob, get CID of encrypted version
3. Include CID and wrapped key in content object
```

---

## 6. Groups and Membership

### 6.1 Group Entity

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
  },
  "sig": "ed25519:..."
}
```

**Visibility:**
- `public` — Anyone can see group and content
- `private` — Only members can see

**Join Policy:**
- `open` — Anyone can join
- `approval` — Requires admin approval
- `invite` — Invite only

**Posting Policy:**
- `members` — Any member can post
- `mods` — Only mods and admins
- `admins` — Only admins

### 6.2 Membership Link

```json
{
  "type": "link",
  "id": "lnk:membership789",
  "kind": "membership",
  "source": "ent:alice",
  "target": "ent:rust-devs",
  "data": {
    "role": "member",
    "joined": "2026-04-23T12:00:00Z"
  },
  "sig": "ed25519:..."  // Signed by group admin for invite/approval
}
```

**Roles:**
- `admin` — Full control
- `mod` — Moderate content, approve members
- `member` — Post and read
- `readonly` — Read only (for paid tiers)

### 6.3 Posting to Groups

Content can specify a group context:

```json
{
  "type": "content",
  "kind": "post",
  "author": "ent:alice",
  "context": "ent:rust-devs",
  "access": {"type": "group", "group": "ent:rust-devs"},
  "data": {"text": "Check out this crate!"},
  "sig": "ed25519:..."
}
```

---

## 7. Subscriptions and Payments

### 7.1 Subscription Tiers

Publications/creators define tiers:

```json
{
  "type": "entity",
  "id": "ent:alice-newsletter",
  "kind": "publication",
  "data": {
    "name": "Alice's Tech Insights",
    "tiers": [
      {"id": "free", "name": "Free", "price": 0},
      {"id": "supporter", "name": "Supporter", "price": {"amount": 5, "currency": "USD", "period": "month"}},
      {"id": "premium", "name": "Premium", "price": {"amount": 15, "currency": "USD", "period": "month"}}
    ]
  }
}
```

### 7.2 Subscription Link

```json
{
  "type": "link",
  "id": "lnk:sub123",
  "kind": "subscription",
  "source": "ent:bob",
  "target": "ent:alice-newsletter",
  "data": {
    "tier": "premium",
    "started": "2026-04-01T00:00:00Z",
    "expires": "2026-05-01T00:00:00Z",
    "payment_ref": "stripe:sub_abc123"
  },
  "sig": "ed25519:..."  // Signed by payment provider or publication
}
```

### 7.3 Paid Content Access

```json
{
  "type": "content",
  "kind": "article",
  "author": "ent:alice",
  "access": {
    "type": "paid",
    "entity": "ent:alice-newsletter",
    "min_tier": "supporter"
  },
  "data": { ... },
  "encrypted": {
    "ciphertext": "base64...",
    "key_ref": "key:alice-newsletter-supporter-v3"
  }
}
```

### 7.4 Payment Verification

The protocol doesn't process payments. It verifies:

1. **Subscription link exists** with valid tier
2. **Link is signed** by authorized party (payment provider or publication)
3. **Link is not expired**

Payment processing is external (Stripe, crypto, etc.).

---

## 8. Threading Model

### 8.1 Reply Chain

Replies use `reply_to` in content data:

```json
{
  "type": "content",
  "kind": "post",
  "author": "ent:bob",
  "schema": "social.post.v1",
  "data": {
    "text": "Great point!",
    "reply_to": "cnt:original123"
  }
}
```

### 8.2 Thread Construction

```
Thread = all content where reply_to chain leads to root

cnt:original123 (root)
├── cnt:reply1 (reply_to: original123)
│   ├── cnt:reply3 (reply_to: reply1)
│   └── cnt:reply4 (reply_to: reply1)
└── cnt:reply2 (reply_to: original123)
```

### 8.3 Thread Query

```
GET /content/{id}/thread?depth=10&sort=chronological
```

---

## 9. Sync Protocol

### 9.1 Timestamp-Based Sync

```
GET /entities?since=2026-04-23T00:00:00Z&limit=100
GET /content?author=ent:alice&since=2026-04-23T00:00:00Z&limit=100
GET /links?source=ent:alice&kind=follow&since=2026-04-23T00:00:00Z
```

### 9.2 Subscription Hints

For real-time updates:

```json
// WebSocket subscribe
{
  "op": "subscribe",
  "filters": [
    {"type": "content", "authors": ["ent:alice", "ent:bob"]},
    {"type": "link", "targets": ["ent:me"], "kinds": ["follow", "react"]}
  ]
}

// Server push
{
  "op": "event",
  "object": { ... }
}
```

### 9.3 Cursor Pagination

```json
{
  "items": [...],
  "cursor": "eyJsYXN0IjoiMjAyNi0wNC0yM1QxMjowMDowMFoifQ==",
  "has_more": true
}
```

---

## 10. Cryptographic Primitives

| Purpose | Algorithm |
|---------|-----------|
| Signing | Ed25519 |
| Key exchange | X25519 |
| Symmetric encryption | XChaCha20-Poly1305 |
| Hashing | SHA-256, BLAKE3 |
| Key derivation | Argon2id (passwords), HKDF (keys) |
| Content addressing | CIDv1 (multihash) |

---

## 11. Wire Formats

### 11.1 Object Envelope

```json
{
  "type": "entity|content|link",
  "id": "ent:...|cnt:...|lnk:...",
  "created": "2026-04-23T12:00:00Z",
  "updated": "2026-04-23T12:00:00Z",
  ... type-specific fields ...
  "sig": "ed25519:base64..."
}
```

### 11.2 Signature

Sign over canonical JSON (sorted keys, no whitespace):

```
sig = Ed25519.sign(private_key, sha256(canonical_json(object_without_sig)))
```

### 11.3 Content Addressing

```
object_hash = sha256(canonical_json(object_without_sig))
content_id = "cnt:" + base58(object_hash)
```

---

## 12. API Endpoints

### 12.1 Entity Operations

```
POST   /entities              Create entity
GET    /entities/{id}         Get entity
PUT    /entities/{id}         Update entity
GET    /entities/{id}/keys    Get public keys
```

### 12.2 Content Operations

```
POST   /content               Create content
GET    /content/{id}          Get content
PUT    /content/{id}          Update content
DELETE /content/{id}          Delete (soft)
GET    /content/{id}/thread   Get thread
```

### 12.3 Link Operations

```
POST   /links                 Create link
GET    /links/{id}            Get link
DELETE /links/{id}            Remove link
GET    /links?source={id}     Query links by source
GET    /links?target={id}     Query links by target
```

### 12.4 Feed Operations

```
GET    /feed/home             Home feed (from follows)
GET    /feed/entity/{id}      Entity's content
GET    /feed/group/{id}       Group feed
GET    /feed/explore          Discovery feed
```

---

## 13. Use Case Examples

### 13.1 Simple Blog

```
Entity: ent:my-blog (kind: publication)
Content: cnt:article1 (kind: article, access: public)
Content: cnt:article2 (kind: article, access: public)
Links: ent:reader1 -> ent:my-blog (kind: follow)
```

### 13.2 Social Network

```
Entities: ent:alice, ent:bob (kind: user)
Content: cnt:post1 (kind: post, author: ent:alice)
Links: ent:bob -> ent:alice (kind: follow)
Links: ent:bob -> cnt:post1 (kind: react, data: {emoji: "❤️"})
```

### 13.3 Private Group

```
Entity: ent:secret-club (kind: group, visibility: private)
Links: ent:alice -> ent:secret-club (kind: membership, role: admin)
Links: ent:bob -> ent:secret-club (kind: membership, role: member)
Content: cnt:secret-post (kind: post, context: ent:secret-club, access: {type: group})
```

### 13.4 Paid Newsletter

```
Entity: ent:premium-newsletter (kind: publication, tiers: [free, paid])
Links: ent:subscriber -> ent:premium-newsletter (kind: subscription, tier: paid)
Content: cnt:free-article (kind: article, access: public)
Content: cnt:paid-article (kind: article, access: {type: paid, min_tier: paid})
```

### 13.5 Learning Platform

```
Entity: ent:coding-school (kind: org)
Content: cnt:rust-course (kind: course, schema: lms.course.v1)
Content: cnt:lesson1 (kind: lesson, schema: lms.lesson.v1)
Links: ent:student -> cnt:rust-course (kind: enrollment)
Links: ent:student -> cnt:lesson1 (kind: progress, data: {completed: true})
```

### 13.6 Anonymous Posting

```
Entity: ent:anon123 (kind: user, custody: self, no email)
Content: cnt:anon-post (kind: post, author: ent:anon123)
// No recovery possible - sovereign and ephemeral
```

---

## 14. Comparison

| Feature | FABRIC v2 | FABRIC v1 | AT Protocol | Nostr |
|---------|-----------|-----------|-------------|-------|
| Primitives | 3 | 7 | Many (Lexicon) | 1 (event) |
| Email login | ✓ Native | ✗ | ✓ | ✗ |
| Self-custody | ✓ Optional | ✓ Required | ✗ | ✓ Required |
| Private content | ✓ Native | ✓ | ✗ | ✓ (NIP-04) |
| Groups | ✓ Native | ✓ | ✓ | ✗ |
| Paid content | ✓ Native | ✗ | ✗ | ✗ |
| Custom schemas | ✓ | ✗ | ✓ | ✗ |
| LMS support | ✓ | ✗ | ✗ | ✗ |

---

## 15. Migration from v1

| FABRIC v1 | FABRIC v2 |
|-----------|-----------|
| Identity | Entity (kind: user) |
| Post | Content (kind: post) |
| Edge | Link |
| Reaction | Link (kind: react) |
| Message | Content (kind: message, access: private) |
| Label | Link (kind: label) or Content (kind: label) |
| View | Client-side computation |

---

## 16. Summary

**Three primitives:**
1. **Entity** — Who (users, orgs, groups)
2. **Content** — What (posts, articles, courses)
3. **Link** — How they relate (follow, react, subscribe)

**Key innovations:**
- Email login with optional self-custody
- Encryption as access layer, not content type
- Flexible schemas for any content type
- Native support for groups, payments, LMS

**What we cut:**
- HLC (regular timestamps are fine for 99% of uses)
- Separate View primitive (client-computed)
- Complex timestamp sync (cursor-based is simpler)

**Result:** A protocol simple enough to understand in an hour, powerful enough to build any social application.

---

*Protocol version: 2.0*
*Status: Draft*
*License: CC0 (Public Domain)*
