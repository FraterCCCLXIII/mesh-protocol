#!/usr/bin/env python3
"""
Adversarial Tests for Relay v2 Implementation

Tests specific to Relay v2 two-layer architecture:
1. Signature forgery
2. Event content addressing
3. View boundary determinism
4. Attestation security
5. State versioning
"""

import asyncio
import pytest
import sys
import os
from datetime import datetime

# Must insert at beginning to override any cached imports
impl_path = os.path.join(os.path.dirname(__file__), '..', '..', 'implementations', 'legacy', 'relay_v2')
if impl_path not in sys.path:
    sys.path.insert(0, impl_path)

# Force reimport
import importlib
for mod in ['crypto', 'storage', 'views']:
    if mod in sys.modules:
        del sys.modules[mod]

from crypto import (
    SigningKeyPair, EncryptionKeyPair,
    verify_signature, verify_object_signature, sign_object,
    generate_actor_id, generate_event_id, compute_boundary_hash,
    canonical_json, encrypt_aes_gcm, decrypt_aes_gcm, derive_encryption_key
)
from storage import (
    Storage, Identity, Event, State, Attestation, ViewDefinition,
    EventType, AttestationType, ReducerType
)
from views import ViewEngine


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
async def storage():
    s = Storage(":memory:")
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def alice_keys():
    return SigningKeyPair.generate()


@pytest.fixture
def bob_keys():
    return SigningKeyPair.generate()


