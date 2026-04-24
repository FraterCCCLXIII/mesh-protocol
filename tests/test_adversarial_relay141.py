#!/usr/bin/env python3
"""
Adversarial Tests for Relay v1.4.1 Implementation

Tests specific to Relay v1.4.1:
1. Signature forgery
2. Prev chain validation
3. Log append attacks
4. Commitment hash verification
5. Channel security
"""

import asyncio
import pytest
import sys
import os
from datetime import datetime

# Must insert at beginning to override any cached imports
impl_path = os.path.join(os.path.dirname(__file__), '..', 'relay_v1.4.1_impl')
if impl_path not in sys.path:
    sys.path.insert(0, impl_path)

# Force reimport
import importlib
if 'crypto' in sys.modules:
    del sys.modules['crypto']
if 'storage' in sys.modules:
    del sys.modules['storage']

from crypto import (
    SigningKeyPair, EncryptionKeyPair,
    verify_signature, verify_object_signature, sign_object,
    generate_actor_id, generate_channel_id, generate_event_id,
    compute_commitment_hash, canonical_json,
    encrypt_aes_gcm, decrypt_aes_gcm, derive_encryption_key
)
from storage import (
    Storage, Identity, LogEvent, StateObject, LogEventType,
    ChannelGenesis
)


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
    enc = EncryptionKeyPair.generate()
    return Identity(
        actor_id=generate_actor_id(alice_keys.public_key_bytes()),
        public_key=alice_keys.public_key_bytes(),
        encryption_key=enc.public_key_bytes(),
        display_name="Alice",
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
        """Random bytes should not verify."""
        assert not verify_signature(
            alice_keys.public_key_bytes(),
            b"message",
            os.urandom(64)
        )
    
    def test_wrong_key_signature_rejected(self, alice_keys, bob_keys):
        """Signature from wrong key should fail."""
        sig = bob_keys.sign(b"message")
        assert not verify_signature(alice_keys.public_key_bytes(), b"message", sig)
    
    def test_modified_message_rejected(self, alice_keys):
        """Modified message should fail verification."""
        sig = alice_keys.sign(b"original")
        assert not verify_signature(alice_keys.public_key_bytes(), b"modified", sig)


# =============================================================================
# 2. PREV CHAIN VALIDATION (§10)
# =============================================================================

class TestPrevChainValidation:
    """Test append-only log with prev chain."""
    
    @pytest.mark.asyncio
    async def test_first_event_must_have_null_prev(self, storage, alice_identity, alice_keys):
        """First event must have prev=null."""
        await storage.put_identity(alice_identity)
        
        # First event with null prev - should work
        event1 = LogEvent(
            id="relay:event:1",
            actor=alice_identity.actor_id,
            type=LogEventType.POST,
            data={"text": "first"},
            ts=datetime.now(),
            prev=None,
            sig=alice_keys.sign(b"event1"),
        )
        await storage.append_log(event1)
        
        head = await storage.get_log_head(alice_identity.actor_id)
        assert head == event1.id
    
    @pytest.mark.asyncio
    async def test_second_event_must_reference_first(self, storage, alice_identity, alice_keys):
        """Second event must have prev pointing to first."""
        await storage.put_identity(alice_identity)
        
        event1 = LogEvent(
            id="relay:event:1",
            actor=alice_identity.actor_id,
            type=LogEventType.POST,
            data={},
            ts=datetime.now(),
            prev=None,
            sig=b"",
        )
        await storage.append_log(event1)
        
        # Correct prev chain
        event2 = LogEvent(
            id="relay:event:2",
            actor=alice_identity.actor_id,
            type=LogEventType.POST,
            data={},
            ts=datetime.now(),
            prev=event1.id,
            sig=b"",
        )
        await storage.append_log(event2)
        
        head = await storage.get_log_head(alice_identity.actor_id)
        assert head == event2.id
    
    @pytest.mark.asyncio
    async def test_wrong_prev_rejected(self, storage, alice_identity, alice_keys):
        """Event with wrong prev should be rejected."""
        await storage.put_identity(alice_identity)
        
        event1 = LogEvent(
            id="relay:event:1",
            actor=alice_identity.actor_id,
            type=LogEventType.POST,
            data={},
            ts=datetime.now(),
            prev=None,
            sig=b"",
        )
        await storage.append_log(event1)
        
        # Wrong prev - should be rejected
        event2 = LogEvent(
            id="relay:event:2",
            actor=alice_identity.actor_id,
            type=LogEventType.POST,
            data={},
            ts=datetime.now(),
            prev="relay:event:WRONG",  # Wrong!
            sig=b"",
        )
        
        with pytest.raises(ValueError, match="Invalid prev"):
            await storage.append_log(event2)
    
    @pytest.mark.asyncio
    async def test_null_prev_after_events_rejected(self, storage, alice_identity):
        """Event with null prev after first event should be rejected."""
        await storage.put_identity(alice_identity)
        
        event1 = LogEvent(
            id="relay:event:1",
            actor=alice_identity.actor_id,
            type=LogEventType.POST,
            data={},
            ts=datetime.now(),
            prev=None,
            sig=b"",
        )
        await storage.append_log(event1)
        
        # Null prev after first event - should be rejected
        event2 = LogEvent(
            id="relay:event:2",
            actor=alice_identity.actor_id,
            type=LogEventType.POST,
            data={},
            ts=datetime.now(),
            prev=None,  # Should be event1.id
            sig=b"",
        )
        
        with pytest.raises(ValueError, match="Invalid prev"):
            await storage.append_log(event2)
    
    @pytest.mark.asyncio
    async def test_fork_attempt_rejected(self, storage, alice_identity):
        """Attempt to create fork should be rejected."""
        await storage.put_identity(alice_identity)
        
        event1 = LogEvent(
            id="relay:event:1",
            actor=alice_identity.actor_id,
            type=LogEventType.POST,
            data={},
            ts=datetime.now(),
            prev=None,
            sig=b"",
        )
        await storage.append_log(event1)
        
        event2 = LogEvent(
            id="relay:event:2",
            actor=alice_identity.actor_id,
            type=LogEventType.POST,
            data={},
            ts=datetime.now(),
            prev=event1.id,
            sig=b"",
        )
        await storage.append_log(event2)
        
        # Try to fork from event1 (not the head)
        fork_event = LogEvent(
            id="relay:event:fork",
            actor=alice_identity.actor_id,
            type=LogEventType.POST,
            data={},
            ts=datetime.now(),
            prev=event1.id,  # Points to old event, not head
            sig=b"",
        )
        
        with pytest.raises(ValueError, match="Invalid prev"):
            await storage.append_log(fork_event)


# =============================================================================
# 3. COMMITMENT HASH VERIFICATION (§13.4)
# =============================================================================

class TestCommitmentHash:
    """Test commitment_hash for action verification."""
    
    def test_commitment_hash_deterministic(self):
        """Same inputs should produce same hash."""
        h1 = compute_commitment_hash("event:123", "relay.action.v1", ["ref1"], {"k": 1})
        h2 = compute_commitment_hash("event:123", "relay.action.v1", ["ref1"], {"k": 1})
        assert h1 == h2
    
    def test_commitment_hash_different_inputs(self):
        """Different inputs should produce different hash."""
        h1 = compute_commitment_hash("event:123", "relay.action.v1", ["ref1"], {"k": 1})
        h2 = compute_commitment_hash("event:456", "relay.action.v1", ["ref1"], {"k": 1})
        assert h1 != h2
    
    def test_commitment_hash_input_order_matters(self):
        """Input refs should be sorted for determinism."""
        h1 = compute_commitment_hash("event:123", "action", ["a", "b", "c"], {})
        h2 = compute_commitment_hash("event:123", "action", ["c", "b", "a"], {})
        # Should be same because inputs are sorted internally
        assert h1 == h2
    
    def test_commitment_hash_length(self):
        """Commitment hash should be 64 hex chars (SHA-256)."""
        h = compute_commitment_hash("event:123", "action", [], {})
        assert len(h) == 64
        assert all(c in '0123456789abcdef' for c in h)


# =============================================================================
# 4. STATE VERSION VALIDATION (§11)
# =============================================================================

class TestStateVersioning:
    """Test state object versioning."""
    
    @pytest.mark.asyncio
    async def test_version_must_increment(self, storage, alice_identity):
        """State version must increment on update."""
        await storage.put_identity(alice_identity)
        
        state1 = StateObject(
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
        
        # Update with higher version - should work
        state2 = StateObject(
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
        
        state1 = StateObject(
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
        
        # Same version - should be rejected
        state2 = StateObject(
            object_id="state:profile",
            actor=alice_identity.actor_id,
            type="profile",
            version=1,
            payload={"name": "Different"},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        
        with pytest.raises(ValueError, match="Version must increment"):
            await storage.put_state(state2)
    
    @pytest.mark.asyncio
    async def test_lower_version_rejected(self, storage, alice_identity):
        """Lower version should be rejected."""
        await storage.put_identity(alice_identity)
        
        state1 = StateObject(
            object_id="state:profile",
            actor=alice_identity.actor_id,
            type="profile",
            version=5,
            payload={"name": "Alice"},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        await storage.put_state(state1)
        
        # Lower version - should be rejected
        state2 = StateObject(
            object_id="state:profile",
            actor=alice_identity.actor_id,
            type="profile",
            version=3,  # Lower than 5
            payload={"name": "Rollback attempt"},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        
        with pytest.raises(ValueError, match="Version must increment"):
            await storage.put_state(state2)


# =============================================================================
# 5. CHANNEL SECURITY
# =============================================================================

class TestChannelSecurity:
    """Test channel genesis and membership."""
    
    @pytest.mark.asyncio
    async def test_channel_id_from_genesis(self, storage, alice_identity):
        """Channel ID should be derived from genesis."""
        await storage.put_identity(alice_identity)
        
        genesis = ChannelGenesis(
            owner_actor_id=alice_identity.actor_id,
            name="test-channel",
            created_at=datetime.now(),
        )
        
        channel = await storage.create_channel(genesis)
        
        # Channel ID should be deterministic
        expected_id = generate_channel_id(genesis.to_dict())
        assert channel.channel_id == expected_id
    
    @pytest.mark.asyncio
    async def test_different_genesis_different_id(self, storage, alice_identity):
        """Different genesis should produce different channel ID."""
        await storage.put_identity(alice_identity)
        
        genesis1 = ChannelGenesis(
            owner_actor_id=alice_identity.actor_id,
            name="channel-1",
            created_at=datetime.now(),
        )
        
        genesis2 = ChannelGenesis(
            owner_actor_id=alice_identity.actor_id,
            name="channel-2",
            created_at=datetime.now(),
        )
        
        channel1 = await storage.create_channel(genesis1)
        channel2 = await storage.create_channel(genesis2)
        
        assert channel1.channel_id != channel2.channel_id
    
    @pytest.mark.asyncio
    async def test_owner_is_first_member(self, storage, alice_identity):
        """Channel owner should be first member."""
        await storage.put_identity(alice_identity)
        
        genesis = ChannelGenesis(
            owner_actor_id=alice_identity.actor_id,
            name="my-channel",
            created_at=datetime.now(),
        )
        
        channel = await storage.create_channel(genesis)
        
        assert alice_identity.actor_id in channel.members
        assert channel.owner == alice_identity.actor_id


# =============================================================================
# 6. ACTOR ID VERIFICATION
# =============================================================================

class TestActorIdVerification:
    """Test actor_id derivation from public key."""
    
    def test_actor_id_deterministic(self, alice_keys):
        """Same public key should produce same actor_id."""
        id1 = generate_actor_id(alice_keys.public_key_bytes())
        id2 = generate_actor_id(alice_keys.public_key_bytes())
        assert id1 == id2
    
    def test_different_keys_different_ids(self, alice_keys, bob_keys):
        """Different keys should produce different actor_ids."""
        alice_id = generate_actor_id(alice_keys.public_key_bytes())
        bob_id = generate_actor_id(bob_keys.public_key_bytes())
        assert alice_id != bob_id
    
    def test_actor_id_format(self, alice_keys):
        """Actor ID should have correct format."""
        actor_id = generate_actor_id(alice_keys.public_key_bytes())
        
        # Should start with relay:actor:
        assert actor_id.startswith("relay:actor:")
        
        # Should contain multihash (1220 = SHA-256)
        assert "1220" in actor_id


# =============================================================================
# 7. ENCRYPTION ATTACKS
# =============================================================================

class TestEncryptionAttacks:
    """Test encryption security."""
    
    def test_wrong_key_fails_decryption(self):
        """Wrong key should fail decryption."""
        alice = EncryptionKeyPair.generate()
        bob = EncryptionKeyPair.generate()
        
        shared_alice = alice.derive_shared_secret(bob.public_key_bytes())
        key_alice = derive_encryption_key(shared_alice)
        
        nonce, ciphertext = encrypt_aes_gcm(b"secret", key_alice)
        
        # Wrong key
        wrong_key = os.urandom(32)
        with pytest.raises(Exception):
            decrypt_aes_gcm(nonce, ciphertext, wrong_key)
    
    def test_modified_ciphertext_fails(self):
        """Modified ciphertext should fail decryption."""
        alice = EncryptionKeyPair.generate()
        bob = EncryptionKeyPair.generate()
        
        shared = alice.derive_shared_secret(bob.public_key_bytes())
        key = derive_encryption_key(shared)
        
        nonce, ciphertext = encrypt_aes_gcm(b"secret", key)
        
        # Modify ciphertext
        modified = bytearray(ciphertext)
        modified[0] ^= 0xFF
        
        with pytest.raises(Exception):
            decrypt_aes_gcm(nonce, bytes(modified), key)


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
