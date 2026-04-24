#!/usr/bin/env python3
"""
Benchmark all three production implementations.
"""

import subprocess
import sys
import os

HOLON_BENCH = """
import asyncio
import time
from datetime import datetime

async def bench():
    from crypto import SigningKeyPair, EncryptionKeyPair, verify_signature, encrypt_for_recipient, decrypt_for_recipient, GroupKey, generate_entity_id
    from storage import Storage, Entity, Content, Link, EntityKind, ContentKind, LinkKind, AccessType
    
    # Crypto benchmark
    start = time.time()
    for _ in range(100):
        keys = SigningKeyPair.generate()
        sig = keys.sign(b"test message")
        verify_signature(keys.public_key_bytes(), b"test message", sig)
    sign_time = (time.time() - start) * 1000 / 100
    
    start = time.time()
    alice = EncryptionKeyPair.generate()
    bob = EncryptionKeyPair.generate()
    for _ in range(100):
        enc = encrypt_for_recipient(b"secret", bob.public_key_bytes())
        decrypt_for_recipient(enc, bob.private_key_bytes())
    enc_time = (time.time() - start) * 1000 / 100
    
    # Storage benchmark
    storage = Storage("bench.db")
    await storage.initialize()
    
    keys = SigningKeyPair.generate()
    enc_keys = EncryptionKeyPair.generate()
    
    start = time.time()
    for i in range(100):
        entity = Entity(
            id=f"ent:{i}",
            kind=EntityKind.USER,
            public_key=keys.public_key_bytes(),
            encryption_key=enc_keys.public_key_bytes(),
            handle=f"user{i}",
            profile={"name": f"User {i}"},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        await storage.create_entity(entity)
    entity_time = (time.time() - start) * 1000 / 100
    
    start = time.time()
    for i in range(100):
        content = Content(
            id=f"cnt:{i}",
            kind=ContentKind.POST,
            author="ent:0",
            body={"text": f"Post {i}"},
            created_at=datetime.now(),
            context=None,
            reply_to=None,
            access=AccessType.PUBLIC,
            encrypted=False,
            encryption_metadata=None,
            sig=b"",
        )
        await storage.create_content(content)
    content_time = (time.time() - start) * 1000 / 100
    
    start = time.time()
    for i in range(100):
        link = Link(
            id=f"lnk:{i}",
            kind=LinkKind.FOLLOW,
            source=f"ent:{i % 10}",
            target=f"ent:{(i+1) % 10}",
            data={},
            created_at=datetime.now(),
            tombstone=False,
            sig=b"",
        )
        await storage.create_link(link)
    link_time = (time.time() - start) * 1000 / 100
    
    start = time.time()
    for _ in range(100):
        await storage.get_followers("ent:0")
    query_time = (time.time() - start) * 1000 / 100
    
    await storage.close()
    import os
    os.remove("bench.db")
    
    print(f"sign:{sign_time:.3f}")
    print(f"encrypt:{enc_time:.3f}")
    print(f"entity:{entity_time:.3f}")
    print(f"content:{content_time:.3f}")
    print(f"link:{link_time:.3f}")
    print(f"query:{query_time:.3f}")

asyncio.run(bench())
"""

RELAY141_BENCH = """
import asyncio
import time
from datetime import datetime

async def bench():
    from crypto import SigningKeyPair, EncryptionKeyPair, verify_signature, generate_actor_id, compute_commitment_hash, encrypt_aes_gcm, decrypt_aes_gcm, derive_encryption_key
    from storage import Storage, Identity, LogEvent, LogEventType
    
    # Crypto benchmark
    start = time.time()
    for _ in range(100):
        keys = SigningKeyPair.generate()
        sig = keys.sign(b"test message")
        verify_signature(keys.public_key_bytes(), b"test message", sig)
    sign_time = (time.time() - start) * 1000 / 100
    
    start = time.time()
    alice = EncryptionKeyPair.generate()
    bob = EncryptionKeyPair.generate()
    for _ in range(100):
        shared = alice.derive_shared_secret(bob.public_key_bytes())
        key = derive_encryption_key(shared)
        n, c = encrypt_aes_gcm(b"secret", key)
        decrypt_aes_gcm(n, c, key)
    enc_time = (time.time() - start) * 1000 / 100
    
    start = time.time()
    for _ in range(100):
        compute_commitment_hash("event123", "action.v1", ["r1", "r2"], {"k": 1})
    commit_time = (time.time() - start) * 1000 / 100
    
    # Storage benchmark
    storage = Storage("bench.db")
    await storage.initialize()
    
    keys = SigningKeyPair.generate()
    enc_keys = EncryptionKeyPair.generate()
    actor_id = generate_actor_id(keys.public_key_bytes())
    
    start = time.time()
    for i in range(100):
        identity = Identity(
            actor_id=f"relay:actor:{i}",
            public_key=keys.public_key_bytes(),
            encryption_key=enc_keys.public_key_bytes(),
            display_name=f"User {i}",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        await storage.put_identity(identity)
    identity_time = (time.time() - start) * 1000 / 100
    
    prev = None
    start = time.time()
    for i in range(100):
        event = LogEvent(
            id=f"relay:event:{i}",
            actor=actor_id,
            type=LogEventType.POST,
            data={"text": f"Post {i}"},
            ts=datetime.now(),
            prev=prev,
            sig=b"",
        )
        await storage.append_log(event)
        prev = event.id
    event_time = (time.time() - start) * 1000 / 100
    
    start = time.time()
    for _ in range(100):
        await storage.get_log(actor_id, limit=50)
    log_query_time = (time.time() - start) * 1000 / 100
    
    await storage.close()
    import os
    os.remove("bench.db")
    
    print(f"sign:{sign_time:.3f}")
    print(f"encrypt:{enc_time:.3f}")
    print(f"commit_hash:{commit_time:.3f}")
    print(f"identity:{identity_time:.3f}")
    print(f"event:{event_time:.3f}")
    print(f"query:{log_query_time:.3f}")

asyncio.run(bench())
"""

