import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(title="MT5 Control Center API", version="1.0.0")
BRIDGE_URL = os.getenv("MT5_BRIDGE_URL", "").rstrip("/")
BRIDGE_KEY = os.getenv("MT5_BRIDGE_API_KEY", "")


def headers() -> dict[str, str]:
    return {"X-API-Key": BRIDGE_KEY} if BRIDGE_KEY else {}


async def bridge_get(path: str, params: dict[str, Any] | None = None):
    if not BRIDGE_URL:
        raise HTTPException(503, "MT5 bridge is not configured")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{BRIDGE_URL}{path}", params=params, headers=headers())
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"MT5 bridge HTTP {e.response.status_code}") from e
    except httpx.HTTPError as e:
        raise HTTPException(502, "MT5 bridge is unreachable") from e


async def bridge_post(path: str, payload: dict[str, Any]):
    if not BRIDGE_URL:
        raise HTTPException(503, "MT5 bridge is not configured")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{BRIDGE_URL}{path}", json=payload, headers=headers())
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"MT5 bridge HTTP {e.response.status_code}") from e
    except httpx.HTTPError as e:
        raise HTTPException(502, "MT5 bridge is unreachable") from e


class OrderRequest(BaseModel):
    symbol: str
    volume: float = Field(gt=0)
    order_type: str = Field(pattern="^(buy|sell)$")
    sl: float | None = None
    tp: float | None = None
    deviation: int = Field(default=20, ge=0)
    magic: int = Field(default=10001, ge=0)
    comment: str = "MT5 Control Center"


@app.get("/")
def root():
    return {"name": "MT5 Control Center", "status": "online", "version": "1.0.0"}


@app.get("/api/health")
async def health():
    if not BRIDGE_URL:
        return {"status": "ok", "service": "api", "mt5": "bridge-not-configured"}
    try:
        return {"status": "ok", "service": "api", "mt5": await bridge_get("/health")}
    except HTTPException as e:
        return {"status": "degraded", "service": "api", "mt5": "unreachable", "detail": e.detail}


@app.get("/api/mt5/status")
async def mt5_status():
    return await bridge_get("/status")


@app.get("/api/account")
async def account():
    return await bridge_get("/account")


@app.get("/api/positions")
async def positions(symbol: str | None = Query(None)):
    return await bridge_get("/positions", {"symbol": symbol} if symbol else None)


@app.get("/api/orders")
async def orders(symbol: str | None = Query(None)):
    return await bridge_get("/orders", {"symbol": symbol} if symbol else None)


@app.get("/api/symbols")
async def symbols(search: str | None = Query(None)):
    return await bridge_get("/symbols", {"search": search} if search else None)


@app.get("/api/tick/{symbol}")
async def tick(symbol: str):
    return await bridge_get(f"/tick/{symbol}")


@app.get("/api/history")
async def history(days: int = Query(7, ge=1, le=90)):
    return await bridge_get("/history", {"days": days})


@app.post("/api/order")
async def create_order(order: OrderRequest):
    return await bridge_post("/order", order.model_dump())


@app.post("/api/position/{ticket}/close")
async def close_position(ticket: int):
    return await bridge_post(f"/position/{ticket}/close", {})
