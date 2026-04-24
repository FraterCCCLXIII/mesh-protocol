"""
MESH Protocol - Moderation Layer
Attestations for third-party claims (from Relay v2)
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class AttestationType(str, Enum):
    TRUST = "trust"  # Vouching for someone
    LABEL = "label"  # Labeling content/user
    BADGE = "badge"  # Awarding a badge
    BLOCK = "block"  # Blocking recommendation
    VERIFY = "verify"  # Verification claim
    FLAG = "flag"  # Content flag


@dataclass
class Attestation:
    """
    Third-party claim about a subject.
    Attestations NEVER modify the underlying facts - they compose on top.
    """
    id: str
    issuer: str  # Who made this attestation
    subject: str  # Who/what it's about (entity_id or content_id)
    type: AttestationType
    claim: dict  # The actual claim data
    evidence: Optional[dict]  # Supporting evidence
    ts: datetime
    expires_at: Optional[datetime]
    revoked: bool
    sig: bytes
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "issuer": self.issuer,
            "subject": self.subject,
            "type": self.type.value,
            "claim": self.claim,
            "evidence": self.evidence,
            "ts": self.ts.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked": self.revoked,
            "sig": self.sig.hex(),
        }
    
    def is_valid(self) -> bool:
        """Check if attestation is currently valid."""
        if self.revoked:
            return False
        if self.expires_at and self.expires_at < datetime.now():
            return False
        return True


@dataclass
class TrustNetwork:
    """
    Composable trust network based on attestations.
    Users can choose which issuers to trust.
    """
    owner: str  # Who owns this trust config
    trusted_issuers: list[str]  # List of entity_ids to trust
    trust_depth: int  # How many hops to follow (0 = direct only)
    attestation_types: list[AttestationType]  # Which types to consider
    
    def to_dict(self) -> dict:
        return {
            "owner": self.owner,
            "trusted_issuers": self.trusted_issuers,
            "trust_depth": self.trust_depth,
            "attestation_types": [t.value for t in self.attestation_types],
        }


class ModerationEngine:
    """Applies attestation-based moderation."""
    
    def __init__(self, storage):
        self.storage = storage
    
    async def get_labels_for(self, subject: str, trust_network: TrustNetwork) -> list[Attestation]:
        """Get all valid labels for a subject from trusted issuers."""
        attestations = await self.storage.get_attestations_for(subject)
        
        valid = []
        for att in attestations:
            if not att.is_valid():
                continue
            if att.type not in trust_network.attestation_types:
                continue
            if att.issuer not in trust_network.trusted_issuers:
                continue
            valid.append(att)
        
        return valid
    
    async def should_filter(self, content_id: str, trust_network: TrustNetwork) -> tuple[bool, Optional[str]]:
        """Check if content should be filtered based on attestations."""
        labels = await self.get_labels_for(content_id, trust_network)
        
        for label in labels:
            if label.type == AttestationType.BLOCK:
                return True, f"Blocked by {label.issuer}: {label.claim.get('reason', 'no reason')}"
            if label.type == AttestationType.FLAG:
                severity = label.claim.get("severity", "low")
                if severity in ["high", "critical"]:
                    return True, f"Flagged by {label.issuer}: {label.claim.get('reason')}"
        
        return False, None
