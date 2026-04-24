#!/usr/bin/env python3
"""
MESH Identity Vault Service

A third-party identity service that enables:
- Email-based authentication (familiar UX)
- Secure encrypted key storage (vault never sees plaintext keys)
- Device management and authorization
- Key recovery options

Security Model:
- User password is used to derive encryption key (Argon2id)
- Private keys are encrypted CLIENT-SIDE before storage
- Vault stores only encrypted blobs
- Even if vault is compromised, keys remain secure
"""

import os
import json
import secrets
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
import aiosqlite
import argon2

# ========== Configuration ==========

VAULT_SECRET = os.environ.get("VAULT_SECRET", secrets.token_hex(32))
DATABASE_URL = os.environ.get("VAULT_DATABASE_URL", "sqlite:///./vault.db")
DB_PATH = DATABASE_URL.replace("sqlite:///", "")

SMTP_HOST = os.environ.get("VAULT_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("VAULT_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("VAULT_SMTP_USER", "")
SMTP_PASS = os.environ.get("VAULT_SMTP_PASS", "")
FROM_EMAIL = os.environ.get("VAULT_FROM_EMAIL", "noreply@mesh.local")

# Token expiry
ACCESS_TOKEN_EXPIRE_HOURS = 24
MAGIC_LINK_EXPIRE_MINUTES = 15

# Password hashing
ph = argon2.PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
)

# ========== Database ==========

db: Optional[aiosqlite.Connection] = None


async def init_db():
    global db
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    
    await db.executescript("""
        -- Users table
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            email_verified INTEGER DEFAULT 0,
            password_hash TEXT NOT NULL,
            totp_secret TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        
        -- Encrypted keys (vault stores only encrypted blobs)
        CREATE TABLE IF NOT EXISTS encrypted_keys (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            entity_id TEXT NOT NULL,
            key_type TEXT NOT NULL DEFAULT 'signing',
            encrypted_key BLOB NOT NULL,
            key_derivation_params TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, entity_id, key_type)
        );
        
        -- Devices
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            device_name TEXT NOT NULL,
            device_public_key TEXT,
            user_agent TEXT,
            ip_address TEXT,
            authorized_at TEXT NOT NULL,
            last_used_at TEXT NOT NULL,
            revoked INTEGER DEFAULT 0
        );
        
        -- Sessions
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            device_id TEXT REFERENCES devices(id),
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        
        -- Magic links for passwordless login
        CREATE TABLE IF NOT EXISTS magic_links (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        
        -- Recovery configs
        CREATE TABLE IF NOT EXISTS recovery_configs (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            method TEXT NOT NULL,
            config TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        
        -- Email verification tokens
        CREATE TABLE IF NOT EXISTS email_verifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
        CREATE INDEX IF NOT EXISTS idx_encrypted_keys_user ON encrypted_keys(user_id);
        CREATE INDEX IF NOT EXISTS idx_devices_user ON devices(user_id);
    """)
    await db.commit()


async def close_db():
    if db:
        await db.close()


# ========== Models ==========

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MagicLinkRequest(BaseModel):
    email: EmailStr


class StoreKeysRequest(BaseModel):
    entity_id: str
    encrypted_signing_key: str  # Base64 encoded encrypted key
    encrypted_encryption_key: Optional[str] = None  # Base64 encoded
    key_derivation_params: str  # JSON with salt, algorithm, etc.


class DeviceAuthRequest(BaseModel):
    device_name: str
    device_public_key: Optional[str] = None


class RecoverySetupRequest(BaseModel):
    method: str  # 'backup_codes', 'social', 'custodial'
    config: dict


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    user_id: str


class UserResponse(BaseModel):
    id: str
    email: str
    email_verified: bool
    created_at: str


# ========== Helpers ==========

def generate_id() -> str:
    return secrets.token_hex(16)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def now_iso() -> str:
    return datetime.utcnow().isoformat()


