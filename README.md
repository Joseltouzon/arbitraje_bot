# Arbitraje Bot - Triangular Arbitrage for Binance

Bot de arbitraje triangular que detecta y ejecuta oportunidades de arbitraje entre pares de trading en Binance en tiempo real.

## Qué hace

Detecta inconsistencias de precio entre 3 pares de trading y las aprovecha:

```
USDT → BTC → ETH → USDT
Si el producto de los 3 tipos de cambio > 1 = ciclo rentable
```

## Modos de operación

| Modo | Descripción |
|------|-------------|
| **detect** | Solo detecta y muestra oportunidades (default) |
| **paper** | Simula trades con dinero virtual, rastrea P&L |
| **live** | Ejecuta trades reales en Binance (requiere confirmación) |

## Features

- WebSocket streaming desde Binance (precios en tiempo real)
- Detección de ciclos con Bellman-Ford (múltiples monedas: USDT, BTC, ETH, BNB)
- Órdenes límite con fallback a market
- Filtro por liquidez mínima
- Notificaciones por Telegram
- Dashboard React con actualizaciones en tiempo real
- Historial y analytics en PostgreSQL
- Gestión de riesgo (stop-loss, límites de trades)

## Requisitos previos

- Python 3.12+
- Node.js 20+
- PostgreSQL
- Redis
- Cuenta en Binance con API key configurada

## Instalación

```bash
# Clonar repo
git clone https://github.com/Joseltouzon/arbitraje_bot.git
cd arbitraje_bot

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# Backend
cd backend
pip install uv
uv sync --extra dev

# Frontend
cd ../frontend
npm install -g pnpm
pnpm install

# Base de datos
cd ../backend
uv run alembic upgrade head
```

## Ejecución

```bash
# Backend (terminal 1)
cd backend
uv run python -m uvicorn app.main:app --reload

# Frontend (terminal 2)
cd frontend
pnpm dev

# Abrir http://localhost:3000
```

## Configuración (.env)

```env
# Binance API
BINANCE_API_KEY=tu_api_key
BINANCE_API_SECRET=tu_api_secret

# Modo de operación
OPERATION_MODE=detect    # detect | paper | live
AUTO_TRADE=false

# Arbitraje
MIN_PROFIT_THRESHOLD_PCT=0.2
START_CURRENCIES=USDT,BTC,ETH,BNB
TRADE_AMOUNT_USDT=150
MIN_LIQUIDITY_USDT=5000

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=tu_token
TELEGRAM_CHAT_ID=tu_chat_id

# Base de datos
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/arbitrage
```

## API Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/health` | GET | Estado del sistema |
| `/api/cycles/` | GET | Ciclos rentables actuales |
| `/api/cycles/scan` | POST | Trigger manual de escaneo |
| `/api/prices/tickers` | GET | Precios actuales |
| `/api/paper/status` | GET | Estado paper trading |
| `/api/paper/enable` | POST | Activar paper trading |
| `/api/paper/trades` | GET | Historial de paper trades |
| `/api/live/status` | GET | Estado live trading |
| `/api/live/enable` | POST | Activar (requiere confirmación) |
| `/api/live/confirm` | POST | Confirmar live trading |
| `/api/live/disable` | POST | Detener live trading |
| `/api/history/cycles` | GET | Historial de ciclos |
| `/api/history/analytics/summary` | GET | Resumen de performance |
| `/ws` | WebSocket | Actualizaciones en tiempo real |

## Tests

```bash
cd backend
uv run python -m pytest -v
```

## Estructura del proyecto

```
backend/
├── app/
│   ├── api/routes/      # Endpoints REST
│   ├── core/            # Lógica de arbitraje (graph, calculator, risk)
│   ├── exchanges/       # Adaptadores de Binance (REST + WebSocket)
│   ├── services/        # Servicios (scanner, paper, live, telegram)
│   ├── db/              # Modelos y sesión de base de datos
│   └── main.py          # Entry point FastAPI
└── tests/

frontend/
├── src/
│   ├── components/      # Componentes React
│   ├── hooks/           # Hooks (useWebSocket)
│   └── lib/             # API client y utils
```

## Disclaimer

Este bot es para fines educativos. El trading de criptomonedas conlleva riesgo de pérdida. Nunca inviertas más de lo que puedas permitirte perder.

## Licencia

MIT
