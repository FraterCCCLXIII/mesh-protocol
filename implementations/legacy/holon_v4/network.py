"""
HOLON v4 Implementation - Network Layer

HTTP API and WebSocket for relay communication:
- REST API for queries
- WebSocket for real-time sync
- Multi-relay federation
"""

import json
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Set, Callable, Any
from enum import Enum

import aiohttp
from aiohttp import web, WSMsgType
import websockets
from websockets.server import WebSocketServerProtocol

from storage import Storage, Entity, Content, Link, EntityKind, ContentKind, LinkKind, AccessType
from crypto import (
    SigningKeyPair, verify_object_signature, sign_object,
    canonical_json, generate_entity_id
)

logger = logging.getLogger(__name__)


# =============================================================================
# PROTOCOL MESSAGES
# =============================================================================

class MessageType(Enum):
    # Queries
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    QUERY = "query"
    
    # Responses
    EVENTS = "events"
    RESULT = "result"
    ERROR = "error"
    
    # Sync
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"
    
    # Real-time
    NEW_ENTITY = "new_entity"
    NEW_CONTENT = "new_content"
    NEW_LINK = "new_link"


@dataclass
class Message:
    type: MessageType
    data: dict
    request_id: Optional[str] = None
    
    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "data": self.data,
            "request_id": self.request_id,
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        obj = json.loads(json_str)
        return cls(
            type=MessageType(obj["type"]),
            data=obj["data"],
            request_id=obj.get("request_id"),
        )


# =============================================================================
# WEBSOCKET SERVER
# =============================================================================