async def get_user_by_email(email: str) -> Optional[dict]:
    cursor = await db.execute(
        "SELECT * FROM users WHERE email = ?", (email.lower(),)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_user_by_id(user_id: str) -> Optional[dict]:
    cursor = await db.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_session(user_id: str, device_id: Optional[str] = None) -> str:
    token = secrets.token_urlsafe(32)
    session_id = generate_id()
    expires_at = (datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)).isoformat()
    
    await db.execute("""
        INSERT INTO sessions (id, user_id, device_id, token_hash, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, user_id, device_id, hash_token(token), expires_at, now_iso()))
    await db.commit()
    
    return token


async def verify_session(token: str) -> Optional[str]:
    """Verify session token and return user_id if valid."""
    cursor = await db.execute("""
        SELECT user_id, expires_at FROM sessions 
        WHERE token_hash = ? AND expires_at > ?
    """, (hash_token(token), now_iso()))
    row = await cursor.fetchone()
    
    if row:
        return row["user_id"]
    return None


async def send_email(to: str, subject: str, body: str):
    """Send email (stub - implement with actual SMTP)."""
    if not SMTP_HOST:
        print(f"[Email] Would send to {to}: {subject}")
        print(f"[Email] Body: {body}")
        return
    
    import aiosmtplib
    from email.mime.text import MIMEText
    
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to
    
    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASS,
        use_tls=True,
    )


# ========== Auth Dependencies ==========

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    if not credentials:
        return None
    
    user_id = await verify_session(credentials.credentials)
    if not user_id:
        return None
    
    return await get_user_by_id(user_id)


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_id = await verify_session(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


# ========== App Setup ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("[Vault] Database initialized")
    yield
    await close_db()
    print("[Vault] Database closed")


app = FastAPI(
    title="MESH Identity Vault",
    description="Secure key storage with email authentication",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== Health ==========

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "identity-vault"}


# ========== Auth Endpoints ==========

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(req: RegisterRequest, background_tasks: BackgroundTasks):
    """Register a new user with email and password."""
    email = req.email.lower()
    
    # Check if exists
    existing = await get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    
    # Hash password
    try:
        password_hash = ph.hash(req.password)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid password")
    
    # Create user
    user_id = generate_id()
    now = now_iso()
    
    await db.execute("""
        INSERT INTO users (id, email, password_hash, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, email, password_hash, now, now))
    await db.commit()
    
    # Create session
    token = await create_session(user_id)
    expires_at = (datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)).isoformat()
    
    # Send verification email
    verification_token = secrets.token_urlsafe(32)
    verification_expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    
    await db.execute("""
        INSERT INTO email_verifications (id, user_id, token_hash, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (generate_id(), user_id, hash_token(verification_token), verification_expires, now))
    await db.commit()
    
    background_tasks.add_task(
        send_email,
        email,
        "Verify your MESH account",
        f"Click to verify: https://vault.mesh.example.com/verify?token={verification_token}"
    )
    
    return TokenResponse(
        access_token=token,
        expires_at=expires_at,
        user_id=user_id,
    )


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Login with email and password."""
    email = req.email.lower()
    
    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Verify password
    try:
        ph.verify(user["password_hash"], req.password)
    except argon2.exceptions.VerifyMismatchError:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Rehash if needed (Argon2 supports this)
    if ph.check_needs_rehash(user["password_hash"]):
        new_hash = ph.hash(req.password)
        await db.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (new_hash, now_iso(), user["id"])
        )
        await db.commit()
    
    # Create session
    token = await create_session(user["id"])
    expires_at = (datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)).isoformat()
    
    return TokenResponse(
        access_token=token,
        expires_at=expires_at,
        user_id=user["id"],
    )


@app.post("/api/auth/magic-link")
async def request_magic_link(req: MagicLinkRequest, background_tasks: BackgroundTasks):
    """Request a magic link for passwordless login."""
    email = req.email.lower()
    
    user = await get_user_by_email(email)
    if not user:
        # Don't reveal if user exists
        return {"message": "If this email exists, a login link has been sent"}
    
    # Generate magic link token
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(minutes=MAGIC_LINK_EXPIRE_MINUTES)).isoformat()
    
    await db.execute("""
        INSERT INTO magic_links (id, user_id, token_hash, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (generate_id(), user["id"], hash_token(token), expires_at, now_iso()))
    await db.commit()
    
    background_tasks.add_task(
        send_email,
        email,
        "Your MESH login link",
        f"Click to login: https://vault.mesh.example.com/magic?token={token}\n\nThis link expires in {MAGIC_LINK_EXPIRE_MINUTES} minutes."
    )
    
    return {"message": "If this email exists, a login link has been sent"}


@app.post("/api/auth/magic-link/verify", response_model=TokenResponse)
async def verify_magic_link(token: str):
    """Verify magic link and return session token."""
    cursor = await db.execute("""
        SELECT user_id, expires_at, used FROM magic_links
        WHERE token_hash = ?
    """, (hash_token(token),))
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired link")
    
    if row["used"]:
        raise HTTPException(status_code=401, detail="Link already used")
    
    if row["expires_at"] < now_iso():
        raise HTTPException(status_code=401, detail="Link expired")
    
    # Mark as used
    await db.execute(
        "UPDATE magic_links SET used = 1 WHERE token_hash = ?",
        (hash_token(token),)
    )
    await db.commit()
    
    # Create session
    session_token = await create_session(row["user_id"])
    expires_at = (datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)).isoformat()
    
    return TokenResponse(
        access_token=session_token,
        expires_at=expires_at,
        user_id=row["user_id"],
    )


@app.post("/api/auth/logout")
async def logout(user: dict = Depends(require_auth), credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Logout and invalidate current session."""
    await db.execute(
        "DELETE FROM sessions WHERE token_hash = ?",
        (hash_token(credentials.credentials),)
    )
    await db.commit()
    return {"message": "Logged out"}


@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(require_auth)):
    """Get current user info."""
    return UserResponse(
        id=user["id"],
        email=user["email"],
        email_verified=bool(user["email_verified"]),
        created_at=user["created_at"],
    )


