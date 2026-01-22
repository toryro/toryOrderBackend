from fastapi import WebSocket
from typing import List, Dict

class ConnectionManager:
    def __init__(self):
        # 어떤 가게(int)에 어떤 소켓들(List)이 연결되어 있는지 관리하는 딕셔너리
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, store_id: int):
        await websocket.accept()
        if store_id not in self.active_connections:
            self.active_connections[store_id] = []
        self.active_connections[store_id].append(websocket)
        print(f"--- Store {store_id}: 새로운 기기가 연결되었습니다. ---")

    def disconnect(self, websocket: WebSocket, store_id: int):
        if store_id in self.active_connections:
            if websocket in self.active_connections[store_id]:
                self.active_connections[store_id].remove(websocket)

    # 특정 가게에 연결된 모든 기기(주방태블릿, 카운터PC 등)에 메시지 전송
    async def broadcast(self, message: str, store_id: int):
        if store_id in self.active_connections:
            for connection in self.active_connections[store_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    print(f"전송 실패: {e}")

# 전역에서 하나만 쓸 매니저 객체 생성
manager = ConnectionManager()