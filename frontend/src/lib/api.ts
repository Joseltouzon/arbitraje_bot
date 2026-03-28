const API_BASE = '/api';

export async function fetchCycles() {
  const res = await fetch(`${API_BASE}/cycles/`);
  return res.json();
}

export async function triggerScan() {
  const res = await fetch(`${API_BASE}/cycles/scan`, { method: 'POST' });
  return res.json();
}

export async function fetchPrices() {
  const res = await fetch(`${API_BASE}/prices/tickers`);
  return res.json();
}

export async function fetchSettings() {
  const res = await fetch(`${API_BASE}/settings/`);
  return res.json();
}

export async function updateSettings(data: Record<string, unknown>) {
  const res = await fetch(`${API_BASE}/settings/`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function fetchHealth() {
  const res = await fetch('/health');
  return res.json();
}

export async function fetchCycleHistory(limit = 50) {
  const res = await fetch(`${API_BASE}/history/cycles?limit=${limit}`);
  return res.json();
}

export async function fetchTradeHistory(limit = 50) {
  const res = await fetch(`${API_BASE}/history/trades?limit=${limit}`);
  return res.json();
}

export async function fetchAnalyticsSummary() {
  const res = await fetch(`${API_BASE}/history/analytics/summary`);
  return res.json();
}

export async function fetchProfitTimeseries(hours = 24) {
  const res = await fetch(
    `${API_BASE}/history/analytics/timeseries?hours=${hours}`
  );
  return res.json();
}

export async function fetchTopCycles(limit = 10) {
  const res = await fetch(`${API_BASE}/history/analytics/top?limit=${limit}`);
  return res.json();
}

// Paper Trading
export async function fetchPaperStatus() {
  const res = await fetch(`${API_BASE}/paper/status`);
  return res.json();
}

export async function enablePaper() {
  const res = await fetch(`${API_BASE}/paper/enable`, { method: 'POST' });
  return res.json();
}

export async function disablePaper() {
  const res = await fetch(`${API_BASE}/paper/disable`, { method: 'POST' });
  return res.json();
}

export async function fetchPaperTrades(limit = 20) {
  const res = await fetch(`${API_BASE}/paper/trades?limit=${limit}`);
  return res.json();
}

export async function fetchPaperBalanceHistory() {
  const res = await fetch(`${API_BASE}/paper/balance-history`);
  return res.json();
}

export async function resetPaper() {
  const res = await fetch(`${API_BASE}/paper/reset`, { method: 'POST' });
  return res.json();
}

// Live Trading
export async function fetchLiveStatus() {
  const res = await fetch(`${API_BASE}/live/status`);
  return res.json();
}

export async function enableLive() {
  const res = await fetch(`${API_BASE}/live/enable`, { method: 'POST' });
  return res.json();
}

export async function confirmLive() {
  const res = await fetch(`${API_BASE}/live/confirm`, { method: 'POST' });
  return res.json();
}

export async function disableLive() {
  const res = await fetch(`${API_BASE}/live/disable`, { method: 'POST' });
  return res.json();
}

export async function pauseLive() {
  const res = await fetch(`${API_BASE}/live/pause`, { method: 'POST' });
  return res.json();
}

export async function resumeLive() {
  const res = await fetch(`${API_BASE}/live/resume`, { method: 'POST' });
  return res.json();
}

export async function fetchLiveTrades(limit = 20) {
  const res = await fetch(`${API_BASE}/live/trades?limit=${limit}`);
  return res.json();
}
