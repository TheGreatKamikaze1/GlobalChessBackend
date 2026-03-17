"""
Chess Voice Chat - FastAPI WebRTC Signaling Server
---------------------------------------------------
This server handles WebRTC signaling (offer/answer/ICE candidates)
so two players in the same chess game can establish a peer-to-peer
audio connection.

How it works:
1. Both players join a "room" using their game ID
2. Player 1 sends an "offer" → server relays it to Player 2
3. Player 2 sends an "answer" → server relays it to Player 1
4. Both exchange ICE candidates → server relays them
5. WebRTC peer connection is established → audio flows directly P2P

Install dependencies:
    pip install fastapi uvicorn websockets python-multipart

Run:
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import logging
from typing import Dict, List
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Chess Voice Chat Signaling Server")

# Allow all origins for dev — tighten this in production to your domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# rooms: { room_id: [WebSocket, WebSocket] }
# Each room holds max 2 players (one chess game)
rooms: Dict[str, List[WebSocket]] = {}


class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str) -> int:
        """Add player to room. Returns player index (0 or 1)."""
        await websocket.accept()

        if room_id not in self.rooms:
            self.rooms[room_id] = []

        room = self.rooms[room_id]

        if len(room) >= 2:
            # Room is full — reject
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Room is full"
            }))
            await websocket.close()
            return -1

        room.append(websocket)
        player_index = len(room) - 1
        logger.info(f"Player {player_index} joined room '{room_id}' ({len(room)}/2 players)")

        # Tell the player their index and if partner is already here
        await websocket.send_text(json.dumps({
            "type": "joined",
            "player_index": player_index,
            "partner_ready": len(room) == 2
        }))

        # If second player just joined, tell player 0 their partner arrived
        if len(room) == 2:
            await room[0].send_text(json.dumps({
                "type": "partner_joined"
            }))

        return player_index

    def disconnect(self, websocket: WebSocket, room_id: str):
        """Remove player from room."""
        if room_id in self.rooms:
            room = self.rooms[room_id]
            if websocket in room:
                room.remove(websocket)
                logger.info(f"Player left room '{room_id}' ({len(room)}/2 players)")

            # Clean up empty rooms
            if len(room) == 0:
                del self.rooms[room_id]
                logger.info(f"Room '{room_id}' deleted (empty)")

    async def relay(self, sender: WebSocket, room_id: str, message: dict):
        """Relay a signaling message to the OTHER player in the room."""
        if room_id not in self.rooms:
            return

        room = self.rooms[room_id]
        for ws in room:
            if ws != sender:
                try:
                    await ws.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Failed to relay message: {e}")

    async def notify_partner_left(self, sender: WebSocket, room_id: str):
        """Tell the remaining player their partner disconnected."""
        if room_id not in self.rooms:
            return
        room = self.rooms[room_id]
        for ws in room:
            if ws != sender:
                try:
                    await ws.send_text(json.dumps({"type": "partner_left"}))
                except:
                    pass


manager = ConnectionManager()


@app.websocket("/ws/voice/{room_id}")
async def voice_signaling(websocket: WebSocket, room_id: str):
    """
    WebSocket endpoint for WebRTC signaling.
    room_id should be your chess game's unique ID.
    """
    player_index = await manager.connect(websocket, room_id)

    if player_index == -1:
        return  # Room was full, connection rejected

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            logger.info(f"Room '{room_id}' Player {player_index} → {msg_type}")

            # These are the 3 WebRTC signaling messages — just relay them to partner
            if msg_type in ("offer", "answer", "ice-candidate"):
                await manager.relay(websocket, room_id, message)

            # Player toggled their mic on/off — tell partner so they can show UI state
            elif msg_type == "mic_status":
                await manager.relay(websocket, room_id, {
                    "type": "partner_mic_status",
                    "active": message.get("active", False)
                })

    except WebSocketDisconnect:
        await manager.notify_partner_left(websocket, room_id)
        manager.disconnect(websocket, room_id)
        logger.info(f"Room '{room_id}' Player {player_index} disconnected")

    except Exception as e:
        logger.error(f"Error in room '{room_id}': {e}")
        await manager.notify_partner_left(websocket, room_id)
        manager.disconnect(websocket, room_id)


@app.get("/health")
async def health():
    """Health check + active rooms info."""
    return {
        "status": "ok",
        "active_rooms": len(manager.rooms),
        "rooms": {
            room_id: len(players)
            for room_id, players in manager.rooms.items()
        }
    }


@app.get("/")
async def root():
    return {"message": "Chess Voice Chat Signaling Server is running. Connect via WebSocket at /ws/voice/{room_id}"}