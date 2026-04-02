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
| 11 | Redis cache para tickers, settings y estado (crash recovery) | Alto | — |
| 12 | WebSocket streaming (!bookTicker) con REST fallback | Alto | — |
| 13 | Bug fix: extracción quote/base currency en live_executor | Alto | — |
| 14 | Settings persistencia (Redis) y thread-safe con asyncio.Lock | Medio | — |
| 15 | Tests ampliados: 23 → 56 tests (live_executor, risk, redis, volatility) | Medio | — |
| 16 | CI/CD pipeline (GitHub Actions: lint + test + build) | Medio | — |
| 17 | Spot-Futures executor fix: discount abre ambas patas (sell spot + buy futures) | Alto | — |
| 18 | Spot-Futures: selección automática de mejor oportunidad + notificación solo al ejecutar | Alto | — |
| 19 | Spot-Futures: step sizes por símbolo para spot y futures | Medio | — |
| 20 | Funding rate carry strategy reemplaza premium/discount | Alto | — |

## Mejoras descartadas (no implementar de nuevo sin justificación)

| # | Mejora | Razón del descarte |
|---|--------|--------------------|
| 1 | Batch orders (1 API call para 3 patas) | Riesgo alto por ganancia mínima (~200ms). Si falla una pata, quedás colgado con moneda intermedia. |
| 2 | Order book profundo (top 5-10 niveles) | Impacto marginal. El 99% de las veces el nivel 1 es suficiente. |

## Arquitectura actual

### Modos de arbitraje
1. **Triangular** (USDT → X → Y → USDT) — detecta ciclos de 3 pares dentro de Binance
2. **Spot-Futures** — detecta premium entre precio spot y futuros USDⓈ-M

### Feed de precios
- **Primario**: WebSocket `!bookTicker` stream (latencia ~ms)
- **Fallback**: REST polling cada 1s si WS falla
- **Cache**: Redis persiste tickers para recovery post-crash

### Spot-Futures: flujo de ejecución (funding rate carry)
```
Scanner (cada 30s)
  └→ Obtiene funding rates de todos los símbolos (premiumIndex endpoint)
  └→ Filtra por |rate| >= 0.005% (umbral de entrada)
  └→ Ordena por |rate| DESC
  └→ Elige el MEJOR (mayor funding rate absoluto)
  └→ Intenta ejecutar con sf_executor
       ├→ OK → notifica Telegram + broadcast WebSocket
       └→ Skip → solo log (sin notificación)
  └→ Si hay posición abierta, verifica should_close()
       └→ Close cuando rate baja de 0.002% o cambia de signo
```

**Estrategia:**
- **funding_positive** (rate > 0): buy spot + short futures → cobrás funding de longs cada 8h
- **funding_negative** (rate < 0): sell spot + long futures → cobrás funding de shorts cada 8h
- **Salida**: cuando |rate| baja de 0.002% o cambia de signo
- **Retorno estimado**: 0.5-3% mensual dependiendo del rate promedio

**Returns por funding rate:**
| Rate por 8h | Diario | Mensual | Anual |
|-------------|--------|---------|-------|
| 0.005% | 0.015% | 0.45% | 5.5% |
| 0.010% | 0.030% | 0.90% | 11.0% |
| 0.030% | 0.090% | 2.70% | 32.9% |

### Endpoints clave
- `GET /api/cycles/` — ciclos triangulares actuales
- `GET /api/spot-futures/opportunities` — oportunidades spot-futures
- `GET /api/history/cycles` — historial triangular (DB)
- `GET /api/history/spot-futures` — historial spot-futures (DB)
- `GET /health` — estado completo del sistema (incluye Redis stats)

### Base de datos
- `cycle_snapshots` — ciclos triangulares detectados
- `spot_futures_history` — oportunidades spot-futures detectadas
- `trade_history` — trades ejecutados (paper/live)
- `daily_stats` — estadísticas agregadas diarias

### Redis keys
- `arb:tickers` — hash de precios actuales
- `arb:paper:state` — estado del paper trader
- `arb:cycles:latest` — últimos ciclos (TTL 5min)
- `arb:settings` — settings runtime persistidos

## Notas sobre el mercado

- Mercado eficiente la mayoría del tiempo → 0 ciclos en 12+ horas es normal
- Ciclos aparecen en momentos de alta volatilidad (noticias, crashes, pumps)
- Triangular arbitrage con $150 USDT es viable pero oportunidades son raras
- Profit realista: 0-5 ciclos/día en días normales, 10-30 en alta volatilidad
- Volatility monitor ajusta scan: 2x más rápido en alta volatilidad, 2x más lento en calma
- Spot-futures premium aparece más seguido que triangular (funding rate + precio divergencia)
