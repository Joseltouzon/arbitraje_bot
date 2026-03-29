import { useState, useEffect } from 'react';
import { Header } from './components/layout/Header';
import { CycleList } from './components/dashboard/CycleList';
import { StatsCard } from './components/dashboard/StatsCard';
import { OrderBook } from './components/dashboard/OrderBook';
import { ProfitChart } from './components/charts/ProfitChart';
import { CycleCountChart } from './components/charts/CycleCountChart';
import { CycleHistory } from './components/history/CycleHistory';
import { SpotFuturesHistory } from './components/history/SpotFuturesHistory';
import { SpotFuturesStats } from './components/history/SpotFuturesStats';
import { AnalyticsSummary } from './components/history/AnalyticsSummary';
import { PaperDashboard } from './components/paper/PaperDashboard';
import { LiveDashboard } from './components/live/LiveDashboard';
import { SpotFuturesFeed } from './components/spotfutures/SpotFuturesFeed';
import { useWebSocket } from './hooks/useWebSocket';
import {
  fetchPaperStatus,
  fetchPaperTrades,
  enablePaper,
  disablePaper,
  fetchLiveStatus,
  fetchLiveTrades,
  enableLive,
  confirmLive,
  disableLive,
  pauseLive,
  resumeLive,
} from './lib/api';

type Tab = 'dashboard' | 'paper' | 'live' | 'history' | 'analytics';

interface PaperStats {
  enabled: boolean;
  initial_balance: number;
  current_balance: number;
  net_profit: number;
  net_profit_pct: number;
  total_trades: number;
  success_rate: number;
  total_fees_paid: number;
  consecutive_losses: number;
  avg_latency_ms: number;
}

interface PaperTrade {
  trade_id: number;
  currencies: string[];
  profit_usdt: number;
  profit_pct: number;
  balance: number;
}

interface LiveStats {
  enabled: boolean;
  confirmed: boolean;
  total_trades: number;
  profitable_trades: number;
  failed_trades: number;
  partial_trades: number;
  success_rate: number;
  total_profit_usdt: number;
  total_fees_usdt: number;
  risk: {
    paused: boolean;
    consecutive_losses: number;
    daily_pnl: number;
  };
}

interface LiveTrade {
  id: number;
  currencies: string[];
  profit_usdt: number;
  profit_pct: number;
  status: string;
  duration_ms: number;
}

function App() {
  const { cycles, spotFutures, connected } = useWebSocket();
  const [tab, setTab] = useState<Tab>('dashboard');
  const [paperStats, setPaperStats] = useState<PaperStats | null>(null);
  const [paperTrades, setPaperTrades] = useState<PaperTrade[]>([]);
  const [liveStats, setLiveStats] = useState<LiveStats | null>(null);
  const [liveTrades, setLiveTrades] = useState<LiveTrade[]>([]);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [paperRes, paperTradesRes, liveRes, liveTradesRes] =
          await Promise.all([
            fetchPaperStatus(),
            fetchPaperTrades(20),
            fetchLiveStatus(),
            fetchLiveTrades(20),
          ]);
        setPaperStats(paperRes);
        setPaperTrades(paperTradesRes.trades || []);
        setLiveStats(liveRes);
        setLiveTrades(liveTradesRes.trades || []);
      } catch {
        // ignore
      }
    };
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleTogglePaper = async (enabled: boolean) => {
    try {
      if (enabled) await enablePaper();
      else await disablePaper();
      setPaperStats(await fetchPaperStatus());
    } catch { /* ignore */ }
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'paper', label: 'Paper' },
    { id: 'live', label: 'Live' },
    { id: 'history', label: 'History' },
    { id: 'analytics', label: 'Analytics' },
  ];

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      <Header connected={connected} />

      <div className="flex border-b border-gray-800 px-4">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${
              tab === t.id
                ? t.id === 'live'
                  ? 'border-red-500 text-red-400'
                  : 'border-blue-500 text-blue-400'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'dashboard' && (
        <>
          <StatsCard cycles={cycles} />
          <div className="flex-1 flex gap-4 p-4 overflow-hidden">
            <div className="flex-1 overflow-y-auto space-y-4">
              <CycleList cycles={cycles} connected={connected} />
              <SpotFuturesFeed opportunities={spotFutures} />
            </div>
            <div className="w-96 space-y-4 overflow-y-auto">
              <ProfitChart />
              <OrderBook />
            </div>
          </div>
        </>
      )}

      {tab === 'paper' && (
        <div className="flex-1 p-4 overflow-y-auto">
          <PaperDashboard
            stats={paperStats}
            trades={paperTrades}
            onToggle={handleTogglePaper}
          />
        </div>
      )}

      {tab === 'live' && (
        <div className="flex-1 p-4 overflow-y-auto">
          <LiveDashboard
            stats={liveStats}
            trades={liveTrades}
            onEnable={async () => { await enableLive(); setLiveStats(await fetchLiveStatus()); }}
            onConfirm={async () => { await confirmLive(); setLiveStats(await fetchLiveStatus()); }}
            onDisable={async () => { await disableLive(); setLiveStats(await fetchLiveStatus()); }}
            onPause={async () => { await pauseLive(); setLiveStats(await fetchLiveStatus()); }}
            onResume={async () => { await resumeLive(); setLiveStats(await fetchLiveStatus()); }}
          />
        </div>
      )}

      {tab === 'history' && (
        <div className="flex-1 p-4 space-y-4 overflow-y-auto">
          <CycleHistory />
          <SpotFuturesHistory />
        </div>
      )}

      {tab === 'analytics' && (
        <div className="flex-1 p-4 space-y-4 overflow-y-auto">
          <AnalyticsSummary />
          <SpotFuturesStats />
          <div className="grid grid-cols-2 gap-4">
            <ProfitChart />
            <CycleCountChart />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
