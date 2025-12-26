from fastapi import WebSocket, WebSocketDisconnect
from sockets.manager import ConnectionManager

manager = ConnectionManager()

async def game_socket(websocket: WebSocket):
    game_id = websocket.query_params.get("gameId")
    user_name = websocket.query_params.get("userName")
    color = websocket.query_params.get("color")

    await manager.connect(game_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()

            event = data.get("event")

            if event == "join-game":
                await manager.broadcast(game_id, {
                    "event": "player-joined",
                    "userName": user_name,
                    "color": color
                }, websocket)

            elif event == "make-move":
                await manager.broadcast(game_id, {
                    "event": "game-move",
                    "move": data["move"],
                    "userName": user_name
                }, websocket)

            elif event == "update-cursor":
                await manager.broadcast(game_id, {
                    "event": "cursor-update",
                    "position": data["position"]
                }, websocket)

            elif event == "leave-game":
                manager.disconnect(game_id, websocket)
                await manager.broadcast(game_id, {
                    "event": "player-left",
                    "userName": user_name
                }, websocket)
                break

    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)
