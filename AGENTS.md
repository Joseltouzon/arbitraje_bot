# AGENTS.md - Crypto Triangular Arbitrage App

## Project Overview

Build a **triangular arbitrage detection and execution platform** for Binance that detects profitable currency cycles within a single exchange in real-time.

**What is Triangular Arbitrage?**
Exploit price inconsistencies between three trading pairs on the same exchange:
```
USDT → BTC → ETH → USDT
If: 100 USDT → 0.00144 BTC → 0.032 ETH → 100.8 USDT
Profit: +0.8% before fees
Net profit after 3x fees (0.1% each): +0.5%
```

**Why only Binance?**
- Zero withdrawal fees (all trades on same exchange)
- Lowest trading fees in the market (0.1%)
- Highest liquidity = less slippage
- Best API for real-time order book data
- 1000+ trading pairs = more potential cycles

---

## Agent Role (Generador)

| Responsibility | Description |
|---------------|-------------|
| **Scaffolding** | Create project structure, initialize FastAPI, React, Docker |
| **Code Generation** | Write all backend services, cycle detection, frontend components |
| **Configuration** | Generate .env, docker-compose, pyproject.toml, package.json |
| **Testing** | Unit/integration tests for arbitrage math, cycle detection, order simulation |
| **Optimization** | Benchmark latency, optimize Bellman-Ford, minimize API calls |
| **Troubleshooting** | Debug false positives, fix execution timing issues |

**User Responsibilities:**
- Provide Binance API key/secret
- Fund Binance spot wallet with ~150 USDT
- Start/stop the application
- Approve live trading activation

---

## What You Need to Operate

### Required
1. **Binance account** (KYC verified)
2. **API Key + Secret:**
   - binance.com → Profile → API Management → Create API
   - Permissions: **Enable Spot Trading only** (NEVER withdrawal)
   - Enable IP restriction for security
3. **~150 USDT** in Binance spot wallet
4. **Python 3.12+** and **Node 20+** installed

### Optional
- **Docker + docker-compose** (simplified deployment)
- **VPS** (for 24/7 operation)

---

## How It Works

### Operational Modes

```
┌─────────────────────────────────────────────────────┐
│                   OPERATION MODES                    │
├──────────────────┬──────────────────────────────────┤
│  DETECT MODE     │  Only detects and shows cycles.  │
│  (default)       │  No trades executed.             │
├──────────────────┼──────────────────────────────────┤
│  PAPER MODE      │  Simulates trades. Tracks P&L.   │
│                  │  Use to validate strategy.       │
├──────────────────┼──────────────────────────────────┤
│  LIVE MODE       │  Executes real trades. HIGH RISK. │
│  (opt-in only)   │  Set AUTO_TRADE=true to enable.  │
└──────────────────┴──────────────────────────────────┘
```

### Automatic Flow

```
1. Order Book Poller (every 500ms - Binance REST or WebSocket)
   └→ Fetches top 20 bid/ask for key trading pairs
   └→ Stores in Redis for instant access

2. Cycle Finder (continuous - Bellman-Ford)
   └→ Builds directed graph: nodes = currencies, edges = exchange rates
   └→ Finds profitable cycles: A → B → C → A
   └→ Calculates exact profit after 3x trading fees
   └→ Filters: only cycles with profit > threshold

3. Opportunity Emitter (WebSocket → Frontend)
   └→ Pushes profitable cycles to dashboard
   └→ Logs to database with timestamp and profit details

4. Execution Engine (if AUTO_TRADE=true)
   └→ For each profitable cycle:
       a. Verify sufficient balance
       b. Check rate limits and risk limits
       c. Place 3 sequential market orders (A→B, B→C, C→A)
       d. Log each order result
       e. Update P&L tracker

5. Risk Manager (continuous)
   └→ Max trades per hour
   └→ Max exposure per cycle
   └→ Stop-loss trigger
   └→ Pause on consecutive losses
```

### To Start

```bash
# 1. Setup
git clone <repo>
cd crypto-arbitrage
cp .env.example .env

# 2. Add your Binance API keys to .env

# 3. Start
docker-compose up -d
# or: uv run uvicorn app.main:app --reload

# 4. Open dashboard
open http://localhost:3000

# 5. Watch cycles appear in real-time (detection mode)
```

---

## Architecture

