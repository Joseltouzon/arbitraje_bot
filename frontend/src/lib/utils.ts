export function formatPct(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(4)}%`;
}

export function formatUsdt(value: number): string {
  return `$${value.toFixed(2)}`;
}

export function formatRate(value: number): string {
  if (value < 0.001) return value.toExponential(4);
  return value.toFixed(8);
}

export function formatTime(iso: string | null): string {
  if (!iso) return 'Never';
  const date = new Date(iso);
  return date.toLocaleTimeString();
}
