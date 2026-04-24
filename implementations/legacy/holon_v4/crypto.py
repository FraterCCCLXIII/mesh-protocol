"""
HOLON v4 Implementation - Cryptography Layer

Real cryptographic operations:
- Ed25519 signatures (identity, signing)
- X25519 key exchange (encryption key derivation)
- AES-256-GCM encryption (content encryption)
"""

import os
import json
import hashlib
import base64
from dataclasses import dataclass
from typing import Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.exceptions import InvalidSignature


# =============================================================================
# ED25519 SIGNING (Identity & Signatures)
# =============================================================================

@dataclass
class SigningKeyPair:
    """Ed25519 signing key pair."""
    private_key: ed25519.Ed25519PrivateKey
    public_key: ed25519.Ed25519PublicKey
    
    @classmethod
    def generate(cls) -> 'SigningKeyPair':
        """Generate a new Ed25519 key pair."""
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        return cls(private_key=private_key, public_key=public_key)
    
    @classmethod
    def from_seed(cls, seed: bytes) -> 'SigningKeyPair':
        """Derive key pair from 32-byte seed (deterministic)."""
        if len(seed) != 32:
            raise ValueError("Seed must be 32 bytes")
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
        public_key = private_key.public_key()
        return cls(private_key=private_key, public_key=public_key)
    
    def sign(self, message: bytes) -> bytes:
        """Sign a message, returns 64-byte signature."""
        return self.private_key.sign(message)
    
    def public_key_bytes(self) -> bytes:
        """Get raw 32-byte public key."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    def private_key_bytes(self) -> bytes:
        """Get raw 32-byte private key (seed)."""
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )


def verify_signature(public_key_bytes: bytes, message: bytes, signature: bytes) -> bool:
    """Verify an Ed25519 signature."""
    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature, message)
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


def generate_entity_id(public_key_bytes: bytes) -> str:
    """
    Generate entity ID from public key.
    entity_id = ent: + base58(sha256(pubkey)[:16])
    """
    hash_bytes = hashlib.sha256(public_key_bytes).digest()[:16]
    return f"ent:{base64.urlsafe_b64encode(hash_bytes).decode().rstrip('=')}"


# =============================================================================
# X25519 KEY EXCHANGE (Encryption Key Derivation)
# =============================================================================

@dataclass
class EncryptionKeyPair:
    """X25519 encryption key pair for key exchange."""
    private_key: x25519.X25519PrivateKey
    public_key: x25519.X25519PublicKey
    
    @classmethod
    def generate(cls) -> 'EncryptionKeyPair':
        """Generate a new X25519 key pair."""
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()
        return cls(private_key=private_key, public_key=public_key)
    
    @classmethod
    def from_private_bytes(cls, private_bytes: bytes) -> 'EncryptionKeyPair':
        """Load from raw private key bytes."""
        private_key = x25519.X25519PrivateKey.from_private_bytes(private_bytes)
        public_key = private_key.public_key()
        return cls(private_key=private_key, public_key=public_key)
    
    def derive_shared_secret(self, peer_public_key_bytes: bytes) -> bytes:
        """Derive shared secret with peer's public key."""
        peer_public_key = x25519.X25519PublicKey.from_public_bytes(peer_public_key_bytes)
        return self.private_key.exchange(peer_public_key)
    
    def public_key_bytes(self) -> bytes:
        """Get raw 32-byte public key."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    def private_key_bytes(self) -> bytes:
        """Get raw 32-byte private key."""
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )


def derive_encryption_key(shared_secret: bytes, context: bytes = b"holon-v4-encryption") -> bytes:
    """Derive a 256-bit encryption key from shared secret using HKDF."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=context,
    )
    return hkdf.derive(shared_secret)


# =============================================================================
# AES-256-GCM ENCRYPTION (Content Encryption)
# =============================================================================

def encrypt_content(plaintext: bytes, key: bytes) -> Tuple[bytes, bytes]:
    """
    Encrypt content with AES-256-GCM.
    
    Returns: (nonce, ciphertext) where ciphertext includes auth tag.
    """
    if len(key) != 32:
        raise ValueError("Key must be 32 bytes for AES-256")
    
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    return nonce, ciphertext


def decrypt_content(nonce: bytes, ciphertext: bytes, key: bytes) -> bytes:
    """
    Decrypt content with AES-256-GCM.
    
    Raises exception if authentication fails.
    """
    if len(key) != 32:
        raise ValueError("Key must be 32 bytes for AES-256")
    
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


# =============================================================================
# CONTENT KEY MANAGEMENT
# =============================================================================

@dataclass
class EncryptedContent:
    """Encrypted content with metadata for decryption."""
    nonce: bytes
    ciphertext: bytes
    ephemeral_public_key: bytes  # For recipient to derive shared secret
    
    def to_dict(self) -> dict:
        return {
            "nonce": base64.b64encode(self.nonce).decode(),
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "ephemeral_public_key": base64.b64encode(self.ephemeral_public_key).decode(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'EncryptedContent':
        return cls(
            nonce=base64.b64decode(data["nonce"]),
            ciphertext=base64.b64decode(data["ciphertext"]),
            ephemeral_public_key=base64.b64decode(data["ephemeral_public_key"]),
        )


def encrypt_for_recipient(plaintext: bytes, recipient_public_key: bytes) -> EncryptedContent:
    """
    Encrypt content for a specific recipient using ECDH + AES-GCM.
    
    1. Generate ephemeral X25519 key pair
    2. Derive shared secret with recipient's public key
    3. Derive encryption key from shared secret
    4. Encrypt with AES-256-GCM
    """
    # Generate ephemeral key pair
    ephemeral = EncryptionKeyPair.generate()
    
    # Derive shared secret
    shared_secret = ephemeral.derive_shared_secret(recipient_public_key)
    
    # Derive encryption key
    encryption_key = derive_encryption_key(shared_secret)
    
    # Encrypt
    nonce, ciphertext = encrypt_content(plaintext, encryption_key)
    
    return EncryptedContent(
        nonce=nonce,
        ciphertext=ciphertext,
        ephemeral_public_key=ephemeral.public_key_bytes(),
    )


def decrypt_for_recipient(encrypted: EncryptedContent, recipient_private_key: bytes) -> bytes:
    """
    Decrypt content encrypted for this recipient.
    
    1. Derive shared secret from ephemeral public key
    2. Derive encryption key
    3. Decrypt with AES-256-GCM
    """
    # Load recipient's key pair
    recipient = EncryptionKeyPair.from_private_bytes(recipient_private_key)
    
    # Derive shared secret
    shared_secret = recipient.derive_shared_secret(encrypted.ephemeral_public_key)
    
    # Derive encryption key
    encryption_key = derive_encryption_key(shared_secret)
    
    # Decrypt
    return decrypt_content(encrypted.nonce, encrypted.ciphertext, encryption_key)


# =============================================================================
# GROUP ENCRYPTION
# =============================================================================

@dataclass
class GroupKey:
    """Symmetric key for group encryption."""
    key: bytes
    key_id: str
    created_at: float
    
    @classmethod
    def generate(cls) -> 'GroupKey':
        """Generate a new random group key."""
        key = os.urandom(32)
        key_id = base64.urlsafe_b64encode(hashlib.sha256(key).digest()[:8]).decode().rstrip('=')
        import time
        return cls(key=key, key_id=key_id, created_at=time.time())
    
    def encrypt(self, plaintext: bytes) -> Tuple[bytes, bytes]:
        """Encrypt with this group key."""
        return encrypt_content(plaintext, self.key)
    
    def decrypt(self, nonce: bytes, ciphertext: bytes) -> bytes:
        """Decrypt with this group key."""
        return decrypt_content(nonce, ciphertext, self.key)


def wrap_group_key_for_member(group_key: GroupKey, member_public_key: bytes) -> EncryptedContent:
    """Encrypt the group key for a specific member."""
    return encrypt_for_recipient(group_key.key, member_public_key)


def unwrap_group_key(encrypted_key: EncryptedContent, member_private_key: bytes, 
                     key_id: str, created_at: float) -> GroupKey:
    """Decrypt a wrapped group key."""
    key_bytes = decrypt_for_recipient(encrypted_key, member_private_key)
    return GroupKey(key=key_bytes, key_id=key_id, created_at=created_at)


# =============================================================================
# SIGNED OBJECTS
# =============================================================================

def canonical_json(obj: dict) -> bytes:
    """Create canonical JSON bytes for signing."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')


def sign_object(obj: dict, signing_key: SigningKeyPair) -> dict:
    """
    Sign a JSON object.
    
    Adds 'sig' field with base64-encoded Ed25519 signature.
    """
    # Remove existing signature if present
    obj_copy = {k: v for k, v in obj.items() if k != 'sig'}
    
    # Create canonical bytes
    message = canonical_json(obj_copy)
    
    # Sign
    signature = signing_key.sign(message)
    
    # Add signature
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
# CONTENT HASHING
# =============================================================================

def content_hash(content: bytes) -> str:
    """Generate content-addressed hash."""
    hash_bytes = hashlib.sha256(content).digest()
    return base64.urlsafe_b64encode(hash_bytes[:16]).decode().rstrip('=')


def generate_content_id(content_dict: dict) -> str:
    """Generate content ID from content."""
    canonical = canonical_json(content_dict)
    return f"cnt:{content_hash(canonical)}"


def generate_link_id(link_dict: dict) -> str:
    """Generate link ID from link."""
    canonical = canonical_json(link_dict)
    return f"lnk:{content_hash(canonical)}"
