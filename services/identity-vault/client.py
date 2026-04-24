#!/usr/bin/env python3
"""
MESH Identity Vault Client Library

This library handles client-side key encryption/decryption
and communication with the Identity Vault service.

Security Model:
- Keys are encrypted CLIENT-SIDE using a key derived from password
- Vault NEVER sees plaintext private keys
- Even if vault is compromised, keys remain secure
"""

import os
import json
import base64
import hashlib
import secrets
from typing import Optional, Tuple
from dataclasses import dataclass

# Crypto imports
from nacl.signing import SigningKey, VerifyKey
from nacl.public import PrivateKey, PublicKey
from nacl.secret import SecretBox
from nacl.pwhash import argon2id
from nacl.encoding import HexEncoder
import httpx


@dataclass
class VaultKeys:
    """Decrypted keys from the vault."""
    entity_id: str
    signing_key: SigningKey
    encryption_key: Optional[PrivateKey] = None


class VaultClient:
    """
    Client for the MESH Identity Vault.
    
    Usage:
        vault = VaultClient("https://vault.mesh.example.com")
        
        # Register
        token = await vault.register("alice@example.com", "password123")
        
        # Generate and store keys
        entity_id, signing_key = await vault.create_identity("password123")
        
        # Later, retrieve keys
        keys = await vault.get_keys(entity_id, "password123")
        
        # Use keys to sign MESH operations
        signature = keys.signing_key.sign(message)
    """
    
    def __init__(self, vault_url: str):
        self.vault_url = vault_url.rstrip("/")
        self.access_token: Optional[str] = None
        self.user_id: Optional[str] = None
    
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers
    
    async def _request(self, method: str, path: str, data: dict = None) -> dict:
        async with httpx.AsyncClient() as client:
            url = f"{self.vault_url}{path}"
            
            if method == "GET":
                resp = await client.get(url, headers=self._headers())
            elif method == "POST":
                resp = await client.post(url, headers=self._headers(), json=data)
            elif method == "DELETE":
                resp = await client.delete(url, headers=self._headers())
            else:
                raise ValueError(f"Unknown method: {method}")
            
            if resp.status_code >= 400:
                raise VaultError(f"Vault error {resp.status_code}: {resp.text}")
            
            return resp.json() if resp.text else {}
    
    # ========== Auth ==========
    
    async def register(self, email: str, password: str) -> str:
        """Register a new user with email and password."""
        data = await self._request("POST", "/api/auth/register", {
            "email": email,
            "password": password,
        })
        
        self.access_token = data["access_token"]
        self.user_id = data["user_id"]
        
        return self.access_token
    
    async def login(self, email: str, password: str) -> str:
        """Login with email and password."""
        data = await self._request("POST", "/api/auth/login", {
            "email": email,
            "password": password,
        })
        
        self.access_token = data["access_token"]
        self.user_id = data["user_id"]
        
        return self.access_token
    
    async def request_magic_link(self, email: str):
        """Request a magic link for passwordless login."""
        await self._request("POST", "/api/auth/magic-link", {
            "email": email,
        })
    
    async def verify_magic_link(self, token: str) -> str:
        """Verify magic link and get access token."""
        data = await self._request("POST", f"/api/auth/magic-link/verify?token={token}", {})
        
        self.access_token = data["access_token"]
        self.user_id = data["user_id"]
        
        return self.access_token
    
    async def logout(self):
        """Logout and invalidate session."""
        await self._request("POST", "/api/auth/logout", {})
        self.access_token = None
        self.user_id = None
    
    async def get_me(self) -> dict:
        """Get current user info."""
        return await self._request("GET", "/api/auth/me")
    
    # ========== Key Management ==========
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using Argon2id."""
        return argon2id.kdf(
            size=SecretBox.KEY_SIZE,
            password=password.encode(),
            salt=salt,
            opslimit=argon2id.OPSLIMIT_MODERATE,
            memlimit=argon2id.MEMLIMIT_MODERATE,
        )
    
    def _encrypt_key(self, key_bytes: bytes, password: str) -> Tuple[bytes, dict]:
        """
        Encrypt a private key with password-derived key.
        Returns (encrypted_key, derivation_params)
        """
        salt = secrets.token_bytes(argon2id.SALTBYTES)
        derived_key = self._derive_key(password, salt)
        
        box = SecretBox(derived_key)
        encrypted = box.encrypt(key_bytes)
        
        params = {
            "algorithm": "argon2id",
            "salt": base64.b64encode(salt).decode(),
            "opslimit": argon2id.OPSLIMIT_MODERATE,
            "memlimit": argon2id.MEMLIMIT_MODERATE,
        }
        
        return encrypted, params
    
    def _decrypt_key(self, encrypted: bytes, password: str, params: dict) -> bytes:
        """Decrypt a private key using password."""
        salt = base64.b64decode(params["salt"])
        derived_key = self._derive_key(password, salt)
        
        box = SecretBox(derived_key)
        return box.decrypt(encrypted)
    
    async def create_identity(
        self, 
        password: str,
        create_encryption_key: bool = True
    ) -> Tuple[str, SigningKey, Optional[PrivateKey]]:
        """
        Create a new MESH identity with keys stored in the vault.
        
        1. Generates Ed25519 signing key
        2. Optionally generates X25519 encryption key
        3. Encrypts keys with password-derived key
        4. Stores encrypted keys in vault
        
        Returns (entity_id, signing_key, encryption_key)
        """
        if not self.access_token:
            raise VaultError("Not authenticated")
        
        # Generate keys
        signing_key = SigningKey.generate()
        encryption_key = PrivateKey.generate() if create_encryption_key else None
        
        # Calculate entity ID (same as MESH protocol)
        entity_id = "ent:" + hashlib.sha256(
            signing_key.verify_key.encode()
        ).hexdigest()[:32]
        
        # Encrypt keys
        encrypted_signing, params = self._encrypt_key(
            signing_key.encode(),
            password
        )
        
        encrypted_encryption = None
        if encryption_key:
            # Use same params for both keys
            salt = base64.b64decode(params["salt"])
            derived_key = self._derive_key(password, salt)
            box = SecretBox(derived_key)
            encrypted_encryption = box.encrypt(encryption_key.encode())
        
        # Store in vault
        await self._request("POST", "/api/keys/store", {
            "entity_id": entity_id,
            "encrypted_signing_key": base64.b64encode(encrypted_signing).decode(),
            "encrypted_encryption_key": base64.b64encode(encrypted_encryption).decode() if encrypted_encryption else None,
            "key_derivation_params": json.dumps(params),
        })
        
        return entity_id, signing_key, encryption_key
    
    async def get_keys(self, entity_id: str, password: str) -> VaultKeys:
        """
        Retrieve and decrypt keys from the vault.
        
        Keys are decrypted CLIENT-SIDE using the password.
        """
        if not self.access_token:
            raise VaultError("Not authenticated")
        
        data = await self._request("GET", f"/api/keys/{entity_id}")
        
        params = json.loads(data["key_derivation_params"])
        
        # Decrypt signing key
        encrypted_signing = base64.b64decode(data["encrypted_signing_key"])
        signing_bytes = self._decrypt_key(encrypted_signing, password, params)
        signing_key = SigningKey(signing_bytes)
        
        # Decrypt encryption key if present
        encryption_key = None
        if data.get("encrypted_encryption_key"):
            encrypted_encryption = base64.b64decode(data["encrypted_encryption_key"])
            encryption_bytes = self._decrypt_key(encrypted_encryption, password, params)
            encryption_key = PrivateKey(encryption_bytes)
        
        return VaultKeys(
            entity_id=entity_id,
            signing_key=signing_key,
            encryption_key=encryption_key,
        )
    
    async def list_identities(self) -> list:
        """List all entity IDs with stored keys."""
        if not self.access_token:
            raise VaultError("Not authenticated")
        
        data = await self._request("GET", "/api/keys")
        return data.get("entities", [])
    
    async def delete_identity(self, entity_id: str):
        """Delete keys for an identity (careful!)."""
        if not self.access_token:
            raise VaultError("Not authenticated")
        
        await self._request("DELETE", f"/api/keys/{entity_id}")
    
    # ========== Devices ==========
    
    async def authorize_device(self, device_name: str, device_public_key: str = None) -> dict:
        """Authorize a new device."""
        if not self.access_token:
            raise VaultError("Not authenticated")
        
        return await self._request("POST", "/api/devices", {
            "device_name": device_name,
            "device_public_key": device_public_key,
        })
    
    async def list_devices(self) -> list:
        """List authorized devices."""
        if not self.access_token:
            raise VaultError("Not authenticated")
        
        data = await self._request("GET", "/api/devices")
        return data.get("devices", [])
    
    async def revoke_device(self, device_id: str):
        """Revoke a device."""
        if not self.access_token:
            raise VaultError("Not authenticated")
        
        await self._request("DELETE", f"/api/devices/{device_id}")
    
    # ========== Recovery ==========
    
    async def setup_backup_codes(self) -> list:
        """Setup backup codes for recovery. Returns codes (save these!)."""
        if not self.access_token:
            raise VaultError("Not authenticated")
        
        data = await self._request("POST", "/api/recovery/setup", {
            "method": "backup_codes",
            "config": {},
        })
        
        return data.get("backup_codes", [])
    
    async def setup_social_recovery(self, guardian_entity_ids: list):
        """Setup social recovery with trusted guardians."""
        if not self.access_token:
            raise VaultError("Not authenticated")
        
        if len(guardian_entity_ids) < 3:
            raise VaultError("Need at least 3 guardians for social recovery")
        
        await self._request("POST", "/api/recovery/setup", {
            "method": "social",
            "config": {"guardians": guardian_entity_ids},
        })
    
    async def get_recovery_status(self) -> dict:
        """Get recovery configuration status."""
        if not self.access_token:
            raise VaultError("Not authenticated")
        
        return await self._request("GET", "/api/recovery")


class VaultError(Exception):
    """Error from the vault."""
    pass


# ========== Convenience functions ==========

async def create_vault_identity(
    vault_url: str,
    email: str,
    password: str,
    register: bool = True
) -> Tuple[VaultClient, str, SigningKey]:
    """
    Convenience function to create a new MESH identity with vault storage.
    
    Args:
        vault_url: URL of the identity vault
        email: User's email address
        password: Password for both vault auth and key encryption
        register: Whether to register (True) or login (False)
    
    Returns:
        (vault_client, entity_id, signing_key)
    """
    vault = VaultClient(vault_url)
    
    if register:
        await vault.register(email, password)
    else:
        await vault.login(email, password)
    
    entity_id, signing_key, _ = await vault.create_identity(password)
    
    return vault, entity_id, signing_key


async def load_vault_identity(
    vault_url: str,
    email: str,
    password: str,
    entity_id: str
) -> Tuple[VaultClient, VaultKeys]:
    """
    Convenience function to load an existing MESH identity from vault.
    
    Args:
        vault_url: URL of the identity vault
        email: User's email address
        password: Password for both vault auth and key decryption
        entity_id: MESH entity ID to load
    
    Returns:
        (vault_client, keys)
    """
    vault = VaultClient(vault_url)
    await vault.login(email, password)
    
    keys = await vault.get_keys(entity_id, password)
    
    return vault, keys


# ========== Example Usage ==========

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        vault_url = "http://localhost:12003"
        
        # Create new identity
        print("Creating new identity...")
        vault, entity_id, signing_key = await create_vault_identity(
            vault_url,
            email="demo@example.com",
            password="securepassword123",
            register=True
        )
        
        print(f"  Entity ID: {entity_id}")
        print(f"  Public Key: {signing_key.verify_key.encode(HexEncoder).decode()}")
        
        # Demonstrate signing
        message = b"Hello MESH!"
        signature = signing_key.sign(message)
        print(f"  Signed message: {signature.signature.hex()[:32]}...")
        
        # Demonstrate loading
        print("\nLoading identity from vault...")
        vault2, keys = await load_vault_identity(
            vault_url,
            email="demo@example.com",
            password="securepassword123",
            entity_id=entity_id
        )
        
        print(f"  Loaded entity: {keys.entity_id}")
        print(f"  Keys match: {keys.signing_key.encode() == signing_key.encode()}")
        
        # Demonstrate device management
        print("\nAuthorizing device...")
        device = await vault.authorize_device("Test Device")
        print(f"  Device ID: {device['device_id']}")
        
        devices = await vault.list_devices()
        print(f"  Total devices: {len(devices)}")
        
        # Setup backup codes
        print("\nSetting up backup codes...")
        codes = await vault.setup_backup_codes()
        print(f"  Backup codes: {codes[:2]}... (save these!)")
        
        print("\nDemo complete!")
    
    asyncio.run(demo())
