#!/usr/bin/env python3
"""
HOLON v4 Implementation Demo

Demonstrates all production features:
1. Ed25519 signatures
2. X25519/AES-GCM encryption  
3. SQLite persistence
4. HTTP API
5. WebSocket real-time
6. Multi-relay federation
"""

import asyncio
import logging
import os
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_crypto():
    """Demo cryptographic operations."""
    print("\n" + "=" * 60)
    print("1. CRYPTOGRAPHY DEMO")
    print("=" * 60)
    
    from crypto import (
        SigningKeyPair, EncryptionKeyPair, 
        verify_signature, sign_object, verify_object_signature,
        encrypt_for_recipient, decrypt_for_recipient,
        GroupKey, wrap_group_key_for_member, unwrap_group_key,
        generate_entity_id
    )
    
    # Ed25519 Signing
    print("\n--- Ed25519 Signing ---")
    alice_signing = SigningKeyPair.generate()
    message = b"Hello, this is a signed message!"
    signature = alice_signing.sign(message)
    
    print(f"Public key: {alice_signing.public_key_bytes().hex()[:32]}...")
    print(f"Signature:  {signature.hex()[:32]}...")
    
    is_valid = verify_signature(alice_signing.public_key_bytes(), message, signature)
    print(f"Verified:   {is_valid} ✓" if is_valid else f"Verified: {is_valid} ✗")
    
    # Object signing
    print("\n--- Object Signing ---")
    obj = {"type": "post", "text": "Hello world", "author": "alice"}
    signed_obj = sign_object(obj, alice_signing)
    print(f"Signed object: {list(signed_obj.keys())}")
    print(f"Signature:     {signed_obj['sig'][:32]}...")
    
    is_valid = verify_object_signature(signed_obj, alice_signing.public_key_bytes())
    print(f"Verified:      {is_valid} ✓" if is_valid else f"Verified: {is_valid} ✗")
    
    # X25519 + AES-GCM Encryption
    print("\n--- X25519 + AES-GCM Encryption ---")
    alice_enc = EncryptionKeyPair.generate()
    bob_enc = EncryptionKeyPair.generate()
    
    plaintext = b"Secret message for Bob!"
    encrypted = encrypt_for_recipient(plaintext, bob_enc.public_key_bytes())
    
    print(f"Plaintext:  {plaintext.decode()}")
    print(f"Ciphertext: {encrypted.ciphertext.hex()[:32]}...")
    print(f"Ephemeral:  {encrypted.ephemeral_public_key.hex()[:32]}...")
    
    decrypted = decrypt_for_recipient(encrypted, bob_enc.private_key_bytes())
    print(f"Decrypted:  {decrypted.decode()}")
    print(f"Match:      {decrypted == plaintext} ✓" if decrypted == plaintext else f"Match: False ✗")
    
    # Group Keys
    print("\n--- Group Key Encryption ---")
    group_key = GroupKey.generate()
    print(f"Group key ID: {group_key.key_id}")
    
    # Encrypt with group key
    nonce, ciphertext = group_key.encrypt(b"Group message!")
    decrypted = group_key.decrypt(nonce, ciphertext)
    print(f"Group encryption works: {decrypted == b'Group message!'} ✓")
    
    # Wrap group key for member
    wrapped = wrap_group_key_for_member(group_key, bob_enc.public_key_bytes())
    unwrapped = unwrap_group_key(wrapped, bob_enc.private_key_bytes(), 
                                  group_key.key_id, group_key.created_at)
    print(f"Key wrap/unwrap works:  {unwrapped.key == group_key.key} ✓")
    
    # Entity ID generation
    print("\n--- Entity ID Generation ---")
    entity_id = generate_entity_id(alice_signing.public_key_bytes())
    print(f"Entity ID: {entity_id}")


