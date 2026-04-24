"""
Relay v1.4.1 Implementation - Network Layer

Based on Relay_v1.4.1.md:
- HTTP REST API (§16, §17)
- WebSocket (§18)
- Signature verification on writes
"""

import json
import asyncio
import logging
import base64
from typing import Optional, Dict, List, Callable
from datetime import datetime

import aiohttp
from aiohttp import web
import websockets
from websockets.server import WebSocketServerProtocol

from storage import Storage, Identity, LogEvent, StateObject, LogEventType
from crypto import verify_object_signature, generate_event_id

logger = logging.getLogger(__name__)


# =============================================================================
# HTTP API SERVER
# =============================================================================

class HTTPServer:
    """
    HTTP REST API server per §16, §17.
    
    Implements:
    - GET/PUT /actors/{actor_id}/identity
    - POST /actors/{actor_id}/log
    - GET /actors/{actor_id}/log
    - GET/PUT /actors/{actor_id}/state/{object_id}
    """
    
    def __init__(self, storage: Storage, host: str = "0.0.0.0", port: int = 8080):
        self.storage = storage
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner = None
        self._setup_routes()
    
    def _setup_routes(self):
        # Health
        self.app.router.add_get('/health', self._health)
        self.app.router.add_get('/metrics', self._metrics)
        
        # Identity (§8)
        self.app.router.add_get('/actors/{actor_id}/identity', self._get_identity)
        self.app.router.add_put('/actors/{actor_id}/identity', self._put_identity)
        
        # Log (§10, §16.3)
        self.app.router.add_get('/actors/{actor_id}/log', self._get_log)
        self.app.router.add_post('/actors/{actor_id}/log', self._append_log)
        self.app.router.add_get('/actors/{actor_id}/log/events/{event_id}', self._get_event)
        
        # State (§11, §16.1)
        self.app.router.add_get('/actors/{actor_id}/state/{object_id}', self._get_state)
        self.app.router.add_put('/actors/{actor_id}/state/{object_id}', self._put_state)
        
        # Channels (§13)
        self.app.router.add_post('/channels', self._create_channel)
        self.app.router.add_get('/channels/{channel_id}', self._get_channel)
        
        # Feed definitions (§11.1)
        self.app.router.add_get('/feeds/{object_id}', self._get_feed)
        self.app.router.add_put('/feeds/{object_id}', self._put_feed)
        self.app.router.add_get('/feeds/{object_id}/execute', self._execute_feed)
        
        # Sync
        self.app.router.add_post('/sync', self._sync)
    
    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        logger.info(f"HTTP server started on http://{self.host}:{self.port}")
    
    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
    
    # === Health ===
    
    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "protocol": "relay-v1.4.1"})
    
    async def _metrics(self, request: web.Request) -> web.Response:
        metrics = await self.storage.get_metrics()
        return web.json_response(metrics)
    
    # === Identity (§8) ===
    
    async def _get_identity(self, request: web.Request) -> web.Response:
        actor_id = request.match_info['actor_id']
        identity = await self.storage.get_identity(actor_id)
        if identity:
            return web.json_response(identity.to_dict())
        return web.json_response({"error": "Not found"}, status=404)
    
    async def _put_identity(self, request: web.Request) -> web.Response:
        actor_id = request.match_info['actor_id']
        data = await request.json()
        
        # Verify signature
        public_key = base64.b64decode(data.get('keys', {}).get('active', ''))
        if not verify_object_signature(data, public_key):
            return web.json_response({"error": "Invalid signature"}, status=400)
        
        identity = Identity(
            actor_id=actor_id,
            public_key=public_key,
            encryption_key=base64.b64decode(data.get('encryption_key', '')),
            display_name=data.get('display_name', ''),
            bio=data.get('bio', ''),
            origins=data.get('origins', {}),
            created_at=datetime.fromisoformat(data['created_at'].rstrip('Z')),
            updated_at=datetime.fromisoformat(data['updated_at'].rstrip('Z')),
            sig=base64.b64decode(data.get('sig', '')),
        )
        
        seq = await self.storage.put_identity(identity)
        return web.json_response({"seq": seq}, status=201)
    
    # === Log (§10, §16.3) ===
    
    async def _get_log(self, request: web.Request) -> web.Response:
        actor_id = request.match_info['actor_id']
        limit = int(request.query.get('limit', 100))
        since = int(request.query.get('since_seq', 0))
        
        events = await self.storage.get_log(actor_id, limit, since)
        return web.json_response({
            "events": [e.to_dict() for e in events],
            "head": await self.storage.get_log_head(actor_id),
        })
    
    async def _append_log(self, request: web.Request) -> web.Response:
        actor_id = request.match_info['actor_id']
        data = await request.json()
        
        # Get actor's identity for signature verification
        identity = await self.storage.get_identity(actor_id)
        if not identity:
            return web.json_response({"error": "Actor not found"}, status=404)
        
        # Verify signature
        if not verify_object_signature(data, identity.public_key):
            return web.json_response({"error": "Invalid signature"}, status=400)
        
        # Create event
        event = LogEvent(
            id=data.get('id') or generate_event_id(data),
            actor=actor_id,
            type=LogEventType(data['type']),
            data=data.get('data', {}),
            ts=datetime.fromisoformat(data['ts'].rstrip('Z')),
            prev=data.get('prev'),
            sig=base64.b64decode(data.get('sig', '')),
            target=data.get('target'),
            expires_at=datetime.fromisoformat(data['expires_at'].rstrip('Z')) if data.get('expires_at') else None,
        )
        
        try:
            seq = await self.storage.append_log(event)
            return web.json_response({"seq": seq, "event_id": event.id}, status=201)
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=409)
    
    async def _get_event(self, request: web.Request) -> web.Response:
        event_id = request.match_info['event_id']
        event = await self.storage.get_event(event_id)
        if event:
            return web.json_response(event.to_dict())
        return web.json_response({"error": "Not found"}, status=404)
    
    # === State (§11, §16.1) ===
    
    async def _get_state(self, request: web.Request) -> web.Response:
        object_id = request.match_info['object_id']
        state = await self.storage.get_state(object_id)
        if state:
            return web.json_response(state.to_dict())
        return web.json_response({"error": "Not found"}, status=404)
    
    async def _put_state(self, request: web.Request) -> web.Response:
        actor_id = request.match_info['actor_id']
        object_id = request.match_info['object_id']
        data = await request.json()
        
        # Verify signature
        identity = await self.storage.get_identity(actor_id)
        if not identity:
            return web.json_response({"error": "Actor not found"}, status=404)
        
        if not verify_object_signature(data, identity.public_key):
            return web.json_response({"error": "Invalid signature"}, status=400)
        
        state = StateObject(
            object_id=object_id,
            actor=actor_id,
            type=data['type'],
            version=data['version'],
            payload=data.get('payload', {}),
            created_at=datetime.fromisoformat(data['created_at'].rstrip('Z')),
            updated_at=datetime.fromisoformat(data['updated_at'].rstrip('Z')),
            sig=base64.b64decode(data.get('sig', '')),
        )
        
        try:
            seq = await self.storage.put_state(state)
            return web.json_response({"seq": seq}, status=201)
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=409)
    
    # === Channels (§13) ===
    
    async def _create_channel(self, request: web.Request) -> web.Response:
        from storage import ChannelGenesis
        data = await request.json()
        
        genesis = ChannelGenesis(
            owner_actor_id=data['owner_actor_id'],
            name=data['name'],
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()).rstrip('Z')),
        )
        
        channel = await self.storage.create_channel(genesis)
        return web.json_response({
            "channel_id": channel.channel_id,
            "genesis": genesis.to_dict(),
        }, status=201)
    
    async def _get_channel(self, request: web.Request) -> web.Response:
        channel_id = request.match_info['channel_id']
        channel = await self.storage.get_channel(channel_id)
        if channel:
            return web.json_response({
                "channel_id": channel.channel_id,
                "owner": channel.owner,
                "members": channel.members,
                "genesis": channel.genesis.to_dict(),
            })
        return web.json_response({"error": "Not found"}, status=404)
    
    # === Feed Definitions (§11.1) ===
    
    async def _get_feed(self, request: web.Request) -> web.Response:
        object_id = request.match_info['object_id']
        feed_def = await self.storage.get_feed_definition(object_id)
        if feed_def:
            return web.json_response(feed_def.to_dict())
        return web.json_response({"error": "Not found"}, status=404)
    
    async def _put_feed(self, request: web.Request) -> web.Response:
        from storage import FeedDefinition
        object_id = request.match_info['object_id']
        data = await request.json()
        
        feed_def = FeedDefinition(
            object_id=object_id,
            actor=data['actor'],
            version=data['version'],
            sources=data['sources'],
            reduce=data['reduce'],
            params=data.get('params', {}),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()).rstrip('Z')),
            updated_at=datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat()).rstrip('Z')),
        )
        
        try:
            seq = await self.storage.put_feed_definition(feed_def)
            return web.json_response({"seq": seq}, status=201)
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=409)
    
    async def _execute_feed(self, request: web.Request) -> web.Response:
        from feeds import FeedReducerEngine
        object_id = request.match_info['object_id']
        
        feed_def = await self.storage.get_feed_definition(object_id)
        if not feed_def:
            return web.json_response({"error": "Not found"}, status=404)
        
        engine = FeedReducerEngine(self.storage)
        result = await engine.reduce(feed_def)
        
        return web.json_response(result.to_dict())
    
    # === Sync ===
    
    async def _sync(self, request: web.Request) -> web.Response:
        data = await request.json()
        since_seq = data.get('since_seq', 0)
        
        metrics = await self.storage.get_metrics()
        return web.json_response({
            "current_seq": metrics['sequence'],
        })


