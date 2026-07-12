"""WebSocket server for real-time updates.

Provides real-time updates for:
- Job pipeline progress
- Campaign status changes
- Inbox messages
- Review queue updates

Features:
- Room-based broadcasting (job:id, campaign:id, inbox)
- Automatic connection cleanup
- Heartbeat monitoring
- Error handling with fallback
"""
from __future__ import annotations

import asyncio
import json
from typing import Dict, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from app.core.auth import authenticate_ws, CurrentUser
from app.core.db import get_supabase
from app.core.logging import get_logger

log = get_logger(__name__)

router = APIRouter()


def _authorize_ws(token: Optional[str], *, job_id: str | None = None,
                  campaign_id: str | None = None) -> Optional[CurrentUser]:
    """Verify the WS token and (if a job/campaign is given) that it belongs to the
    caller's org. Returns CurrentUser on success, None on any failure."""
    if not token:
        return None
    try:
        user = authenticate_ws(token)
    except Exception:
        return None

    try:
        sb = get_supabase()
        if job_id is not None:
            r = sb.table("jobs").select("id").eq("id", job_id).eq("org_id", user.org_id).execute()
            if not r.data:
                return None
        if campaign_id is not None:
            r = sb.table("outreach_campaigns").select("id").eq("id", campaign_id).eq("org_id", user.org_id).execute()
            if not r.data:
                return None
    except Exception:
        return None

    return user


