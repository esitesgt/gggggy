import os
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="MT5 Bridge", version="1.0.0")
API_KEY = os.getenv("BRIDGE_API_KEY", "")


def auth(key: str | None):
    if API_KEY and key != API_KEY:
        raise HTTPException(401, "Invalid bridge API key")


def connect() -> bool:
    path = os.getenv("MT5_TERMINAL_PATH")
    kwargs = {}
    if os.getenv("MT5_LOGIN"):
        kwargs["login"] = int(os.getenv("MT5_LOGIN"))
    if os.getenv("MT5_PASSWORD"):
        kwargs["password"] = os.getenv("MT5_PASSWORD")
    if os.getenv("MT5_SERVER"):
        kwargs["server"] = os.getenv("MT5_SERVER")
    return mt5.initialize(path, **kwargs) if path else mt5.initialize(**kwargs)


def require_mt5():
    if not connect():
        raise HTTPException(503, {"connected": False, "error": mt5.last_error()})


def as_dict(item):
    return item._asdict() if item else None


class OrderRequest(BaseModel):
    symbol: str
    volume: float = Field(gt=0)
    order_type: str = Field(pattern="^(buy|sell)$")
    sl: float | None = None
    tp: float | None = None
    deviation: int = Field(20, ge=0)
    magic: int = Field(10001, ge=0)
    comment: str = "MT5 Control Center"


@app.get("/health")
def health(x_api_key: str | None = Header(None)):
    auth(x_api_key)
    return {"status": "ok", "service": "mt5-bridge", "mt5_available": bool(mt5.version())}


@app.get("/status")
def status(x_api_key: str | None = Header(None)):
    auth(x_api_key)
    require_mt5()
    return {"connected": True, "version": mt5.version(), "terminal": as_dict(mt5.terminal_info()), "account": as_dict(mt5.account_info())}


@app.get("/account")
def account(x_api_key: str | None = Header(None)):
    auth(x_api_key); require_mt5()
    return as_dict(mt5.account_info()) or {}


@app.get("/positions")
def positions(symbol: str | None = Query(None), x_api_key: str | None = Header(None)):
    auth(x_api_key); require_mt5()
    data = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    return [as_dict(x) for x in (data or [])]


@app.get("/orders")
def orders(symbol: str | None = Query(None), x_api_key: str | None = Header(None)):
    auth(x_api_key); require_mt5()
    data = mt5.orders_get(symbol=symbol) if symbol else mt5.orders_get()
    return [as_dict(x) for x in (data or [])]


@app.get("/symbols")
def symbols(search: str | None = Query(None), x_api_key: str | None = Header(None)):
    auth(x_api_key); require_mt5()
    data = mt5.symbols_get(group=f"*{search}*") if search else mt5.symbols_get()
    return [{"name": x.name, "path": x.path, "visible": x.visible, "trade_mode": x.trade_mode} for x in (data or [])]


@app.get("/tick/{symbol}")
def tick(symbol: str, x_api_key: str | None = Header(None)):
    auth(x_api_key); require_mt5()
    if not mt5.symbol_select(symbol, True):
        raise HTTPException(404, f"Symbol not found: {symbol}")
    return as_dict(mt5.symbol_info_tick(symbol)) or {}


@app.get("/history")
def history(days: int = Query(7, ge=1, le=90), x_api_key: str | None = Header(None)):
    auth(x_api_key); require_mt5()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    data = mt5.history_deals_get(start, end)
    return [as_dict(x) for x in (data or [])]


@app.post("/order")
def order(req: OrderRequest, x_api_key: str | None = Header(None)):
    auth(x_api_key); require_mt5()
    info = mt5.symbol_info(req.symbol)
    if info is None:
        raise HTTPException(404, f"Symbol not found: {req.symbol}")
    if not info.visible:
        mt5.symbol_select(req.symbol, True)
    tick_info = mt5.symbol_info_tick(req.symbol)
    if tick_info is None:
        raise HTTPException(503, f"No tick data for {req.symbol}")
    order_type = mt5.ORDER_TYPE_BUY if req.order_type == "buy" else mt5.ORDER_TYPE_SELL
    price = tick_info.ask if req.order_type == "buy" else tick_info.bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": req.symbol,
        "volume": req.volume,
        "type": order_type,
        "price": price,
        "sl": req.sl or 0.0,
        "tp": req.tp or 0.0,
        "deviation": req.deviation,
        "magic": req.magic,
        "comment": req.comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    return as_dict(result) or {"error": mt5.last_error()}


@app.post("/position/{ticket}/close")
def close_position(ticket: int, x_api_key: str | None = Header(None)):
    auth(x_api_key); require_mt5()
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        raise HTTPException(404, f"Position not found: {ticket}")
    p = positions[0]
    tick_info = mt5.symbol_info_tick(p.symbol)
    if not tick_info:
        raise HTTPException(503, f"No tick data for {p.symbol}")
    close_type = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick_info.bid if p.type == mt5.POSITION_TYPE_BUY else tick_info.ask
    result = mt5.order_send({"action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol, "volume": p.volume, "type": close_type, "position": p.ticket, "price": price, "deviation": 20, "magic": 10001, "comment": "MT5 Control Center close", "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC})
    return as_dict(result) or {"error": mt5.last_error()}
