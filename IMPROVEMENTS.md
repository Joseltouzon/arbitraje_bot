# IMPROVEMENTS.md — Registro de mejoras evaluadas

## Mejoras implementadas

| # | Mejora | Impacto | Commit |
|---|--------|---------|--------|
| 1 | REST polling (1s) reemplaza WebSocket | Medio | `97439cd` |
| 2 | Multi-moneda inicio (USDT, BTC, ETH, BNB) | Medio | `4f6f846` |
| 3 | Órdenes límite con fallback a market | Medio | `7b49fd8` |
| 4 | Filtro por liquidez ($5000 min) | Bajo | `ecd1afb` |
| 5 | Notificaciones Telegram | Bajo | `e130e45` |
| 6 | Filtro de quote currencies expandido (941 pares vs 100) | Medio | `d604463` |
| 7 | Monitoreo de volatilidad (scan adaptivo) | Medio | `773a163` |
| 8 | Spot-Futures arbitrage (premium detector + DB + UI) | Alto | `3f98e4c`, `c36ac49` |
| 9 | Spot-Futures executor (auto open/close positions) | Alto | `f452bc8` |
| 10 | Dashboard improvements (ActivityLog, VolatilityGauge) | Medio | `ac6bfea` |

## Mejoras descartadas (no implementar de nuevo sin justificación)

| # | Mejora | Razón del descarte |
|---|--------|--------------------|
| 1 | Batch orders (1 API call para 3 patas) | Riesgo alto por ganancia mínima (~200ms). Si falla una pata, quedás colgado con moneda intermedia. |
| 2 | Order book profundo (top 5-10 niveles) | Impacto marginal. El 99% de las veces el nivel 1 es suficiente. |
| 3 | WebSocket streaming (!bookTicker) | Stream de Binance no devuelve datos (0 updates). REST polling funciona. |

## Mejoras pendientes

Ninguna por ahora. Todas las propuestas originales están implementadas o descartadas.

## Arquitectura actual

### Modos de arbitraje
1. **Triangular** (USDT → X → Y → USDT) — detecta ciclos de 3 pares dentro de Binance
2. **Spot-Futures** — detecta premium entre precio spot y futuros USDⓈ-M

### Endpoints clave
- `GET /api/cycles/` — ciclos triangulares actuales
- `GET /api/spot-futures/opportunities` — oportunidades spot-futures
- `GET /api/history/cycles` — historial triangular (DB)
- `GET /api/history/spot-futures` — historial spot-futures (DB)
- `GET /health` — estado completo del sistema

### Base de datos
- `cycle_snapshots` — ciclos triangulares detectados
- `spot_futures_history` — oportunidades spot-futures detectadas
- `trade_history` — trades ejecutados (paper/live)
- `daily_stats` — estadísticas agregadas diarias

## Notas sobre el mercado

- Mercado eficiente la mayoría del tiempo → 0 ciclos en 12+ horas es normal
- Ciclos aparecen en momentos de alta volatilidad (noticias, crashes, pumps)
- Triangular arbitrage con $150 USDT es viable pero oportunidades son raras
- Profit realista: 0-5 ciclos/día en días normales, 10-30 en alta volatilidad
- Volatility monitor ajusta scan: 2x más rápido en alta volatilidad, 2x más lento en calma
- Spot-futures premium aparece más seguido que triangular (funding rate + precio divergencia)
