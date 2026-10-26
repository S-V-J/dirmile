import { useCallback } from "react";
import type { HeatmapMetric } from "./HeatmapLayer";

interface ForecastSliderProps {
  hour: number;
  onHourChange: (hour: number) => void;
  metric: HeatmapMetric;
  onMetricChange: (metric: HeatmapMetric) => void;
  visible: boolean;
  onToggleVisible: (visible: boolean) => void;
}

const METRIC_OPTIONS: ReadonlyArray<{
  value: HeatmapMetric;
  label: string;
}> = [
  { value: "risk", label: "Combined Risk" },
  { value: "wind", label: "Wind" },
  { value: "rain", label: "Rain" },
  { value: "snow", label: "Snow" },
];

function formatHour(h: number): string {
  if (h === 0) return "Departure";
  if (h === 1) return "+1 hr";
  if (h === 24) return "+24 hrs (1 day)";
  if (h === 48) return "+48 hrs (2 days)";
  return `+${h} hrs`;
}

export function ForecastSlider({
  hour,
  onHourChange,
  metric,
  onMetricChange,
  visible,
  onToggleVisible,
}: ForecastSliderProps) {
  const handleSlider = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onHourChange(Number(e.target.value));
    },
    [onHourChange]
  );

  return (
    <div className="space-y-3">
      {/* Header row: toggle + title */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-brand-400">
          Weather Heatmap
        </h3>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-brand-300">
          <input
            type="checkbox"
            checked={visible}
            onChange={(e) => onToggleVisible(e.target.checked)}
            className="h-3.5 w-3.5 accent-brand-400"
          />
          Show
        </label>
      </div>

      {/* Metric selector */}
      <div className="flex flex-wrap gap-1.5">
        {METRIC_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onMetricChange(opt.value)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
              metric === opt.value
                ? "bg-brand-500 text-white"
                : "bg-brand-800/50 text-brand-300 hover:bg-brand-700/50 hover:text-brand-200"
            }`}
            aria-pressed={metric === opt.value}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Slider */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs text-brand-400">
          <span>Departure</span>
          <span className="font-mono font-semibold text-brand-200">
            {formatHour(hour)}
          </span>
          <span>+48 hrs</span>
        </div>
        <input
          type="range"
          min={0}
          max={48}
          step={1}
          value={hour}
          onChange={handleSlider}
          className="h-2 w-full cursor-pointer appearance-none rounded-full bg-brand-800 accent-brand-400"
          aria-label="Forecast hour offset from departure"
          aria-valuemin={0}
          aria-valuemax={48}
          aria-valuenow={hour}
          aria-valuetext={formatHour(hour)}
        />
      </div>

      {/* Gradient legend */}
      <div className="space-y-1">
        <div
          className="h-2 w-full rounded-full"
          style={{
            background:
              "linear-gradient(to right, #22c55e 0%, #eab308 25%, #f97316 50%, #dc2626 75%, #7f1d1d 100%)",
          }}
          aria-hidden="true"
        />
        <div className="flex justify-between text-[10px] text-brand-500">
          <span>Low</span>
          <span>Moderate</span>
          <span>High</span>
          <span>Severe</span>
          <span>No Travel</span>
        </div>
      </div>
    </div>
  );
}