class ConnectionManager:
    """Manages WebSocket connections with room-based broadcasting."""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, room: str):
        """Accept and register a WebSocket connection to a room."""
        await websocket.accept()
        async with self._lock:
            if room not in self.active_connections:
                self.active_connections[room] = set()
            self.active_connections[room].add(websocket)
        log.info(f"WebSocket connected to room '{room}' (total: {len(self.active_connections[room])})")
    
    def disconnect(self, websocket: WebSocket, room: str):
        """Remove a WebSocket connection from a room."""
        if room in self.active_connections:
            self.active_connections[room].discard(websocket)
            if not self.active_connections[room]:
                del self.active_connections[room]
            log.info(f"WebSocket disconnected from room '{room}'")
    
    async def broadcast(self, room: str, message: dict):
        """
        Broadcast a message to all connections in a room.
        
        Args:
            room: Room identifier (e.g., "job:123", "campaign:456", "inbox")
            message: Message dictionary to send
        """
        if room not in self.active_connections:
            return
        
        dead_connections = set()
        message_json = json.dumps(message)
        
        for connection in self.active_connections[room].copy():
            try:
                await connection.send_text(message_json)
            except Exception as e:
                log.warning(f"Failed to send to connection in room '{room}': {e}")
                dead_connections.add(connection)
        
        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                for conn in dead_connections:
                    self.active_connections[room].discard(conn)
                if not self.active_connections[room]:
                    del self.active_connections[room]
            log.info(f"Cleaned up {len(dead_connections)} dead connections from room '{room}'")
    
    async def send_to_connection(self, websocket: WebSocket, message: dict):
        """Send a message to a specific connection."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            log.error(f"Failed to send message to connection: {e}")
    
    def get_room_count(self, room: str) -> int:
        """Get the number of active connections in a room."""
        return len(self.active_connections.get(room, set()))
    
    def get_total_connections(self) -> int:
        """Get the total number of active connections across all rooms."""
        return sum(len(conns) for conns in self.active_connections.values())


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_updates(websocket: WebSocket, job_id: str, token: Optional[str] = None):
    """
    WebSocket endpoint for job pipeline updates.

    Listens to Redis pub/sub for real-time updates from Celery tasks.
    Requires ?token=<JWT> and verifies the job belongs to the caller's org.
    """
    user = _authorize_ws(token, job_id=job_id)
    if not user:
        await websocket.close(code=4401)
        return

    room = f"job:{job_id}"
    await manager.connect(websocket, room)
    
    try:
        # Send initial connection confirmation
        await manager.send_to_connection(websocket, {
            "type": "connected",
            "room": room,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        # Subscribe to Redis pub/sub channel
        from app.core.db import get_redis
        import json
        
        redis = get_redis()
        pubsub = redis.pubsub()
        channel = f"ws:{room}"
        pubsub.subscribe(channel)
        
        # Create tasks for both WebSocket receive and Redis pub/sub
        async def listen_redis():
            """Listen for Redis pub/sub messages."""
            import asyncio
            while True:
                message = pubsub.get_message(ignore_subscribe_messages=True)
                if message and message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        await manager.send_to_connection(websocket, data)
                    except Exception as e:
                        log.warning(f"Failed to parse Redis message: {e}")
                await asyncio.sleep(0.1)  # Small delay to avoid busy loop
        
        async def listen_websocket():
            """Listen for WebSocket messages (ping/pong)."""
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    if data == "ping":
                        await manager.send_to_connection(websocket, {"type": "pong"})
                except asyncio.TimeoutError:
                    await manager.send_to_connection(websocket, {"type": "heartbeat"})
        
        # Run both listeners concurrently
        await asyncio.gather(listen_redis(), listen_websocket())
            
    except WebSocketDisconnect:
        log.info(f"WebSocket disconnected normally from {room}")
    except Exception as e:
        log.error(f"WebSocket error in {room}: {e}")
    finally:
        try:
            pubsub.unsubscribe(channel)
            pubsub.close()
        except:
            pass
        manager.disconnect(websocket, room)


@router.websocket("/ws/campaigns/{campaign_id}")
async def websocket_campaign_updates(websocket: WebSocket, campaign_id: str, token: Optional[str] = None):
    """
    WebSocket endpoint for campaign updates.

    Sends real-time updates for:
    - Campaign status changes
    - Lead counts
    - Send progress
    - Reply notifications
    Requires ?token=<JWT> and verifies the campaign belongs to the caller's org.
    """
    user = _authorize_ws(token, campaign_id=campaign_id)
    if not user:
        await websocket.close(code=4401)
        return

    room = f"campaign:{campaign_id}"
    await manager.connect(websocket, room)
    
    try:
        await manager.send_to_connection(websocket, {
            "type": "connected",
            "room": room,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await manager.send_to_connection(websocket, {"type": "pong"})
            except asyncio.TimeoutError:
                await manager.send_to_connection(websocket, {"type": "heartbeat"})
            
    except WebSocketDisconnect:
        log.info(f"WebSocket disconnected normally from {room}")
    except Exception as e:
        log.error(f"WebSocket error in {room}: {e}")
    finally:
        manager.disconnect(websocket, room)


@router.websocket("/ws/inbox")
async def websocket_inbox_updates(websocket: WebSocket, token: Optional[str] = None):
    """
    WebSocket endpoint for inbox updates.

    Sends real-time updates for:
    - New messages
    - Lead status changes
    - Unread count updates
    Requires ?token=<JWT>.
    """
    user = _authorize_ws(token)
    if not user:
        await websocket.close(code=4401)
        return

    room = "inbox"
    await manager.connect(websocket, room)
    
    try:
        await manager.send_to_connection(websocket, {
            "type": "connected",
            "room": room,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await manager.send_to_connection(websocket, {"type": "pong"})
            except asyncio.TimeoutError:
                await manager.send_to_connection(websocket, {"type": "heartbeat"})
            
    except WebSocketDisconnect:
        log.info(f"WebSocket disconnected normally from {room}")
    except Exception as e:
        log.error(f"WebSocket error in {room}: {e}")
    finally:
        manager.disconnect(websocket, room)


# Helper functions for emitting updates from other parts of the application

async def notify_job_update(job_id: str, update: dict):
    """
    Notify all clients subscribed to a job about an update.
    
    Args:
        job_id: Job ID
        update: Update data (status, stage, count, etc.)
    """
    await manager.broadcast(f"job:{job_id}", {
        "type": "job_update",
        "job_id": job_id,
        "data": update,
        "timestamp": asyncio.get_event_loop().time()
    })


async def notify_campaign_update(campaign_id: str, update: dict):
    """
    Notify all clients subscribed to a campaign about an update.
    
    Args:
        campaign_id: Campaign ID
        update: Update data (status, counts, etc.)
    """
    await manager.broadcast(f"campaign:{campaign_id}", {
        "type": "campaign_update",
        "campaign_id": campaign_id,
        "data": update,
        "timestamp": asyncio.get_event_loop().time()
    })


async def notify_inbox_update(update: dict):
    """
    Notify all clients subscribed to inbox about an update.
    
    Args:
        update: Update data (new message, status change, etc.)
    """
    await manager.broadcast("inbox", {
        "type": "inbox_update",
        "data": update,
        "timestamp": asyncio.get_event_loop().time()
    })


def get_websocket_stats() -> dict:
    """Get WebSocket connection statistics."""
    return {
        "total_connections": manager.get_total_connections(),
        "rooms": {
            room: len(conns) 
            for room, conns in manager.active_connections.items()
        }
    }
