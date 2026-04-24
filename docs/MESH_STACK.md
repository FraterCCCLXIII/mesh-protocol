# MESH Protocol - Complete Stack Architecture

## Overview

A complete MESH network requires multiple independent services working together. This document outlines all required components, their responsibilities, and implementation priorities.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT APPLICATIONS                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │
│  │  Web App    │  │ Mobile App  │  │ Desktop App │  │   Bot SDK   │                │
│  │  (Vite)     │  │ (React Nat.)│  │  (Electron) │  │  (Python)   │                │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                │
│         │                │                │                │                        │
│         └────────────────┴────────────────┴────────────────┘                        │
│                                    │                                                 │
│                                    ▼                                                 │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                              GATEWAY LAYER                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                         API Gateway / Load Balancer                          │   │
│  │                    (Rate limiting, Auth proxy, Caching)                      │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                                 │
│         ┌──────────────────────────┼──────────────────────────┐                     │
│         ▼                          ▼                          ▼                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                              CORE SERVICES                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                     │
│  │  RELAY NODE     │  │ IDENTITY VAULT  │  │    INDEXER      │                     │
│  │                 │  │                 │  │                 │                     │
│  │ • Entity CRUD   │  │ • Key storage   │  │ • Entity search │                     │
│  │ • Content CRUD  │  │ • Email login   │  │ • Relay discovery│                    │
│  │ • Link CRUD     │  │ • Key recovery  │  │ • Social graph  │                     │
│  │ • Federation    │  │ • Device auth   │  │ • Full-text     │                     │
│  │ • WebSocket     │  │ • OAuth bridge  │  │ • Trending      │                     │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘                     │
│           │                    │                    │                               │
│           └────────────────────┴────────────────────┘                               │
│                                │                                                     │
│         ┌──────────────────────┼──────────────────────────┐                         │
│         ▼                      ▼                          ▼                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                           EXTENSION SERVICES                                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────┐ │
│  │   MEDIA CDN     │  │  NOTIFICATION   │  │   MODERATION    │  │   PAYMENTS    │ │
│  │                 │  │    SERVICE      │  │    SERVICE      │  │   (Stripe)    │ │
│  │ • Image upload  │  │ • Push notifs   │  │ • Attestations  │  │ • Subs mgmt   │ │
│  │ • Video transc. │  │ • Email digest  │  │ • Spam filter   │  │ • Payouts     │ │
│  │ • CDN delivery  │  │ • WebSocket hub │  │ • Trust network │  │ • Invoices    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └───────────────┘ │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Core Services

### 1.1 Relay Node (EXISTING - needs enhancement)

The fundamental building block of the MESH network.

**Status:** ✅ Partially Implemented (`app/server/main.py`)

**Responsibilities:**
- Store and serve entities, content, links
- Manage append-only log events
- Federation with other relays
- WebSocket real-time updates
- Handle resolution

**Missing Features:**
| Feature | Priority | Description |
|---------|----------|-------------|
| LogEvent integrity | HIGH | Proper prev-chain validation |
| Multi-device support | HIGH | Device key management |
| E2EE for DMs | MEDIUM | X25519 encryption |
| Rate limiting | MEDIUM | Per-user/IP limits |
| Blob storage | MEDIUM | For media attachments |
| Backup/restore | LOW | Data export/import |

**API Endpoints:**
```
POST   /api/entities              # Create entity
GET    /api/entities/{id}         # Get entity
POST   /api/content               # Create content
GET    /api/content/{id}          # Get content
POST   /api/links                 # Create link
GET    /api/feed                  # Get feed
WS     /ws                        # Real-time updates
GET    /api/federation/sync       # Federation sync
GET    /.well-known/mesh-node     # Node discovery
```

---

### 1.2 Identity Vault (NEW)

Third-party service for secure key management with email-based authentication.

**Status:** 🔴 Not Implemented

**Purpose:**
- Allow users to log in with email (familiar UX)
- Securely store encrypted private keys
- Enable key recovery without compromising self-sovereignty
- Bridge traditional auth to cryptographic identity

