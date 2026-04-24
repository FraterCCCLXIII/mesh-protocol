# HOLON v4 Production Implementation

A **production-ready** implementation of the HOLON protocol with real cryptography, persistent storage, and network capabilities.

## Features

| Feature | Status | Implementation |
|---------|:------:|----------------|
| **Ed25519 Signatures** | ✅ | `cryptography` library |
| **X25519 Key Exchange** | ✅ | ECDH for encryption key derivation |
| **AES-256-GCM Encryption** | ✅ | Authenticated encryption |
| **SQLite Persistence** | ✅ | `aiosqlite` async storage |
| **HTTP REST API** | ✅ | `aiohttp` server |
| **WebSocket Real-time** | ✅ | `websockets` library |
| **Multi-Relay Federation** | ✅ | Peer connections |

## Quick Start

```bash
cd holon_v4_impl

# Install dependencies
pip install cryptography aiosqlite aiohttp websockets

# Run demo
python run_demo.py
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  CLIENT (client.py)                                          │
│  Identity │ Posts │ Follows │ Groups │ Encryption            │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  NETWORK (network.py)                                        │
│  HTTPServer │ WebSocketServer │ RelayClient │ Federation     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  STORAGE (storage.py)                                        │
│  Entities │ Content │ Links │ Views │ Graph Queries          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  CRYPTO (crypto.py)                                          │
│  Ed25519 │ X25519 │ AES-GCM │ HKDF │ Signing │ Encryption    │
└─────────────────────────────────────────────────────────────┘
```

## Cryptography

### Ed25519 Signing

```python
from crypto import SigningKeyPair, verify_signature

# Generate key pair
keys = SigningKeyPair.generate()

# Sign message
message = b"Hello, world!"
signature = keys.sign(message)

# Verify
is_valid = verify_signature(keys.public_key_bytes(), message, signature)
```

### X25519 + AES-GCM Encryption

```python
from crypto import (
    EncryptionKeyPair, 
    encrypt_for_recipient, 
    decrypt_for_recipient
)

# Generate key pairs
alice = EncryptionKeyPair.generate()
bob = EncryptionKeyPair.generate()

# Alice encrypts for Bob
plaintext = b"Secret message for Bob"
encrypted = encrypt_for_recipient(plaintext, bob.public_key_bytes())

# Bob decrypts
decrypted = decrypt_for_recipient(encrypted, bob.private_key_bytes())
assert decrypted == plaintext
```

### Group Encryption

```python
from crypto import GroupKey, wrap_group_key_for_member

# Create group key
group_key = GroupKey.generate()

# Encrypt with group key
nonce, ciphertext = group_key.encrypt(b"Group message")
plaintext = group_key.decrypt(nonce, ciphertext)

# Share key with member
wrapped = wrap_group_key_for_member(group_key, member_public_key)
```

## Storage

### Async SQLite

```python
from storage import Storage, Entity, Content, Link

storage = Storage("holon.db")
await storage.initialize()

# Create entity
await storage.create_entity(entity)

# Query
entity = await storage.get_entity(entity_id)
followers = await storage.get_followers(entity_id)

# Search
results = await storage.search_content("query")

# Graph queries
suggestions = await storage.get_follows_of_follows(entity_id)
```

## Network

### HTTP API

```python
from network import HTTPServer
from storage import Storage

storage = Storage("relay.db")
http = HTTPServer(storage, port=8080)
await http.start()
```

Endpoints:
- `GET /health` - Health check
- `GET /metrics` - Storage metrics
- `GET /entities/{id}` - Get entity
- `POST /entities` - Create entity (with signature verification)
- `GET /content/{id}` - Get content
- `POST /content` - Create content
- `GET /entities/{id}/followers` - Get followers
- `GET /discover/follows-of-follows/{id}` - Discovery

### WebSocket

```python
from network import WebSocketServer

ws = WebSocketServer(storage, port=8765)
await ws.start()
```

Messages:
- `subscribe` - Subscribe to entities
- `query` - Query data
- `new_content` - Real-time content updates

### Federation

