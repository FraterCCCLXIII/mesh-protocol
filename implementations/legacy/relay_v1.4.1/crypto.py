"""
Relay v1.4.1 Implementation - Cryptography Layer

Based on Relay_v1.4.1.md:
- §7: Ed25519 signatures
- §4.3: actor_id = multihash(SHA-256(pubkey))
- §4.3.1: channel_id from genesis
- §13.4: commitment_hash for action events
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
# ED25519 SIGNING (§7)
# =============================================================================

@dataclass
class SigningKeyPair:
    """Ed25519 signing key pair per §7."""
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
    """Verify Ed25519 signature per §7."""
    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature, message)
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


# =============================================================================
# MULTIHASH IDENTIFIERS (§4.2, §4.3)
# =============================================================================

def multihash_sha256(data: bytes) -> str:
    """
    Create multihash with SHA-256 (code 0x12, 32-byte digest).
    Returns hex string.
    """
    digest = hashlib.sha256(data).digest()
    # Multihash format: varint(hash_code) + varint(length) + digest
    # SHA-256: code=0x12, length=0x20 (32)
    return f"1220{digest.hex()}"


def generate_actor_id(public_key_bytes: bytes) -> str:
    """
    Generate actor_id from Ed25519 public key (§4.3).
    
    actor_id = relay:actor: + multihash(SHA-256(raw 32-byte pubkey))
    """
    mh = multihash_sha256(public_key_bytes)
    return f"relay:actor:{mh}"


def generate_channel_id(genesis: dict) -> str:
    """
    Generate channel_id from genesis document (§4.3.1).
    
    channel_id = relay:channel: + multihash(SHA-256(canonical JSON of genesis))
    """
    canonical = canonical_json(genesis)
    mh = multihash_sha256(canonical)
    return f"relay:channel:{mh}"


def generate_event_id(event: dict) -> str:
    """Generate event_id from event content."""
    canonical = canonical_json(event)
    mh = multihash_sha256(canonical)
    return f"relay:event:{mh[:48]}"  # Truncate for readability


def generate_object_id(obj: dict) -> str:
    """Generate object_id from content (§4.2)."""
    canonical = canonical_json(obj)
    mh = multihash_sha256(canonical)
    return f"relay:obj:{mh[:48]}"


# =============================================================================
# CANONICAL JSON (§4.1)
# =============================================================================

def canonical_json(obj: dict) -> bytes:
    """
    Create canonical JSON bytes per §4.1.
    
    - Sorted keys
    - No whitespace
    - UTF-8 encoded
    """
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')


# =============================================================================
# SIGNED OBJECTS
# =============================================================================

def sign_object(obj: dict, signing_key: SigningKeyPair) -> dict:
    """
    Sign a JSON object per §7/§10.
    
    Adds 'sig' field with base64-encoded Ed25519 signature.
    """
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
# COMMITMENT HASH (§13.4)
# =============================================================================

def compute_commitment_hash(request_event_id: str, action_id: str,
                            input_refs: list, agent_params: dict) -> str:
    """
    Compute commitment_hash for action.commit (§13.4, Appendix C).
    
    SHA-256 of canonical relay.action.commitment.v1 object.
    """
    commitment = {
        "kind": "relay.action.commitment.v1",
        "request_event_id": request_event_id,
        "action_id": action_id,
        "input_refs": sorted(input_refs),
        "agent_params": agent_params,
    }
    canonical = canonical_json(commitment)
    return hashlib.sha256(canonical).hexdigest()


# =============================================================================
# X25519 ENCRYPTION (for private actions §13.5)
# =============================================================================

@dataclass
class EncryptionKeyPair:
    """X25519 encryption key pair for private actions (§13.5)."""
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


def derive_encryption_key(shared_secret: bytes, context: bytes = b"relay-v1.4-encryption") -> bytes:
    """Derive 256-bit encryption key from shared secret using HKDF."""
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=context)
    return hkdf.derive(shared_secret)


def encrypt_aes_gcm(plaintext: bytes, key: bytes) -> Tuple[bytes, bytes]:
    """Encrypt with AES-256-GCM. Returns (nonce, ciphertext)."""
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce, ciphertext


def decrypt_aes_gcm(nonce: bytes, ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt with AES-256-GCM."""
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


# =============================================================================
# PRIVATE ACTION TAG (§13.5)
# =============================================================================

def compute_action_tag(target_actor_id: str, action_id: str, nonce: str) -> str:
    """
    Compute tag for private action addressing (§13.5).
    
    tag = SHA-256(canonical relay.action.tag.v1)
    """
    tag_obj = {
        "kind": "relay.action.tag.v1",
        "target": target_actor_id,
        "action_id": action_id,
        "nonce": nonce,
    }
    canonical = canonical_json(tag_obj)
    return hashlib.sha256(canonical).hexdigest()
