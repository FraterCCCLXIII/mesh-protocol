"""
MESH Protocol - Unified implementation combining:
- HOLON v4: Simple primitives (Entity, Content, Link)
- Relay v1.4.1: Integrity (prev chain, commitment_hash)
- Relay v2: Views (boundary determinism, attestations)
"""

from .crypto import (
    SigningKeyPair, EncryptionKeyPair, GroupKey,
    verify_signature, verify_object_signature, sign_object,
    encrypt_for_recipient, decrypt_for_recipient,
    encrypt_aes_gcm, decrypt_aes_gcm,
    generate_entity_id, generate_content_id, generate_link_id,
    commitment_hash, boundary_hash,
    canonical_json, sha256,
)

from .primitives import (
    Entity, Content, Link,
    EntityKind, ContentKind, LinkKind, AccessType,
)

from .integrity import (
    LogEvent, OpType, ObjectType,
    generate_log_event_id, validate_log_chain, detect_fork,
)

from .views import (
    ViewDefinition, ViewResult, ViewEngine,
    Source, Filter, ReducerType, SourceKind,
)

from .attestations import (
    Attestation, AttestationType,
    TrustNetwork, ModerationEngine,
)

from .storage import Storage

__all__ = [
    # Crypto
    'SigningKeyPair', 'EncryptionKeyPair', 'GroupKey',
    'verify_signature', 'verify_object_signature', 'sign_object',
    'encrypt_for_recipient', 'decrypt_for_recipient',
    'commitment_hash', 'boundary_hash',
    
    # Primitives
    'Entity', 'Content', 'Link',
    'EntityKind', 'ContentKind', 'LinkKind', 'AccessType',
    
    # Integrity
    'LogEvent', 'OpType', 'ObjectType',
    'generate_log_event_id', 'validate_log_chain', 'detect_fork',
    
    # Views
    'ViewDefinition', 'ViewResult', 'ViewEngine',
    'Source', 'Filter', 'ReducerType', 'SourceKind',
    
    # Attestations
    'Attestation', 'AttestationType',
    'TrustNetwork', 'ModerationEngine',
    
    # Storage
    'Storage',
]
