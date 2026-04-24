#!/usr/bin/env python3
"""
MESH Protocol Performance Benchmark

Tests all layers:
- Privacy Layer: Ed25519, X25519, AES-GCM
- Social Layer: Entity, Content, Link
- Integrity Layer: LogEvent with prev chain
- View Layer: ViewDefinition execution
- Moderation Layer: Attestations
"""

import asyncio
import time
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from mesh_unified.crypto import (
    SigningKeyPair, EncryptionKeyPair, GroupKey,
    verify_signature, sign_object, verify_object_signature,
    encrypt_for_recipient, decrypt_for_recipient,
    generate_entity_id, generate_content_id, generate_link_id,
    commitment_hash, boundary_hash,
)
from mesh_unified.primitives import (
    Entity, Content, Link,
    EntityKind, ContentKind, LinkKind, AccessType,
)
from mesh_unified.integrity import (
    LogEvent, OpType, ObjectType,
    generate_log_event_id, validate_log_chain,
)
from mesh_unified.views import (
    ViewDefinition, ViewEngine,
    Source, Filter, ReducerType, SourceKind,
)
from mesh_unified.attestations import (
    Attestation, AttestationType,
)
from mesh_unified.storage import Storage


def benchmark(name: str, iterations: int = 100):
    """Decorator for timing benchmarks."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Warmup
            for _ in range(5):
                await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            # Benchmark
            start = time.perf_counter()
            for _ in range(iterations):
                await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            
            per_op = (elapsed / iterations) * 1000
            ops_per_sec = iterations / elapsed
            
            print(f"  {name:<40} {per_op:>8.3f}ms  ({ops_per_sec:>10,.0f}/sec)")
            return per_op
        return wrapper
    return decorator


async def run_benchmarks():
    print("=" * 70)
    print("MESH PROTOCOL PERFORMANCE BENCHMARK")
    print("=" * 70)
    
    # Setup
    alice_keys = SigningKeyPair.generate()
    bob_keys = SigningKeyPair.generate()
    alice_enc = EncryptionKeyPair.generate()
    bob_enc = EncryptionKeyPair.generate()
    
    results = {}
    
    # =========================================================================
    print("\n[PRIVACY LAYER - Crypto Operations]")
    # =========================================================================
    
    @benchmark("Ed25519 key generation")
    def bench_keygen():
        SigningKeyPair.generate()
    results['keygen'] = await bench_keygen()
    
    @benchmark("Ed25519 sign")
    def bench_sign():
        alice_keys.sign(b"test message for signing")
    results['sign'] = await bench_sign()
    
    sig = alice_keys.sign(b"test message")
    @benchmark("Ed25519 verify")
    def bench_verify():
        verify_signature(alice_keys.public_key_bytes(), b"test message", sig)
    results['verify'] = await bench_verify()
    
    @benchmark("Ed25519 sign + verify")
    def bench_sign_verify():
        msg = b"test message"
        s = alice_keys.sign(msg)
        verify_signature(alice_keys.public_key_bytes(), msg, s)
    results['sign_verify'] = await bench_sign_verify()
    
    @benchmark("X25519 + AES-GCM encrypt")
    def bench_encrypt():
        encrypt_for_recipient(b"secret message", bob_enc.public_key_bytes())
    results['encrypt'] = await bench_encrypt()
    
    encrypted = encrypt_for_recipient(b"secret message", bob_enc.public_key_bytes())
    @benchmark("X25519 + AES-GCM decrypt")
    def bench_decrypt():
        decrypt_for_recipient(encrypted, bob_enc.private_key_bytes())
    results['decrypt'] = await bench_decrypt()
    
    gk = GroupKey.generate()
    @benchmark("Group key encrypt")
    def bench_group_encrypt():
        gk.encrypt(b"group message")
    results['group_encrypt'] = await bench_group_encrypt()
    
    nonce, ct = gk.encrypt(b"group message")
    @benchmark("Group key decrypt")
    def bench_group_decrypt():
        gk.decrypt(nonce, ct)
    results['group_decrypt'] = await bench_group_decrypt()
    
    @benchmark("commitment_hash")
    def bench_commitment():
        commitment_hash("event:123", "post.create", ["ref1", "ref2"], {"text": "hello"})
    results['commitment_hash'] = await bench_commitment()
    
    @benchmark("boundary_hash")
    def bench_boundary():
        boundary_hash(["e1", "e2", "e3", "e4", "e5"], {"a1": "h1", "a2": "h2"})
    results['boundary_hash'] = await bench_boundary()
    
    # =========================================================================
    print("\n[SOCIAL LAYER - Primitive Creation]")
    # =========================================================================
    
    @benchmark("Generate entity_id")
    def bench_entity_id():
        generate_entity_id(alice_keys.public_key_bytes())
    results['entity_id'] = await bench_entity_id()
    
    @benchmark("Generate content_id")
    def bench_content_id():
        generate_content_id({"author": "alice", "text": "hello", "ts": "2026-01-01"})
    results['content_id'] = await bench_content_id()
    
    @benchmark("Sign object (JSON)")
    def bench_sign_object():
        sign_object({"type": "post", "text": "hello world"}, alice_keys)
    results['sign_object'] = await bench_sign_object()
    
    # =========================================================================
    print("\n[INTEGRITY LAYER - Log Operations]")
    # =========================================================================
    
    @benchmark("Generate log_event_id")
    def bench_log_id():
        generate_log_event_id("ent:alice", 42)
    results['log_event_id'] = await bench_log_id()
    
    # Create a chain of events for validation
    events = []
    prev = None
    for i in range(100):
        event = LogEvent(
            id=generate_log_event_id("ent:alice", i+1),
            actor="ent:alice",
            seq=i+1,
            prev=prev,
            op=OpType.CREATE,
            object_type=ObjectType.CONTENT,
            object_id=f"content:{i}",
            payload={"text": f"post {i}"},
            ts=datetime.now(),
            sig=b"",
        )
        events.append(event)
        prev = event.id
    
    @benchmark("Validate log chain (100 events)", iterations=10)
    def bench_validate_chain():
        validate_log_chain(events)
    results['validate_chain'] = await bench_validate_chain()
    
    # =========================================================================
    print("\n[STORAGE LAYER - Database Operations]")
    # =========================================================================
    
    storage = Storage(":memory:")
    await storage.initialize()
    
    # Create test entity
    alice_entity = Entity(
        id=generate_entity_id(alice_keys.public_key_bytes()),
        kind=EntityKind.USER,
        public_key=alice_keys.public_key_bytes(),
        encryption_key=alice_enc.public_key_bytes(),
        handle="alice",
        profile={"name": "Alice", "bio": "Test user"},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sig=alice_keys.sign(b"entity"),
    )
    await storage.create_entity(alice_entity)
    
    content_counter = [0]
    @benchmark("Create content (with commit)")
    async def bench_create_content():
        content_counter[0] += 1
        content = Content(
            id=f"cnt:{content_counter[0]}",
            author=alice_entity.id,
            kind=ContentKind.POST,
            body={"text": f"Post number {content_counter[0]}"},
            reply_to=None,
            created_at=datetime.now(),
            access=AccessType.PUBLIC,
            encrypted=False,
            encryption_metadata=None,
            sig=alice_keys.sign(b"content"),
        )
        await storage.create_content(content)
    results['create_content'] = await bench_create_content()
    
    link_counter = [0]
    @benchmark("Create link (with commit)")
    async def bench_create_link():
        link_counter[0] += 1
        link = Link(
            id=f"lnk:{link_counter[0]}",
            source=alice_entity.id,
            target=f"ent:user{link_counter[0]}",
            kind=LinkKind.FOLLOW,
            data={},
            created_at=datetime.now(),
            tombstone=False,
            sig=alice_keys.sign(b"link"),
        )
        await storage.create_link(link)
    results['create_link'] = await bench_create_link()
    
    # Create some followers for query test
    for i in range(100):
        link = Link(
            id=f"lnk:follower{i}",
            source=f"ent:user{i}",
            target=alice_entity.id,
            kind=LinkKind.FOLLOW,
            data={},
            created_at=datetime.now(),
            tombstone=False,
            sig=b"",
        )
        await storage.create_link(link)
    
    @benchmark("Query followers (100 results)")
    async def bench_query_followers():
        await storage.get_followers(alice_entity.id)
    results['query_followers'] = await bench_query_followers()
    
    @benchmark("Query following")
    async def bench_query_following():
        await storage.get_following(alice_entity.id)
    results['query_following'] = await bench_query_following()
    
    # Test log operations with storage
    log_counter = [0]
    
    @benchmark("Append log event (with prev validation)")
    async def bench_append_log():
        log_counter[0] += 1
        prev = await storage.get_log_head(alice_entity.id)
        seq = await storage.get_log_seq(alice_entity.id) + 1
        
        event = LogEvent(
            id=generate_log_event_id(alice_entity.id, seq),
            actor=alice_entity.id,
            seq=seq,
            prev=prev,
            op=OpType.CREATE,
            object_type=ObjectType.CONTENT,
            object_id=f"content:log{log_counter[0]}",
            payload={"text": f"log post {log_counter[0]}"},
            ts=datetime.now(),
            sig=alice_keys.sign(b"event"),
            commitment=commitment_hash(
                f"event:{log_counter[0]}", 
                "post.create", 
                [], 
                {"text": f"log post {log_counter[0]}"}
            ),
        )
        await storage.append_log(event)
    results['append_log'] = await bench_append_log()
    
    @benchmark("Get events by actor")
    async def bench_get_events():
        await storage.get_events_by_actor(alice_entity.id)
    results['get_events'] = await bench_get_events()
    
    # =========================================================================
    print("\n[MODERATION LAYER - Attestations]")
    # =========================================================================
    
    att_counter = [0]
    @benchmark("Create attestation")
    async def bench_create_attestation():
        att_counter[0] += 1
        att = Attestation(
            id=f"att:{att_counter[0]}",
            issuer=alice_entity.id,
            subject=f"ent:subject{att_counter[0]}",
            type=AttestationType.TRUST,
            claim={"level": "high"},
            evidence=None,
            ts=datetime.now(),
            expires_at=None,
            revoked=False,
            sig=alice_keys.sign(b"attestation"),
        )
        await storage.put_attestation(att)
    results['create_attestation'] = await bench_create_attestation()
    
    # Create attestations for query test
    for i in range(50):
        att = Attestation(
            id=f"att:query{i}",
            issuer=f"ent:issuer{i}",
            subject=alice_entity.id,
            type=AttestationType.LABEL,
            claim={"label": f"label{i}"},
            evidence=None,
            ts=datetime.now(),
            expires_at=None,
            revoked=False,
            sig=b"",
        )
        await storage.put_attestation(att)
    
    @benchmark("Query attestations for subject (50 results)")
    async def bench_query_attestations():
        await storage.get_attestations_for(alice_entity.id)
    results['query_attestations'] = await bench_query_attestations()
    
    # =========================================================================
    print("\n[VIEW LAYER - View Execution]")
    # =========================================================================
    
    # Create events for view
    for i in range(100):
        prev = await storage.get_log_head(alice_entity.id)
        seq = await storage.get_log_seq(alice_entity.id) + 1
        event = LogEvent(
            id=generate_log_event_id(alice_entity.id, seq),
            actor=alice_entity.id,
            seq=seq,
            prev=prev,
            op=OpType.CREATE,
            object_type=ObjectType.CONTENT,
            object_id=f"content:view{i}",
            payload={"text": f"view post {i}"},
            ts=datetime.now(),
            sig=b"",
        )
        await storage.append_log(event)
    
    view_def = ViewDefinition(
        id="view:test",
        owner=alice_entity.id,
        version=1,
        sources=[Source(kind=SourceKind.ACTOR, actor_id=alice_entity.id)],
        filters=[],
        reducer=ReducerType.REVERSE_CHRONOLOGICAL,
        params={"limit": 50},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sig=b"",
    )
    await storage.put_view_definition(view_def)
    
    engine = ViewEngine(storage)
    
    @benchmark("Execute view (no cache)", iterations=20)
    async def bench_view_execute():
        await engine.execute(view_def, use_cache=False)
    results['view_execute'] = await bench_view_execute()
    
    # Warm cache
    await engine.execute(view_def, use_cache=True)
    
    @benchmark("Execute view (cached)")
    async def bench_view_cached():
        await engine.execute(view_def, use_cache=True)
    results['view_cached'] = await bench_view_cached()
    
    await storage.close()
    
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    print(f"""
MESH Protocol Performance (per operation):

  PRIVACY LAYER:
    Ed25519 sign+verify:      {results['sign_verify']:.3f}ms
    X25519+AES encrypt:       {results['encrypt']:.3f}ms
    Group key encrypt:        {results['group_encrypt']:.3f}ms
    commitment_hash:          {results['commitment_hash']:.3f}ms
    boundary_hash:            {results['boundary_hash']:.3f}ms

  SOCIAL LAYER:
    Generate entity_id:       {results['entity_id']:.3f}ms
    Sign object (JSON):       {results['sign_object']:.3f}ms

  INTEGRITY LAYER:
    Generate log_event_id:    {results['log_event_id']:.3f}ms
    Validate chain (100):     {results['validate_chain']:.3f}ms
    Append log event:         {results['append_log']:.3f}ms

  STORAGE LAYER:
    Create content:           {results['create_content']:.3f}ms
    Create link:              {results['create_link']:.3f}ms
    Query followers (100):    {results['query_followers']:.3f}ms

  MODERATION LAYER:
    Create attestation:       {results['create_attestation']:.3f}ms
    Query attestations (50):  {results['query_attestations']:.3f}ms

  VIEW LAYER:
    Execute view (no cache):  {results['view_execute']:.3f}ms
    Execute view (cached):    {results['view_cached']:.3f}ms
""")

    # Throughput estimates
    writes_per_sec = 1000 / results['create_content']
    print(f"""
THROUGHPUT ESTIMATES:
    Storage writes:           {writes_per_sec:,.0f}/sec
    Log appends:              {1000/results['append_log']:,.0f}/sec
    Queries (simple):         {1000/results['query_followers']:,.0f}/sec
    Views (uncached):         {1000/results['view_execute']:,.0f}/sec
    Views (cached):           {1000/results['view_cached']:,.0f}/sec
""")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_benchmarks())
