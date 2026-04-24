#!/usr/bin/env python3
"""
MESH Notification Service
Real-time notifications via WebSocket and async delivery
"""
import os
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiosqlite

DB_PATH = os.environ.get("NOTIF_DB_PATH", "notifications.db")

# Connection manager for WebSocket
class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, Set[WebSocket]] = {}  # entity_id -> websockets
    
    async def connect(self, websocket: WebSocket, entity_id: str):
        await websocket.accept()
        if entity_id not in self.active:
            self.active[entity_id] = set()
        self.active[entity_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, entity_id: str):
        if entity_id in self.active:
            self.active[entity_id].discard(websocket)
    
    async def send_to_user(self, entity_id: str, message: dict):
        if entity_id in self.active:
            for ws in list(self.active[entity_id]):
                try:
                    await ws.send_json(message)
                except:
                    self.active[entity_id].discard(ws)

manager = ConnectionManager()
db: Optional[aiosqlite.Connection] = None

async def init_db():
    global db
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            recipient_id TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT,
            data TEXT,
            read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
            entity_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            PRIMARY KEY (entity_id, channel)
        );
        CREATE INDEX IF NOT EXISTS idx_notif_recipient ON notifications(recipient_id);
    """)
    await db.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("[Notification Service] Started")
    yield
    if db: await db.close()

app = FastAPI(title="MESH Notification Service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class NotificationCreate(BaseModel):
    recipient_id: str
    type: str  # like, reply, follow, mention, system
    title: str
    body: Optional[str] = None
    data: Optional[dict] = None

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "notification"}

@app.post("/api/notifications")
async def create_notification(notif: NotificationCreate):
    """Create and deliver a notification"""
    import secrets
    notif_id = secrets.token_hex(16)
    now = datetime.utcnow().isoformat()
    
    await db.execute("""
        INSERT INTO notifications (id, recipient_id, type, title, body, data, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (notif_id, notif.recipient_id, notif.type, notif.title, notif.body, 
          json.dumps(notif.data) if notif.data else None, now))
    await db.commit()
    
    # Real-time delivery
    message = {"id": notif_id, "type": notif.type, "title": notif.title, "body": notif.body, "data": notif.data, "created_at": now}
    await manager.send_to_user(notif.recipient_id, {"event": "notification", "data": message})
    
    return {"id": notif_id, "delivered": notif.recipient_id in manager.active}

@app.get("/api/notifications/{entity_id}")
async def get_notifications(entity_id: str, limit: int = 50, unread_only: bool = False):
    """Get notifications for a user"""
    query = "SELECT * FROM notifications WHERE recipient_id = ?"
    params = [entity_id]
    if unread_only:
        query += " AND read = 0"
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    
    return {"items": [dict(row) for row in rows]}

@app.put("/api/notifications/{notif_id}/read")
async def mark_read(notif_id: str):
    """Mark notification as read"""
    await db.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notif_id,))
    await db.commit()
    return {"status": "read"}

@app.put("/api/notifications/{entity_id}/read-all")
async def mark_all_read(entity_id: str):
    """Mark all notifications as read"""
    await db.execute("UPDATE notifications SET read = 1 WHERE recipient_id = ?", (entity_id,))
    await db.commit()
    return {"status": "all_read"}

@app.websocket("/ws/{entity_id}")
async def websocket_endpoint(websocket: WebSocket, entity_id: str):
    await manager.connect(websocket, entity_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle ping/pong or other messages
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, entity_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "12004")))