# ========== Key Storage Endpoints ==========

@app.post("/api/keys/store")
async def store_keys(req: StoreKeysRequest, user: dict = Depends(require_auth)):
    """
    Store encrypted keys for a MESH entity.
    
    IMPORTANT: Keys must be encrypted CLIENT-SIDE before sending.
    The vault NEVER sees plaintext private keys.
    """
    import base64
    
    # Validate base64
    try:
        encrypted_signing = base64.b64decode(req.encrypted_signing_key)
    except:
        raise HTTPException(status_code=400, detail="Invalid base64 for signing key")
    
    encrypted_encryption = None
    if req.encrypted_encryption_key:
        try:
            encrypted_encryption = base64.b64decode(req.encrypted_encryption_key)
        except:
            raise HTTPException(status_code=400, detail="Invalid base64 for encryption key")
    
    # Validate key derivation params
    try:
        params = json.loads(req.key_derivation_params)
        if "salt" not in params or "algorithm" not in params:
            raise ValueError("Missing required params")
    except:
        raise HTTPException(status_code=400, detail="Invalid key derivation params")
    
    now = now_iso()
    
    # Store signing key
    key_id = generate_id()
    await db.execute("""
        INSERT OR REPLACE INTO encrypted_keys 
        (id, user_id, entity_id, key_type, encrypted_key, key_derivation_params, created_at, updated_at)
        VALUES (?, ?, ?, 'signing', ?, ?, ?, ?)
    """, (key_id, user["id"], req.entity_id, encrypted_signing, req.key_derivation_params, now, now))
    
    # Store encryption key if provided
    if encrypted_encryption:
        key_id = generate_id()
        await db.execute("""
            INSERT OR REPLACE INTO encrypted_keys
            (id, user_id, entity_id, key_type, encrypted_key, key_derivation_params, created_at, updated_at)
            VALUES (?, ?, ?, 'encryption', ?, ?, ?, ?)
        """, (key_id, user["id"], req.entity_id, encrypted_encryption, req.key_derivation_params, now, now))
    
    await db.commit()
    
    return {
        "status": "stored",
        "entity_id": req.entity_id,
    }


@app.get("/api/keys/{entity_id}")
async def get_keys(entity_id: str, user: dict = Depends(require_auth)):
    """
    Retrieve encrypted keys for a MESH entity.
    
    Returns encrypted blobs that must be decrypted CLIENT-SIDE.
    """
    import base64
    
    cursor = await db.execute("""
        SELECT key_type, encrypted_key, key_derivation_params
        FROM encrypted_keys
        WHERE user_id = ? AND entity_id = ?
    """, (user["id"], entity_id))
    
    rows = await cursor.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Keys not found")
    
    result = {
        "entity_id": entity_id,
        "key_derivation_params": None,
    }
    
    for row in rows:
        key_type = row["key_type"]
        encrypted = base64.b64encode(row["encrypted_key"]).decode()
        result[f"encrypted_{key_type}_key"] = encrypted
        result["key_derivation_params"] = row["key_derivation_params"]
    
    return result


