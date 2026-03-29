# IMPROVEMENTS.md — Registro de mejoras evaluadas

## Mejoras implementadas

| # | Mejora | Impacto | Estado | Commit |
|---|--------|---------|--------|--------|
| 1 | WebSocket streaming (cambiado a REST polling) | Medio | ✅ | `97439cd` |
| 2 | Multi-moneda inicio (USDT, BTC, ETH, BNB) | Medio | ✅ | `4f6f846` |
| 3 | Órdenes límite con fallback a market | Medio | ✅ | `7b49fd8` |
| 4 | Filtro por liquidez ($5000 min) | Bajo | ✅ | `ecd1afb` |
| 5 | Notificaciones Telegram | Bajo | ✅ | `e130e45` |

## Mejoras descartadas (no implementar de nuevo sin justificación)

| # | Mejora | Razón del descarte |
|---|--------|--------------------|
| 1 | Batch orders (1 API call para 3 patas) | Riesgo alto por ganancia mínima (~200ms). Si falla una pata, quedás colgado con moneda intermedia. Fallback a secuencial no justifica la complejidad. |
| 2 | Order book profundo (top 5-10 niveles) | Impacto marginal. El 99% de las veces el nivel 1 es suficiente. Agrega complejidad sin beneficio real. |
| 3 | WebSocket streaming (!bookTicker) | Stream de Binance no devuelve datos (0 updates). REST polling cada 1s funciona y es suficiente. |

## Mejoras pendientes (por evaluar e implementar)

| # | Mejora | Impacto esperado | Complejidad | Estado |
|---|--------|-----------------|-------------|--------|
| 1 | Más quote currencies (DOGE, XRP, SOL, ADA) | Medio (4x más ciclos) | Baja | 📋 Pendiente |
| 2 | Monitoreo de volatilidad (funding rates, volume spikes) | Alto (saber CUÁNDO buscar) | Media | 📋 Pendiente |
| 3 | Spot-Futures arbitrage | Alto (más oportunidades) | Alta (API de futuros, permisos extra) | 📋 Pendiente |

## Notas sobre el mercado

- Mercado eficiente la mayoría del tiempo → 0 ciclos en 12+ horas es normal
- Ciclos aparecen en momentos de alta volatilidad (noticias, crashes, pumps)
- Triangular arbitrage con $150 USDT es viable pero oportunidades son raras
- Profit realista: 0-5 ciclos/día en días normales, 10-30 en alta volatilidad
