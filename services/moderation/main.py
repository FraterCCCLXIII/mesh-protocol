#!/usr/bin/env python3
"""
MESH Moderation Service
Attestation-based moderation with trust networks
"""
import os
import json
import secrets
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiosqlite

DB_PATH = os.environ.get("MOD_DB_PATH", "moderation.db")
db: Optional[aiosqlite.Connection] = None

async def init_db():
    global db
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS attestations (
            id TEXT PRIMARY KEY,
            issuer TEXT NOT NULL,
            subject TEXT NOT NULL,
            type TEXT NOT NULL,
            claim TEXT NOT NULL,
            evidence TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            revoked INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS trust_follows (
            follower TEXT NOT NULL,
            labeler TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (follower, labeler)
        );
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            reporter TEXT NOT NULL,
            subject TEXT NOT NULL,
            subject_type TEXT NOT NULL,
            reason TEXT NOT NULL,
            details TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            resolved_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_att_subject ON attestations(subject);
        CREATE INDEX IF NOT EXISTS idx_att_issuer ON attestations(issuer);
        CREATE INDEX IF NOT EXISTS idx_att_type ON attestations(type);
        CREATE INDEX IF NOT EXISTS idx_trust_follower ON trust_follows(follower);
        CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
    """)
    await db.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("[Moderation Service] Started")
    yield
    if db: await db.close()

app = FastAPI(title="MESH Moderation Service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Models
class AttestationCreate(BaseModel):
    issuer: str
    subject: str
    type: str  # spam, nsfw, misleading, harassment, verified, trusted
    claim: dict
    evidence: Optional[dict] = None
    expires_at: Optional[str] = None

class ReportCreate(BaseModel):
    reporter: str
    subject: str
    subject_type: str  # content, entity, group
    reason: str  # spam, harassment, illegal, other
    details: Optional[str] = None

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "moderation"}

# Attestations
@app.post("/api/attestations")
async def create_attestation(att: AttestationCreate):
    """Create a new attestation (label)"""
    att_id = secrets.token_hex(16)
    now = datetime.utcnow().isoformat()
    
    await db.execute("""
        INSERT INTO attestations (id, issuer, subject, type, claim, evidence, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (att_id, att.issuer, att.subject, att.type, json.dumps(att.claim),
          json.dumps(att.evidence) if att.evidence else None, now, att.expires_at))
    await db.commit()
    
    return {"id": att_id, "created_at": now}

@app.get("/api/attestations/{att_id}")
async def get_attestation(att_id: str):
    """Get attestation by ID"""
    cursor = await db.execute("SELECT * FROM attestations WHERE id = ?", (att_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Attestation not found")
    result = dict(row)
    result["claim"] = json.loads(result["claim"]) if result["claim"] else {}
    result["evidence"] = json.loads(result["evidence"]) if result["evidence"] else None
    return result

@app.get("/api/subjects/{subject}/labels")
async def get_subject_labels(subject: str, viewer: Optional[str] = None):
    """Get all labels for a subject, optionally filtered by viewer's trust network"""
    query = """
        SELECT a.* FROM attestations a
        WHERE a.subject = ? AND a.revoked = 0
        AND (a.expires_at IS NULL OR a.expires_at > ?)
    """
    params = [subject, datetime.utcnow().isoformat()]
    
    # If viewer specified, prioritize trusted labelers
    if viewer:
        query = """
            SELECT a.*, 
                CASE WHEN t.labeler IS NOT NULL THEN 1 ELSE 0 END as trusted
            FROM attestations a
            LEFT JOIN trust_follows t ON t.follower = ? AND t.labeler = a.issuer
            WHERE a.subject = ? AND a.revoked = 0
            AND (a.expires_at IS NULL OR a.expires_at > ?)
            ORDER BY trusted DESC, a.created_at DESC
        """
        params = [viewer, subject, datetime.utcnow().isoformat()]
    
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    
    labels = []
    for row in rows:
        label = dict(row)
        label["claim"] = json.loads(label["claim"]) if label["claim"] else {}
        labels.append(label)
    
    return {"subject": subject, "labels": labels}

@app.delete("/api/attestations/{att_id}")
async def revoke_attestation(att_id: str, issuer: str = Query(...)):
    """Revoke an attestation (issuer only)"""
    cursor = await db.execute("SELECT issuer FROM attestations WHERE id = ?", (att_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, "Attestation not found")
    if row["issuer"] != issuer:
        raise HTTPException(403, "Not issuer")
    
    await db.execute("UPDATE attestations SET revoked = 1 WHERE id = ?", (att_id,))
    await db.commit()
    return {"status": "revoked"}

# Trust Network
@app.post("/api/trust/follow")
async def follow_labeler(follower: str, labeler: str):
    """Follow a labeler (trust their labels)"""
    now = datetime.utcnow().isoformat()
    await db.execute("""
        INSERT OR REPLACE INTO trust_follows (follower, labeler, created_at)
        VALUES (?, ?, ?)
    """, (follower, labeler, now))
    await db.commit()
    return {"status": "following", "labeler": labeler}

@app.delete("/api/trust/follow")
async def unfollow_labeler(follower: str, labeler: str):
    """Unfollow a labeler"""
    await db.execute("DELETE FROM trust_follows WHERE follower = ? AND labeler = ?",
                     (follower, labeler))
    await db.commit()
    return {"status": "unfollowed"}

@app.get("/api/trust/{entity_id}")
async def get_trust_network(entity_id: str):
    """Get entity's trusted labelers"""
    cursor = await db.execute(
        "SELECT labeler, created_at FROM trust_follows WHERE follower = ?",
        (entity_id,)
    )
    rows = await cursor.fetchall()
    return {"entity_id": entity_id, "trusted_labelers": [dict(r) for r in rows]}

# Reports
@app.post("/api/reports")
async def create_report(report: ReportCreate):
    """Submit a content/user report"""
    report_id = secrets.token_hex(16)
    now = datetime.utcnow().isoformat()
    
    await db.execute("""
        INSERT INTO reports (id, reporter, subject, subject_type, reason, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (report_id, report.reporter, report.subject, report.subject_type,
          report.reason, report.details, now))
    await db.commit()
    
    return {"id": report_id, "status": "pending"}

@app.get("/api/reports")
async def list_reports(status: str = "pending", limit: int = 50):
    """List reports (for moderators)"""
    cursor = await db.execute(
        "SELECT * FROM reports WHERE status = ? ORDER BY created_at DESC LIMIT ?",
        (status, limit)
    )
    rows = await cursor.fetchall()
    return {"items": [dict(r) for r in rows]}

@app.put("/api/reports/{report_id}")
async def update_report(report_id: str, status: str, resolution: Optional[str] = None):
    """Update report status"""
    now = datetime.utcnow().isoformat()
    await db.execute(
        "UPDATE reports SET status = ?, resolved_at = ? WHERE id = ?",
        (status, now if status in ["resolved", "dismissed"] else None, report_id)
    )
    await db.commit()
    return {"id": report_id, "status": status}

# Content filtering
@app.post("/api/filter")
async def filter_content(content_ids: List[str], viewer: str):
    """Filter content based on viewer's trust network and global labels"""
    # Get viewer's trusted labelers
    cursor = await db.execute(
        "SELECT labeler FROM trust_follows WHERE follower = ?",
        (viewer,)
    )
    trusted = {row["labeler"] for row in await cursor.fetchall()}
    
    # Get labels for all content
    placeholders = ",".join("?" * len(content_ids))
    cursor = await db.execute(f"""
        SELECT subject, type, issuer FROM attestations
        WHERE subject IN ({placeholders})
        AND revoked = 0
        AND (expires_at IS NULL OR expires_at > ?)
    """, content_ids + [datetime.utcnow().isoformat()])
    
    # Build filter results
    labels_by_content = {}
    for row in await cursor.fetchall():
        cid = row["subject"]
        if cid not in labels_by_content:
            labels_by_content[cid] = {"trusted": [], "other": []}
        
        label = {"type": row["type"], "issuer": row["issuer"]}
        if row["issuer"] in trusted:
            labels_by_content[cid]["trusted"].append(label)
        else:
            labels_by_content[cid]["other"].append(label)
    
    # Determine visibility
    results = {}
    for cid in content_ids:
        labels = labels_by_content.get(cid, {"trusted": [], "other": []})
        
        # Check for blocking labels from trusted sources
        blocked = any(l["type"] in ["spam", "illegal", "harassment"] 
                     for l in labels["trusted"])
        
        # Check for warning labels
        warned = any(l["type"] in ["nsfw", "misleading"] 
                    for l in labels["trusted"])
        
        results[cid] = {
            "visible": not blocked,
            "warning": warned,
            "labels": labels,
        }
    
    return {"results": results}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "12006")))
