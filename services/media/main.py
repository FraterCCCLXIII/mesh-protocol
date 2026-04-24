#!/usr/bin/env python3
"""
MESH Media Service
Content-addressed media storage with image processing
"""
import os
import io
import hashlib
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import aiosqlite

STORAGE_PATH = os.environ.get("MEDIA_STORAGE_PATH", "./media_storage")
DB_PATH = os.environ.get("MEDIA_DB_PATH", "media.db")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

os.makedirs(STORAGE_PATH, exist_ok=True)
os.makedirs(f"{STORAGE_PATH}/original", exist_ok=True)
os.makedirs(f"{STORAGE_PATH}/thumb", exist_ok=True)

db: Optional[aiosqlite.Connection] = None

async def init_db():
    global db
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS media (
            cid TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            filename TEXT,
            mime_type TEXT NOT NULL,
            size INTEGER NOT NULL,
            width INTEGER,
            height INTEGER,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS quotas (
            entity_id TEXT PRIMARY KEY,
            used_bytes INTEGER DEFAULT 0,
            max_bytes INTEGER DEFAULT 104857600
        );
        CREATE INDEX IF NOT EXISTS idx_media_owner ON media(owner_id);
    """)
    await db.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("[Media Service] Started")
    yield
    if db: await db.close()

app = FastAPI(title="MESH Media Service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def compute_cid(data: bytes) -> str:
    """Compute content ID (hash) for data"""
    return hashlib.sha256(data).hexdigest()

def get_path(cid: str, variant: str = "original") -> str:
    return f"{STORAGE_PATH}/{variant}/{cid}"

async def resize_image(data: bytes, max_size: int) -> bytes:
    """Resize image to max dimension"""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        fmt = img.format or "JPEG"
        img.save(output, format=fmt, quality=85)
        return output.getvalue()
    except ImportError:
        return data  # PIL not available, return original
    except Exception:
        return data

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "media"}

@app.post("/api/media/upload")
async def upload_media(
    file: UploadFile = File(...),
    owner_id: str = Query(...),
):
    """Upload a media file"""
    # Read file
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Max size: {MAX_FILE_SIZE // 1024 // 1024}MB")
    
    # Validate mime type
    mime = file.content_type or "application/octet-stream"
    if not mime.startswith(("image/", "video/", "audio/")):
        raise HTTPException(400, "Only image, video, and audio files allowed")
    
    # Compute CID
    cid = compute_cid(data)
    
    # Check if already exists
    cursor = await db.execute("SELECT cid FROM media WHERE cid = ?", (cid,))
    if await cursor.fetchone():
        return {"cid": cid, "url": f"/api/media/{cid}", "exists": True}
    
    # Check quota
    cursor = await db.execute("SELECT used_bytes, max_bytes FROM quotas WHERE entity_id = ?", (owner_id,))
    quota = await cursor.fetchone()
    used = quota["used_bytes"] if quota else 0
    max_bytes = quota["max_bytes"] if quota else 100 * 1024 * 1024
    
    if used + len(data) > max_bytes:
        raise HTTPException(400, "Storage quota exceeded")
    
    # Save original
    with open(get_path(cid, "original"), "wb") as f:
        f.write(data)
    
    # Generate thumbnail for images
    width, height = None, None
    if mime.startswith("image/"):
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(data))
            width, height = img.size
            
            # Create thumbnail
            thumb_data = await resize_image(data, 200)
            with open(get_path(cid, "thumb"), "wb") as f:
                f.write(thumb_data)
        except:
            pass
    
    # Save metadata
    now = datetime.utcnow().isoformat()
    await db.execute("""
        INSERT INTO media (cid, owner_id, filename, mime_type, size, width, height, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (cid, owner_id, file.filename, mime, len(data), width, height, now))
    
    # Update quota
    await db.execute("""
        INSERT INTO quotas (entity_id, used_bytes) VALUES (?, ?)
        ON CONFLICT(entity_id) DO UPDATE SET used_bytes = used_bytes + ?
    """, (owner_id, len(data), len(data)))
    
    await db.commit()
    
    return {
        "cid": cid,
        "url": f"/api/media/{cid}",
        "thumb_url": f"/api/media/{cid}/thumb" if mime.startswith("image/") else None,
        "size": len(data),
        "mime_type": mime,
        "width": width,
        "height": height,
    }

@app.get("/api/media/{cid}")
async def get_media(cid: str):
    """Get media by CID"""
    cursor = await db.execute("SELECT * FROM media WHERE cid = ?", (cid,))
    meta = await cursor.fetchone()
    if not meta:
        raise HTTPException(404, "Media not found")
    
    path = get_path(cid, "original")
    if not os.path.exists(path):
        raise HTTPException(404, "Media file not found")
    
    def iterfile():
        with open(path, "rb") as f:
            yield from f
    
    return StreamingResponse(iterfile(), media_type=meta["mime_type"])

@app.get("/api/media/{cid}/thumb")
async def get_thumbnail(cid: str):
    """Get thumbnail"""
    cursor = await db.execute("SELECT mime_type FROM media WHERE cid = ?", (cid,))
    meta = await cursor.fetchone()
    if not meta:
        raise HTTPException(404, "Media not found")
    
    path = get_path(cid, "thumb")
    if not os.path.exists(path):
        # Fall back to original
        path = get_path(cid, "original")
    
    if not os.path.exists(path):
        raise HTTPException(404, "File not found")
    
    def iterfile():
        with open(path, "rb") as f:
            yield from f
    
    return StreamingResponse(iterfile(), media_type=meta["mime_type"])

@app.get("/api/media/{cid}/info")
async def get_media_info(cid: str):
    """Get media metadata"""
    cursor = await db.execute("SELECT * FROM media WHERE cid = ?", (cid,))
    meta = await cursor.fetchone()
    if not meta:
        raise HTTPException(404, "Media not found")
    return dict(meta)

@app.delete("/api/media/{cid}")
async def delete_media(cid: str, owner_id: str = Query(...)):
    """Delete media (owner only)"""
    cursor = await db.execute("SELECT owner_id, size FROM media WHERE cid = ?", (cid,))
    meta = await cursor.fetchone()
    if not meta:
        raise HTTPException(404, "Media not found")
    if meta["owner_id"] != owner_id:
        raise HTTPException(403, "Not owner")
    
    # Delete files
    for variant in ["original", "thumb"]:
        path = get_path(cid, variant)
        if os.path.exists(path):
            os.remove(path)
    
    # Update quota
    await db.execute("UPDATE quotas SET used_bytes = used_bytes - ? WHERE entity_id = ?", 
                     (meta["size"], owner_id))
    
    # Delete record
    await db.execute("DELETE FROM media WHERE cid = ?", (cid,))
    await db.commit()
    
    return {"status": "deleted"}

@app.get("/api/quota/{entity_id}")
async def get_quota(entity_id: str):
    """Get storage quota"""
    cursor = await db.execute("SELECT used_bytes, max_bytes FROM quotas WHERE entity_id = ?", (entity_id,))
    quota = await cursor.fetchone()
    if not quota:
        return {"used_bytes": 0, "max_bytes": 100 * 1024 * 1024, "used_percent": 0}
    return {
        "used_bytes": quota["used_bytes"],
        "max_bytes": quota["max_bytes"],
        "used_percent": round(quota["used_bytes"] / quota["max_bytes"] * 100, 2),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "12005")))