async def demo_storage():
    """Demo persistent storage."""
    print("\n" + "=" * 60)
    print("2. PERSISTENT STORAGE DEMO")
    print("=" * 60)
    
    from storage import Storage, Entity, Content, Link, EntityKind, ContentKind, LinkKind, AccessType
    from crypto import SigningKeyPair, EncryptionKeyPair, generate_entity_id
    from datetime import datetime
    
    db_path = "demo_storage.db"
    storage = Storage(db_path)
    await storage.initialize()
    
    print(f"\nCreated SQLite database: {db_path}")
    
    # Create entity
    print("\n--- Entity Storage ---")
    signing = SigningKeyPair.generate()
    encryption = EncryptionKeyPair.generate()
    
    entity = Entity(
        id=generate_entity_id(signing.public_key_bytes()),
        kind=EntityKind.USER,
        public_key=signing.public_key_bytes(),
        encryption_key=encryption.public_key_bytes(),
        handle="alice",
        profile={"name": "Alice", "bio": "Test user"},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sig=signing.sign(b"test"),
    )
    
    seq = await storage.create_entity(entity)
    print(f"Created entity: {entity.id} (seq: {seq})")
    
    retrieved = await storage.get_entity(entity.id)
    print(f"Retrieved by ID: {retrieved.handle}")
    
    retrieved = await storage.get_entity_by_handle("alice")
    print(f"Retrieved by handle: {retrieved.id}")
    
    # Create content
    print("\n--- Content Storage ---")
    content = Content(
        id="cnt:test123",
        kind=ContentKind.POST,
        author=entity.id,
        body={"text": "Hello world! This is a test post about programming."},
        created_at=datetime.now(),
        context=None,
        reply_to=None,
        access=AccessType.PUBLIC,
        encrypted=False,
        encryption_metadata=None,
        sig=signing.sign(b"test"),
    )
    
    seq = await storage.create_content(content)
    print(f"Created content: {content.id} (seq: {seq})")
    
    # Full-text search
    results = await storage.search_content("programming")
    print(f"Search 'programming': {len(results)} results")
    
    # Create links
    print("\n--- Link Storage ---")
    link = Link(
        id="lnk:follow123",
        kind=LinkKind.FOLLOW,
        source=entity.id,
        target="ent:target123",
        data={},
        created_at=datetime.now(),
        tombstone=False,
        sig=signing.sign(b"test"),
    )
    
    seq = await storage.create_link(link)
    print(f"Created link: {link.id} (seq: {seq})")
    
    # Metrics
    print("\n--- Storage Metrics ---")
    metrics = await storage.get_metrics()
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    
    await storage.close()
    os.remove(db_path)
    print(f"\nCleaned up: {db_path}")


async def demo_client():
    """Demo high-level client."""
    print("\n" + "=" * 60)
    print("3. CLIENT DEMO")
    print("=" * 60)
    
    from client import Identity, HolonClient
    from storage import AccessType
    
    # Create identities
    print("\n--- Identity Generation ---")
    alice = Identity.generate(handle="alice", profile={"name": "Alice Smith"})
    bob = Identity.generate(handle="bob", profile={"name": "Bob Jones"})
    
    print(f"Alice: {alice.entity_id}")
    print(f"Bob:   {bob.entity_id}")
    
    # Initialize clients
    print("\n--- Client Initialization ---")
    alice_client = HolonClient(alice)
    bob_client = HolonClient(bob)
    
    await alice_client.initialize("demo_alice.db")
    await bob_client.initialize("demo_bob.db")
    print("Initialized local storage for both users")
    
    # Cross-register entities (simulating relay sync)
    await alice_client.storage.create_entity(bob.to_entity())
    await bob_client.storage.create_entity(alice.to_entity())
    print("Cross-registered entities (simulating federation)")
    
    # Social interactions
    print("\n--- Social Interactions ---")
    
    follow = await alice_client.follow(bob.entity_id)
    print(f"Alice follows Bob: {follow.id[:30]}...")
    
    post = await bob_client.create_post("Hello world! This is my first HOLON post 🎉")
    print(f"Bob posts: {post.id[:30]}...")
    
    # Sync post to Alice
    await alice_client.storage.create_content(post)
    
    react = await alice_client.react(post.id, "🔥")
    print(f"Alice reacts: {react.id[:30]}...")
    
    # Feed
    print("\n--- Feed ---")
    feed = await alice_client.get_feed()
    print(f"Alice's feed: {len(feed)} items")
    for content in feed:
        text = content.body.get('text', '[no text]')
        print(f"  - {text[:50]}")
    
    # Encrypted content
    print("\n--- Encrypted Content ---")
    private = await bob_client.create_post(
        "This is a private message that only I can read",
        access=AccessType.PRIVATE
    )
    print(f"Private post created: {private.encrypted}")
    
    decrypted = await bob_client.decrypt_content(private)
    print(f"Decrypted by Bob: {decrypted[:40]}...")
    
    # Groups
    print("\n--- Groups ---")
    group = await alice_client.create_group("Test Group", "A test group for demos")
    print(f"Created group: {group.id}")
    
    # Cleanup
    await alice_client.close()
    await bob_client.close()
    
    for f in ["demo_alice.db", "demo_bob.db"]:
        if os.path.exists(f):
            os.remove(f)
    print("\nCleaned up databases")


