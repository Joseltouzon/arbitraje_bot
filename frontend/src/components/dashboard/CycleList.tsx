import type { TriangularCycle } from '../../types';
import { CycleCard } from '../cycle/CycleCard';

interface CycleListProps {
  cycles: TriangularCycle[];
  connected: boolean;
}

export function CycleList({ cycles, connected }: CycleListProps) {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      {!connected ? (
        <div className="text-center text-gray-500 py-20">
          <p className="text-lg">Connecting to server...</p>
          <p className="text-sm mt-2">Make sure the backend is running</p>
        </div>
      ) : cycles.length === 0 ? (
        <div className="text-center text-gray-500 py-20">
          <p className="text-lg">Scanning for profitable cycles...</p>
          <p className="text-sm mt-2">
            Looking for USDT → X → Y → USDT opportunities
          </p>
          <p className="text-xs mt-1 text-gray-600">
            Cycles appear when price inconsistencies are detected
          </p>
        </div>
      ) : (
        <>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-white">
              Profitable Cycles
            </h2>
            <span className="text-gray-400 text-sm">
              {cycles.length} found
            </span>
          </div>
          {cycles.map((cycle, idx) => (
            <CycleCard key={`${cycle.currencies.join('-')}-${idx}`} cycle={cycle} />
          ))}
        </>
      )}
    </div>
  );
}
