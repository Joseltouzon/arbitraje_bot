from __future__ import annotations

import math
from typing import Any

from app.models.primitives import BidAsk
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Known quote currencies on Binance (order by length for correct parsing)
QUOTE_CURRENCIES = {
    "USDT", "USDC", "BUSD", "TUSD", "DAI", "FDUSD",
    "BTC", "ETH", "BNB", "SOL", "DOGE", "XRP", "ADA",
    "AVAX", "DOT", "MATIC", "LINK", "UNI", "SHIB",
}


def build_currency_graph(
    pairs: dict[str, BidAsk],
    quote_currencies: set[str] | None = None,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, dict]]]:
    """
    Build directed graph of currency exchange rates.

    Each pair BTCUSDT creates two edges:
      USDT → BTC at rate = 1/ask (buy BTC with USDT, pay ask)
      BTC → USDT at rate = bid  (sell BTC for USDT, receive bid)

    Returns:
        graph[base][quote] = exchange_rate (how much quote per 1 base)
        metadata[base][quote] = {"pair": symbol, "side": "buy"/"sell", "rate": float}
    """
    if quote_currencies is None:
        quote_currencies = QUOTE_CURRENCIES

    graph: dict[str, dict[str, float]] = {}
    metadata: dict[str, dict[str, dict]] = {}

    for symbol, bidask in pairs.items():
        base, quote = _parse_pair(symbol, quote_currencies)
        if base is None or quote is None:
            continue

        if base not in graph:
            graph[base] = {}
            metadata[base] = {}
        if quote not in graph:
            graph[quote] = {}
            metadata[quote] = {}

        # Buy: quote → base (you pay ask price)
        buy_rate = 1.0 / bidask.ask if bidask.ask > 0 else 0.0
        if buy_rate > 0:
            graph[quote][base] = buy_rate
            metadata[quote][base] = {
                "pair": symbol, "side": "buy",
                "rate": buy_rate,
                "bid": bidask.bid, "ask": bidask.ask,
            }

        # Sell: base → quote (you receive bid price)
        sell_rate = bidask.bid
        if sell_rate > 0:
            graph[base][quote] = sell_rate
            metadata[base][quote] = {
                "pair": symbol, "side": "sell",
                "rate": sell_rate,
                "bid": bidask.bid, "ask": bidask.ask,
            }

    logger.info(
        f"Graph built: {len(graph)} currencies, "
        f"{sum(len(e) for e in graph.values())} edges"
    )
    return graph, metadata


def _parse_pair(
    symbol: str, quote_currencies: set[str]
) -> tuple[str | None, str | None]:
    """Parse Binance symbol like BTCUSDT into (BTC, USDT)."""
    for quote in sorted(quote_currencies, key=len, reverse=True):
        if symbol.endswith(quote):
            base = symbol[: -len(quote)]
            if len(base) >= 2:
                return base, quote
    return None, None


# ─────────────────────────────────────────────
# Bellman-Ford cycle detection
# ─────────────────────────────────────────────