@app.get("/api/keys")
async def list_keys(user: dict = Depends(require_auth)):
    """List all entity IDs with stored keys."""
    cursor = await db.execute("""
        SELECT DISTINCT entity_id, created_at
        FROM encrypted_keys
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user["id"],))
    
    rows = await cursor.fetchall()
    
    return {
        "entities": [
            {"entity_id": row["entity_id"], "created_at": row["created_at"]}
            for row in rows
        ]
    }


@app.delete("/api/keys/{entity_id}")
async def delete_keys(entity_id: str, user: dict = Depends(require_auth)):
    """Delete keys for an entity (careful!)."""
    await db.execute("""
        DELETE FROM encrypted_keys
        WHERE user_id = ? AND entity_id = ?
    """, (user["id"], entity_id))
    await db.commit()
    
    return {"status": "deleted", "entity_id": entity_id}


# ========== Device Management ==========

@app.post("/api/devices")
async def authorize_device(req: DeviceAuthRequest, user: dict = Depends(require_auth)):
    """Authorize a new device."""
    device_id = generate_id()
    now = now_iso()
    
    await db.execute("""
        INSERT INTO devices (id, user_id, device_name, device_public_key, authorized_at, last_used_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (device_id, user["id"], req.device_name, req.device_public_key, now, now))
    await db.commit()
    
    return {
        "device_id": device_id,
        "device_name": req.device_name,
        "authorized_at": now,
    }


@app.get("/api/devices")
async def list_devices(user: dict = Depends(require_auth)):
    """List authorized devices."""
    cursor = await db.execute("""
        SELECT id, device_name, authorized_at, last_used_at, revoked
        FROM devices
        WHERE user_id = ?
        ORDER BY last_used_at DESC
    """, (user["id"],))
    
    rows = await cursor.fetchall()
    
    return {
        "devices": [
            {
                "id": row["id"],
                "device_name": row["device_name"],
                "authorized_at": row["authorized_at"],
                "last_used_at": row["last_used_at"],
                "revoked": bool(row["revoked"]),
            }
            for row in rows
        ]
    }


@app.delete("/api/devices/{device_id}")
async def revoke_device(device_id: str, user: dict = Depends(require_auth)):
    """Revoke a device."""
    await db.execute("""
        UPDATE devices SET revoked = 1 WHERE id = ? AND user_id = ?
    """, (device_id, user["id"]))
    
    # Also delete sessions for this device
    await db.execute("""
        DELETE FROM sessions WHERE device_id = ?
    """, (device_id,))
    
    await db.commit()
    
    return {"status": "revoked", "device_id": device_id}


# ========== Recovery ==========

@app.post("/api/recovery/setup")
async def setup_recovery(req: RecoverySetupRequest, user: dict = Depends(require_auth)):
    """Setup recovery method."""
    now = now_iso()
    
    # Validate method
    if req.method not in ["backup_codes", "social", "custodial"]:
        raise HTTPException(status_code=400, detail="Invalid recovery method")
    
    # Generate backup codes if that method
    if req.method == "backup_codes":
        codes = [secrets.token_hex(4).upper() for _ in range(10)]
        config = {
            "codes": [hash_token(c) for c in codes],  # Store hashes only
            "used": [],
        }
        
        await db.execute("""
            INSERT OR REPLACE INTO recovery_configs (user_id, method, config, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user["id"], req.method, json.dumps(config), now, now))
        await db.commit()
        
        return {
            "status": "configured",
            "method": req.method,
            "backup_codes": codes,  # Show only once!
        }
    
    # Social recovery
    elif req.method == "social":
        if "guardians" not in req.config or len(req.config["guardians"]) < 3:
            raise HTTPException(status_code=400, detail="Need at least 3 guardians")
        
        await db.execute("""
            INSERT OR REPLACE INTO recovery_configs (user_id, method, config, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user["id"], req.method, json.dumps(req.config), now, now))
        await db.commit()
        
        return {
            "status": "configured",
            "method": req.method,
            "guardians": len(req.config["guardians"]),
        }
    
    # Custodial recovery
    else:
        await db.execute("""
            INSERT OR REPLACE INTO recovery_configs (user_id, method, config, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user["id"], req.method, json.dumps(req.config), now, now))
        await db.commit()
        
        return {
            "status": "configured",
            "method": req.method,
        }


@app.get("/api/recovery")
async def get_recovery_status(user: dict = Depends(require_auth)):
    """Get recovery configuration status."""
    cursor = await db.execute("""
        SELECT method, created_at FROM recovery_configs WHERE user_id = ?
    """, (user["id"],))
    row = await cursor.fetchone()
    
    if not row:
        return {"configured": False}
    
    return {
        "configured": True,
        "method": row["method"],
        "configured_at": row["created_at"],
    }


# ========== Email Verification ==========

@app.post("/api/auth/verify-email")
async def verify_email(token: str):
    """Verify email address."""
    cursor = await db.execute("""
        SELECT user_id, expires_at FROM email_verifications
        WHERE token_hash = ?
    """, (hash_token(token),))
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    
    if row["expires_at"] < now_iso():
        raise HTTPException(status_code=400, detail="Verification token expired")
    
    # Mark email as verified
    await db.execute(
        "UPDATE users SET email_verified = 1, updated_at = ? WHERE id = ?",
        (now_iso(), row["user_id"])
    )
    
    # Delete used token
    await db.execute(
        "DELETE FROM email_verifications WHERE token_hash = ?",
        (hash_token(token),)
    )
    
    await db.commit()
    
    return {"status": "verified"}


# ========== Main ==========

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "12003"))
    uvicorn.run(app, host="0.0.0.0", port=port)
