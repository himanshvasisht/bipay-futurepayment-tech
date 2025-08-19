"""
Simple WebSocket-based realtime broadcaster for transaction events.
Clients can connect to `/ws/transactions` and receive JSON messages when new transactions complete.
"""
from typing import List
from fastapi import WebSocket
import asyncio
import json
from loguru import logger

class RealtimeManager:
    def __init__(self):
        self.connections: List[WebSocket] = []
        self.lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.connections.append(ws)
            logger.info(f"Realtime: client connected (total={len(self.connections)})")

    async def disconnect(self, ws: WebSocket):
        async with self.lock:
            if ws in self.connections:
                self.connections.remove(ws)
                logger.info(f"Realtime: client disconnected (total={len(self.connections)})")

    async def broadcast(self, event: dict):
        message = json.dumps(event, default=str)
        async with self.lock:
            to_remove = []
            for ws in self.connections:
                try:
                    await ws.send_text(message)
                except Exception as e:
                    logger.warning(f"Realtime: failed to send to a client, scheduling removal: {e}")
                    to_remove.append(ws)
            for ws in to_remove:
                if ws in self.connections:
                    self.connections.remove(ws)

realtime_manager = RealtimeManager()