**Architecture:**
```
┌─────────────────────────────────────────────────────────────────┐
│                      IDENTITY VAULT                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐      ┌─────────────────┐                   │
│  │  Auth Provider  │      │   Key Storage   │                   │
│  │                 │      │                 │                   │
│  │ • Email/pass    │      │ • Encrypted     │                   │
│  │ • Magic link    │      │   private keys  │                   │
│  │ • OAuth (opt.)  │      │ • Per-device    │                   │
│  │ • 2FA/TOTP      │      │   keys          │                   │
│  └────────┬────────┘      └────────┬────────┘                   │
│           │                        │                             │
│           └───────────┬────────────┘                             │
│                       ▼                                          │
│           ┌─────────────────────┐                                │
│           │   Key Derivation    │                                │
│           │                     │                                │
│           │ • Master key from   │                                │
│           │   password (Argon2) │                                │
│           │ • Keys encrypted    │                                │
│           │   client-side       │                                │
│           │ • Vault never sees  │                                │
│           │   plaintext keys    │                                │
│           └─────────────────────┘                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Security Model:**
```python
# Client-side key encryption (vault never sees plaintext)
def encrypt_keys_for_vault(private_key: bytes, password: str) -> bytes:
    # Derive encryption key from password
    salt = os.urandom(32)
    master_key = argon2.hash(password, salt, time_cost=3, memory_cost=65536)
    
    # Encrypt private key with master key
    nonce = os.urandom(12)
    encrypted = aes_gcm_encrypt(master_key, nonce, private_key)
    
    return salt + nonce + encrypted

def decrypt_keys_from_vault(encrypted: bytes, password: str) -> bytes:
    salt = encrypted[:32]
    nonce = encrypted[32:44]
    ciphertext = encrypted[44:]
    
    master_key = argon2.hash(password, salt, time_cost=3, memory_cost=65536)
    return aes_gcm_decrypt(master_key, nonce, ciphertext)
```

**API Endpoints:**
```
POST   /api/auth/register         # Register with email + password
POST   /api/auth/login            # Login, get session token
POST   /api/auth/magic-link       # Send magic link to email
GET    /api/auth/verify/{token}   # Verify magic link
POST   /api/auth/logout           # Logout

POST   /api/keys/store            # Store encrypted keys
GET    /api/keys/retrieve         # Get encrypted keys (requires auth)
DELETE /api/keys/delete           # Delete keys (account deletion)

POST   /api/devices/authorize     # Authorize new device
GET    /api/devices               # List authorized devices
DELETE /api/devices/{id}          # Revoke device

POST   /api/recovery/setup        # Setup recovery (social/backup)
POST   /api/recovery/initiate     # Start recovery process
POST   /api/recovery/complete     # Complete recovery
```

**Database Schema:**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    password_hash TEXT NOT NULL,  -- Argon2 hash
    totp_secret TEXT,             -- For 2FA
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE encrypted_keys (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    entity_id TEXT NOT NULL,      -- MESH entity ID
    encrypted_private_key BLOB,   -- Client-encrypted
    encrypted_encryption_key BLOB,
    key_derivation_params TEXT,   -- Salt, algorithm params
    created_at TIMESTAMP
);

CREATE TABLE devices (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    device_name TEXT,
    device_public_key BLOB,
    authorized_at TIMESTAMP,
    last_used_at TIMESTAMP,
    revoked BOOLEAN DEFAULT FALSE
);

CREATE TABLE recovery_configs (
    user_id UUID PRIMARY KEY REFERENCES users(id),
    method TEXT,  -- 'social', 'backup_codes', 'custodial'
    config TEXT,  -- JSON config for recovery method
    created_at TIMESTAMP
);

CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    device_id UUID REFERENCES devices(id),
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP
);
```

---

### 1.3 Indexer Service (EXISTING - needs enhancement)

Global discovery and search across the network.

**Status:** ✅ Partially Implemented (`app/server/discovery.py`)

**Responsibilities:**
- Crawl relays to build entity index
- Full-text search across entities
- Handle resolution
- Relay discovery and health monitoring
- Trending content/users

**Missing Features:**
| Feature | Priority | Description |
|---------|----------|-------------|
| Persistent storage | HIGH | Currently in-memory only |
| Full-text search | HIGH | Proper text indexing (SQLite FTS5 or Meilisearch) |
| Trending algorithm | MEDIUM | Popular content/users |
| Content indexing | MEDIUM | Search post content |
| Scheduled crawling | MEDIUM | Background job queue |
| Clustering | LOW | Multiple indexer nodes |

