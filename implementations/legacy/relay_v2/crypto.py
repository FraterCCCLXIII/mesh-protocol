"""
Relay v2 Implementation - Cryptography Layer

Based on Relay_v2.md:
- §8: Identity with actor_id = multihash(SHA-256(pubkey))
- Ed25519 signatures
- Content-addressed events
"""

import hashlib
import json
import base64
import os
from dataclasses import dataclass
from typing import Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.exceptions import InvalidSignature


# =============================================================================
# ED25519 SIGNING
# =============================================================================

@dataclass
class SigningKeyPair:
    """Ed25519 signing key pair."""
    private_key: ed25519.Ed25519PrivateKey
    public_key: ed25519.Ed25519PublicKey
    
    @classmethod
    def generate(cls) -> 'SigningKeyPair':
        private_key = ed25519.Ed25519PrivateKey.generate()
        return cls(private_key=private_key, public_key=private_key.public_key())
    
    @classmethod
    def from_seed(cls, seed: bytes) -> 'SigningKeyPair':
        if len(seed) != 32:
            raise ValueError("Seed must be 32 bytes")
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
        return cls(private_key=private_key, public_key=private_key.public_key())
    
    def sign(self, message: bytes) -> bytes:
        return self.private_key.sign(message)
    
    def public_key_bytes(self) -> bytes:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    def private_key_bytes(self) -> bytes:
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )


def verify_signature(public_key_bytes: bytes, message: bytes, signature: bytes) -> bool:
    """Verify Ed25519 signature."""
    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature, message)
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


# =============================================================================
# IDENTIFIERS
# =============================================================================

def multihash_sha256(data: bytes) -> str:
    """Create multihash with SHA-256."""
    digest = hashlib.sha256(data).digest()
    return f"1220{digest.hex()}"


def generate_actor_id(public_key_bytes: bytes) -> str:
    """
    Generate actor_id from public key (§8).
    actor_id = multihash(SHA-256(pubkey))
    """
    mh = multihash_sha256(public_key_bytes)
    return mh


def content_hash(data: bytes) -> str:
    """Generate content hash for content-addressed objects."""
    return hashlib.sha256(data).hexdigest()


# =============================================================================
# CANONICAL JSON
# =============================================================================

def canonical_json(obj: dict) -> bytes:
    """Create canonical JSON bytes."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')


# =============================================================================
# SIGNED OBJECTS
# =============================================================================

def sign_object(obj: dict, signing_key: SigningKeyPair) -> dict:
    """Sign a JSON object."""
    obj_copy = {k: v for k, v in obj.items() if k != 'sig'}
    message = canonical_json(obj_copy)
    signature = signing_key.sign(message)
    obj_copy['sig'] = base64.b64encode(signature).decode()
    return obj_copy


def verify_object_signature(obj: dict, public_key_bytes: bytes) -> bool:
    """Verify a signed JSON object."""
    if 'sig' not in obj:
        return False
    try:
        signature = base64.b64decode(obj['sig'])
        obj_copy = {k: v for k, v in obj.items() if k != 'sig'}
        message = canonical_json(obj_copy)
        return verify_signature(public_key_bytes, message, signature)
    except Exception:
        return False


# =============================================================================
# EVENT ID GENERATION (Content-Addressed)
# =============================================================================

def generate_event_id(event: dict) -> str:
    """
    Generate event_id from event content.
    Events are content-addressed.
    """
    # Exclude sig from hash
    hashable = {k: v for k, v in event.items() if k != 'sig' and k != 'id'}
    canonical = canonical_json(hashable)
    return content_hash(canonical)


# =============================================================================
# X25519 ENCRYPTION
# =============================================================================

@dataclass
class EncryptionKeyPair:
    """X25519 encryption key pair."""
    private_key: x25519.X25519PrivateKey
    public_key: x25519.X25519PublicKey
    
    @classmethod
    def generate(cls) -> 'EncryptionKeyPair':
        private_key = x25519.X25519PrivateKey.generate()
        return cls(private_key=private_key, public_key=private_key.public_key())
    
    @classmethod
    def from_private_bytes(cls, private_bytes: bytes) -> 'EncryptionKeyPair':
        private_key = x25519.X25519PrivateKey.from_private_bytes(private_bytes)
        return cls(private_key=private_key, public_key=private_key.public_key())
    
    def derive_shared_secret(self, peer_public_key_bytes: bytes) -> bytes:
        peer_public_key = x25519.X25519PublicKey.from_public_bytes(peer_public_key_bytes)
        return self.private_key.exchange(peer_public_key)
    
    def public_key_bytes(self) -> bytes:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    def private_key_bytes(self) -> bytes:
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )


def derive_encryption_key(shared_secret: bytes, context: bytes = b"relay-v2-encryption") -> bytes:
    """Derive encryption key from shared secret using HKDF."""
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=context)
    return hkdf.derive(shared_secret)


def encrypt_aes_gcm(plaintext: bytes, key: bytes) -> Tuple[bytes, bytes]:
    """Encrypt with AES-256-GCM."""
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce, ciphertext


def decrypt_aes_gcm(nonce: bytes, ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt with AES-256-GCM."""
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


# =============================================================================
# BOUNDARY HASH (for deterministic verification)
# =============================================================================

def compute_boundary_hash(event_ids: list, source_heads: dict) -> str:
    """
    Compute boundary hash for deterministic verification.
    Same inputs MUST produce same output.
    """
    boundary = {
        "event_ids": sorted(event_ids),
        "source_heads": dict(sorted(source_heads.items())),
    }
    canonical = canonical_json(boundary)
    return hashlib.sha256(canonical).hexdigest()