RELAY2_BENCH = """
import asyncio
import time
from datetime import datetime

async def bench():
    from crypto import SigningKeyPair, EncryptionKeyPair, verify_signature, generate_actor_id, generate_event_id, compute_boundary_hash, encrypt_aes_gcm, decrypt_aes_gcm, derive_encryption_key
    from storage import Storage, Identity, Event, State, Attestation, ViewDefinition, EventType, AttestationType, ReducerType
    from views import ViewEngine
    
    # Crypto benchmark
    start = time.time()
    for _ in range(100):
        keys = SigningKeyPair.generate()
        sig = keys.sign(b"test message")
        verify_signature(keys.public_key_bytes(), b"test message", sig)
    sign_time = (time.time() - start) * 1000 / 100
    
    start = time.time()
    alice = EncryptionKeyPair.generate()
    bob = EncryptionKeyPair.generate()
    for _ in range(100):
        shared = alice.derive_shared_secret(bob.public_key_bytes())
        key = derive_encryption_key(shared)
        n, c = encrypt_aes_gcm(b"secret", key)
        decrypt_aes_gcm(n, c, key)
    enc_time = (time.time() - start) * 1000 / 100
    
    start = time.time()
    for _ in range(100):
        compute_boundary_hash(["e1", "e2", "e3"], {"a1": "h1", "a2": "h2"})
    boundary_time = (time.time() - start) * 1000 / 100
    
    # Storage benchmark
    storage = Storage("bench.db")
    await storage.initialize()
    
    keys = SigningKeyPair.generate()
    actor_id = generate_actor_id(keys.public_key_bytes())
    
    start = time.time()
    for i in range(100):
        identity = Identity(
            actor_id=f"actor:{i}",
            public_key=keys.public_key_bytes(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        await storage.put_identity(identity)
    identity_time = (time.time() - start) * 1000 / 100
    
    start = time.time()
    for i in range(100):
        event = Event(
            id=generate_event_id({"i": i, "ts": str(datetime.now())}),
            actor=actor_id,
            type=EventType.POST,
            data={"text": f"Post {i}"},
            ts=datetime.now(),
            parents=[],
            sig=b"",
        )
        await storage.append_event(event)
    event_time = (time.time() - start) * 1000 / 100
    
    start = time.time()
    for i in range(100):
        attestation = Attestation(
            id=f"att:{i}",
            issuer=actor_id,
            subject=f"actor:{i % 10}",
            type=AttestationType.TRUST,
            claim={"level": "high"},
            ts=datetime.now(),
            sig=b"",
        )
        await storage.put_attestation(attestation)
    attestation_time = (time.time() - start) * 1000 / 100
    
    view_def = ViewDefinition(
        object_id="view:bench",
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
    
    engine = ViewEngine(storage)
    start = time.time()
    for _ in range(20):
        await engine.execute(view_def, use_cache=False)
    view_time = (time.time() - start) * 1000 / 20
    
    await storage.close()
    import os
    os.remove("bench.db")
    
    print(f"sign:{sign_time:.3f}")
    print(f"encrypt:{enc_time:.3f}")
    print(f"boundary_hash:{boundary_time:.3f}")
    print(f"identity:{identity_time:.3f}")
    print(f"event:{event_time:.3f}")
    print(f"attestation:{attestation_time:.3f}")
    print(f"view_exec:{view_time:.3f}")

asyncio.run(bench())
"""

