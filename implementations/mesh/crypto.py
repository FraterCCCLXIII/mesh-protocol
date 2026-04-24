"""
MESH Protocol - Privacy Layer
Ed25519 signatures, X25519 key exchange, AES-256-GCM encryption
"""

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def canonical_json(obj: dict) -> bytes:
    """Deterministic JSON serialization."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')


def sha256(data: bytes) -> str:
    """SHA-256 hash as hex string."""
    return hashlib.sha256(data).hexdigest()


class SigningKeyPair:
    """Ed25519 signing key pair."""
    
    def __init__(self, private_key: Ed25519PrivateKey):
        self._private = private_key
        self._public = private_key.public_key()
    
    @classmethod
    def generate(cls) -> 'SigningKeyPair':
        return cls(Ed25519PrivateKey.generate())
    
    @classmethod
    def from_seed(cls, seed: bytes) -> 'SigningKeyPair':
        return cls(Ed25519PrivateKey.from_private_bytes(seed[:32]))
    
    def sign(self, message: bytes) -> bytes:
        return self._private.sign(message)
    
    def public_key_bytes(self) -> bytes:
        return self._public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    def private_key_bytes(self) -> bytes:
        return self._private.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )


def verify_signature(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Verify Ed25519 signature."""
    if len(public_key) != 32 or len(signature) != 64:
        return False
    try:
        pk = Ed25519PublicKey.from_public_bytes(public_key)
        pk.verify(signature, message)
        return True
    except Exception:
        return False


def sign_object(obj: dict, keypair: SigningKeyPair) -> dict:
    """Sign a dictionary object."""
    obj_copy = {k: v for k, v in obj.items() if k != 'sig'}
    sig = keypair.sign(canonical_json(obj_copy))
    return {**obj_copy, 'sig': sig.hex()}


def verify_object_signature(obj: dict, public_key: bytes) -> bool:
    """Verify object signature."""
    if 'sig' not in obj:
        return False
    try:
        sig = bytes.fromhex(obj['sig'])
        obj_copy = {k: v for k, v in obj.items() if k != 'sig'}
        return verify_signature(public_key, canonical_json(obj_copy), sig)
    except Exception:
        return False


class EncryptionKeyPair:
    """X25519 key exchange pair."""
    
    def __init__(self, private_key: X25519PrivateKey):
        self._private = private_key
        self._public = private_key.public_key()
    
    @classmethod
    def generate(cls) -> 'EncryptionKeyPair':
        return cls(X25519PrivateKey.generate())
    
    def public_key_bytes(self) -> bytes:
        return self._public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    def private_key_bytes(self) -> bytes:
        return self._private.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
    
    def derive_shared_secret(self, peer_public_key: bytes) -> bytes:
        peer_pk = X25519PublicKey.from_public_bytes(peer_public_key)
        return self._private.exchange(peer_pk)


def derive_encryption_key(shared_secret: bytes) -> bytes:
    """Derive AES key from shared secret using HKDF."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'mesh-encryption-v1',
    )
    return hkdf.derive(shared_secret)


def encrypt_aes_gcm(plaintext: bytes, key: bytes) -> tuple[bytes, bytes]:
    """Encrypt with AES-256-GCM. Returns (nonce, ciphertext)."""
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce, ciphertext


def decrypt_aes_gcm(nonce: bytes, ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt AES-256-GCM."""
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


@dataclass
class EncryptedMessage:
    """E2EE message for DMs."""
    ephemeral_public_key: bytes
    nonce: bytes
    ciphertext: bytes


def encrypt_for_recipient(plaintext: bytes, recipient_public_key: bytes) -> EncryptedMessage:
    """Encrypt a message for a specific recipient (DM)."""
    ephemeral = EncryptionKeyPair.generate()
    shared = ephemeral.derive_shared_secret(recipient_public_key)
    key = derive_encryption_key(shared)
    nonce, ciphertext = encrypt_aes_gcm(plaintext, key)
    return EncryptedMessage(
        ephemeral_public_key=ephemeral.public_key_bytes(),
        nonce=nonce,
        ciphertext=ciphertext,
    )


def decrypt_for_recipient(msg: EncryptedMessage, recipient_private_key: bytes) -> bytes:
    """Decrypt a message received as DM."""
    recipient = X25519PrivateKey.from_private_bytes(recipient_private_key)
    ephemeral_pk = X25519PublicKey.from_public_bytes(msg.ephemeral_public_key)
    shared = recipient.exchange(ephemeral_pk)
    key = derive_encryption_key(shared)
    return decrypt_aes_gcm(msg.nonce, msg.ciphertext, key)


class GroupKey:
    """Symmetric key for group encryption."""
    
    def __init__(self, key: bytes, version: int = 1):
        self.key = key
        self.version = version
        self._aesgcm = AESGCM(key)
    
    @classmethod
    def generate(cls, version: int = 1) -> 'GroupKey':
        return cls(os.urandom(32), version)
    
    def encrypt(self, plaintext: bytes) -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        return nonce, ciphertext
    
    def decrypt(self, nonce: bytes, ciphertext: bytes) -> bytes:
        return self._aesgcm.decrypt(nonce, ciphertext, None)


# ID generation functions
def generate_entity_id(public_key: bytes) -> str:
    """Entity ID from public key."""
    return f"ent:{sha256(public_key)[:32]}"


def generate_content_id(content_dict: dict) -> str:
    """Content ID from content hash."""
    return sha256(canonical_json(content_dict))[:48]


def generate_link_id(source: str, kind: str, target: str) -> str:
    """Link ID from components."""
    return sha256(f"{source}:{kind}:{target}".encode())[:32]


def generate_log_event_id(actor: str, seq: int) -> str:
    """Log event ID from actor and sequence."""
    return sha256(f"{actor}:{seq}".encode())[:48]


def commitment_hash(event_id: str, action_type: str, input_refs: list, params: dict) -> str:
    """Compute commitment hash for action verification (from Relay v1.4.1)."""
    data = {
        "event_id": event_id,
        "action_type": action_type,
        "input_refs": sorted(input_refs),
        "params": params,
    }
    return sha256(canonical_json(data))


def boundary_hash(event_ids: list, actor_heads: dict) -> str:
    """Compute boundary hash for view determinism (from Relay v2)."""
    data = {
        "events": sorted(event_ids),
        "heads": dict(sorted(actor_heads.items())),
    }
    return sha256(canonical_json(data))