**API Endpoints:**
```
GET    /api/search                # Search entities
GET    /api/search/content        # Search content (NEW)
GET    /api/resolve/{handle}      # Resolve handle
GET    /api/locate/{entity_id}    # Find entity relays
GET    /api/trending/users        # Trending users (NEW)
GET    /api/trending/content      # Trending content (NEW)
POST   /api/index/crawl           # Trigger crawl
POST   /api/index/register        # Register relay
GET    /api/index/stats           # Index statistics
GET    /api/relays                # Known relays
GET    /api/relays/{url}/health   # Relay health (NEW)
```

---

## 2. Extension Services

### 2.1 Media Service (NEW)

Handles media uploads, processing, and CDN delivery.

**Status:** 🔴 Not Implemented

**Responsibilities:**
- Image upload and resizing
- Video transcoding
- Content-addressed storage (CID-based)
- CDN integration
- Bandwidth management

**API Endpoints:**
```
POST   /api/media/upload          # Upload file
GET    /api/media/{cid}           # Get media by CID
GET    /api/media/{cid}/thumb     # Get thumbnail
DELETE /api/media/{cid}           # Delete (if owner)
GET    /api/media/quota           # Check storage quota
```

**Storage Model:**
```python
# Content-addressed storage
def store_media(file: bytes, mime_type: str) -> str:
    cid = sha256(file).hexdigest()
    
    # Store original
    storage.put(f"original/{cid}", file)
    
    # Generate variants
    if mime_type.startswith("image/"):
        thumb = resize_image(file, max_size=200)
        medium = resize_image(file, max_size=800)
        storage.put(f"thumb/{cid}", thumb)
        storage.put(f"medium/{cid}", medium)
    
    return cid
```

---

### 2.2 Notification Service (NEW)

Real-time and async notifications.

**Status:** 🔴 Not Implemented

**Responsibilities:**
- WebSocket notification hub
- Push notifications (mobile)
- Email digests
- Notification preferences

**API Endpoints:**
```
GET    /api/notifications         # Get notifications
PUT    /api/notifications/{id}/read  # Mark as read
POST   /api/notifications/settings   # Update preferences
WS     /ws/notifications          # Real-time stream

# Internal (relay → notification service)
POST   /internal/notify           # Send notification
```

---

### 2.3 Moderation Service (NEW)

Attestation-based moderation and trust networks.

**Status:** 🔴 Not Implemented

**Responsibilities:**
- Issue and verify attestations
- Manage trust networks
- Spam detection
- Content flagging
- Label propagation

**API Endpoints:**
```
POST   /api/attestations          # Create attestation
GET    /api/attestations/{id}     # Get attestation
GET    /api/entity/{id}/labels    # Get labels for entity
POST   /api/reports               # Report content
GET    /api/trust/network         # Get trust network
POST   /api/trust/follow          # Follow labeler
```

---

### 2.4 Payment Service (NEW)

Stripe integration for subscriptions and payments.

**Status:** 🔴 Not Implemented (Stripe endpoints exist but incomplete)

**Responsibilities:**
- Publication subscriptions
- Creator payouts
- Payment history
- Invoice generation

**API Endpoints:**
```
POST   /api/payments/checkout     # Create checkout session
POST   /api/payments/webhook      # Stripe webhook
GET    /api/subscriptions         # User's subscriptions
POST   /api/subscriptions/cancel  # Cancel subscription
GET    /api/payouts               # Creator payouts
POST   /api/payouts/request       # Request payout
```

---

## 3. Client Applications

### 3.1 Web Application (EXISTING)

**Status:** ✅ Implemented (`app/client/`)

**Tech Stack:** Vite + React + TypeScript + Tailwind CSS + shadcn/ui

**Features Needed:**
| Feature | Priority | Status |
|---------|----------|--------|
| Home feed | HIGH | ✅ Done |
| Profile page | HIGH | ✅ Done |
| Groups | HIGH | ✅ Done |
| Post creation | HIGH | ✅ Done |
| Comments/replies | HIGH | ✅ Done |
| Likes | HIGH | ✅ Done |
| Identity Vault login | HIGH | 🔴 TODO |
| Publications | MEDIUM | ✅ Partial |
| Notifications UI | MEDIUM | 🔴 TODO |
| Search | MEDIUM | 🔴 TODO |
| Settings | LOW | 🔴 TODO |
| Dark mode | LOW | 🔴 TODO |

---

### 3.2 Mobile Application (FUTURE)

**Status:** 🔴 Not Started