def run_bench(impl_dir, code):
    result = subprocess.run(
        [sys.executable, '-c', code],
        cwd=impl_dir,
        capture_output=True,
        text=True,
        timeout=60,
    )
    metrics = {}
    for line in result.stdout.strip().split('\n'):
        if ':' in line:
            parts = line.split(':')
            if len(parts) == 2:
                metrics[parts[0]] = float(parts[1])
    return metrics, result.stderr

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    print('=' * 70)
    print('BENCHMARK COMPARISON (100 operations each, time in ms)')
    print('=' * 70)
    
    # Run benchmarks
    print('\nRunning HOLON v4...')
    holon, err = run_bench(os.path.join(base_dir, 'holon_v4_impl'), HOLON_BENCH)
    if err and 'Traceback' in err:
        print(f'  Error: {err.split(chr(10))[-2][:80]}')
    
    print('Running Relay v1.4.1...')
    relay141, err = run_bench(os.path.join(base_dir, 'relay_v1.4.1_impl'), RELAY141_BENCH)
    if err and 'Traceback' in err:
        print(f'  Error: {err.split(chr(10))[-2][:80]}')
    
    print('Running Relay v2...')
    relay2, err = run_bench(os.path.join(base_dir, 'relay_v2_impl'), RELAY2_BENCH)
    if err and 'Traceback' in err:
        print(f'  Error: {err.split(chr(10))[-2][:80]}')
    
    print()
    print('=' * 70)
    print('CRYPTOGRAPHY (per operation)')
    print('=' * 70)
    print(f"{'Operation':<25} {'HOLON v4':>12} {'Relay v1.4.1':>12} {'Relay v2':>12}")
    print('-' * 65)
    print(f"{'Ed25519 sign+verify':<25} {holon.get('sign',0):>10.3f}ms {relay141.get('sign',0):>10.3f}ms {relay2.get('sign',0):>10.3f}ms")
    print(f"{'X25519+AES encrypt/dec':<25} {holon.get('encrypt',0):>10.3f}ms {relay141.get('encrypt',0):>10.3f}ms {relay2.get('encrypt',0):>10.3f}ms")
    print(f"{'commitment_hash':<25} {'-':>12} {relay141.get('commit_hash',0):>10.3f}ms {'-':>12}")
    print(f"{'boundary_hash':<25} {'-':>12} {'-':>12} {relay2.get('boundary_hash',0):>10.3f}ms")
    
    print()
    print('=' * 70)
    print('STORAGE (per operation)')
    print('=' * 70)
    print(f"{'Operation':<25} {'HOLON v4':>12} {'Relay v1.4.1':>12} {'Relay v2':>12}")
    print('-' * 65)
    print(f"{'Create identity/entity':<25} {holon.get('entity',0):>10.3f}ms {relay141.get('identity',0):>10.3f}ms {relay2.get('identity',0):>10.3f}ms")
    print(f"{'Create content/event':<25} {holon.get('content',0):>10.3f}ms {relay141.get('event',0):>10.3f}ms {relay2.get('event',0):>10.3f}ms")
    print(f"{'Create link':<25} {holon.get('link',0):>10.3f}ms {'-':>12} {'-':>12}")
    print(f"{'Create attestation':<25} {'-':>12} {'-':>12} {relay2.get('attestation',0):>10.3f}ms")
    print(f"{'Query (followers/log)':<25} {holon.get('query',0):>10.3f}ms {relay141.get('query',0):>10.3f}ms {'-':>12}")
    print(f"{'View execution':<25} {'-':>12} {'-':>12} {relay2.get('view_exec',0):>10.3f}ms")
    
    print()
    print('=' * 70)
    print('SUMMARY')
    print('=' * 70)
    
    holon_crypto = holon.get('sign',0) + holon.get('encrypt',0)
    relay141_crypto = relay141.get('sign',0) + relay141.get('encrypt',0) + relay141.get('commit_hash',0)
    relay2_crypto = relay2.get('sign',0) + relay2.get('encrypt',0) + relay2.get('boundary_hash',0)
    
    holon_storage = holon.get('entity',0) + holon.get('content',0) + holon.get('link',0)
    relay141_storage = relay141.get('identity',0) + relay141.get('event',0)
    relay2_storage = relay2.get('identity',0) + relay2.get('event',0) + relay2.get('attestation',0)
    
    print(f"{'Metric':<25} {'HOLON v4':>12} {'Relay v1.4.1':>12} {'Relay v2':>12}")
    print('-' * 65)
    print(f"{'Crypto total (ms)':<25} {holon_crypto:>12.3f} {relay141_crypto:>12.3f} {relay2_crypto:>12.3f}")
    print(f"{'Storage total (ms)':<25} {holon_storage:>12.3f} {relay141_storage:>12.3f} {relay2_storage:>12.3f}")
    if holon_crypto > 0:
        print(f"{'Ops/sec (crypto)':<25} {1000/holon_crypto:>12.0f} {1000/relay141_crypto if relay141_crypto else 0:>12.0f} {1000/relay2_crypto if relay2_crypto else 0:>12.0f}")
    if holon_storage > 0:
        print(f"{'Ops/sec (storage)':<25} {1000/holon_storage:>12.0f} {1000/relay141_storage if relay141_storage else 0:>12.0f} {1000/relay2_storage if relay2_storage else 0:>12.0f}")

if __name__ == '__main__':
    main()