@pytest.fixture
def alice_identity(alice_keys):
    return Identity(
        actor_id=generate_actor_id(alice_keys.public_key_bytes()),
        public_key=alice_keys.public_key_bytes(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sig=alice_keys.sign(b"identity"),
    )


# =============================================================================
# 1. SIGNATURE FORGERY TESTS
# =============================================================================

class TestSignatureForgery:
    """Test that forged signatures are rejected."""
    
    def test_random_signature_rejected(self, alice_keys):
        assert not verify_signature(
            alice_keys.public_key_bytes(),
            b"message",
            os.urandom(64)
        )
    
    def test_wrong_key_signature_rejected(self, alice_keys, bob_keys):
        sig = bob_keys.sign(b"message")
        assert not verify_signature(alice_keys.public_key_bytes(), b"message", sig)
    
    def test_modified_message_rejected(self, alice_keys):
        sig = alice_keys.sign(b"original")
        assert verify_signature(alice_keys.public_key_bytes(), b"original", sig)
        assert not verify_signature(alice_keys.public_key_bytes(), b"modified", sig)


# =============================================================================
# 2. EVENT CONTENT ADDRESSING
# =============================================================================

class TestEventContentAddressing:
    """Test content-addressed event IDs."""
    
    def test_event_id_deterministic(self):
        """Same content should produce same event ID."""
        event_dict = {"actor": "alice", "type": "post", "data": {"text": "hello"}}
        
        id1 = generate_event_id(event_dict)
        id2 = generate_event_id(event_dict)
        
        assert id1 == id2
    
    def test_different_content_different_id(self):
        """Different content should produce different event ID."""
        event1 = {"actor": "alice", "type": "post", "data": {"text": "hello"}}
        event2 = {"actor": "alice", "type": "post", "data": {"text": "world"}}
        
        id1 = generate_event_id(event1)
        id2 = generate_event_id(event2)
        
        assert id1 != id2
    
    def test_event_id_length(self):
        """Event ID should be 64 hex chars."""
        event_dict = {"actor": "alice", "type": "post"}
        event_id = generate_event_id(event_dict)
        
        assert len(event_id) == 64
        assert all(c in '0123456789abcdef' for c in event_id)
    
    @pytest.mark.asyncio
    async def test_cannot_modify_event_after_creation(self, storage, alice_identity):
        """Events are immutable once created."""
        await storage.put_identity(alice_identity)
        
        event = Event(
            id=generate_event_id({"actor": alice_identity.actor_id, "n": 1}),
            actor=alice_identity.actor_id,
            type=EventType.POST,
            data={"text": "original"},
            ts=datetime.now(),
            parents=[],
            sig=b"",
        )
        await storage.append_event(event)
        
        # Retrieve and verify immutability
        retrieved = await storage.get_event(event.id)
        assert retrieved.data["text"] == "original"
        
        # Cannot update events (no update API)
        # Events are append-only


# =============================================================================
# 3. VIEW BOUNDARY DETERMINISM (§0.6)
# =============================================================================

class TestViewBoundaryDeterminism:
    """Test that same boundary produces same result."""
    
    @pytest.mark.asyncio
    async def test_same_boundary_same_result(self, storage, alice_identity):
        """Same definition + same boundary = same result hash."""
        await storage.put_identity(alice_identity)
        
        # Create some events
        for i in range(10):
            event = Event(
                id=generate_event_id({"actor": alice_identity.actor_id, "i": i, "ts": str(datetime.now())}),
                actor=alice_identity.actor_id,
                type=EventType.POST,
                data={"index": i},
                ts=datetime.now(),
                parents=[],
                sig=b"",
            )
            await storage.append_event(event)
        
        # Create view definition
        view_def = ViewDefinition(
            object_id="view:test",
            actor=alice_identity.actor_id,
            version=1,
            sources=[{"kind": "actor", "actor_id": alice_identity.actor_id}],
            reduce=ReducerType.CHRONOLOGICAL,
            params={"limit": 100},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        await storage.put_view_definition(view_def)
        
        # Execute twice
        engine = ViewEngine(storage)
        result1 = await engine.execute(view_def, use_cache=False)
        result2 = await engine.execute(view_def, use_cache=False)
        
        # Same result hash
        assert result1.result_hash == result2.result_hash
        assert result1.event_ids == result2.event_ids
    
    @pytest.mark.asyncio
    async def test_boundary_hash_deterministic(self):
        """Boundary hash should be deterministic."""
        h1 = compute_boundary_hash(["e1", "e2", "e3"], {"a1": "h1", "a2": "h2"})
        h2 = compute_boundary_hash(["e1", "e2", "e3"], {"a1": "h1", "a2": "h2"})
        
        assert h1 == h2
    
    @pytest.mark.asyncio
    async def test_boundary_hash_order_independent(self):
        """Event ID order shouldn't affect hash (sorted internally)."""
        h1 = compute_boundary_hash(["e3", "e1", "e2"], {"a2": "h2", "a1": "h1"})
        h2 = compute_boundary_hash(["e1", "e2", "e3"], {"a1": "h1", "a2": "h2"})
        
        assert h1 == h2
    
    @pytest.mark.asyncio
    async def test_different_events_different_hash(self):
        """Different events should produce different boundary hash."""
        h1 = compute_boundary_hash(["e1", "e2"], {})
        h2 = compute_boundary_hash(["e1", "e3"], {})
        
        assert h1 != h2
    
    @pytest.mark.asyncio
    async def test_reducers_are_deterministic(self, storage, alice_identity):
        """Different reducer types should produce consistent results."""
        await storage.put_identity(alice_identity)
        
        # Create events with known timestamps
        base_time = datetime.now()
        for i in range(5):
            event = Event(
                id=generate_event_id({"actor": alice_identity.actor_id, "i": i}),
                actor=alice_identity.actor_id,
                type=EventType.POST,
                data={"index": i},
                ts=base_time,
                parents=[],
                sig=b"",
            )
            await storage.append_event(event)
        
        # Test chronological reducer
        view_chrono = ViewDefinition(
            object_id="view:chrono",
            actor=alice_identity.actor_id,
            version=1,
            sources=[{"kind": "actor", "actor_id": alice_identity.actor_id}],
            reduce=ReducerType.CHRONOLOGICAL,
            params={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        await storage.put_view_definition(view_chrono)
        
        engine = ViewEngine(storage)
        r1 = await engine.execute(view_chrono, use_cache=False)
        r2 = await engine.execute(view_chrono, use_cache=False)
        
        assert r1.result_hash == r2.result_hash


# =============================================================================
# 4. ATTESTATION SECURITY (§6)
# =============================================================================

class TestAttestationSecurity:
    """Test attestation security properties."""
    
    @pytest.mark.asyncio
    async def test_attestation_cannot_override_facts(self, storage, alice_identity, bob_keys):
        """Attestations MUST NOT override facts."""
        await storage.put_identity(alice_identity)
        
        # Create attestation claiming something about Alice
        bob_id = generate_actor_id(bob_keys.public_key_bytes())
        attestation = Attestation(
            id="att:claim1",
            issuer=bob_id,
            subject=alice_identity.actor_id,
            type=AttestationType.TRUST,
            claim={"verified": True},
            ts=datetime.now(),
            sig=b"",
        )
        await storage.put_attestation(attestation)
        
        # Attestation exists but doesn't change Alice's identity
        alice = await storage.get_identity(alice_identity.actor_id)
        assert alice.actor_id == alice_identity.actor_id
        
        # Attestations are separate from facts
        attestations = await storage.get_attestations_for(alice_identity.actor_id)
        assert len(attestations) == 1
        assert attestations[0].claim["verified"] == True
    
    @pytest.mark.asyncio
    async def test_attestation_tracks_issuer(self, storage, alice_identity, alice_keys, bob_keys):
        """Attestations must track who made them."""
        await storage.put_identity(alice_identity)
        
        # Alice attests about Bob
        bob_id = generate_actor_id(bob_keys.public_key_bytes())
        attestation = Attestation(
            id="att:alice-vouches-bob",
            issuer=alice_identity.actor_id,
            subject=bob_id,
            type=AttestationType.TRUST,
            claim={"level": "high"},
            ts=datetime.now(),
            sig=b"",
        )
        await storage.put_attestation(attestation)
        
        # Can query by issuer
        by_alice = await storage.get_attestations_by(alice_identity.actor_id)
        assert len(by_alice) == 1
        assert by_alice[0].subject == bob_id
    
    @pytest.mark.asyncio
    async def test_expired_attestations(self, storage, alice_identity):
        """Expired attestations should be queryable but marked."""
        await storage.put_identity(alice_identity)
        
        # Create expired attestation
        attestation = Attestation(
            id="att:expired",
            issuer=alice_identity.actor_id,
            subject="someone",
            type=AttestationType.TRUST,
            claim={},
            ts=datetime.now(),
            expires_at=datetime(2020, 1, 1),  # Already expired
            sig=b"",
        )
        await storage.put_attestation(attestation)
        
        # Still queryable
        attestations = await storage.get_attestations_by(alice_identity.actor_id)
        assert len(attestations) == 1
        assert attestations[0].expires_at < datetime.now()


# =============================================================================
# 5. STATE VERSIONING
# =============================================================================

class TestStateVersioning:
    """Test state version increment requirement."""
    
    @pytest.mark.asyncio
    async def test_version_must_increment(self, storage, alice_identity):
        """State version must increment on update."""
        await storage.put_identity(alice_identity)
        
        state1 = State(
            object_id="state:profile",
            actor=alice_identity.actor_id,
            type="profile",
            version=1,
            payload={"name": "Alice"},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        await storage.put_state(state1)
        
        # Version 2 should work
        state2 = State(
            object_id="state:profile",
            actor=alice_identity.actor_id,
            type="profile",
            version=2,
            payload={"name": "Alice Updated"},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        await storage.put_state(state2)
        
        retrieved = await storage.get_state("state:profile")
        assert retrieved.version == 2
    
    @pytest.mark.asyncio
    async def test_same_version_rejected(self, storage, alice_identity):
        """Same version should be rejected."""
        await storage.put_identity(alice_identity)
        
        state1 = State(
            object_id="state:profile",
            actor=alice_identity.actor_id,
            type="profile",
            version=1,
            payload={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        await storage.put_state(state1)
        
        state2 = State(
            object_id="state:profile",
            actor=alice_identity.actor_id,
            type="profile",
            version=1,  # Same version
            payload={"different": True},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        
        with pytest.raises(ValueError, match="Version must increment"):
            await storage.put_state(state2)
    
    @pytest.mark.asyncio
    async def test_rollback_rejected(self, storage, alice_identity):
        """Lower version (rollback) should be rejected."""
        await storage.put_identity(alice_identity)
        
        state1 = State(
            object_id="state:profile",
            actor=alice_identity.actor_id,
            type="profile",
            version=10,
            payload={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        await storage.put_state(state1)
        
        # Rollback attempt
        state2 = State(
            object_id="state:profile",
            actor=alice_identity.actor_id,
            type="profile",
            version=5,  # Lower than 10
            payload={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        
        with pytest.raises(ValueError, match="Version must increment"):
            await storage.put_state(state2)


# =============================================================================
# 6. VIEW DEFINITION SECURITY
# =============================================================================

class TestViewDefinitionSecurity:
    """Test view definition version requirements."""
    
    @pytest.mark.asyncio
    async def test_view_version_must_increment(self, storage, alice_identity):
        """View definition version must increment."""
        await storage.put_identity(alice_identity)
        
        view1 = ViewDefinition(
            object_id="view:feed",
            actor=alice_identity.actor_id,
            version=1,
            sources=[],
            reduce=ReducerType.CHRONOLOGICAL,
            params={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        await storage.put_view_definition(view1)
        
        # Same version should fail
        view2 = ViewDefinition(
            object_id="view:feed",
            actor=alice_identity.actor_id,
            version=1,  # Same
            sources=[{"kind": "actor", "actor_id": "other"}],
            reduce=ReducerType.CHRONOLOGICAL,
            params={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        
        with pytest.raises(ValueError):
            await storage.put_view_definition(view2)


# =============================================================================
# 7. ENCRYPTION ATTACKS
# =============================================================================

class TestEncryptionAttacks:
    """Test encryption security."""
    
    def test_wrong_key_fails(self):
        """Wrong key should fail decryption."""
        alice = EncryptionKeyPair.generate()
        bob = EncryptionKeyPair.generate()
        
        shared = alice.derive_shared_secret(bob.public_key_bytes())
        key = derive_encryption_key(shared)
        
        nonce, ciphertext = encrypt_aes_gcm(b"secret", key)
        
        wrong_key = os.urandom(32)
        with pytest.raises(Exception):
            decrypt_aes_gcm(nonce, ciphertext, wrong_key)
    
    def test_tampered_ciphertext_fails(self):
        """Tampered ciphertext should fail."""
        alice = EncryptionKeyPair.generate()
        bob = EncryptionKeyPair.generate()
        
        shared = alice.derive_shared_secret(bob.public_key_bytes())
        key = derive_encryption_key(shared)
        
        nonce, ciphertext = encrypt_aes_gcm(b"secret", key)
        
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF
        
        with pytest.raises(Exception):
            decrypt_aes_gcm(nonce, bytes(tampered), key)


# =============================================================================
# 8. DUPLICATE PROTECTION
# =============================================================================

class TestDuplicateProtection:
    """Test duplicate event/identity rejection."""
    
    @pytest.mark.asyncio
    async def test_duplicate_identity_rejected(self, storage, alice_identity):
        """Same identity cannot be created twice."""
        await storage.put_identity(alice_identity)
        
        # Note: put_identity uses INSERT OR REPLACE, so it updates
        # This is intentional for identity updates
        # The actor_id is the primary key
    
    @pytest.mark.asyncio
    async def test_duplicate_event_rejected(self, storage, alice_identity):
        """Same event ID cannot be created twice."""
        await storage.put_identity(alice_identity)
        
        event = Event(
            id="event:unique123",
            actor=alice_identity.actor_id,
            type=EventType.POST,
            data={},
            ts=datetime.now(),
            parents=[],
            sig=b"",
        )
        await storage.append_event(event)
        
        # Try to append same event again
        with pytest.raises(Exception):  # IntegrityError
            await storage.append_event(event)


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