class WebSocketServer:
    """WebSocket server for real-time sync."""
    
    def __init__(self, storage: Storage, host: str = "0.0.0.0", port: int = 8765):
        self.storage = storage
        self.host = host
        self.port = port
        self.clients: Dict[str, WebSocketServerProtocol] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # client_id -> set of entity_ids
        self.server = None
    
    async def start(self):
        """Start WebSocket server."""
        self.server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port
        )
        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
    
    async def stop(self):
        """Stop WebSocket server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
    
    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle a client connection."""
        client_id = str(id(websocket))
        self.clients[client_id] = websocket
        self.subscriptions[client_id] = set()
        
        logger.info(f"Client connected: {client_id}")
        
        try:
            async for message in websocket:
                await self._handle_message(client_id, websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            del self.clients[client_id]
            del self.subscriptions[client_id]
            logger.info(f"Client disconnected: {client_id}")
    
    async def _handle_message(self, client_id: str, websocket: WebSocketServerProtocol, raw_message: str):
        """Handle incoming message."""
        try:
            msg = Message.from_json(raw_message)
            
            if msg.type == MessageType.SUBSCRIBE:
                entities = msg.data.get("entities", [])
                self.subscriptions[client_id].update(entities)
                
                response = Message(
                    type=MessageType.RESULT,
                    data={"subscribed": list(self.subscriptions[client_id])},
                    request_id=msg.request_id,
                )
                await websocket.send(response.to_json())
            
            elif msg.type == MessageType.UNSUBSCRIBE:
                entities = msg.data.get("entities", [])
                self.subscriptions[client_id] -= set(entities)
                
                response = Message(
                    type=MessageType.RESULT,
                    data={"subscribed": list(self.subscriptions[client_id])},
                    request_id=msg.request_id,
                )
                await websocket.send(response.to_json())
            
            elif msg.type == MessageType.QUERY:
                result = await self._handle_query(msg.data)
                response = Message(
                    type=MessageType.RESULT,
                    data=result,
                    request_id=msg.request_id,
                )
                await websocket.send(response.to_json())
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            response = Message(
                type=MessageType.ERROR,
                data={"error": str(e)},
                request_id=msg.request_id if 'msg' in dir() else None,
            )
            await websocket.send(response.to_json())
    
    async def _handle_query(self, query: dict) -> dict:
        """Handle a query."""
        query_type = query.get("type")
        
        if query_type == "get_entity":
            entity = await self.storage.get_entity(query["id"])
            return {"entity": entity.to_dict() if entity else None}
        
        elif query_type == "get_content":
            content = await self.storage.get_content(query["id"])
            return {"content": content.to_dict() if content else None}
        
        elif query_type == "get_followers":
            followers = await self.storage.get_followers(query["entity_id"])
            return {"followers": followers}
        
        elif query_type == "get_following":
            following = await self.storage.get_following(query["entity_id"])
            return {"following": following}
        
        elif query_type == "search_content":
            content = await self.storage.search_content(query["query"], query.get("limit", 20))
            return {"content": [c.to_dict() for c in content]}
        
        return {"error": f"Unknown query type: {query_type}"}
    
    async def broadcast_new_entity(self, entity: Entity):
        """Broadcast new entity to subscribed clients."""
        msg = Message(
            type=MessageType.NEW_ENTITY,
            data=entity.to_dict(),
        )
        await self._broadcast_to_subscribers(entity.id, msg)
    
    async def broadcast_new_content(self, content: Content):
        """Broadcast new content to subscribed clients."""
        msg = Message(
            type=MessageType.NEW_CONTENT,
            data=content.to_dict(),
        )
        await self._broadcast_to_subscribers(content.author, msg)
    
    async def broadcast_new_link(self, link: Link):
        """Broadcast new link to subscribed clients."""
        msg = Message(
            type=MessageType.NEW_LINK,
            data=link.to_dict(),
        )
        # Broadcast to subscribers of both source and target
        await self._broadcast_to_subscribers(link.source, msg)
        await self._broadcast_to_subscribers(link.target, msg)
    
    async def _broadcast_to_subscribers(self, entity_id: str, msg: Message):
        """Send message to all clients subscribed to an entity."""
        for client_id, subscribed in self.subscriptions.items():
            if entity_id in subscribed:
                websocket = self.clients.get(client_id)
                if websocket:
                    try:
                        await websocket.send(msg.to_json())
                    except:
                        pass


# =============================================================================
# HTTP API SERVER
# =============================================================================

class HTTPServer:
    """HTTP REST API server."""
    
    def __init__(self, storage: Storage, host: str = "0.0.0.0", port: int = 8080):
        self.storage = storage
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner = None
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Set up API routes."""
        self.app.router.add_get('/health', self._health)
        self.app.router.add_get('/metrics', self._metrics)
        
        # Entity routes
        self.app.router.add_get('/entities/{id}', self._get_entity)
        self.app.router.add_post('/entities', self._create_entity)
        self.app.router.add_get('/entities/{id}/followers', self._get_followers)
        self.app.router.add_get('/entities/{id}/following', self._get_following)
        self.app.router.add_get('/entities/search', self._search_entities)
        
        # Content routes
        self.app.router.add_get('/content/{id}', self._get_content)
        self.app.router.add_post('/content', self._create_content)
        self.app.router.add_get('/content/{id}/replies', self._get_replies)
        self.app.router.add_get('/content/search', self._search_content)
        self.app.router.add_get('/entities/{id}/content', self._get_entity_content)
        
        # Link routes
        self.app.router.add_get('/links/{id}', self._get_link)
        self.app.router.add_post('/links', self._create_link)
        
        # Sync routes
        self.app.router.add_post('/sync', self._sync)
        
        # Discovery routes
        self.app.router.add_get('/discover/follows-of-follows/{id}', self._follows_of_follows)
    
    async def start(self):
        """Start HTTP server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        logger.info(f"HTTP server started on http://{self.host}:{self.port}")
    
    async def stop(self):
        """Stop HTTP server."""
        if self.runner:
            await self.runner.cleanup()
    
    # =========================================================================
    # Route handlers
    # =========================================================================
    
    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})
    
    async def _metrics(self, request: web.Request) -> web.Response:
        metrics = await self.storage.get_metrics()
        return web.json_response(metrics)
    
    async def _get_entity(self, request: web.Request) -> web.Response:
        entity_id = request.match_info['id']
        entity = await self.storage.get_entity(entity_id)
        if entity:
            return web.json_response(entity.to_dict())
        return web.json_response({"error": "Not found"}, status=404)
    
    async def _create_entity(self, request: web.Request) -> web.Response:
        data = await request.json()
        
        # Verify signature
        public_key = bytes.fromhex(data.get('public_key_hex', ''))
        if not verify_object_signature(data, public_key):
            return web.json_response({"error": "Invalid signature"}, status=400)
        
        entity = Entity(
            id=data['id'],
            kind=EntityKind(data['kind']),
            public_key=public_key,
            encryption_key=bytes.fromhex(data.get('encryption_key_hex', '')),
            handle=data.get('handle'),
            profile=data.get('profile', {}),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            sig=bytes.fromhex(data.get('sig_hex', '')),
        )
        
        await self.storage.create_entity(entity)
        return web.json_response(entity.to_dict(), status=201)
    
    async def _get_followers(self, request: web.Request) -> web.Response:
        entity_id = request.match_info['id']
        followers = await self.storage.get_followers(entity_id)
        return web.json_response({"followers": followers})
    
    async def _get_following(self, request: web.Request) -> web.Response:
        entity_id = request.match_info['id']
        following = await self.storage.get_following(entity_id)
        return web.json_response({"following": following})
    
    async def _search_entities(self, request: web.Request) -> web.Response:
        query = request.query.get('q', '')
        limit = int(request.query.get('limit', 20))
        entities = await self.storage.search_entities(query, limit)
        return web.json_response({"entities": [e.to_dict() for e in entities]})
    
    async def _get_content(self, request: web.Request) -> web.Response:
        content_id = request.match_info['id']
        content = await self.storage.get_content(content_id)
        if content:
            return web.json_response(content.to_dict())
        return web.json_response({"error": "Not found"}, status=404)
    
    async def _create_content(self, request: web.Request) -> web.Response:
        data = await request.json()
        
        # Get author's public key for verification
        author = await self.storage.get_entity(data['author'])
        if not author:
            return web.json_response({"error": "Author not found"}, status=400)
        
        if not verify_object_signature(data, author.public_key):
            return web.json_response({"error": "Invalid signature"}, status=400)
        
        content = Content(
            id=data['id'],
            kind=ContentKind(data['kind']),
            author=data['author'],
            body=data['body'],
            created_at=datetime.fromisoformat(data['created_at']),
            context=data.get('context'),
            reply_to=data.get('reply_to'),
            access=AccessType(data.get('access', 'public')),
            encrypted=data.get('encrypted', False),
            encryption_metadata=data.get('encryption_metadata'),
            sig=bytes.fromhex(data.get('sig_hex', '')),
        )
        
        await self.storage.create_content(content)
        return web.json_response(content.to_dict(), status=201)
    
    async def _get_replies(self, request: web.Request) -> web.Response:
        content_id = request.match_info['id']
        replies = await self.storage.get_replies(content_id)
        return web.json_response({"replies": [r.to_dict() for r in replies]})
    
    async def _search_content(self, request: web.Request) -> web.Response:
        query = request.query.get('q', '')
        limit = int(request.query.get('limit', 20))
        content = await self.storage.search_content(query, limit)
        return web.json_response({"content": [c.to_dict() for c in content]})
    
    async def _get_entity_content(self, request: web.Request) -> web.Response:
        entity_id = request.match_info['id']
        limit = int(request.query.get('limit', 100))
        content = await self.storage.get_content_by_author(entity_id, limit)
        return web.json_response({"content": [c.to_dict() for c in content]})
    
    async def _get_link(self, request: web.Request) -> web.Response:
        link_id = request.match_info['id']
        link = await self.storage.get_link(link_id)
        if link:
            return web.json_response(link.to_dict())
        return web.json_response({"error": "Not found"}, status=404)
    
    async def _create_link(self, request: web.Request) -> web.Response:
        data = await request.json()
        
        # Get source entity's public key for verification
        source = await self.storage.get_entity(data['source'])
        if not source:
            return web.json_response({"error": "Source not found"}, status=400)
        
        if not verify_object_signature(data, source.public_key):
            return web.json_response({"error": "Invalid signature"}, status=400)
        
        link = Link(
            id=data['id'],
            kind=LinkKind(data['kind']),
            source=data['source'],
            target=data['target'],
            data=data.get('data', {}),
            created_at=datetime.fromisoformat(data['created_at']),
            tombstone=data.get('tombstone', False),
            sig=bytes.fromhex(data.get('sig_hex', '')),
        )
        
        await self.storage.create_link(link)
        return web.json_response(link.to_dict(), status=201)
    
    async def _sync(self, request: web.Request) -> web.Response:
        """Handle sync request from another relay."""
        data = await request.json()
        since_seq = data.get('since_seq', 0)
        
        # Return events since sequence
        # (Simplified - in production would batch properly)
        return web.json_response({
            "events": [],
            "current_seq": await self.storage.next_seq() - 1,
        })
    
    async def _follows_of_follows(self, request: web.Request) -> web.Response:
        entity_id = request.match_info['id']
        limit = int(request.query.get('limit', 20))
        suggestions = await self.storage.get_follows_of_follows(entity_id, limit)
        return web.json_response({"suggestions": suggestions})


