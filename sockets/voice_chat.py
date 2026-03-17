import os
import json
import logging
from typing import Dict, List, Optional

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import Game

logger = logging.getLogger(__name__)

voice_router = APIRouter()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALG = "HS256"


def _get_user_id_from_token(token: str) -> Optional[str]:
    if not JWT_SECRET:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG], options={"verify_exp": True})
        return payload.get("id")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _get_db() -> Session:
    return SessionLocal()


class ConnectionManager:
    def __init__(self):
        # room_id -> list[WebSocket] (max 2)
        self.rooms: Dict[str, List[WebSocket]] = {}
        # websocket -> user_id (for logging/debug)
        self.ws_users: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str) -> int:
        """Add player to room. Returns player index (0 or 1)."""
        await websocket.accept()

        if room_id not in self.rooms:
            self.rooms[room_id] = []

        room = self.rooms[room_id]

        if len(room) >= 2:
            await websocket.send_text(json.dumps({"type": "error", "message": "Room is full"}))
            await websocket.close(code=1008)
            return -1

        room.append(websocket)
        self.ws_users[websocket] = user_id

        player_index = len(room) - 1
        logger.info(f"[voice] user={user_id} joined room={room_id} idx={player_index} ({len(room)}/2)")

        await websocket.send_text(
            json.dumps({"type": "joined", "player_index": player_index, "partner_ready": len(room) == 2})
        )

        if len(room) == 2:
            # notify player 0 partner joined
            try:
                await room[0].send_text(json.dumps({"type": "partner_joined"}))
            except Exception:
                pass

        return player_index

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.rooms:
            room = self.rooms[room_id]
            if websocket in room:
                room.remove(websocket)

            self.ws_users.pop(websocket, None)

            if len(room) == 0:
                del self.rooms[room_id]

    async def relay(self, sender: WebSocket, room_id: str, message: dict):
        room = self.rooms.get(room_id) or []
        for ws in room:
            if ws != sender:
                try:
                    await ws.send_text(json.dumps(message))
                except Exception as e:
                    logger.warning(f"[voice] relay failed: {e}")

    async def notify_partner_left(self, sender: WebSocket, room_id: str):
        room = self.rooms.get(room_id) or []
        for ws in room:
            if ws != sender:
                try:
                    await ws.send_text(json.dumps({"type": "partner_left"}))
                except Exception:
                    pass


manager = ConnectionManager()


async def _reject(websocket: WebSocket, message: str, code: int = 1008):
    # must accept to send a message
    await websocket.accept()
    await websocket.send_text(json.dumps({"type": "error", "message": message}))
    await websocket.close(code=code)


@voice_router.websocket("/ws/voice/{game_id}")
async def voice_signaling(websocket: WebSocket, game_id: str):
    """
    Authenticated WebRTC signaling endpoint.
    Connect like: wss://.../ws/voice/{gameId}?token=JWT
    """

    token = websocket.query_params.get("token")
    if not token:
        return await _reject(websocket, "Missing token")

    user_id = _get_user_id_from_token(token)
    if not user_id:
        return await _reject(websocket, "Invalid or expired token")

    # verify user is participant of game
    db = _get_db()
    try:
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return await _reject(websocket, "Game not found")

        if user_id not in (str(game.white_id), str(game.black_id)):
            return await _reject(websocket, "Not a participant in this game")

    finally:
        db.close()

    player_index = await manager.connect(websocket, game_id, user_id)
    if player_index == -1:
        return

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            t = msg.get("type")

            # relay WebRTC signaling to partner
            if t in ("offer", "answer", "ice-candidate"):
                await manager.relay(websocket, game_id, msg)

            # mic state relay (UI)
            elif t == "mic_status":
                await manager.relay(websocket, game_id, {"type": "partner_mic_status", "active": bool(msg.get("active"))})

            # optional keepalive
            elif t == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            else:
                # ignore unknown types (don’t crash)
                await websocket.send_text(json.dumps({"type": "error", "message": "Unknown message type"}))

    except WebSocketDisconnect:
        await manager.notify_partner_left(websocket, game_id)
        manager.disconnect(websocket, game_id)

    except Exception as e:
        logger.error(f"[voice] error room={game_id}: {e}")
        await manager.notify_partner_left(websocket, game_id)
        manager.disconnect(websocket, game_id)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass