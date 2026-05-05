"""WebSocket endpoint for real-time EDAS data updates.

This module provides WebSocket connections for instant disease detection updates.
When new sensor data arrives, all connected clients are notified immediately.
"""

import asyncio
import json
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# WebSocket Connection Manager
# =============================================================================

class EDASConnectionManager:
    """Manages WebSocket connections for real-time EDAS updates."""
    
    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection to register
        """
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        
        logger.info(
            "New WebSocket client connected",
            extra={"total_connections": len(self.active_connections)}
        )
    
    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection to remove
        """
        async with self._lock:
            self.active_connections.discard(websocket)
        
        logger.info(
            "WebSocket client disconnected",
            extra={"total_connections": len(self.active_connections)}
        )
    
    async def broadcast(self, message: dict):
        """Send a message to all connected clients.
        
        Args:
            message: Dictionary to send (will be converted to JSON)
        """
        if not self.active_connections:
            return
        
        json_message = json.dumps(message)
        disconnected = set()
        
        async with self._lock:
            connections = self.active_connections.copy()
        
        for connection in connections:
            try:
                await connection.send_text(json_message)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected.add(connection)
        
        # Remove disconnected clients
        if disconnected:
            async with self._lock:
                self.active_connections -= disconnected
        
        logger.debug(
            "Broadcast message to clients",
            extra={
                "clients_reached": len(connections) - len(disconnected),
                "clients_failed": len(disconnected),
            }
        )
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific client.
        
        Args:
            message: Dictionary to send
            websocket: Target WebSocket connection
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")


# Global connection manager instance
edas_ws_manager = EDASConnectionManager()


# =============================================================================
# WebSocket Endpoints
# =============================================================================

@router.websocket("/ws/edas/live")
async def websocket_edas_live(websocket: WebSocket):
    """WebSocket endpoint for real-time EDAS sensor data updates.
    
    **Connection URL:** `ws://localhost:8000/api/v1/edas-data/ws/edas/live`
    
    **Message Types Received by Client:**
    
    1. **Connection Confirmation:**
       ```json
       {
         "type": "connection",
         "status": "connected",
         "message": "Connected to EDAS live data stream"
       }
       ```
    
    2. **New Sensor Data:**
       ```json
       {
         "type": "sensor_data",
         "data": {
           "device_id": "edas_zone1",
           "plant_temperature": 29.63,
           "air_temperature": 29.83,
           "humidity": 81.71,
           "temperature_difference": -0.20,
           "timestamp": "2026-01-06T23:45:00+05:30",
           "hour": 23,
           "is_day": false,
           "time_period": "night"
         }
       }
       ```
    
    3. **Disease Prediction Update:**
       ```json
       {
         "type": "prediction",
         "data": {
           "sensor_data": {...},
           "prediction": {
             "disease_risk_level": "high",
             "risk_score": 85,
             "alerts": [...],
             "recommendations": [...]
           }
         }
       }
       ```
    
    4. **Heartbeat (keep-alive):**
       ```json
       {
         "type": "heartbeat",
         "timestamp": "2026-01-06T23:45:00+05:30"
       }
       ```
    
    **Client Messages to Server:**
    
    - `{"type": "ping"}` - Request heartbeat response
    - `{"type": "get_latest"}` - Request latest data immediately
    
    **Usage Example (JavaScript):**
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/v1/edas-data/ws/edas/live');
    
    ws.onopen = () => {
        console.log('Connected to EDAS live stream');
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'sensor_data') {
            updateDiseaseCard(data.data);
        }
    };
    ```
    """
    await edas_ws_manager.connect(websocket)
    
    try:
        # Send connection confirmation
        await edas_ws_manager.send_personal_message(
            {
                "type": "connection",
                "status": "connected",
                "message": "Connected to EDAS live data stream",
                "info": "You will receive real-time updates when new sensor data arrives"
            },
            websocket
        )
        
        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages (with timeout for heartbeat)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # 30 second timeout
                )
                
                try:
                    message = json.loads(data)
                    
                    # Handle ping request
                    if message.get("type") == "ping":
                        await edas_ws_manager.send_personal_message(
                            {
                                "type": "pong",
                                "timestamp": asyncio.get_event_loop().time()
                            },
                            websocket
                        )
                    
                    # Handle get_latest request (requires JWT — same scope as REST)
                    elif message.get("type") == "get_latest":
                        from app.db.collections import users as user_repo
                        from app.db.collections.edas_sensor_data import get_latest_edas_reading
                        from app.db.mongodb import get_database
                        from app.services.auth_service import decode_jwt

                        token = message.get("token")
                        if not token:
                            await edas_ws_manager.send_personal_message(
                                {
                                    "type": "error",
                                    "detail": "get_latest requires a Bearer token in the message",
                                },
                                websocket,
                            )
                            continue

                        payload = decode_jwt(token)
                        email = payload.get("email") if payload else None
                        if not email:
                            await edas_ws_manager.send_personal_message(
                                {
                                    "type": "error",
                                    "detail": "Invalid or expired token",
                                },
                                websocket,
                            )
                            continue

                        db = get_database()
                        user = await user_repo.get_user_by_email(db, email)
                        if not user:
                            await edas_ws_manager.send_personal_message(
                                {
                                    "type": "error",
                                    "detail": "User not found",
                                },
                                websocket,
                            )
                            continue

                        latest = await get_latest_edas_reading(
                            db, user_id=str(user["_id"])
                        )

                        if latest:
                            await edas_ws_manager.send_personal_message(
                                {
                                    "type": "sensor_data",
                                    "data": latest,
                                },
                                websocket,
                            )
                
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON from WebSocket client")
            
            except asyncio.TimeoutError:
                # Send heartbeat if no messages for 30 seconds
                await edas_ws_manager.send_personal_message(
                    {
                        "type": "heartbeat",
                        "timestamp": asyncio.get_event_loop().time()
                    },
                    websocket
                )
    
    except WebSocketDisconnect:
        await edas_ws_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected normally")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await edas_ws_manager.disconnect(websocket)


# =============================================================================
# Helper Function for Broadcasting Updates
# =============================================================================

async def broadcast_new_sensor_data(sensor_data: dict):
    """Broadcast new sensor data to all connected WebSocket clients.
    
    Call this function after inserting new data into MongoDB to notify
    all connected clients immediately.
    
    Args:
        sensor_data: The sensor data dictionary to broadcast
    
    Example:
        ```python
        # After inserting data
        await broadcast_new_sensor_data({
            "device_id": "edas_zone1",
            "plant_temperature": 29.63,
            ...
        })
        ```
    """
    await edas_ws_manager.broadcast({
        "type": "sensor_data",
        "data": sensor_data,
        "timestamp": asyncio.get_event_loop().time()
    })


async def broadcast_disease_prediction(prediction_data: dict):
    """Broadcast disease prediction to all connected WebSocket clients.
    
    Args:
        prediction_data: Full prediction response including sensor data and prediction
    """
    await edas_ws_manager.broadcast({
        "type": "prediction",
        "data": prediction_data,
        "timestamp": asyncio.get_event_loop().time()
    })


# Export the manager for use in other modules
__all__ = [
    "router",
    "edas_ws_manager",
    "broadcast_new_sensor_data",
    "broadcast_disease_prediction",
]