# =============================================================================
# WEBSOCKET SERVER (§18)
# =============================================================================

class WebSocketServer:
    """WebSocket server for real-time sync (§18)."""
    
    def __init__(self, storage: Storage, host: str = "0.0.0.0", port: int = 8765):
        self.storage = storage
        self.host = host
        self.port = port
        self.clients: Dict[str, WebSocketServerProtocol] = {}
        self.subscriptions: Dict[str, set] = {}
        self.server = None
    
    async def start(self):
        self.server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port
        )
        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
    
    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
    
    async def _handle_client(self, websocket: WebSocketServerProtocol):
        client_id = str(id(websocket))
        self.clients[client_id] = websocket
        self.subscriptions[client_id] = set()
        
        try:
            async for message in websocket:
                await self._handle_message(client_id, websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            del self.clients[client_id]
            del self.subscriptions[client_id]
    
    async def _handle_message(self, client_id: str, websocket, raw_message: str):
        try:
            msg = json.loads(raw_message)
            msg_type = msg.get('type')
            
            if msg_type == 'subscribe':
                actors = msg.get('actors', [])
                self.subscriptions[client_id].update(actors)
                await websocket.send(json.dumps({
                    "type": "subscribed",
                    "actors": list(self.subscriptions[client_id]),
                }))
            
            elif msg_type == 'query':
                result = await self._handle_query(msg.get('query', {}))
                await websocket.send(json.dumps({
                    "type": "result",
                    "request_id": msg.get('request_id'),
                    "data": result,
                }))
        
        except Exception as e:
            await websocket.send(json.dumps({
                "type": "error",
                "error": str(e),
            }))
    
    async def _handle_query(self, query: dict) -> dict:
        query_type = query.get('type')
        
        if query_type == 'get_identity':
            identity = await self.storage.get_identity(query['actor_id'])
            return {"identity": identity.to_dict() if identity else None}
        
        elif query_type == 'get_log':
            events = await self.storage.get_log(query['actor_id'])
            return {"events": [e.to_dict() for e in events]}
        
        elif query_type == 'get_followers':
            followers = await self.storage.get_followers(query['actor_id'])
            return {"followers": followers}
        
        return {"error": f"Unknown query: {query_type}"}
    
    async def broadcast_event(self, event: LogEvent):
        """Broadcast event to subscribers."""
        msg = json.dumps({
            "type": "event",
            "event": event.to_dict(),
        })
        
        for client_id, subscribed in self.subscriptions.items():
            if event.actor in subscribed:
                websocket = self.clients.get(client_id)
                if websocket:
                    try:
                        await websocket.send(msg)
                    except:
                        pass


# =============================================================================
# RELAY CLIENT (Federation)
# =============================================================================

class RelayClient:
    """Client for connecting to other relays."""
    
    def __init__(self, relay_url: str):
        self.relay_url = relay_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def connect(self):
        self.session = aiohttp.ClientSession()
    
    async def disconnect(self):
        if self.session:
            await self.session.close()
    
    async def get_identity(self, actor_id: str) -> Optional[dict]:
        async with self.session.get(f"{self.relay_url}/actors/{actor_id}/identity") as resp:
            if resp.status == 200:
                return await resp.json()
        return None
    
    async def get_log(self, actor_id: str, since_seq: int = 0) -> List[dict]:
        async with self.session.get(
            f"{self.relay_url}/actors/{actor_id}/log",
            params={"since_seq": since_seq}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get('events', [])
        return []
    
    async def sync(self, since_seq: int = 0) -> dict:
        async with self.session.post(
            f"{self.relay_url}/sync",
            json={"since_seq": since_seq}
        ) as resp:
            if resp.status == 200:
                return await resp.json()
        return {"current_seq": 0}


# =============================================================================
# RELAY NODE
# =============================================================================

class RelayNode:
    """Complete relay node."""
    
    def __init__(self, storage: Storage, http_port: int = 8080, ws_port: int = 8765):
        self.storage = storage
        self.http_server = HTTPServer(storage, port=http_port)
        self.ws_server = WebSocketServer(storage, port=ws_port)
        self.peers: Dict[str, RelayClient] = {}
    
    async def start(self):
        await self.storage.initialize()
        await self.http_server.start()
        await self.ws_server.start()
        logger.info("Relay node started")
    
    async def stop(self):
        await self.http_server.stop()
        await self.ws_server.stop()
        for client in self.peers.values():
            await client.disconnect()
        await self.storage.close()
    
    async def add_peer(self, relay_url: str):
        client = RelayClient(relay_url)
        await client.connect()
        self.peers[relay_url] = client
        logger.info(f"Added peer: {relay_url}")
    
    async def sync_from_peer(self, relay_url: str, actor_id: str):
        """Sync an actor's log from a peer."""
        client = self.peers.get(relay_url)
        if not client:
            return
        
        events = await client.get_log(actor_id)
        for event_data in events:
            # Would need to verify and store
            pass