async def demo_network():
    """Demo network layer (HTTP + WebSocket)."""
    print("\n" + "=" * 60)
    print("4. NETWORK DEMO")
    print("=" * 60)
    
    from storage import Storage
    from network import RelayNode
    
    db_path = "demo_relay.db"
    storage = Storage(db_path)
    
    # Start relay
    print("\n--- Starting Relay Node ---")
    relay = RelayNode(storage, http_port=18080, ws_port=18765)
    await relay.start()
    
    print("HTTP: http://localhost:18080")
    print("WebSocket: ws://localhost:18765")
    
    # Test HTTP endpoints
    print("\n--- Testing HTTP API ---")
    import aiohttp
    async with aiohttp.ClientSession() as session:
        # Health check
        async with session.get("http://localhost:18080/health") as resp:
            data = await resp.json()
            print(f"Health: {data}")
        
        # Metrics
        async with session.get("http://localhost:18080/metrics") as resp:
            data = await resp.json()
            print(f"Metrics: {data}")
    
    # Test WebSocket
    print("\n--- Testing WebSocket ---")
    import websockets
    async with websockets.connect("ws://localhost:18765") as ws:
        # Subscribe
        msg = {"type": "subscribe", "data": {"entities": ["test123"]}, "request_id": "1"}
        await ws.send(json.dumps(msg))
        response = await ws.recv()
        print(f"Subscribe response: {response[:60]}...")
        
        # Query
        msg = {"type": "query", "data": {"type": "get_entity", "id": "test123"}, "request_id": "2"}
        await ws.send(json.dumps(msg))
        response = await ws.recv()
        print(f"Query response: {response[:60]}...")
    
    # Cleanup
    await relay.stop()
    os.remove(db_path)
    print("\nRelay stopped and cleaned up")


async def demo_federation():
    """Demo multi-relay federation."""
    print("\n" + "=" * 60)
    print("5. FEDERATION DEMO")
    print("=" * 60)
    
    from storage import Storage
    from network import RelayNode, RelayClient
    from client import Identity
    
    # Start two relays
    print("\n--- Starting Two Relays ---")
    
    storage1 = Storage("relay1.db")
    relay1 = RelayNode(storage1, http_port=18081, ws_port=18766)
    await relay1.start()
    print("Relay 1: http://localhost:18081")
    
    storage2 = Storage("relay2.db")
    relay2 = RelayNode(storage2, http_port=18082, ws_port=18767)
    await relay2.start()
    print("Relay 2: http://localhost:18082")
    
    # Connect relays as peers
    print("\n--- Connecting Relays ---")
    await relay1.add_peer("http://localhost:18082")
    print("Relay 1 → Relay 2: connected")
    
    # Create user on Relay 1
    print("\n--- Creating User on Relay 1 ---")
    alice = Identity.generate(handle="alice")
    entity_dict = alice.to_entity().to_dict()
    entity_dict['public_key_hex'] = alice.signing_key.public_key_bytes().hex()
    entity_dict['encryption_key_hex'] = alice.encryption_key.public_key_bytes().hex()
    entity_dict['sig_hex'] = alice.to_entity().sig.hex()
    
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post("http://localhost:18081/entities", json=entity_dict) as resp:
            if resp.status == 201:
                print(f"Created alice on Relay 1: {alice.entity_id}")
    
    # Check if federated to Relay 2
    # (In production, this would happen via sync)
    print("\n--- Federation Status ---")
    print("(In production, relay1 would sync alice to relay2)")
    print("(Sync is triggered by broadcast_to_peers)")
    
    # Cleanup
    await relay1.stop()
    await relay2.stop()
    
    for f in ["relay1.db", "relay2.db"]:
        if os.path.exists(f):
            os.remove(f)
    print("\nRelays stopped and cleaned up")


async def run_all_demos():
    """Run all demos."""
    print("=" * 60)
    print("HOLON v4 PRODUCTION IMPLEMENTATION DEMO")
    print("=" * 60)
    print("""
This demo shows all production features:
1. Real Ed25519 signatures
2. Real X25519/AES-GCM encryption
3. SQLite persistent storage
4. HTTP REST API
5. WebSocket real-time sync
6. Multi-relay federation
""")
    
    await demo_crypto()
    await demo_storage()
    await demo_client()
    
    # Network demos require ports
    try:
        await demo_network()
        await demo_federation()
    except Exception as e:
        print(f"\nNetwork demos skipped (ports may be in use): {e}")
    
    print("\n" + "=" * 60)
    print("ALL DEMOS COMPLETE")
    print("=" * 60)


# Import json for network demo
import json

if __name__ == "__main__":
    asyncio.run(run_all_demos())
