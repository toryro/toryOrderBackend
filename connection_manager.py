from fastapi import WebSocket
from typing import List, Dict
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.display_snapshots: Dict[int, list] = {}

    async def connect(self, websocket: WebSocket, store_id: int):
        await websocket.accept()
        if store_id not in self.active_connections:
            self.active_connections[store_id] = []
        self.active_connections[store_id].append(websocket)
        print(f"--- Store {store_id}: 새로운 기기가 연결되었습니다. ---")
        snapshot = self.display_snapshots.get(store_id, [])
        await websocket.send_text(json.dumps({"type": "RESTORE_DISPLAY", "displayOrders": snapshot}))

    def save_snapshot(self, store_id: int, display_orders: list):
        self.display_snapshots[store_id] = display_orders

    def disconnect(self, websocket: WebSocket, store_id: int):
        if store_id in self.active_connections:
            if websocket in self.active_connections[store_id]:
                self.active_connections[store_id].remove(websocket)

    async def broadcast(self, message: str, store_id: int):
        if store_id not in self.active_connections:
            return
        dead = []
        for connection in self.active_connections[store_id]:
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for conn in dead:
            self.active_connections[store_id].remove(conn)

    async def ping_all(self):
        """모든 연결에 heartbeat ping을 보내고 끊긴 소켓을 제거한다."""
        ping_msg = json.dumps({"type": "ping"})
        for store_id in list(self.active_connections.keys()):
            dead = []
            for connection in self.active_connections[store_id]:
                try:
                    await connection.send_text(ping_msg)
                except Exception:
                    dead.append(connection)
            for conn in dead:
                self.active_connections[store_id].remove(conn)

manager = ConnectionManager()