```python
from network import RelayNode

relay = RelayNode(storage, http_port=8080, ws_port=8765)
await relay.start()

# Add peer
await relay.add_peer("http://other-relay.example")

# Broadcast to peers
await relay.broadcast_to_peers(content_dict, "content")
```

## Client

### Identity

```python
from client import Identity, HolonClient

# Generate identity
alice = Identity.generate(handle="alice", profile={"name": "Alice"})

# Or from seed (deterministic)
alice = Identity.from_seed(seed_bytes, handle="alice")

# Initialize client
client = HolonClient(alice)
await client.initialize("alice.db")
```

### Social Operations

```python
# Connect to relay
await client.connect_relay("http://relay.example:8080")

# Post (public)
post = await client.create_post("Hello world!")

# Post (encrypted)
private = await client.create_post("Secret", access=AccessType.PRIVATE)

# Follow
await client.follow(bob_entity_id)

# React
await client.react(post_id, "🔥")

# Get feed
feed = await client.get_feed()

# Discover
suggestions = await client.discover_follows_of_follows()
```

### Groups

```python
# Create group
group = await client.create_group("My Group", "Description")

# Join group
await client.join_group(group_id)

# Post to group (encrypted with group key)
post = await client.create_post(
    "Group-only message",
    context=group_id,
    access=AccessType.GROUP
)
```

## Demo Output

```
============================================================
1. CRYPTOGRAPHY DEMO
============================================================

--- Ed25519 Signing ---
Public key: 462fff0393f767016a9aaa58741ca027...
Signature:  dcc10f7053744a3c649bb9d6ad5e4320...
Verified:   True ✓

--- X25519 + AES-GCM Encryption ---
Plaintext:  Secret message for Bob!
Ciphertext: f51bd9affab68150822c1c2fbc74992b...
Decrypted:  Secret message for Bob!
Match:      True ✓

--- Group Key Encryption ---
Group key ID: kBpw8-DGMQE
Group encryption works: True ✓
Key wrap/unwrap works:  True ✓

============================================================
2. PERSISTENT STORAGE DEMO
============================================================

Created SQLite database: demo_storage.db
Created entity: ent:NFsXhIbjXTeOzbDDNkPkUg (seq: 1)
Search 'programming': 1 results

--- Storage Metrics ---
  entity_count: 1
  content_count: 1
  link_count: 1
  sequence: 3

============================================================
3. CLIENT DEMO
============================================================

--- Identity Generation ---
Alice: ent:4kmBi5QrVw5jZANiQjkVmQ
Bob:   ent:ItcraXr5GS9ZgByLJ-PyVA

--- Social Interactions ---
Alice follows Bob: lnk:moHp6ZB3JBuO_D4xoQ5eBA...
Bob posts: cnt:O3egB0FRN4mXX3PHwc15oA...
Alice reacts: lnk:dTHRdt5AsES9vg5TCgd39w...

--- Feed ---
Alice's feed: 1 items
  - Hello world! This is my first HOLON post 🎉

--- Encrypted Content ---
Private post created: True
Decrypted by Bob: This is a private message...
```

## Comparison: Simulator vs Implementation

| Aspect | Simulator | This Implementation |
|--------|-----------|---------------------|
| **Signatures** | Fake (random bytes) | Real Ed25519 |
| **Encryption** | Not implemented | Real X25519 + AES-GCM |
| **Storage** | In-memory dict | SQLite with async |
| **Network** | None | HTTP + WebSocket |
| **Federation** | None | Peer connections |
| **Purpose** | Protocol testing | Production use |

## Files

- `crypto.py` - Cryptographic primitives
- `storage.py` - SQLite persistence layer
- `network.py` - HTTP/WebSocket servers and federation
- `client.py` - High-level client library
- `run_demo.py` - Demonstration script

## Dependencies

```
cryptography>=42.0.0
aiosqlite>=0.20.0
aiohttp>=3.9.0
websockets>=12.0
```

## Security Notes

- All signatures use Ed25519 (128-bit security)
- Encryption uses X25519 + HKDF + AES-256-GCM
- Keys are never logged or exposed
- Signatures are verified on all API writes
- Group keys are wrapped per-member with ECDH