```
┌──────────────────────────────────────────────┐
│              Frontend (React)                │
│  Dashboard │ Cycles │ P&L │ Settings         │
└────────────────────┬─────────────────────────┘
                     │ WebSocket + REST
┌────────────────────▼─────────────────────────┐
│              FastAPI Backend                  │
│  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Order Book   │  │ Cycle Detector        │  │
│  │ Poller       │  │ (Bellman-Ford)        │  │
│  └──────┬───────┘  └──────────┬────────────┘  │
│         │                     │               │
│  ┌──────▼─────────────────────▼────────────┐  │
│  │        Binance Adapter                  │  │
│  │  REST API + WebSocket streams           │  │
│  └─────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────┐  │
│  │        Execution Engine (optional)      │  │
│  └─────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
         │                    │
    ┌────▼─────┐       ┌─────▼─────┐
    │ Redis    │       │ PostgreSQL│
    │ (cache)  │       │ (persist) │
    └──────────┘       └───────────┘
```

---

## Project Structure

```
crypto-arbitrage/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app entry
│   │   ├── config.py               # Settings (pydantic-settings)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── cycles.py       # Triangular cycles API
│   │   │   │   ├── prices.py       # Current prices
│   │   │   │   ├── trades.py       # Trade history
│   │   │   │   └── settings.py     # App settings
│   │   │   └── websocket.py        # Real-time opportunity push
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── graph.py            # Currency graph + Bellman-Ford
│   │   │   ├── cycle_detector.py   # Find profitable A→B→C→A cycles
│   │   │   ├── calculator.py       # Profit calculation after fees
│   │   │   └── risk.py             # Risk management rules
│   │   ├── exchanges/
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # Exchange interface
│   │   │   └── binance.py          # Binance REST + WebSocket
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── cycle.py            # Triangular cycle model
│   │   │   ├── trade.py            # Executed trade model
│   │   │   ├── pair.py             # Trading pair model
│   │   │   └── price.py            # Bid/ask snapshot
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── orderbook_poller.py # Fetches order books from Binance
│   │   │   ├── cycle_scanner.py    # Runs cycle detection continuously
│   │   │   └── executor.py         # Executes 3-leg trades
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── session.py
│   │   │   └── migrations/
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── logger.py
│   │       └── rate_limiter.py
│   ├── tests/
│   │   ├── test_graph.py
│   │   ├── test_cycle_detector.py
│   │   ├── test_calculator.py
│   │   ├── test_binance_adapter.py
│   │   └── test_executor.py
│   ├── alembic/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── dashboard/
│   │   │   │   ├── CycleList.tsx        # Live profitable cycles
│   │   │   │   ├── ProfitChart.tsx      # P&L over time
│   │   │   │   ├── StatsCard.tsx        # Key metrics
│   │   │   │   └── OrderBook.tsx        # Top bids/asks
│   │   │   ├── cycle/
│   │   │   │   ├── CycleCard.tsx        # Single cycle display
│   │   │   │   ├── CycleDetail.tsx      # Full cycle breakdown
│   │   │   │   └── CycleHistory.tsx     # Past cycles
│   │   │   └── layout/
│   │   │       ├── Header.tsx
│   │   │       ├── Sidebar.tsx
│   │   │       └── Layout.tsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts          # WebSocket connection
│   │   │   └── useCycles.ts             # Cycle state management
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   └── utils.ts
│   │   ├── types/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── AGENTS.md
```

---

## Triangular Arbitrage Core Logic

### Graph Construction

```python
from decimal import Decimal

def build_currency_graph(pairs: dict[str, BidAsk]) -> dict[str, dict[str, Decimal]]:
    """
    Build directed graph of currency exchange rates.
    Each pair BTC/USDT creates two edges:
      USDT → BTC at rate = 1 / ask  (buy BTC with USDT)
      BTC → USDT at rate = bid      (sell BTC for USDT)

    Args:
        pairs: dict of "BASE/QUOTE" -> BidAsk(bid, ask)
    Returns:
        graph[base][quote] = exchange rate
    """
    graph: dict[str, dict[str, Decimal]] = {}
    for pair, bidask in pairs.items():
        base, quote = pair.split("/")
        if base not in graph:
            graph[base] = {}
        if quote not in graph:
            graph[quote] = {}

        # Buy: quote -> base (you pay ask price)
        graph[quote][base] = Decimal("1") / bidask.ask
        # Sell: base -> quote (you receive bid price)
        graph[base][quote] = bidask.bid

    return graph
```

### Cycle Detection (Bellman-Ford for negative log weights)