**Tech Stack:** React Native or Flutter

---

### 3.3 Bot SDK (FUTURE)

**Status:** 🔴 Not Started

**Purpose:** Enable developers to build bots and integrations

---

## 4. Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1-2)

| Task | Service | Priority |
|------|---------|----------|
| Identity Vault basic | Identity Vault | HIGH |
| Email + password auth | Identity Vault | HIGH |
| Encrypted key storage | Identity Vault | HIGH |
| Web client vault integration | Web App | HIGH |
| Indexer persistence | Indexer | HIGH |

### Phase 2: Feature Completion (Week 3-4)

| Task | Service | Priority |
|------|---------|----------|
| Device management | Identity Vault | HIGH |
| Key recovery | Identity Vault | MEDIUM |
| Full-text search | Indexer | MEDIUM |
| Notifications basic | Notification Service | MEDIUM |
| Media upload | Media Service | MEDIUM |

### Phase 3: Monetization (Week 5-6)

| Task | Service | Priority |
|------|---------|----------|
| Stripe subscriptions | Payment Service | HIGH |
| Publications | Relay + Web App | HIGH |
| Payouts | Payment Service | MEDIUM |

### Phase 4: Scale & Polish (Week 7-8)

| Task | Service | Priority |
|------|---------|----------|
| Rate limiting | All Services | HIGH |
| Moderation | Moderation Service | MEDIUM |
| Mobile app | Mobile App | LOW |
| Bot SDK | SDK | LOW |

---

## 5. Service Dependencies

```
                    ┌─────────────────┐
                    │   Web Client    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    ┌─────────────────┐ ┌─────────┐ ┌─────────────────┐
    │ Identity Vault  │ │  Relay  │ │    Indexer      │
    └─────────────────┘ └────┬────┘ └─────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
    ┌─────────┐       ┌─────────────┐    ┌─────────────┐
    │  Media  │       │Notifications│    │  Payments   │
    └─────────┘       └─────────────┘    └─────────────┘
```

**Startup Order:**
1. Identity Vault (independent)
2. Relay Node (independent)
3. Indexer (needs Relay)
4. Media Service (needs Relay for auth)
5. Notification Service (needs Relay)
6. Payment Service (needs Relay)

---

## 6. Environment Configuration

```bash
# Identity Vault
VAULT_DATABASE_URL=postgres://...
VAULT_SECRET_KEY=...
VAULT_SMTP_HOST=...
VAULT_SMTP_PORT=587
VAULT_SMTP_USER=...
VAULT_SMTP_PASS=...
VAULT_FROM_EMAIL=noreply@mesh.example.com

# Relay Node
MESH_NODE_ID=relay1
MESH_NODE_URL=https://relay1.mesh.example.com
MESH_DATABASE_URL=sqlite:///mesh.db
MESH_VAULT_URL=https://vault.mesh.example.com

# Indexer
INDEXER_DATABASE_URL=postgres://...
INDEXER_SEED_RELAYS=https://relay1.mesh.example.com,https://relay2.mesh.example.com

# Media Service
MEDIA_STORAGE_BACKEND=s3
MEDIA_S3_BUCKET=mesh-media
MEDIA_S3_REGION=us-east-1
MEDIA_CDN_URL=https://cdn.mesh.example.com

# Payment Service
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_CONNECT_CLIENT_ID=ca_...
```

---

## 7. Security Considerations

### Identity Vault
- Keys encrypted client-side before storage
- Vault NEVER sees plaintext private keys
- Rate limiting on auth endpoints
- Brute force protection
- 2FA support

### Relay Node
- Signature verification on all writes
- Rate limiting per user/IP
- Content size limits
- DDoS protection

### Indexer
- Read-only service (no writes to relays)
- Rate limiting on search
- Respect indexing preferences

---

## 8. Monitoring & Observability

Each service should expose:
- `/health` - Health check endpoint
- `/metrics` - Prometheus metrics
- Structured logging (JSON)

Key metrics:
- Request latency (p50, p95, p99)
- Error rate
- Active connections
- Database pool usage
- Cache hit rate

---

## Next Steps

1. **Start with Identity Vault** - Critical for user experience
2. **Integrate with Web Client** - Email login flow
3. **Enhance Indexer** - Persistent storage + full-text search
4. **Add Notifications** - Real-time updates
5. **Complete Payments** - Monetization for creators