def bellman_ford_cycles(
    graph: dict[str, dict[str, float]],
    metadata: dict[str, dict[str, dict]],
    start_currency: str = "USDT",
    min_profit_pct: float = 0.2,
    max_cycle_length: int = 4,
) -> list[dict[str, Any]]:
    """
    Find profitable cycles using Bellman-Ford on -log(rate) weights.

    Key insight:
        -rate_AB * rate_BC * rate_CA > 1  ⟹  cycle is profitable
        ⟺  -log(rate_AB) + -log(rate_BC) + -log(rate_CA) < 0  ⟺  negative cycle

    Algorithm:
        1. Convert all rates to -log(rate) weights
        2. Run Bellman-Ford for V-1 iterations from start_currency
        3. Run one more iteration: if any node can still be relaxed → negative cycle exists
        4. Trace the predecessor chain to extract the cycle path
        5. Filter cycles that start/end with start_currency and have 3-4 legs
        6. Calculate exact profit with fees
    """
    if start_currency not in graph:
        logger.warning(f"Start currency {start_currency} not in graph")
        return []

    currencies = list(graph.keys())
    n = len(currencies)

    if n < 3:
        return []

    # Build -log(weight) graph
    log_graph: dict[str, dict[str, float]] = {}
    for src in graph:
        log_graph[src] = {}
        for dst in graph[src]:
            rate = graph[src][dst]
            if rate > 0:
                log_graph[src][dst] = -math.log(rate)

    # Bellman-Ford initialization
    dist: dict[str, float] = {c: float("inf") for c in currencies}
    pred: dict[str, str | None] = {c: None for c in currencies}
    dist[start_currency] = 0.0

    # Relax edges V-1 times
    for _ in range(n - 1):
        updated = False
        for src in log_graph:
            if dist[src] == float("inf"):
                continue
            for dst in log_graph[src]:
                new_dist = dist[src] + log_graph[src][dst]
                if new_dist < dist[dst]:
                    dist[dst] = new_dist
                    pred[dst] = src
                    updated = True
        if not updated:
            break

    # Detect negative cycles: run one more relaxation pass
    cycle_nodes: set[str] = set()
    for src in log_graph:
        if dist[src] == float("inf"):
            continue
        for dst in log_graph[src]:
            if dist[src] + log_graph[src][dst] < dist[dst]:
                cycle_nodes.add(dst)

    if not cycle_nodes:
        logger.info("No negative cycles detected")
        return []

    logger.info(f"Detected {len(cycle_nodes)} nodes in negative cycles")

    # Extract actual cycles from negative cycle nodes
    cycles = _extract_cycles(
        cycle_nodes=cycle_nodes,
        pred=pred,
        graph=graph,
        log_graph=log_graph,
        metadata=metadata,
        start_currency=start_currency,
        min_profit_pct=min_profit_pct,
        max_cycle_length=max_cycle_length,
    )

    cycles.sort(key=lambda c: c["net_profit_pct"], reverse=True)
    logger.info(f"Found {len(cycles)} profitable cycles from {start_currency}")
    return cycles


def _extract_cycles(
    cycle_nodes: set[str],
    pred: dict[str, str | None],
    graph: dict[str, dict[str, float]],
    log_graph: dict[str, dict[str, float]],
    metadata: dict[str, dict[str, dict]],
    start_currency: str,
    min_profit_pct: float,
    max_cycle_length: int,
) -> list[dict[str, Any]]:
    """
    Extract profitable cycles from Bellman-Ford negative cycle detection.
    Walk back through predecessors to find cycle paths.
    """
    fee_rate = 0.001
    cycles = []
    seen_cycles: set[tuple[str, ...]] = set()

    for node in cycle_nodes:
        # Walk back to find the cycle
        current = node
        visited: list[str] = []
        visited_set: set[str] = set()

        # Walk back max_cycle_length * 2 steps to find the cycle
        max_steps = max_cycle_length * 2
        for _ in range(max_steps):
            if current is None or current in visited_set:
                break
            visited.append(current)
            visited_set.add(current)
            current = pred.get(current)
            if current is None:
                break
            if current in visited_set:
                # Found a cycle - extract it
                cycle_start_idx = visited.index(current)
                cycle_path = visited[cycle_start_idx:]

                # Only consider cycles of valid length
                if 3 <= len(cycle_path) <= max_cycle_length:
                    # Check if cycle can connect back to start_currency
                    cycle_tuple = tuple(cycle_path)
                    if cycle_tuple not in seen_cycles:
                        seen_cycles.add(cycle_tuple)

                        # Try to prepend start_currency if cycle doesn't include it
                        if start_currency not in cycle_path:
                            continue

                        cycle_info = _evaluate_cycle(
                            cycle_path, graph, metadata, fee_rate, min_profit_pct
                        )
                        if cycle_info:
                            cycles.append(cycle_info)
                break

    # Also do targeted DFS from start_currency for triangular cycles
    triangular = _find_triangular_cycles_dfs(
        graph=graph,
        metadata=metadata,
        start_currency=start_currency,
        min_profit_pct=min_profit_pct,
        fee_rate=fee_rate,
    )

    # Merge, deduplicate
    for tc in triangular:
        key = tuple(tc["currencies"])
        if key not in seen_cycles:
            seen_cycles.add(key)
            cycles.append(tc)

    return cycles