# =============================================================================
# RELAY CLIENT
# =============================================================================

class RelayClient:
    """Client for connecting to other relays (federation)."""
    
    def __init__(self, relay_url: str):
        self.relay_url = relay_url.rstrip('/')
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self._message_handlers: Dict[MessageType, List[Callable]] = {}
    
    async def connect(self):
        """Connect to relay."""
        self.session = aiohttp.ClientSession()
        
        # Connect WebSocket
        ws_url = self.relay_url.replace('http', 'ws') + '/ws'
        try:
            self.ws = await websockets.connect(ws_url)
            asyncio.create_task(self._receive_loop())
        except Exception as e:
            logger.warning(f"Failed to connect WebSocket to {ws_url}: {e}")
    
    async def disconnect(self):
        """Disconnect from relay."""
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
    
    async def _receive_loop(self):
        """Receive messages from WebSocket."""
        try:
            async for message in self.ws:
                msg = Message.from_json(message)
                handlers = self._message_handlers.get(msg.type, [])
                for handler in handlers:
                    await handler(msg)
        except websockets.exceptions.ConnectionClosed:
            pass
    
    def on_message(self, message_type: MessageType, handler: Callable):
        """Register message handler."""
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)
    
    async def subscribe(self, entity_ids: List[str]):
        """Subscribe to entities."""
        if self.ws:
            msg = Message(
                type=MessageType.SUBSCRIBE,
                data={"entities": entity_ids},
            )
            await self.ws.send(msg.to_json())
    
    async def get_entity(self, entity_id: str) -> Optional[dict]:
        """Get entity from relay."""
        async with self.session.get(f"{self.relay_url}/entities/{entity_id}") as resp:
            if resp.status == 200:
                return await resp.json()
        return None
    
    async def get_content(self, content_id: str) -> Optional[dict]:
        """Get content from relay."""
        async with self.session.get(f"{self.relay_url}/content/{content_id}") as resp:
            if resp.status == 200:
                return await resp.json()
        return None
    
    async def post_entity(self, entity_data: dict) -> bool:
        """Post entity to relay."""
        async with self.session.post(
            f"{self.relay_url}/entities",
            json=entity_data
        ) as resp:
            return resp.status == 201
    
    async def post_content(self, content_data: dict) -> bool:
        """Post content to relay."""
        async with self.session.post(
            f"{self.relay_url}/content",
            json=content_data
        ) as resp:
            return resp.status == 201
    
    async def post_link(self, link_data: dict) -> bool:
        """Post link to relay."""
        async with self.session.post(
            f"{self.relay_url}/links",
            json=link_data
        ) as resp:
            return resp.status == 201
    
    async def sync(self, since_seq: int = 0) -> dict:
        """Sync with relay."""
        async with self.session.post(
            f"{self.relay_url}/sync",
            json={"since_seq": since_seq}
        ) as resp:
            if resp.status == 200:
                return await resp.json()
        return {"events": [], "current_seq": 0}


