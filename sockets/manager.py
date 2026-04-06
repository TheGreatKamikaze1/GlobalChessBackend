from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_games: Dict[str, List[WebSocket]] = {}

    async def connect(self, game_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_games.setdefault(game_id, []).append(websocket)

    def disconnect(self, game_id: str, websocket: WebSocket):
        sockets = self.active_games.get(game_id)
        if not sockets:
            return

        if websocket in sockets:
            sockets.remove(websocket)

        if not sockets:
            self.active_games.pop(game_id, None)

    async def broadcast(self, game_id: str, message: dict, sender: WebSocket):
        for ws in list(self.active_games.get(game_id, [])):
            if ws != sender:
                try:
                    await ws.send_json(message)
                except Exception:
                    self.disconnect(game_id, ws)
                
MAX_CONNECTIONS = 10
user_connections = {}

def can_connect(user_id):
    user_connections[user_id] = user_connections.get(user_id, 0) + 1
    return user_connections[user_id] <= MAX_CONNECTIONS
