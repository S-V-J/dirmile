import type { Checkpoint, RiskLevel } from "../types/api";
import { RISK_COLORS, RISK_LABELS } from "../types/api";
import { RISK_HEX } from "../lib/riskColors";

interface CheckpointListProps {
  checkpoints: Checkpoint[];
  highlightId?: string | null;
  onCheckpointClick?: (cp: Checkpoint) => void;
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function CheckpointList({
  checkpoints,
  highlightId,
  onCheckpointClick,
}: CheckpointListProps) {
  if (checkpoints.length === 0) {
    return (
      <p className="text-sm text-brand-500">
        Select a route to view checkpoints.
      </p>
    );
  }

  return (
    <div className="max-h-80 overflow-y-auto rounded-lg border border-brand-800/50">
      <table className="w-full text-xs" aria-label="Checkpoint details">
        <thead className="sticky top-0 bg-brand-900 text-brand-400">
          <tr>
            <th className="px-2 py-1.5 text-left">Mile</th>
            <th className="px-2 py-1.5 text-left">ETA</th>
            <th className="px-2 py-1.5 text-right">Wind</th>
            <th className="px-2 py-1.5 text-right">Rain</th>
            <th className="px-2 py-1.5 text-right">Snow</th>
            <th className="px-2 py-1.5 text-left">Risk</th>
          </tr>
        </thead>
        <tbody>
          {checkpoints.map((cp) => {
            const isHighlighted = cp.id === highlightId;
            return (
              <tr
                key={cp.id}
                onClick={() => onCheckpointClick?.(cp)}
                className={`cursor-pointer border-t border-brand-800/30 transition-colors ${
                  isHighlighted
                    ? "bg-brand-800/60"
                    : "hover:bg-brand-900/50"
                }`}
              >
                <td className="px-2 py-1.5 font-mono text-brand-300">
                  {cp.mile_marker.toFixed(0)}
                </td>
                <td className="px-2 py-1.5 text-brand-400">
                  {formatTime(cp.eta_utc)}
                </td>
                <td className="px-2 py-1.5 text-right text-brand-300">
                  {cp.wind_mph.toFixed(1)}
                </td>
                <td className="px-2 py-1.5 text-right text-brand-300">
                  {cp.rain_in_hr.toFixed(2)}
                </td>
                <td className="px-2 py-1.5 text-right text-brand-300">
                  {cp.snow_in_hr.toFixed(2)}
                </td>
                <td className="px-2 py-1.5">
                  <RiskBadge level={cp.overall_risk} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span
      className="inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
      style={{
        backgroundColor: `${RISK_HEX[level]}33`,
        color: RISK_COLORS[level],
      }}
    >
      {RISK_LABELS[level]}
    </span>
  );
}
