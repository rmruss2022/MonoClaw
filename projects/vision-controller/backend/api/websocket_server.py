"""
WebSocket Server for Vision Controller
Real-time gesture streaming to frontend
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Set, Dict, Any
import json
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")
        
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        self.active_connections.discard(websocket)
        logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")
        
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

# Global connection manager
manager = ConnectionManager()

async def handle_gesture_stream(websocket: WebSocket):
    """
    Handle WebSocket connection for gesture streaming
    
    This endpoint receives gesture data from backend processing
    and forwards it to connected frontend clients
    """
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client (could be ping, config update, etc.)
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get('type', 'unknown')
                
                if message_type == 'ping':
                    await manager.send_personal_message({
                        'type': 'pong',
                        'timestamp': message.get('timestamp')
                    }, websocket)
                    
                elif message_type == 'subscribe':
                    # Client wants to subscribe to gesture updates
                    await manager.send_personal_message({
                        'type': 'subscribed',
                        'message': 'Subscribed to gesture updates'
                    }, websocket)
                    
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                    
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {data}")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected (WebSocketDisconnect)")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

async def broadcast_gesture_update(gesture_data: Dict[str, Any]):
    """
    Broadcast gesture update to all connected clients
    
    Args:
        gesture_data: Dict containing gesture, confidence, hand info
    """
    message = {
        'type': 'gesture_update',
        'data': gesture_data
    }
    await manager.broadcast(message)

async def broadcast_hand_landmarks(landmarks_data: Dict[str, Any]):
    """
    Broadcast hand landmark data for visualization
    
    Args:
        landmarks_data: Dict containing hand landmarks
    """
    message = {
        'type': 'landmarks',
        'data': landmarks_data
    }
    await manager.broadcast(message)

# FastAPI WebSocket route setup (to be imported by main server)
def setup_websocket_routes(app):
    """
    Setup WebSocket routes in FastAPI app
    
    Usage:
        from backend.api.websocket_server import setup_websocket_routes
        setup_websocket_routes(app)
    """
    
    @app.websocket("/ws/gestures")
    async def websocket_endpoint(websocket: WebSocket):
        await handle_gesture_stream(websocket)
    
    logger.info("WebSocket routes configured at /ws/gestures")

if __name__ == "__main__":
    print("WebSocket Server Module")
    print("=" * 50)
    print("This module provides WebSocket functionality")
    print("Import and use with FastAPI:")
    print()
    print("from backend.api.websocket_server import setup_websocket_routes, broadcast_gesture_update")
    print("setup_websocket_routes(app)")
