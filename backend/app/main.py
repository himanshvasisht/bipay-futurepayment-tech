"""BiPay backend entrypoint: minimal, modular FastAPI app.

Mount only the router modules and provide a WebSocket endpoint for
realtime transaction events. Business logic lives in the router
modules under `app.*`.
"""

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.database import connect_to_database, close_database_connection
from app.auth.router import router as auth_router
from app.payments.router import router as payments_router
from app.merchant.router import router as merchant_router
from app.realtime import realtime_manager


# App setup
app = FastAPI(title="BiPay - Biometric Payment System", version="2.0.0")

# CORS (development-friendly defaults)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logger
logger = logging.getLogger("bipay")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)



# Lifespan event handler (FastAPI >=0.95)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    logger.info("Starting BiPay application")
    await connect_to_database()
    yield
    logger.info("Shutting down BiPay application")
    await close_database_connection()

# App setup (with lifespan)
app = FastAPI(title="BiPay - Biometric Payment System", version="2.0.0", lifespan=lifespan)


# Mount routers from the modular packages
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(payments_router, prefix="/api/v1/payments", tags=["Payments"])
app.include_router(merchant_router, prefix="/api/v1/merchant", tags=["Merchant"])


@app.get("/", tags=["System"])
async def root():
    return {"message": "BiPay API", "version": "2.0.0"}


@app.get("/health", tags=["System"])
async def health():
    return {"status": "healthy"}


# WebSocket for realtime transaction events
@app.websocket("/ws/transactions")
async def websocket_transactions(websocket: WebSocket):
    await realtime_manager.connect(websocket)
    try:
        # keep the connection open; clients may send pings or no data at all
        while True:
            await websocket.receive_text()
    except Exception:
        # connection closed or error, silently disconnect
        pass
    finally:
        await realtime_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
