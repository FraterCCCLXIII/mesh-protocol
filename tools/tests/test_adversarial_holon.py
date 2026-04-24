#!/usr/bin/env python3
"""
Adversarial Tests for HOLON v4 Implementation

Tests the unhappy paths:
1. Signature forgery
2. Replay attacks
3. Invalid data injection
4. Resource exhaustion
5. Malformed input handling
"""

import asyncio
import pytest
import sys
import os
import random
import string
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'implementations', 'legacy', 'holon_v4'))

from crypto import (
    SigningKeyPair, EncryptionKeyPair, 
    verify_signature, verify_object_signature, sign_object,
    encrypt_for_recipient, decrypt_for_recipient,
    generate_entity_id, generate_content_id, generate_link_id,
    GroupKey, canonical_json
)
from storage import (
    Storage, Entity, Content, Link,
    EntityKind, ContentKind, LinkKind, AccessType
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
async def storage():
    """Create a fresh storage instance."""
    s = Storage(":memory:")  # Use in-memory SQLite
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def alice_keys():
    """Generate Alice's key pair."""
    return SigningKeyPair.generate()


@pytest.fixture
def bob_keys():
    """Generate Bob's key pair."""
    return SigningKeyPair.generate()


@pytest.fixture
def alice_entity(alice_keys):
    """Create Alice's entity."""
    enc = EncryptionKeyPair.generate()
    return Entity(
        id=generate_entity_id(alice_keys.public_key_bytes()),
        kind=EntityKind.USER,
        public_key=alice_keys.public_key_bytes(),
        encryption_key=enc.public_key_bytes(),
        handle="alice",
        profile={"name": "Alice"},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        sig=alice_keys.sign(b"entity"),
    )


# =============================================================================
# 1. SIGNATURE FORGERY TESTS
# =============================================================================

class TestSignatureForgery:
    """Test that forged signatures are rejected."""
    
    def test_random_signature_rejected(self, alice_keys):
        """Random bytes should not verify as valid signature."""
        message = b"authentic message"
        fake_sig = os.urandom(64)
        
        assert not verify_signature(
            alice_keys.public_key_bytes(), 
            message, 
            fake_sig
        )
    
    def test_wrong_key_signature_rejected(self, alice_keys, bob_keys):
        """Signature from wrong key should not verify."""
        message = b"authentic message"
        # Bob signs, but we verify against Alice's key
        bob_sig = bob_keys.sign(message)
        
        assert not verify_signature(
            alice_keys.public_key_bytes(),
            message,
            bob_sig
        )
    
    def test_modified_message_rejected(self, alice_keys):
        """Signature should not verify if message is modified."""
        original = b"original message"
        modified = b"modified message"
        sig = alice_keys.sign(original)
        
        assert verify_signature(alice_keys.public_key_bytes(), original, sig)
        assert not verify_signature(alice_keys.public_key_bytes(), modified, sig)
    
    def test_truncated_signature_rejected(self, alice_keys):
        """Truncated signature should not verify."""
        message = b"authentic message"
        sig = alice_keys.sign(message)
        truncated = sig[:32]  # Only half
        
        assert not verify_signature(
            alice_keys.public_key_bytes(),
            message,
            truncated
        )
    
    def test_extended_signature_rejected(self, alice_keys):
        """Extended signature should not verify."""
        message = b"authentic message"
        sig = alice_keys.sign(message)
        extended = sig + b"\x00" * 32
        
        assert not verify_signature(
            alice_keys.public_key_bytes(),
            message,
            extended
        )
    
    def test_object_signature_forgery(self, alice_keys, bob_keys):
        """Forged object signature should be rejected."""
        obj = {"type": "post", "text": "hello", "author": "alice"}
        
        # Sign with Alice's key
        signed = sign_object(obj, alice_keys)
        
        # Verify with Alice's key - should pass
        assert verify_object_signature(signed, alice_keys.public_key_bytes())
        
        # Verify with Bob's key - should fail
        assert not verify_object_signature(signed, bob_keys.public_key_bytes())
    
    def test_modified_object_rejected(self, alice_keys):
        """Modified object should fail verification."""
        obj = {"type": "post", "text": "hello"}
        signed = sign_object(obj, alice_keys)
        
        # Modify after signing
        signed["text"] = "HACKED"
        
        assert not verify_object_signature(signed, alice_keys.public_key_bytes())
    
    def test_missing_signature_rejected(self, alice_keys):
        """Object without signature should fail verification."""
        obj = {"type": "post", "text": "hello"}
        
        assert not verify_object_signature(obj, alice_keys.public_key_bytes())


# =============================================================================
# 2. REPLAY ATTACK TESTS
# =============================================================================

class TestReplayAttacks:
    """Test protection against replay attacks."""
    
    @pytest.mark.asyncio
    async def test_duplicate_entity_rejected(self, storage, alice_entity):
        """Same entity cannot be created twice."""
        await storage.create_entity(alice_entity)
        
        # Try to create again
        with pytest.raises(Exception):  # Should raise IntegrityError
            await storage.create_entity(alice_entity)
    
    @pytest.mark.asyncio
    async def test_duplicate_content_rejected(self, storage, alice_keys, alice_entity):
        """Same content ID cannot be created twice."""
        await storage.create_entity(alice_entity)
        
        content = Content(
            id="cnt:unique123",
            kind=ContentKind.POST,
            author=alice_entity.id,
            body={"text": "hello"},
            created_at=datetime.now(),
            context=None,
            reply_to=None,
            access=AccessType.PUBLIC,
            encrypted=False,
            encryption_metadata=None,
            sig=alice_keys.sign(b"content"),
        )
        
        await storage.create_content(content)
        
        # Replay the same content
        with pytest.raises(Exception):
            await storage.create_content(content)
    
    @pytest.mark.asyncio
    async def test_duplicate_link_rejected(self, storage, alice_keys, alice_entity):
        """Same link ID cannot be created twice."""
        await storage.create_entity(alice_entity)
        
        link = Link(
            id="lnk:follow123",
            kind=LinkKind.FOLLOW,
            source=alice_entity.id,
            target="ent:bob",
            data={},
            created_at=datetime.now(),
            tombstone=False,
            sig=alice_keys.sign(b"link"),
        )
        
        await storage.create_link(link)
        
        # Replay
        with pytest.raises(Exception):
            await storage.create_link(link)
    
    @pytest.mark.asyncio
    async def test_content_id_derived_from_content(self, alice_keys):
        """Content ID should be deterministically derived from content."""
        content_dict = {
            "type": "content",
            "kind": "post",
            "author": "alice",
            "body": {"text": "hello"},
            "created_at": "2026-01-01T00:00:00",
        }
        
        id1 = generate_content_id(content_dict)
        id2 = generate_content_id(content_dict)
        
        # Same content = same ID
        assert id1 == id2
        
        # Different content = different ID
        content_dict["body"]["text"] = "different"
        id3 = generate_content_id(content_dict)
        assert id1 != id3


# =============================================================================
# 3. INVALID DATA INJECTION
# =============================================================================

class TestInvalidDataInjection:
    """Test handling of malformed/malicious input."""
    
    def test_empty_public_key_rejected(self):
        """Empty public key should fail verification."""
        assert not verify_signature(b"", b"message", b"x" * 64)
    
    def test_short_public_key_rejected(self):
        """Short public key should fail verification."""
        assert not verify_signature(b"short", b"message", b"x" * 64)
    
    def test_null_bytes_in_message(self, alice_keys):
        """Null bytes in message should be handled correctly."""
        message = b"hello\x00world\x00test"
        sig = alice_keys.sign(message)
        
        assert verify_signature(alice_keys.public_key_bytes(), message, sig)
        
        # Truncation attack should fail
        truncated = b"hello"
        assert not verify_signature(alice_keys.public_key_bytes(), truncated, sig)
    
    def test_unicode_in_json(self, alice_keys):
        """Unicode in JSON objects should be handled correctly."""
        obj = {
            "type": "post",
            "text": "Hello 世界 🌍 مرحبا",
            "emoji": "👨‍👩‍👧‍👦",
        }
        
        signed = sign_object(obj, alice_keys)
        assert verify_object_signature(signed, alice_keys.public_key_bytes())
    
    def test_deeply_nested_json(self, alice_keys):
        """Deeply nested JSON should be handled."""
        obj = {"level": 0}
        current = obj
        for i in range(100):
            current["nested"] = {"level": i + 1}
            current = current["nested"]
        
        signed = sign_object(obj, alice_keys)
        assert verify_object_signature(signed, alice_keys.public_key_bytes())
    
    def test_large_json_object(self, alice_keys):
        """Large JSON objects should be handled."""
        obj = {
            "type": "post",
            "text": "x" * 100000,  # 100KB of text
        }
        
        signed = sign_object(obj, alice_keys)
        assert verify_object_signature(signed, alice_keys.public_key_bytes())
    
    def test_special_json_keys(self, alice_keys):
        """Special characters in JSON keys should be handled."""
        obj = {
            "normal": "value",
            "with space": "value",
            "with\ttab": "value",
            "with\nnewline": "value",
            "with\"quote": "value",
            "with\\backslash": "value",
        }
        
        signed = sign_object(obj, alice_keys)
        assert verify_object_signature(signed, alice_keys.public_key_bytes())


# =============================================================================
# 4. ENCRYPTION ATTACKS
# =============================================================================

class TestEncryptionAttacks:
    """Test encryption security properties."""
    
    def test_wrong_recipient_cannot_decrypt(self):
        """Only intended recipient can decrypt."""
        alice = EncryptionKeyPair.generate()
        bob = EncryptionKeyPair.generate()
        eve = EncryptionKeyPair.generate()
        
        # Alice encrypts for Bob
        plaintext = b"secret for Bob"
        encrypted = encrypt_for_recipient(plaintext, bob.public_key_bytes())
        
        # Bob can decrypt
        decrypted = decrypt_for_recipient(encrypted, bob.private_key_bytes())
        assert decrypted == plaintext
        
        # Eve cannot decrypt
        with pytest.raises(Exception):
            decrypt_for_recipient(encrypted, eve.private_key_bytes())
    
    def test_modified_ciphertext_rejected(self):
        """Modified ciphertext should fail decryption."""
        alice = EncryptionKeyPair.generate()
        bob = EncryptionKeyPair.generate()
        
        plaintext = b"secret message"
        encrypted = encrypt_for_recipient(plaintext, bob.public_key_bytes())
        
        # Modify ciphertext
        modified_ct = bytearray(encrypted.ciphertext)
        modified_ct[0] ^= 0xFF  # Flip bits
        encrypted.ciphertext = bytes(modified_ct)
        
        with pytest.raises(Exception):
            decrypt_for_recipient(encrypted, bob.private_key_bytes())
    
    def test_modified_nonce_rejected(self):
        """Modified nonce should fail decryption."""
        bob = EncryptionKeyPair.generate()
        
        plaintext = b"secret message"
        encrypted = encrypt_for_recipient(plaintext, bob.public_key_bytes())
        
        # Modify nonce
        modified_nonce = bytearray(encrypted.nonce)
        modified_nonce[0] ^= 0xFF
        encrypted.nonce = bytes(modified_nonce)
        
        with pytest.raises(Exception):
            decrypt_for_recipient(encrypted, bob.private_key_bytes())
    
    def test_modified_ephemeral_key_rejected(self):
        """Modified ephemeral key should fail decryption."""
        bob = EncryptionKeyPair.generate()
        
        plaintext = b"secret message"
        encrypted = encrypt_for_recipient(plaintext, bob.public_key_bytes())
        
        # Modify ephemeral public key
        modified_epk = bytearray(encrypted.ephemeral_public_key)
        modified_epk[0] ^= 0xFF
        encrypted.ephemeral_public_key = bytes(modified_epk)
        
        with pytest.raises(Exception):
            decrypt_for_recipient(encrypted, bob.private_key_bytes())
    
    def test_group_key_wrong_key(self):
        """Wrong group key should fail decryption."""
        gk1 = GroupKey.generate()
        gk2 = GroupKey.generate()
        
        nonce, ciphertext = gk1.encrypt(b"group secret")
        
        with pytest.raises(Exception):
            gk2.decrypt(nonce, ciphertext)


# =============================================================================
# 5. RESOURCE EXHAUSTION
# =============================================================================

class TestResourceExhaustion:
    """Test handling of resource exhaustion attempts."""
    
    @pytest.mark.asyncio
    async def test_many_entities(self, storage):
        """Storage should handle many entities."""
        keys = SigningKeyPair.generate()
        enc = EncryptionKeyPair.generate()
        
        for i in range(1000):
            entity = Entity(
                id=f"ent:user{i}",
                kind=EntityKind.USER,
                public_key=keys.public_key_bytes(),
                encryption_key=enc.public_key_bytes(),
                handle=f"user{i}",
                profile={},
                created_at=datetime.now(),
                updated_at=datetime.now(),
                sig=b"",
            )
            await storage.create_entity(entity)
        
        metrics = await storage.get_metrics()
        assert metrics['entity_count'] == 1000
    
    @pytest.mark.asyncio
    async def test_many_links_same_target(self, storage, alice_keys):
        """Handle many links to same target."""
        # Create target entity
        enc = EncryptionKeyPair.generate()
        target = Entity(
            id="ent:popular",
            kind=EntityKind.USER,
            public_key=alice_keys.public_key_bytes(),
            encryption_key=enc.public_key_bytes(),
            handle="popular",
            profile={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sig=b"",
        )
        await storage.create_entity(target)
        
        # Many followers
        for i in range(1000):
            link = Link(
                id=f"lnk:follow{i}",
                kind=LinkKind.FOLLOW,
                source=f"ent:user{i}",
                target="ent:popular",
                data={},
                created_at=datetime.now(),
                tombstone=False,
                sig=b"",
            )
            await storage.create_link(link)
        
        followers = await storage.get_followers("ent:popular")
        assert len(followers) == 1000
    
    def test_many_key_generations(self):
        """Key generation should not leak resources."""
        import gc
        
        gc.collect()
        
        for _ in range(10000):
            SigningKeyPair.generate()
            EncryptionKeyPair.generate()
        
        gc.collect()
        # If we get here without OOM, test passes


# =============================================================================
# 6. EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_message_signature(self, alice_keys):
        """Empty message should be signable."""
        sig = alice_keys.sign(b"")
        assert verify_signature(alice_keys.public_key_bytes(), b"", sig)
    
    def test_empty_json_object(self, alice_keys):
        """Empty JSON object should be signable."""
        signed = sign_object({}, alice_keys)
        assert verify_object_signature(signed, alice_keys.public_key_bytes())
    
    def test_json_with_none_values(self, alice_keys):
        """JSON with None values should be handled."""
        obj = {"key": None, "nested": {"also": None}}
        signed = sign_object(obj, alice_keys)
        assert verify_object_signature(signed, alice_keys.public_key_bytes())
    
    def test_json_with_boolean_values(self, alice_keys):
        """JSON with boolean values should be handled."""
        obj = {"true": True, "false": False}
        signed = sign_object(obj, alice_keys)
        assert verify_object_signature(signed, alice_keys.public_key_bytes())
    
    def test_json_with_numeric_values(self, alice_keys):
        """JSON with various numeric values should be handled."""
        obj = {
            "int": 42,
            "negative": -42,
            "float": 3.14159,
            "scientific": 1e10,
            "zero": 0,
        }
        signed = sign_object(obj, alice_keys)
        assert verify_object_signature(signed, alice_keys.public_key_bytes())
    
    def test_canonical_json_deterministic(self):
        """Canonical JSON should be deterministic regardless of key order."""
        obj1 = {"b": 2, "a": 1, "c": 3}
        obj2 = {"a": 1, "b": 2, "c": 3}
        obj3 = {"c": 3, "a": 1, "b": 2}
        
        assert canonical_json(obj1) == canonical_json(obj2) == canonical_json(obj3)


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
