import pytest

from app.core.graph import (
    _find_triangular_cycles_dfs,
    _parse_pair,
    bellman_ford_cycles,
    build_currency_graph,
)
from app.models.primitives import BidAsk


def test_parse_pair_usdt():
    base, quote = _parse_pair("BTCUSDT", {"USDT", "BTC", "ETH"})
    assert base == "BTC"
    assert quote == "USDT"


def test_parse_pair_eth():
    base, quote = _parse_pair("ETHBTC", {"USDT", "BTC", "ETH"})
    assert base == "ETH"
    assert quote == "BTC"


def test_parse_pair_invalid():
    base, quote = _parse_pair("XYZABC", {"USDT", "BTC"})
    assert base is None
    assert quote is None


def test_parse_pair_short_base():
    """Base must be at least 2 chars."""
    base, quote = _parse_pair("XUSDT", {"USDT"})
    assert base is None


def test_build_graph_basic():
    pairs = {
        "BTCUSDT": BidAsk(bid=85000, ask=85010, bid_qty=1.5, ask_qty=0.8),
        "ETHUSDT": BidAsk(bid=3200, ask=3201, bid_qty=10, ask_qty=5),
        "ETHBTC": BidAsk(bid=0.0376, ask=0.0377, bid_qty=20, ask_qty=10),
    }

    graph, metadata = build_currency_graph(pairs)

    assert "USDT" in graph
    assert "BTC" in graph
    assert "ETH" in graph

    # USDT -> BTC (buy BTC with USDT) = 1/ask
    assert graph["USDT"]["BTC"] == pytest.approx(1 / 85010, rel=1e-6)

    # BTC -> USDT (sell BTC for USDT) = bid
    assert graph["BTC"]["USDT"] == pytest.approx(85000, rel=1e-6)


def test_bellman_ford_finds_profitable_cycle():
    """
    Bellman-Ford should detect a profitable USDT -> BTC -> ETH -> USDT cycle.
    Product: (1/85000) * (1/0.0374) * 3220 = 1.0117 (~1.17% gross)
    After 3x fees (0.3%): ~0.87% net profit
    """
    pairs = {
        "BTCUSDT": BidAsk(bid=85100, ask=85000, bid_qty=10, ask_qty=10),
        "ETHUSDT": BidAsk(bid=3220, ask=3200, bid_qty=100, ask_qty=100),
        "ETHBTC": BidAsk(bid=0.0376, ask=0.0374, bid_qty=50, ask_qty=50),
    }

    graph, metadata = build_currency_graph(pairs)
    cycles = bellman_ford_cycles(
        graph, metadata, start_currency="USDT", min_profit_pct=0.1
    )

    assert len(cycles) > 0
    cycle_currencies = [c["currencies"] for c in cycles]
    assert ["USDT", "BTC", "ETH", "USDT"] in cycle_currencies


def test_dfs_finds_triangular_cycle():
    """DFS should find the same triangular cycle as Bellman-Ford."""
    pairs = {
        "BTCUSDT": BidAsk(bid=85100, ask=85000, bid_qty=10, ask_qty=10),
        "ETHUSDT": BidAsk(bid=3220, ask=3200, bid_qty=100, ask_qty=100),
        "ETHBTC": BidAsk(bid=0.0376, ask=0.0374, bid_qty=50, ask_qty=50),
    }

    graph, metadata = build_currency_graph(pairs)
    cycles = _find_triangular_cycles_dfs(
        graph, metadata, start_currency="USDT",
        min_profit_pct=0.1, fee_rate=0.001,
    )

    assert len(cycles) > 0
    assert any(
        c["currencies"] == ["USDT", "BTC", "ETH", "USDT"] for c in cycles
    )


def test_no_profitable_cycle():
    """No cycle should be profitable when prices are consistent."""
    pairs = {
        "BTCUSDT": BidAsk(bid=85000, ask=85010, bid_qty=10, ask_qty=10),
        "ETHUSDT": BidAsk(bid=3200, ask=3201, bid_qty=100, ask_qty=100),
        "ETHBTC": BidAsk(bid=0.03763, ask=0.03764, bid_qty=50, ask_qty=50),
    }

    graph, metadata = build_currency_graph(pairs)
    cycles = bellman_ford_cycles(
        graph, metadata, start_currency="USDT", min_profit_pct=0.2
    )

    assert len(cycles) == 0


def test_zero_spread_pair():
    """Pair with zero spread (bid == ask) should not create profitable cycle."""
    pairs = {
        "BTCUSDT": BidAsk(bid=85000, ask=85000, bid_qty=10, ask_qty=10),
        "ETHUSDT": BidAsk(bid=3200, ask=3200, bid_qty=100, ask_qty=100),
        "ETHBTC": BidAsk(bid=0.03764, ask=0.03764, bid_qty=50, ask_qty=50),
    }

    graph, metadata = build_currency_graph(pairs)
    cycles = bellman_ford_cycles(
        graph, metadata, start_currency="USDT", min_profit_pct=0.1
    )

    assert len(cycles) == 0


def test_missing_start_currency():
    """Start currency not in graph should return empty list."""
    pairs = {
        "BTCETH": BidAsk(bid=0.0376, ask=0.0377, bid_qty=10, ask_qty=10),
    }

    graph, metadata = build_currency_graph(pairs)
    cycles = bellman_ford_cycles(
        graph, metadata, start_currency="USDT", min_profit_pct=0.1
    )

    assert len(cycles) == 0


def test_cycle_uses_only_three_pairs():
    """Should not find cycles that need more than the available pairs."""
    pairs = {
        "BTCUSDT": BidAsk(bid=85000, ask=85010, bid_qty=10, ask_qty=10),
    }

    graph, metadata = build_currency_graph(pairs)
    cycles = bellman_ford_cycles(
        graph, metadata, start_currency="USDT", min_profit_pct=0.1
    )

    # Only 2 currencies, can't form a 3-leg cycle
    assert len(cycles) == 0


def test_multiple_cycles_sorted():
    """Multiple profitable cycles should be sorted by profit descending."""
    pairs = {
        "BTCUSDT": BidAsk(bid=85100, ask=85000, bid_qty=10, ask_qty=10),
        "ETHUSDT": BidAsk(bid=3220, ask=3200, bid_qty=100, ask_qty=100),
        "ETHBTC": BidAsk(bid=0.0376, ask=0.0374, bid_qty=50, ask_qty=50),
        "BNBUSDT": BidAsk(bid=640, ask=635, bid_qty=20, ask_qty=20),
        "BNBBTC": BidAsk(bid=0.00755, ask=0.00750, bid_qty=30, ask_qty=30),
        "BNBETH": BidAsk(bid=0.199, ask=0.197, bid_qty=40, ask_qty=40),
    }

    graph, metadata = build_currency_graph(pairs)
    cycles = bellman_ford_cycles(
        graph, metadata, start_currency="USDT", min_profit_pct=0.05
    )

    # Should be sorted descending by profit
    for i in range(len(cycles) - 1):
        assert cycles[i]["net_profit_pct"] >= cycles[i + 1]["net_profit_pct"]
