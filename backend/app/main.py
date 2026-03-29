from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    cycles,
    history,
    live_route,
    paper_route,
    prices,
    settings_route,
    spot_futures_route,
)
from app.api.websocket import ws_manager
from app.config import settings
from app.deps import (
    aggregator,
    cycle_logger,
    exchange,
    futures_exchange,
    live_executor,
    paper_trader,
    scanner,
    spot_futures,
    telegram,
    volatility,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Background task references
_scan_task: asyncio.Task | None = None
_ws_task: asyncio.Task | None = None
_sf_task: asyncio.Task | None = None


async def spot_futures_scanner_loop():
    """Background loop for spot-futures arbitrage scanning.
    Only takes the BEST opportunity per scan (no concurrent positions)."""
    while True:
        try:
            if aggregator.tickers:
                opportunities = await spot_futures.scan(aggregator.tickers)
                if opportunities:
                    # Take only the best one per scan
                    best = opportunities[0]
                    await ws_manager.broadcast(
                        {"type": "spot_futures", "data": best}
                    )
                    await cycle_logger.log_spot_futures(best)
                    await telegram.send(
                        f"🔄 <b>Spot-Futures</b>\n"
                        f"{best['symbol']}: {best['premium_pct']:.3f}% premium\n"
                        f"Net: {best['net_profit_pct']:.3f}%\n"
                        f"Dir: {best['direction']}"
                    )
        except Exception as e:
            logger.error(f"Spot-futures scan error: {e}")
        await asyncio.sleep(10)


async def broadcast_cycles(cycles_data: list[dict]) -> None:
    if not cycles_data:
        return
    await ws_manager.broadcast({"type": "cycles", "data": cycles_data})


async def notify_cycles_telegram(cycles_data: list[dict]) -> None:
    """Notify top cycle via Telegram (throttled to 1 per minute)."""
    if not telegram.is_configured or not cycles_data:
        return
    top = cycles_data[0]
    if top.get("net_profit_pct", 0) >= settings.min_profit_threshold_pct:
        await telegram.notify_cycle(top)


async def persist_cycles(cycles_data: list[dict]) -> None:
    for cycle in cycles_data:
        await cycle_logger.log_cycle(cycle)


async def execute_paper_trades(cycles_data: list[dict]) -> None:
    if not paper_trader.enabled:
        return
    for cycle in cycles_data:
        result = await paper_trader.try_execute(cycle, scanner.tickers)
        if result:
            await ws_manager.broadcast(
                {"type": "paper_trade", "data": result}
            )
            await telegram.notify_paper_trade(result)


async def execute_live_trades(cycles_data: list[dict]) -> None:
    if not live_executor.enabled:
        return
    for cycle in cycles_data:
        result = await live_executor.execute_cycle(cycle, scanner.tickers)
        if result:
            await ws_manager.broadcast(
                {
                    "type": "live_trade",
                    "data": {
                        "trade_id": result.id,
                        "currencies": result.currencies,
                        "profit_usdt": float(result.profit_usdt),
                        "profit_pct": result.profit_pct,
                        "status": result.status,
                        "duration_ms": result.total_duration_ms,
                    },
                }
            )
            await telegram.notify_live_trade(
                {
                    "currencies": result.currencies,
                    "profit_usdt": float(result.profit_usdt),
                    "profit_pct": result.profit_pct,
                    "status": result.status,
                    "duration_ms": result.total_duration_ms,
                }
            )


scanner.on_cycle_update(broadcast_cycles)
scanner.on_cycle_update(notify_cycles_telegram)
scanner.on_cycle_update(persist_cycles)
scanner.on_cycle_update(execute_paper_trades)
scanner.on_cycle_update(execute_live_trades)

if settings.operation_mode == "paper":
    paper_trader.enable()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scan_task, _ws_task, _sf_task
    logger.info("Starting crypto-arbitrage backend...")
    logger.info(
        f"Mode: {settings.operation_mode} | "
        f"Auto-trade: {settings.auto_trade}"
    )
    logger.info(
        f"Paper: {'ON' if paper_trader.enabled else 'OFF'} | "
        f"Live: {'READY' if settings.auto_trade else 'OFF'}"
    )

    # Start price polling
    poll_interval = settings.poll_interval_ms / 1000.0
    _ws_task = asyncio.create_task(aggregator.start(interval_sec=poll_interval))

    # Wait for initial data
    await asyncio.sleep(2)

    # Start cycle scanner
    _scan_task = asyncio.create_task(scanner.start_scanning())

    # Start spot-futures scanner
    _sf_task = asyncio.create_task(spot_futures_scanner_loop())

    yield

    logger.info("Shutting down...")
    scanner.stop()
    aggregator.stop()
    if _scan_task:
        _scan_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _scan_task
    if _ws_task:
        _ws_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _ws_task
    if _sf_task:
        _sf_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _sf_task
    await exchange.close()
    await futures_exchange.close()


app = FastAPI(
    title="Crypto Arbitrage - Triangular",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cycles.router, prefix="/api/cycles", tags=["cycles"])
app.include_router(prices.router, prefix="/api/prices", tags=["prices"])
app.include_router(
    settings_route.router, prefix="/api/settings", tags=["settings"]
)
app.include_router(history.router, prefix="/api/history", tags=["history"])
app.include_router(
    paper_route.router, prefix="/api/paper", tags=["paper-trading"]
)
app.include_router(
    live_route.router, prefix="/api/live", tags=["live-trading"]
)
app.include_router(
    spot_futures_route.router, prefix="/api/spot-futures", tags=["spot-futures"]
)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": settings.operation_mode,
        "auto_trade": settings.auto_trade,
        "paper_trading": paper_trader.enabled,
        "live_trading": live_executor.enabled,
        "ws_stream": aggregator.get_stats(),
        "scanner": scanner.get_stats(),
        "paper": paper_trader.get_stats(),
        "live": live_executor.get_stats(),
        "telegram": telegram.get_stats(),
        "volatility": volatility.get_stats(),
        "spot_futures": spot_futures.get_stats(),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        if scanner.cycles:
            await websocket.send_json(
                {"type": "cycles", "data": scanner.cycles}
            )
        if paper_trader.enabled:
            await websocket.send_json(
                {"type": "paper_stats", "data": paper_trader.get_stats()}
            )
        if live_executor.enabled:
            await websocket.send_json(
                {"type": "live_stats", "data": live_executor.get_stats()}
            )
        while True:
            try:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
    except Exception:
        pass
    finally:
        ws_manager.disconnect(websocket)