# =============================================================================
# RELAY NODE
# =============================================================================

class RelayNode:
    """A complete relay node with HTTP, WebSocket, and federation."""
    
    def __init__(self, storage: Storage, http_port: int = 8080, ws_port: int = 8765):
        self.storage = storage
        self.http_server = HTTPServer(storage, port=http_port)
        self.ws_server = WebSocketServer(storage, port=ws_port)
        self.peer_clients: Dict[str, RelayClient] = {}
    
    async def start(self):
        """Start the relay node."""
        await self.storage.initialize()
        await self.http_server.start()
        await self.ws_server.start()
        logger.info("Relay node started")
    
    async def stop(self):
        """Stop the relay node."""
        await self.http_server.stop()
        await self.ws_server.stop()
        for client in self.peer_clients.values():
            await client.disconnect()
        await self.storage.close()
        logger.info("Relay node stopped")
    
    async def add_peer(self, relay_url: str):
        """Add a peer relay for federation."""
        client = RelayClient(relay_url)
        await client.connect()
        self.peer_clients[relay_url] = client
        logger.info(f"Added peer: {relay_url}")
    
    async def remove_peer(self, relay_url: str):
        """Remove a peer relay."""
        if relay_url in self.peer_clients:
            await self.peer_clients[relay_url].disconnect()
            del self.peer_clients[relay_url]
            logger.info(f"Removed peer: {relay_url}")
    
    async def broadcast_to_peers(self, data: dict, data_type: str):
        """Broadcast data to all peers."""
        for url, client in self.peer_clients.items():
            try:
                if data_type == "entity":
                    await client.post_entity(data)
                elif data_type == "content":
                    await client.post_content(data)
                elif data_type == "link":
                    await client.post_link(data)
            except Exception as e:
                logger.error(f"Failed to broadcast to {url}: {e}")
