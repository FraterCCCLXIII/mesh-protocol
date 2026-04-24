"""
HOLON v4 Implementation - Client Library

High-level client for interacting with the HOLON protocol:
- Identity management
- Content creation (with encryption)
- Social graph operations
- Multi-relay support
"""

import json
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict

from crypto import (
    SigningKeyPair, EncryptionKeyPair, GroupKey,
    sign_object, verify_object_signature,
    encrypt_for_recipient, decrypt_for_recipient,
    wrap_group_key_for_member, unwrap_group_key,
    generate_entity_id, generate_content_id, generate_link_id,
    canonical_json, EncryptedContent
)
from storage import (
    Storage, Entity, Content, Link,
    EntityKind, ContentKind, LinkKind, AccessType
)
from network import RelayClient, RelayNode


@dataclass
class Identity:
    """User identity with signing and encryption keys."""
    entity_id: str
    signing_key: SigningKeyPair
    encryption_key: EncryptionKeyPair
    handle: Optional[str] = None
    profile: dict = None
    
    @classmethod
    def generate(cls, handle: Optional[str] = None, profile: dict = None) -> 'Identity':
        """Generate a new identity."""
        signing_key = SigningKeyPair.generate()
        encryption_key = EncryptionKeyPair.generate()
        entity_id = generate_entity_id(signing_key.public_key_bytes())
        
        return cls(
            entity_id=entity_id,
            signing_key=signing_key,
            encryption_key=encryption_key,
            handle=handle,
            profile=profile or {},
        )
    
    @classmethod
    def from_seed(cls, seed: bytes, handle: Optional[str] = None) -> 'Identity':
        """Derive identity from 32-byte seed (deterministic)."""
        import hashlib
        signing_key = SigningKeyPair.from_seed(seed)
        # Derive encryption key from signing key
        enc_seed = hashlib.sha256(seed + b"encryption").digest()
        encryption_key = EncryptionKeyPair.from_private_bytes(enc_seed)
        entity_id = generate_entity_id(signing_key.public_key_bytes())
        
        return cls(
            entity_id=entity_id,
            signing_key=signing_key,
            encryption_key=encryption_key,
            handle=handle,
            profile={},
        )
    
    def sign(self, obj: dict) -> dict:
        """Sign an object."""
        return sign_object(obj, self.signing_key)
    
    def to_entity(self) -> Entity:
        """Convert to Entity for storage."""
        now = datetime.now()
        entity_dict = {
            "type": "entity",
            "id": self.entity_id,
            "kind": EntityKind.USER.value,
            "handle": self.handle,
            "profile": self.profile,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        signed = self.sign(entity_dict)
        
        import base64
        return Entity(
            id=self.entity_id,
            kind=EntityKind.USER,
            public_key=self.signing_key.public_key_bytes(),
            encryption_key=self.encryption_key.public_key_bytes(),
            handle=self.handle,
            profile=self.profile,
            created_at=now,
            updated_at=now,
            sig=base64.b64decode(signed['sig']),
        )


class HolonClient:
    """
    High-level client for HOLON protocol.
    
    Handles:
    - Identity management
    - Content creation and encryption
    - Social graph operations
    - Multi-relay sync
    """
    
    def __init__(self, identity: Identity):
        self.identity = identity
        self.storage: Optional[Storage] = None
        self.relay_clients: Dict[str, RelayClient] = {}
        self.group_keys: Dict[str, GroupKey] = {}  # group_id -> GroupKey
    
    async def initialize(self, db_path: str = None):
        """Initialize local storage."""
        db_path = db_path or f"holon_{self.identity.handle or 'user'}.db"
        self.storage = Storage(db_path)
        await self.storage.initialize()
        
        # Store own entity
        entity = self.identity.to_entity()
        try:
            await self.storage.create_entity(entity)
        except:
            pass  # Already exists
    
    async def close(self):
        """Close connections."""
        if self.storage:
            await self.storage.close()
        for client in self.relay_clients.values():
            await client.disconnect()
    
    # =========================================================================
    # RELAY CONNECTIONS
    # =========================================================================
    
    async def connect_relay(self, relay_url: str):
        """Connect to a relay."""
        client = RelayClient(relay_url)
        await client.connect()
        self.relay_clients[relay_url] = client
        
        # Subscribe to own entity
        await client.subscribe([self.identity.entity_id])
        
        # Publish own entity to relay
        entity = self.identity.to_entity()
        await client.post_entity(self._entity_to_api_dict(entity))
    
    async def disconnect_relay(self, relay_url: str):
        """Disconnect from a relay."""
        if relay_url in self.relay_clients:
            await self.relay_clients[relay_url].disconnect()
            del self.relay_clients[relay_url]
    
    def _entity_to_api_dict(self, entity: Entity) -> dict:
        """Convert entity to API format."""
        d = entity.to_dict()
        d['public_key_hex'] = entity.public_key.hex()
        d['encryption_key_hex'] = entity.encryption_key.hex()
        d['sig_hex'] = entity.sig.hex()
        return d
    
    # =========================================================================
    # CONTENT OPERATIONS
    # =========================================================================
    
    async def create_post(self, text: str, context: Optional[str] = None,
                         reply_to: Optional[str] = None,
                         access: AccessType = AccessType.PUBLIC) -> Content:
        """Create a post."""
        now = datetime.now()
        
        body = {"text": text}
        encrypted = False
        encryption_metadata = None
        
        # Encrypt if not public
        if access == AccessType.PRIVATE:
            # Encrypt for self only
            encrypted_content = encrypt_for_recipient(
                text.encode(),
                self.identity.encryption_key.public_key_bytes()
            )
            body = {"encrypted": encrypted_content.to_dict()}
            encrypted = True
            encryption_metadata = {"recipients": [self.identity.entity_id]}
        
        elif access == AccessType.GROUP and context:
            # Encrypt with group key
            group_key = self.group_keys.get(context)
            if group_key:
                nonce, ciphertext = group_key.encrypt(text.encode())
                import base64
                body = {
                    "encrypted": {
                        "nonce": base64.b64encode(nonce).decode(),
                        "ciphertext": base64.b64encode(ciphertext).decode(),
                    }
                }
                encrypted = True
                encryption_metadata = {"key_id": group_key.key_id}
        
        content_dict = {
            "type": "content",
            "kind": ContentKind.POST.value,
            "author": self.identity.entity_id,
            "body": body,
            "created_at": now.isoformat(),
            "context": context,
            "reply_to": reply_to,
            "access": access.value,
            "encrypted": encrypted,
        }
        
        content_id = generate_content_id(content_dict)
        content_dict["id"] = content_id
        
        signed = self.identity.sign(content_dict)
        
        import base64
        content = Content(
            id=content_id,
            kind=ContentKind.POST,
            author=self.identity.entity_id,
            body=body,
            created_at=now,
            context=context,
            reply_to=reply_to,
            access=access,
            encrypted=encrypted,
            encryption_metadata=encryption_metadata,
            sig=base64.b64decode(signed['sig']),
        )
        
        # Store locally
        await self.storage.create_content(content)
        
        # Publish to relays
        api_dict = content.to_dict()
        api_dict['sig_hex'] = content.sig.hex()
        for client in self.relay_clients.values():
            await client.post_content(api_dict)
        
        return content
    
    async def decrypt_content(self, content: Content) -> Optional[str]:
        """Decrypt content if encrypted."""
        if not content.encrypted:
            return content.body.get('text')
        
        encrypted_data = content.body.get('encrypted')
        if not encrypted_data:
            return None
        
        # Try group key
        if content.encryption_metadata and 'key_id' in content.encryption_metadata:
            key_id = content.encryption_metadata['key_id']
            group_key = None
            for gk in self.group_keys.values():
                if gk.key_id == key_id:
                    group_key = gk
                    break
            
            if group_key:
                import base64
                nonce = base64.b64decode(encrypted_data['nonce'])
                ciphertext = base64.b64decode(encrypted_data['ciphertext'])
                plaintext = group_key.decrypt(nonce, ciphertext)
                return plaintext.decode()
        
        # Try personal decryption
        try:
            enc = EncryptedContent.from_dict(encrypted_data)
            plaintext = decrypt_for_recipient(
                enc,
                self.identity.encryption_key.private_key_bytes()
            )
            return plaintext.decode()
        except:
            pass
        
        return None
    
    # =========================================================================
    # LINK OPERATIONS
    # =========================================================================
    
    async def follow(self, target_id: str) -> Link:
        """Follow another entity."""
        return await self._create_link(LinkKind.FOLLOW, target_id)
    
    async def unfollow(self, target_id: str) -> bool:
        """Unfollow an entity."""
        links = await self.storage.get_links_by_source(self.identity.entity_id, LinkKind.FOLLOW)
        for link in links:
            if link.target == target_id:
                await self.storage.tombstone_link(link.id)
                return True
        return False
    
    async def react(self, content_id: str, emoji: str = "❤️") -> Link:
        """React to content."""
        return await self._create_link(LinkKind.REACT, content_id, {"emoji": emoji})
    
    async def join_group(self, group_id: str) -> Link:
        """Join a group."""
        return await self._create_link(LinkKind.MEMBER, group_id, {"role": "member"})
    
    async def tip(self, content_id: str, amount_sats: int) -> Link:
        """Tip content creator."""
        return await self._create_link(LinkKind.TIP, content_id, {"amount_sats": amount_sats})
    
    async def _create_link(self, kind: LinkKind, target: str, data: dict = None) -> Link:
        """Create a link."""
        now = datetime.now()
        
        link_dict = {
            "type": "link",
            "kind": kind.value,
            "source": self.identity.entity_id,
            "target": target,
            "data": data or {},
            "created_at": now.isoformat(),
            "tombstone": False,
        }
        
        link_id = generate_link_id(link_dict)
        link_dict["id"] = link_id
        
        signed = self.identity.sign(link_dict)
        
        import base64
        link = Link(
            id=link_id,
            kind=kind,
            source=self.identity.entity_id,
            target=target,
            data=data or {},
            created_at=now,
            tombstone=False,
            sig=base64.b64decode(signed['sig']),
        )
        
        # Store locally
        await self.storage.create_link(link)
        
        # Publish to relays
        api_dict = link.to_dict()
        api_dict['sig_hex'] = link.sig.hex()
        for client in self.relay_clients.values():
            await client.post_link(api_dict)
        
        return link
    
    # =========================================================================
    # SOCIAL GRAPH
    # =========================================================================
    
    async def get_followers(self) -> List[str]:
        """Get my followers."""
        return await self.storage.get_followers(self.identity.entity_id)
    
    async def get_following(self) -> List[str]:
        """Get who I follow."""
        return await self.storage.get_following(self.identity.entity_id)
    
    async def get_feed(self, limit: int = 50) -> List[Content]:
        """Get feed from followed accounts."""
        following = await self.get_following()
        
        all_content = []
        for entity_id in following:
            content = await self.storage.get_content_by_author(entity_id, limit=limit)
            all_content.extend(content)
        
        # Sort by date
        all_content.sort(key=lambda c: c.created_at, reverse=True)
        return all_content[:limit]
    
    async def discover_follows_of_follows(self, limit: int = 20) -> List[str]:
        """Discover new people to follow."""
        return await self.storage.get_follows_of_follows(self.identity.entity_id, limit)
    
    # =========================================================================
    # GROUP OPERATIONS
    # =========================================================================
    
    async def create_group(self, name: str, description: str = "") -> Entity:
        """Create a group."""
        now = datetime.now()
        
        # Generate group keys
        group_signing = SigningKeyPair.generate()
        group_encryption = EncryptionKeyPair.generate()
        group_id = generate_entity_id(group_signing.public_key_bytes())
        
        entity_dict = {
            "type": "entity",
            "id": group_id,
            "kind": EntityKind.GROUP.value,
            "handle": name.lower().replace(" ", "-"),
            "profile": {
                "name": name,
                "description": description,
                "owner": self.identity.entity_id,
            },
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        
        # Sign with group's key
        signed = sign_object(entity_dict, group_signing)
        
        import base64
        entity = Entity(
            id=group_id,
            kind=EntityKind.GROUP,
            public_key=group_signing.public_key_bytes(),
            encryption_key=group_encryption.public_key_bytes(),
            handle=entity_dict['handle'],
            profile=entity_dict['profile'],
            created_at=now,
            updated_at=now,
            sig=base64.b64decode(signed['sig']),
        )
        
        await self.storage.create_entity(entity)
        
        # Generate and store group key
        group_key = GroupKey.generate()
        self.group_keys[group_id] = group_key
        
        # Join the group
        await self.join_group(group_id)
        
        return entity
    
    async def add_group_key(self, group_id: str, wrapped_key: EncryptedContent, key_id: str):
        """Add a group key (received from another member)."""
        import time
        group_key = unwrap_group_key(
            wrapped_key,
            self.identity.encryption_key.private_key_bytes(),
            key_id,
            time.time()
        )
        self.group_keys[group_id] = group_key
    
    # =========================================================================
    # SEARCH
    # =========================================================================
    
    async def search_content(self, query: str, limit: int = 20) -> List[Content]:
        """Search content."""
        return await self.storage.search_content(query, limit)
    
    async def search_entities(self, query: str, limit: int = 20) -> List[Entity]:
        """Search entities."""
        return await self.storage.search_entities(query, limit)


# =============================================================================
# DEMO / TEST
# =============================================================================

async def demo():
    """Demo the client."""
    print("=== HOLON v4 Client Demo ===\n")
    
    # Create two users
    alice = Identity.generate(handle="alice", profile={"name": "Alice", "bio": "Hello!"})
    bob = Identity.generate(handle="bob", profile={"name": "Bob", "bio": "Hey there!"})
    
    print(f"Created Alice: {alice.entity_id}")
    print(f"Created Bob: {bob.entity_id}")
    
    # Initialize clients
    alice_client = HolonClient(alice)
    bob_client = HolonClient(bob)
    
    await alice_client.initialize("alice.db")
    await bob_client.initialize("bob.db")
    
    # Store Bob's entity in Alice's storage (simulating relay sync)
    await alice_client.storage.create_entity(bob.to_entity())
    await bob_client.storage.create_entity(alice.to_entity())
    
    # Alice follows Bob
    follow_link = await alice_client.follow(bob.entity_id)
    print(f"\nAlice follows Bob: {follow_link.id}")
    
    # Bob creates a post
    post = await bob_client.create_post("Hello world! This is my first post.")
    print(f"Bob posted: {post.id}")
    
    # Sync Bob's post to Alice's storage
    await alice_client.storage.create_content(post)
    
    # Alice reacts to Bob's post
    react = await alice_client.react(post.id, "🔥")
    print(f"Alice reacted: {react.id}")
    
    # Alice's feed
    feed = await alice_client.get_feed()
    print(f"\nAlice's feed: {len(feed)} items")
    for content in feed:
        text = content.body.get('text', '[encrypted]')
        print(f"  - {text[:50]}...")
    
    # Bob creates encrypted post
    private_post = await bob_client.create_post(
        "This is a private message",
        access=AccessType.PRIVATE
    )
    print(f"\nBob's private post: {private_post.id} (encrypted: {private_post.encrypted})")
    
    # Cleanup
    await alice_client.close()
    await bob_client.close()
    
    # Clean up test files
    import os
    for f in ["alice.db", "bob.db"]:
        if os.path.exists(f):
            os.remove(f)
    
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(demo())