```python
import math
from decimal import Decimal

def find_profitable_cycles(
    graph: dict[str, dict[str, Decimal]],
    start_currency: str = "USDT",
    min_profit_pct: Decimal = Decimal("0.2"),
    max_cycle_length: int = 4,
) -> list[list[str]]:
    """
    Find profitable triangular cycles using Bellman-Ford on -log(rate).

    A cycle A → B → C → A is profitable if:
        rate_AB * rate_BC * rate_CA > 1
    Equivalently, if the sum of -log(rate) < 0 (negative weight cycle).

    Steps:
    1. Convert all exchange rates to -log(rate) weights
    2. Run Bellman-Ford from start_currency (USDT)
    3. If a negative cycle exists, trace back the path
    4. Filter cycles of exactly 3 hops (triangular)
    5. Calculate exact profit with fees
    """
    # Implementation in core/graph.py
    pass
```

### Profit Calculation

```python
def calculate_cycle_profit(
    amounts: list[tuple[str, Decimal]],  # [(currency, amount), ...]
    fee_rate: Decimal = Decimal("0.001"), # 0.1% per trade
) -> Decimal:
    """
    Calculate exact profit after 3 trading fees.

    For cycle USDT → BTC → ETH → USDT:
    1. Buy BTC: get_btc = usdt / (btc_ask * (1 + fee))
    2. Buy ETH: get_eth = get_btc / (eth_btc_ask * (1 + fee))
    3. Sell ETH: final_usdt = get_eth * eth_usdt_bid * (1 - fee)
    4. Profit = final_usdt - initial_usdt
    """
    initial = amounts[0][1]
    current = initial

    for i in range(len(amounts) - 1):
        _, curr_amount = amounts[i]
        next_currency, _ = amounts[i + 1]
        # Apply rate and fee
        rate = get_rate(amounts[i][0], next_currency)
        if is_buy(amounts[i][0], next_currency):
            current = current / (rate * (1 + fee_rate))
        else:
            current = current * rate * (1 - fee_rate)

    final = current
    return final - initial  # Net profit in USDT
```

---

## Exchange Adapter (Binance Only)

```python
from abc import ABC, abstractmethod
from decimal import Decimal

class BidAsk:
    bid: Decimal
    ask: Decimal
    bid_qty: Decimal
    ask_qty: Decimal

class ExchangeAdapter(ABC):
    name: str

    @abstractmethod
    async def get_all_tickers(self) -> dict[str, BidAsk]:
        """Get bid/ask for ALL trading pairs (one API call)."""
        ...

    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """Get order book snapshot for a specific pair."""
        ...

    @abstractmethod
    async def get_trading_fees(self, symbol: str) -> Decimal:
        """Get taker fee for a pair."""
        ...

    @abstractmethod
    async def get_balance(self, currency: str) -> Decimal:
        """Get available balance for a currency."""
        ...

    @abstractmethod
    async def create_market_order(
        self, symbol: str, side: str, quantity: Decimal
    ) -> OrderResult:
        """Place a market order (buy or sell)."""
        ...

    @abstractmethod
    async def create_limit_order(
        self, symbol: str, side: str, quantity: Decimal, price: Decimal
    ) -> OrderResult:
        """Place a limit order."""
        ...
```

### Binance Implementation Notes

```python
class BinanceAdapter(ExchangeAdapter):
    name = "binance"
    BASE_URL = "https://api.binance.com"

    # KEY ENDPOINT: Get ALL tickers in ONE call (fast!)
    # GET /api/v3/ticker/bookTicker
    # Returns: [{"symbol":"BTCUSDT","bidPrice":"85000.00","bidQty":"1.5",
    #            "askPrice":"85001.00","askQty":"0.8"}, ...]

    async def get_all_tickers(self) -> dict[str, BidAsk]:
        """
        Single API call gets ALL bid/ask prices.
        Binance returns ~2000 pairs in <200ms.
        This is the foundation for cycle detection.
        """
        resp = await self.client.get("/api/v3/ticker/bookTicker")
        return {
            item["symbol"]: BidAsk(
                bid=Decimal(item["bidPrice"]),
                ask=Decimal(item["askPrice"]),
                bid_qty=Decimal(item["bidQty"]),
                ask_qty=Decimal(item["askQty"]),
            )
            for item in resp.json()
        }
```

---

## Key Configuration (.env)

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/arbitrage
REDIS_URL=redis://localhost:6379/0

# Binance API
BINANCE_API_KEY=
BINANCE_API_SECRET=

# Operation Mode
OPERATION_MODE=detect        # detect | paper | live
AUTO_TRADE=false             # Default: false (detection only)

