import type { LogEntry } from '../../hooks/useWebSocket';

interface ActivityLogProps {
  logs: LogEntry[];
}

export function ActivityLog({ logs }: ActivityLogProps) {
  const typeColors: Record<string, string> = {
    scan: 'text-gray-500',
    cycle: 'text-green-400',
    spot_futures: 'text-blue-400',
    error: 'text-red-400',
    info: 'text-gray-400',
  };

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <h3 className="text-white font-semibold mb-2">Activity Log</h3>
      <div className="h-40 overflow-y-auto font-mono text-xs space-y-0.5">
        {logs.length === 0 ? (
          <p className="text-gray-600">Waiting for activity...</p>
        ) : (
          logs.map((log, idx) => (
            <div key={idx} className="flex gap-2">
              <span className="text-gray-600 shrink-0">{log.time}</span>
              <span className={`${typeColors[log.type]} shrink-0`}>
                [{log.type}]
              </span>
              <span className="text-gray-300">{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
