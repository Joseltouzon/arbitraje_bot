export interface CycleLeg {
  from_currency: string;
  to_currency: string;
  pair: string;
  side: string;
  rate: number;
  bid: number;
  ask: number;
}

export interface CalculatedCycle {
  initial_amount: number;
  final_amount: number;
  gross_profit: number;
  net_profit: number;
  net_profit_pct: number;
  total_fees: number;
  total_slippage: number;
  trade_count: number;
}

export interface TriangularCycle {
  currencies: string[];
  legs: CycleLeg[];
  net_profit_pct: number;
  raw_rate_product: number;
  calculated: CalculatedCycle;
  timestamp: string;
}

export interface ScannerStats {
  scan_count: number;
  last_scan: string | null;
  current_cycles: number;
  top_profit: number;
}

export interface AppSettings {
  operation_mode: string;
  auto_trade: boolean;
  min_profit_threshold_pct: number;
  start_currency: string;
  max_cycle_length: number;
  poll_interval_ms: number;
  trade_amount_usdt: number;
  max_trades_per_hour: number;
  stop_loss_pct: number;
}

export interface TimeseriesPoint {
  timestamp: string;
  count: number;
  avg_profit_pct: number;
  max_profit_pct: number;
  total_profit_usdt: number;
}

export interface AnalyticsSummary {
  total_cycles_detected: number;
  total_trades_executed: number;
  best_profit_pct: number;
  avg_profit_pct: number;
  total_profit_usdt: number;
  success_rate: number;
}

export interface HistoryCycle {
  id: number;
  currencies: string[];
  pairs: string[];
  net_profit_pct: number;
  net_profit_usdt: number;
  detected_at: string;
}

export type AlertType = 'error' | 'warning' | 'circuit_breaker' | 'trade_failed' | 'trade_success' | 'info';

export interface Alert {
  id: number;
  type: AlertType;
  message: string;
  details: Record<string, unknown> | null;
  timestamp: string;
}

export interface AlertsResponse {
  alerts: Alert[];
  count: Record<AlertType, number>;
  total: number;
}