# Triangular Arbitrage Settings
MIN_PROFIT_THRESHOLD_PCT=0.2     # Min 0.2% profit to trigger
START_CURRENCY=USDT              # Start and end cycles with USDT
MAX_CYCLE_LENGTH=4               # Max 4 legs (A→B→C→A or A→B→C→D→A)
POLL_INTERVAL_MS=500             # Poll order books every 500ms
TRADE_AMOUNT_USDT=150            # Amount to trade per cycle

# Risk Management
MAX_TRADES_PER_HOUR=20
MAX_CONSECUTIVE_LOSSES=3         # Pause after 3 losses in a row
STOP_LOSS_PCT=5.0                # Stop if daily loss > 5%
```

---

## Development Phases

### Phase 1: Price Graph Foundation
- [ ] Project setup (FastAPI + React + Docker)
- [ ] Binance adapter: get all tickers + order books
- [ ] Currency graph builder (bid/ask → directed edges)
- [ ] Redis caching of price snapshots
- [ ] Frontend: live price matrix of key pairs

### Phase 2: Cycle Detection Engine
- [ ] Bellman-Ford implementation on -log(rate) graph
- [ ] Cycle extraction and filtering (3-leg only)
- [ ] Profit calculator (exact amounts after 3x fees)
- [ ] Unit tests for edge cases (zero spread, negative cycles)
- [ ] Frontend: live cycle feed with profit % and leg details

### Phase 3: Dashboard & Monitoring
- [ ] WebSocket push of profitable cycles
- [ ] Dashboard: cycle list, profit chart, stats
- [ ] Historical cycle logging in PostgreSQL
- [ ] Cycle performance analytics (avg profit, success rate)
- [ ] Order book depth visualization

### Phase 4: Paper Trading
- [ ] Simulated execution engine (no real orders)
- [ ] Track simulated P&L with real prices
- [ ] Validate cycle detection accuracy
- [ ] Stress test with historical data
- [ ] Performance benchmarks (latency, false positive rate)

### Phase 5: Live Execution (optional - use with caution)
- [ ] Real order placement (3 sequential market orders)
- [ ] Order result verification
- [ ] Risk management enforcement
- [ ] Telegram/Discord notifications
- [ ] Rate limit handling for Binance API

### Phase 6: Optimization
- [ ] WebSocket streaming (instead of REST polling)
- [ ] Batch order endpoint usage
- [ ] Pre-filter pairs by liquidity
- [ ] Parallel cycle evaluation
- [ ] Latency monitoring and alerting

---

## Important Notes

### Security
- **NEVER** log API keys or secrets
- Store API keys encrypted, load into env at runtime
- Use IP whitelisting on Binance API
- Enable only Spot Trading permissions (NO withdrawal)
- API keys in .env only, never in code

### Binance Rate Limits
| Limit | Value |
|-------|-------|
| Request weight | 6000 per minute |
| get_all_tickers | 40 weight (1 request) |
| get_orderbook(depth=20) | 2 weight per call |
| create_order | 1 weight per call |
| Max orders per 10s | 50 |
| Max orders per 24h | 160000 |

### Realistic Expectations
| Metric | Realistic Value |
|--------|----------------|
| Cycles detected per minute | 0-5 (depends on market) |
| Avg profit per cycle | 0.1-0.5% net |
| Execution speed | <500ms for 3 orders |
| Daily profit (paper) | 0.5-2% on capital |
| False positive rate | 5-15% (spread disappears before execution) |

### Why Triangular Can Be Profitable
1. **No withdrawal fees** - all within one exchange
2. **Speed** - 3 orders on same exchange vs cross-exchange transfers
3. **Binance has 1000+ pairs** - many possible cycles
4. **Market inefficiencies** - price updates lag between correlated pairs
5. **Small edges compound** - 0.2% per cycle × 20 cycles/day = 4%

### Testing
- Run `pytest` for backend tests
- Use Binance **testnet** for order simulation: https://testnet.binance.vision
- Paper trading mode for strategy validation before going live

---

## Commands

```bash
# Backend
cd backend
uv sync                                  # Install dependencies
uv run uvicorn app.main:app --reload     # Dev server
uv run pytest                            # Run tests
uv run pytest -v tests/test_cycle_detector.py  # Test cycle detection
uv run ruff check .                      # Lint
uv run ruff format .                     # Format

# Frontend
cd frontend
pnpm install                             # Install dependencies
pnpm dev                                 # Dev server
pnpm test                                # Run tests
pnpm lint                                # Lint

# Docker
docker-compose up -d                     # Start all services
docker-compose logs -f backend           # View backend logs
```