def _find_triangular_cycles_dfs(
    graph: dict[str, dict[str, float]],
    metadata: dict[str, dict[str, dict]],
    start_currency: str,
    min_profit_pct: float,
    fee_rate: float,
) -> list[dict[str, Any]]:
    """
    Targeted DFS for triangular cycles (3 hops: A→B→C→A).
    More reliable than pure Bellman-Ford for finding ALL triangular cycles.
    """
    if start_currency not in graph:
        return []

    total_fee_mult = (1 - fee_rate) ** 3
    cycles: list[dict[str, Any]] = []

    # Get all neighbors of start_currency
    neighbors_b = list(graph[start_currency].keys())

    for b in neighbors_b:
        if b not in graph:
            continue
        # Get neighbors of B (potential C)
        for c in graph[b]:
            if c in (start_currency, b):
                continue
            # Check if C connects back to start_currency
            if start_currency in graph.get(c, {}):
                # Found cycle: start → B → C → start
                rate_ab = graph[start_currency][b]
                rate_bc = graph[b][c]
                rate_ca = graph[c][start_currency]

                product = rate_ab * rate_bc * rate_ca
                net_product = product * total_fee_mult
                profit_pct = (net_product - 1.0) * 100

                if profit_pct > min_profit_pct:
                    cycle_info = _build_cycle_info(
                        path=[start_currency, b, c, start_currency],
                        rates=[rate_ab, rate_bc, rate_ca],
                        metadata=metadata,
                        profit_pct=profit_pct,
                    )
                    cycles.append(cycle_info)

    return cycles


def _evaluate_cycle(
    cycle_path: list[str],
    graph: dict[str, dict[str, float]],
    metadata: dict[str, dict[str, dict]],
    fee_rate: float,
    min_profit_pct: float,
) -> dict[str, Any] | None:
    """Evaluate a cycle and return info if profitable."""
    rates = []
    for i in range(len(cycle_path) - 1):
        src = cycle_path[i]
        dst = cycle_path[i + 1]
        if dst not in graph.get(src, {}):
            return None
        rates.append(graph[src][dst])

    # Also need the return edge
    last = cycle_path[-1]
    first = cycle_path[0]
    if first not in graph.get(last, {}):
        return None
    rates.append(graph[last][first])

    full_path = cycle_path + [first]

    # Calculate profit
    product = 1.0
    for r in rates:
        product *= r

    num_trades = len(rates)
    total_fee_mult = (1 - fee_rate) ** num_trades
    net_product = product * total_fee_mult
    profit_pct = (net_product - 1.0) * 100

    if profit_pct <= min_profit_pct:
        return None

    return _build_cycle_info(full_path, rates, metadata, profit_pct)


def _build_cycle_info(
    path: list[str],
    rates: list[float],
    metadata: dict[str, dict[str, dict]],
    profit_pct: float,
) -> dict[str, Any]:
    """Build detailed cycle info with leg-by-leg breakdown."""
    legs = []
    for i in range(len(path) - 1):
        from_c = path[i]
        to_c = path[i + 1]
        edge_meta = metadata.get(from_c, {}).get(to_c, {})
        legs.append(
            {
                "from_currency": from_c,
                "to_currency": to_c,
                "pair": edge_meta.get("pair", f"{from_c}{to_c}"),
                "side": edge_meta.get("side", "unknown"),
                "rate": rates[i],
                "bid": edge_meta.get("bid", 0),
                "ask": edge_meta.get("ask", 0),
            }
        )

    return {
        "currencies": path,
        "legs": legs,
        "net_profit_pct": round(profit_pct, 4),
        "raw_rate_product": round(math.prod(rates), 8),
    }
