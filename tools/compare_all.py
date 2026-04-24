#!/usr/bin/env python3
"""
Compare all three production implementations via subprocess.
"""

import subprocess
import sys
import os

def run_test(impl_dir, test_code):
    """Run test code in implementation directory."""
    result = subprocess.run(
        [sys.executable, "-c", test_code],
        cwd=impl_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout, result.stderr, result.returncode

# Test code for each implementation
HOLON_V4_TEST = '''
import asyncio
import time
from datetime import datetime

async def test():
    results = {}
    
    # Crypto
    from crypto import (
        SigningKeyPair, EncryptionKeyPair, 
        verify_signature, encrypt_for_recipient, decrypt_for_recipient,
        GroupKey, generate_entity_id
    )
    
    start = time.time()
    
    # Ed25519
    keys = SigningKeyPair.generate()
    sig = keys.sign(b"test")
    verified = verify_signature(keys.public_key_bytes(), b"test", sig)
    print(f"Ed25519: {'PASS' if verified else 'FAIL'}")
    
    # X25519 + AES-GCM
    alice = EncryptionKeyPair.generate()
    bob = EncryptionKeyPair.generate()
    enc = encrypt_for_recipient(b"secret", bob.public_key_bytes())
    dec = decrypt_for_recipient(enc, bob.private_key_bytes())
    enc_ok = dec == b"secret"
    print(f"X25519+AES: {'PASS' if enc_ok else 'FAIL'}")
    
    # Group key
    gk = GroupKey.generate()
    n, c = gk.encrypt(b"msg")
    d = gk.decrypt(n, c)
    print(f"GroupKey: {'PASS' if d == b'msg' else 'FAIL'}")
    
    print(f"Crypto time: {(time.time()-start)*1000:.1f}ms")
    
    # Storage
    from storage import Storage, Entity, Content, Link, EntityKind, ContentKind, LinkKind, AccessType
    
    start = time.time()
    storage = Storage("test.db")
    await storage.initialize()
    
    entity = Entity(
        id=generate_entity_id(keys.public_key_bytes()),
        kind=EntityKind.USER,
        public_key=keys.public_key_bytes(),
        encryption_key=alice.public_key_bytes(),
        handle="test",
        profile={},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sig=b"",
    )
    await storage.create_entity(entity)
    
    content = Content(
        id="cnt:test",
        kind=ContentKind.POST,
        author=entity.id,
        body={"text": "Hello"},
        created_at=datetime.now(),
        context=None,
        reply_to=None,
        access=AccessType.PUBLIC,
        encrypted=False,
        encryption_metadata=None,
        sig=b"",
    )
    await storage.create_content(content)
    
    metrics = await storage.get_metrics()
    print(f"Entities: {metrics['entity_count']}")
    print(f"Content: {metrics['content_count']}")
    print(f"Storage time: {(time.time()-start)*1000:.1f}ms")
    
    await storage.close()
    import os
    os.remove("test.db")
    print("Storage: PASS")

asyncio.run(test())
'''

RELAY_V141_TEST = '''
import asyncio
import time
from datetime import datetime

async def test():
    from crypto import (
        SigningKeyPair, EncryptionKeyPair,
        verify_signature, generate_actor_id, generate_channel_id,
        compute_commitment_hash, encrypt_aes_gcm, decrypt_aes_gcm,
        derive_encryption_key
    )
    
    start = time.time()
    
    # Ed25519
    keys = SigningKeyPair.generate()
    sig = keys.sign(b"test")
    verified = verify_signature(keys.public_key_bytes(), b"test", sig)
    print(f"Ed25519: {'PASS' if verified else 'FAIL'}")
    
    # Actor ID
    actor_id = generate_actor_id(keys.public_key_bytes())
    print(f"ActorID: {'PASS' if actor_id.startswith('relay:actor:') else 'FAIL'}")
    
    # Channel ID
    genesis = {"kind": "relay.channel.genesis.v1", "owner_actor_id": actor_id, "name": "test", "created_at": "2026-01-01T00:00:00Z"}
    channel_id = generate_channel_id(genesis)
    print(f"ChannelID: {'PASS' if channel_id.startswith('relay:channel:') else 'FAIL'}")
    
    # Commitment hash
    ch = compute_commitment_hash("e1", "action.v1", ["r1"], {"k": 1})
    print(f"CommitHash: {'PASS' if len(ch) == 64 else 'FAIL'}")
    
    # X25519 + AES-GCM
    alice = EncryptionKeyPair.generate()
    bob = EncryptionKeyPair.generate()
    shared = alice.derive_shared_secret(bob.public_key_bytes())
    key = derive_encryption_key(shared)
    n, c = encrypt_aes_gcm(b"secret", key)
    d = decrypt_aes_gcm(n, c, key)
    print(f"X25519+AES: {'PASS' if d == b'secret' else 'FAIL'}")
    
    print(f"Crypto time: {(time.time()-start)*1000:.1f}ms")
    
    # Storage
    from storage import Storage, Identity, LogEvent, LogEventType, ChannelGenesis
    
    start = time.time()
    storage = Storage("test.db")
    await storage.initialize()
    
    identity = Identity(
        actor_id=actor_id,
        public_key=keys.public_key_bytes(),
        encryption_key=alice.public_key_bytes(),
        display_name="Test",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sig=b"",
    )
    await storage.put_identity(identity)
    
    event = LogEvent(
        id="relay:event:test",
        actor=actor_id,
        type=LogEventType.POST,
        data={"text": "Hello"},
        ts=datetime.now(),
        prev=None,
        sig=b"",
    )
    await storage.append_log(event)
    
    # Prev chain
    event2 = LogEvent(
        id="relay:event:test2",
        actor=actor_id,
        type=LogEventType.POST,
        data={"text": "Second"},
        ts=datetime.now(),
        prev=event.id,
        sig=b"",
    )
    await storage.append_log(event2)
    head = await storage.get_log_head(actor_id)
    print(f"PrevChain: {'PASS' if head == event2.id else 'FAIL'}")
    
    metrics = await storage.get_metrics()
    print(f"Identities: {metrics['identity_count']}")
    print(f"Events: {metrics['event_count']}")
    print(f"Storage time: {(time.time()-start)*1000:.1f}ms")
    
    await storage.close()
    import os
    os.remove("test.db")
    print("Storage: PASS")

asyncio.run(test())
'''

RELAY_V2_TEST = '''
import asyncio
import time
from datetime import datetime

async def test():
    from crypto import (
        SigningKeyPair, EncryptionKeyPair,
        verify_signature, generate_actor_id, generate_event_id,
        encrypt_aes_gcm, decrypt_aes_gcm, derive_encryption_key,
        compute_boundary_hash
    )
    
    start = time.time()
    
    # Ed25519
    keys = SigningKeyPair.generate()
    sig = keys.sign(b"test")
    verified = verify_signature(keys.public_key_bytes(), b"test", sig)
    print(f"Ed25519: {'PASS' if verified else 'FAIL'}")
    
    # Actor ID
    actor_id = generate_actor_id(keys.public_key_bytes())
    print(f"ActorID: {'PASS' if actor_id.startswith('1220') else 'FAIL'}")
    
    # Event ID (content-addressed)
    eid = generate_event_id({"actor": actor_id, "type": "post"})
    print(f"EventID: {'PASS' if len(eid) == 64 else 'FAIL'}")
    
    # Boundary hash
    bh = compute_boundary_hash(["e1", "e2"], {"a1": "h1"})
    print(f"BoundaryHash: {'PASS' if len(bh) == 64 else 'FAIL'}")
    
    print(f"Crypto time: {(time.time()-start)*1000:.1f}ms")
    
    # Storage (Two-Layer)
    from storage import (
        Storage, Identity, Event, State, Attestation, ViewDefinition,
        EventType, AttestationType, ReducerType
    )
    
    start = time.time()
    storage = Storage("test.db")
    await storage.initialize()
    
    # Truth Layer
    identity = Identity(
        actor_id=actor_id,
        public_key=keys.public_key_bytes(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sig=b"",
    )
    await storage.put_identity(identity)
    
    event = Event(
        id=generate_event_id({"actor": actor_id, "type": "post", "ts": str(datetime.now())}),
        actor=actor_id,
        type=EventType.POST,
        data={"text": "Hello"},
        ts=datetime.now(),
        parents=[],
        sig=b"",
    )
    await storage.append_event(event)
    
    state = State(
        object_id="state:test",
        actor=actor_id,
        type="profile",
        version=1,
        payload={"name": "Test"},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sig=b"",
    )
    await storage.put_state(state)
    
    attestation = Attestation(
        id="att:test",
        issuer=actor_id,
        subject=actor_id,
        type=AttestationType.TRUST,
        claim={"level": "high"},
        ts=datetime.now(),
        sig=b"",
    )
    await storage.put_attestation(attestation)
    
    # View Layer
    view_def = ViewDefinition(
        object_id="view:test",
        actor=actor_id,
        version=1,
        sources=[{"kind": "actor", "actor_id": actor_id}],
        reduce=ReducerType.CHRONOLOGICAL,
        params={"limit": 50},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sig=b"",
    )
    await storage.put_view_definition(view_def)
    
    # Execute view
    from views import ViewEngine
    engine = ViewEngine(storage)
    result = await engine.execute(view_def)
    print(f"ViewExec: {'PASS' if result.is_deterministic else 'FAIL'}")
    
    # Test determinism
    result2 = await engine.execute(view_def)
    print(f"Determinism: {'PASS' if result.result_hash == result2.result_hash else 'FAIL'}")
    
    metrics = await storage.get_metrics()
    print(f"Identities: {metrics['identity_count']}")
    print(f"Events: {metrics['event_count']}")
    print(f"States: {metrics['state_count']}")
    print(f"Attestations: {metrics['attestation_count']}")
    print(f"Views: {metrics['view_definition_count']}")
    print(f"Storage time: {(time.time()-start)*1000:.1f}ms")
    
    await storage.close()
    import os
    os.remove("test.db")
    print("Storage: PASS")

asyncio.run(test())
'''

def main():
    print("=" * 70)
    print("PRODUCTION IMPLEMENTATION COMPARISON")
    print("=" * 70)
    print()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # HOLON v4
    print("=" * 50)
    print("HOLON v4")
    print("=" * 50)
    stdout, stderr, code = run_test(os.path.join(base_dir, "holon_v4_impl"), HOLON_V4_TEST)
    print(stdout)
    if stderr:
        print(f"Errors: {stderr[:200]}")
    
    # Relay v1.4.1
    print("\n" + "=" * 50)
    print("RELAY v1.4.1")
    print("=" * 50)
    stdout, stderr, code = run_test(os.path.join(base_dir, "relay_v1.4.1_impl"), RELAY_V141_TEST)
    print(stdout)
    if stderr:
        print(f"Errors: {stderr[:200]}")
    
    # Relay v2
    print("\n" + "=" * 50)
    print("RELAY v2")
    print("=" * 50)
    stdout, stderr, code = run_test(os.path.join(base_dir, "relay_v2_impl"), RELAY_V2_TEST)
    print(stdout)
    if stderr:
        print(f"Errors: {stderr[:200]}")
    
    # Summary
    print("\n" + "=" * 70)
    print("FEATURE COMPARISON")
    print("=" * 70)
    print(f"""
{'Feature':<30} {'HOLON v4':<15} {'Relay v1.4.1':<15} {'Relay v2':<15}
{'-' * 75}
{'Ed25519 Signatures':<30} {'✓':<15} {'✓':<15} {'✓':<15}
{'X25519 Key Exchange':<30} {'✓':<15} {'✓':<15} {'✓':<15}
{'AES-256-GCM Encryption':<30} {'✓':<15} {'✓':<15} {'✓':<15}
{'SQLite Persistence':<30} {'✓':<15} {'✓':<15} {'✓':<15}
{'Content-Addressed IDs':<30} {'-':<15} {'✓':<15} {'✓':<15}
{'Prev Chain (Log)':<30} {'-':<15} {'✓':<15} {'-':<15}
{'Parents (DAG)':<30} {'-':<15} {'-':<15} {'✓':<15}
{'Attestations':<30} {'-':<15} {'-':<15} {'✓':<15}
{'View Determinism':<30} {'-':<15} {'✓':<15} {'✓':<15}
{'action.* Flows':<30} {'-':<15} {'✓':<15} {'✓':<15}
{'Group Keys':<30} {'✓':<15} {'-':<15} {'-':<15}
{'Channel Genesis':<30} {'-':<15} {'✓':<15} {'-':<15}
{'Two-Layer Architecture':<30} {'-':<15} {'-':<15} {'✓':<15}
""")

if __name__ == "__main__":
    main()
