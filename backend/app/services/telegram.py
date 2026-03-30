from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org"


class TelegramNotifier:
    """Sends notifications via Telegram Bot API."""

    def __init__(self) -> None:
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.enabled = bool(self.bot_token and self.chat_id)
        self._client: httpx.AsyncClient | None = None
        self._sent_count = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram."""
        if not self.is_configured:
            return False

        try:
            client = await self._get_client()
            resp = await client.post(
                f"{TELEGRAM_API}/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": parse_mode,
                },
            )
            resp.raise_for_status()
            self._sent_count += 1
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def notify_cycle(self, cycle: dict[str, Any]) -> bool:
        """Notify about a detected profitable cycle."""
        currencies = cycle.get("currencies", [])
        profit = cycle.get("net_profit_pct", 0)
        profit_usdt = cycle.get("calculated", {}).get("net_profit", 0)

        msg = (
            f"🔄 <b>Cycle Detected</b>\n"
            f"{' → '.join(currencies)}\n"
            f"Profit: <b>+{profit:.3f}%</b> (${profit_usdt:.4f})\n"
        )

        for leg in cycle.get("legs", []):
            side_emoji = "🟢" if leg["side"] == "buy" else "🔴"
            msg += f"  {side_emoji} {leg['pair']} {leg['side'].upper()}\n"

        return await self.send(msg)

    async def notify_paper_trade(self, trade: dict[str, Any]) -> bool:
        """Notify about a paper trade execution."""
        currencies = trade.get("currencies", [])
        profit = trade.get("profit_usdt", 0)
        profit_pct = trade.get("profit_pct", 0)
        emoji = "✅" if profit >= 0 else "❌"

        msg = (
            f"{emoji} <b>Paper Trade</b>\n"
            f"{' → '.join(currencies)}\n"
            f"P&L: <b>{'+' if profit >= 0 else ''}${profit:.4f}</b> "
            f"({profit_pct:.3f}%)\n"
            f"Balance: ${trade.get('balance', 0):.2f}"
        )

        return await self.send(msg)

    async def notify_live_trade(self, trade: dict[str, Any]) -> bool:
        """Notify about a live trade execution."""
        currencies = trade.get("currencies", [])
        profit = trade.get("profit_usdt", 0)
        profit_pct = trade.get("profit_pct", 0)
        status = trade.get("status", "unknown")
        emoji = "✅" if profit >= 0 else "❌"

        msg = (
            f"{emoji} <b>LIVE TRADE</b>\n"
            f"{' → '.join(currencies)}\n"
            f"P&L: <b>{'+' if profit >= 0 else ''}${profit:.4f}</b> "
            f"({profit_pct:.3f}%)\n"
            f"Status: {status}\n"
            f"Duration: {trade.get('duration_ms', 0):.0f}ms"
        )

        return await self.send(msg)

    async def notify_error(self, error: str) -> bool:
        """Notify about an error."""
        return await self.send(f"⚠️ <b>Error</b>\n{error}")

    async def notify_summary(self, stats: dict[str, Any]) -> bool:
        """Send periodic summary."""
        msg = (
            f"📊 <b>Summary</b>\n"
            f"Cycles: {stats.get('scan_count', 0)}\n"
            f"Found: {stats.get('current_cycles', 0)}\n"
            f"Top profit: {stats.get('top_profit', 0):.3f}%\n"
        )
        return await self.send(msg)

    def get_stats(self) -> dict[str, Any]:
        return {
            "configured": self.is_configured,
            "enabled": self.enabled,
            "sent_count": self._sent_count,
        }

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_updates(self, offset: int = 0) -> list[dict]:
        """Get new messages from Telegram."""
        if not self.is_configured:
            return []
        try:
            client = await self._get_client()
            params = {"timeout": 1}
            if offset:
                params["offset"] = offset
            resp = await client.get(
                f"{TELEGRAM_API}/bot{self.bot_token}/getUpdates",
                params=params,
            )
            resp.raise_for_status()
            return resp.json().get("result", [])
        except Exception:
            return []

    async def handle_command(self, command: str, deps: dict) -> str:
        """Handle a Telegram command and return response text."""
        cmd = command.strip().lower()

        if cmd == "/status":
            scanner = deps.get("scanner")
            sf = deps.get("spot_futures")
            vol = deps.get("volatility")
            s = scanner.get_stats() if scanner else {}
            v = vol.get_stats() if vol else {}
            sf_s = sf.get_stats() if sf else {}
            return (
                f"📊 <b>Status</b>\n"
                f"Scans: {s.get('scan_count', 0)}\n"
                f"Pairs: {s.get('tickers_loaded', 0)}\n"
                f"Triangular: {s.get('current_cycles', 0)} cycles\n"
                f"Spot-Futures: {sf_s.get('opportunities', 0)} opportunities\n"
                f"Volatility: {v.get('volatility_score', 0):.1f}\n"
                f"{'🔴 HIGH' if v.get('is_volatile') else '🟢 Normal'}"
            )

        elif cmd == "/cycles":
            scanner = deps.get("scanner")
            cycles = scanner.cycles if scanner else []
            if not cycles:
                return "No triangular cycles detected."
            lines = []
            for c in cycles[:5]:
                lines.append(
                    f"{'→'.join(c['currencies'])} +{c['net_profit_pct']:.3f}%"
                )
            return "🔄 <b>Cycles</b>\n" + "\n".join(lines)

        elif cmd == "/futures":
            sf = deps.get("spot_futures")
            opps = sf._opportunities if sf else []
            if not opps:
                return "No spot-futures opportunities."
            lines = []
            for o in opps[:5]:
                lines.append(
                    f"{o['symbol']}: {o['premium_pct']:.3f}% "
                    f"net={o['net_profit_pct']:.3f}%"
                )
            return "📈 <b>Spot-Futures</b>\n" + "\n".join(lines)

        elif cmd == "/balance":
            spot = deps.get("exchange")
            futures = deps.get("futures_exchange")
            try:
                spot_usdt = await spot.get_balance("USDT") if spot else 0
                futures_usdt = (
                    await futures.get_futures_usdt_balance() if futures else 0
                )
                return (
                    f"💰 <b>Balance</b>\n"
                    f"Spot: {spot_usdt} USDT\n"
                    f"Futures: {futures_usdt} USDT"
                )
            except Exception as e:
                return f"Error getting balance: {e}"

        elif cmd == "/paper":
            paper = deps.get("paper_trader")
            if not paper:
                return "Paper trading not configured."
            s = paper.get_stats()
            return (
                f"📝 <b>Paper Trading</b>\n"
                f"{'ON' if s['enabled'] else 'OFF'}\n"
                f"Balance: ${s['current_balance']:.2f}\n"
                f"P&L: ${s['net_profit']:.4f} ({s['net_profit_pct']:.2f}%)\n"
                f"Trades: {s['total_trades']}\n"
                f"Win rate: {s['success_rate']:.1f}%"
            )

        elif cmd == "/live":
            live = deps.get("live_executor")
            if not live:
                return "Live trading not configured."
            s = live.get_stats()
            status = (
                "ACTIVE" if s['enabled'] and s['confirmed']
                else "ENABLED" if s['enabled']
                else "OFF"
            )
            return (
                f"🔴 <b>Live Trading</b>\n"
                f"Status: {status}\n"
                f"Trades: {s['total_trades']}\n"
                f"Profit: ${s['total_profit_usdt']:.4f}\n"
                f"Has position: {s['has_position']}"
            )

        elif cmd == "/pause":
            live = deps.get("live_executor")
            if live:
                live.risk.pause()
                return "⏸ Live trading paused."
            return "Live trading not configured."

        elif cmd == "/resume":
            live = deps.get("live_executor")
            if live:
                live.risk.resume()
                return "▶️ Live trading resumed."
            return "Live trading not configured."

        else:
            return (
                "Available commands:\n"
                "/status - Bot status\n"
                "/cycles - Triangular cycles\n"
                "/futures - Spot-futures opportunities\n"
                "/balance - Account balances\n"
                "/paper - Paper trading stats\n"
                "/live - Live trading stats\n"
                "/pause - Pause live trading\n"
                "/resume - Resume live trading"
            )
