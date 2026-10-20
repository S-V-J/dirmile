import { useState, type FormEvent } from "react";

import * as api from "../api/client";
import type { TripPlanDetail } from "../types/api";

interface TripFormProps {
  onPlanCreated: (plan: TripPlanDetail) => void;
  defaultLoadLb?: number;
  defaultInterval?: 10 | 25 | 50;
}

const INTERVAL_OPTIONS: readonly (10 | 25 | 50)[] = [10, 25, 50];

/**
 * Returns an ISO datetime string for `hours` hours from now,
 * rounded to the nearest 15 minutes, suitable for <input type="datetime-local">.
 */
function defaultDeparture(): string {
  const now = new Date();
  now.setMinutes(Math.ceil(now.getMinutes() / 15) * 15, 0, 0);
  now.setHours(now.getHours() + 1);
  // Format as YYYY-MM-DDTHH:mm (local time, no timezone suffix)
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

export function TripForm({
  onPlanCreated,
  defaultLoadLb = 30000,
  defaultInterval = 25,
}: TripFormProps) {
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [departure, setDeparture] = useState(defaultDeparture);
  const [loadLb, setLoadLb] = useState(String(defaultLoadLb));
  const [intervalMiles, setIntervalMiles] = useState<10 | 25 | 50>(defaultInterval);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progressStep, setProgressStep] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // Client-side validation
    if (!origin.trim()) {
      setError("Origin is required.");
      return;
    }
    if (!destination.trim()) {
      setError("Destination is required.");
      return;
    }
    if (origin.trim().toLowerCase() === destination.trim().toLowerCase()) {
      setError("Origin and destination cannot be the same.");
      return;
    }
    if (!departure) {
      setError("Departure date/time is required.");
      return;
    }
    const loadNum = Number(loadLb);
    if (!Number.isFinite(loadNum) || loadNum < 0) {
      setError("Load weight must be a non-negative number.");
      return;
    }
    if (loadNum > 80000) {
      // Warning but allow submission
    }

    setIsSubmitting(true);
    try {
      setProgressStep("Geocoding places…");
      const plan = await api.createTripPlan({
        origin: origin.trim(),
        destination: destination.trim(),
        departure: new Date(departure).toISOString(),
        load_lb: Math.round(loadNum),
        interval_miles: intervalMiles,
      });
      setProgressStep(null);
      onPlanCreated(plan);
    } catch (err) {
      setProgressStep(null);
      if (err instanceof api.ApiRequestError) {
        const detail = err.data;
        if (typeof detail.detail === "string") {
          setError(detail.detail);
        } else if (typeof detail.origin === "string") {
          setError(`Origin: ${detail.origin}`);
        } else if (typeof detail.destination === "string") {
          setError(`Destination: ${detail.destination}`);
        } else if (typeof detail.departure === "string") {
          setError(`Departure: ${detail.departure}`);
        } else if (typeof detail.load_lb === "string") {
          setError(`Load: ${detail.load_lb}`);
        } else {
          setError(JSON.stringify(detail));
        }
      } else {
        setError("Failed to create trip plan. Check your connection.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputClass =
    "mt-1 block w-full rounded-md border border-brand-700 bg-brand-900 px-3 py-2 text-white placeholder-brand-500 focus:border-brand-400 focus:outline-none focus:ring-1 focus:ring-brand-400";
  const labelClass = "block text-sm font-medium text-brand-200";

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4"
      noValidate
      aria-label="Trip planning form"
    >
      {error && (
        <div
          role="alert"
          className="rounded-md border border-red-800 bg-red-950/60 px-4 py-3 text-sm text-red-300"
        >
          {error}
        </div>
      )}

      {progressStep && (
        <div className="flex items-center gap-2 rounded-md border border-brand-700 bg-brand-900/50 px-4 py-3 text-sm text-brand-300">
          <span
            className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-brand-400 border-t-transparent"
            aria-hidden="true"
          />
          {progressStep}
        </div>
      )}

      {/* Origin */}
      <div>
        <label htmlFor="trip-origin" className={labelClass}>
          Origin *
        </label>
        <input
          id="trip-origin"
          type="text"
          value={origin}
          onChange={(e) => setOrigin(e.target.value)}
          className={inputClass}
          placeholder="e.g. Cincinnati, OH"
          autoComplete="off"
          disabled={isSubmitting}
        />
      </div>

      {/* Destination */}
      <div>
        <label htmlFor="trip-destination" className={labelClass}>
          Destination *
        </label>
        <input
          id="trip-destination"
          type="text"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          className={inputClass}
          placeholder="e.g. Chicago, IL"
          autoComplete="off"
          disabled={isSubmitting}
        />
      </div>

      {/* Departure */}
      <div>
        <label htmlFor="trip-departure" className={labelClass}>
          Departure Date &amp; Time *
        </label>
        <input
          id="trip-departure"
          type="datetime-local"
          value={departure}
          onChange={(e) => setDeparture(e.target.value)}
          className={inputClass}
          disabled={isSubmitting}
        />
        <p className="mt-1 text-xs text-brand-500">
          Local time. Up to 16 days in the future.
        </p>
      </div>

      {/* Load Weight */}
      <div>
        <label htmlFor="trip-load" className={labelClass}>
          Load Weight (lb) *
        </label>
        <input
          id="trip-load"
          type="number"
          min={0}
          max={200000}
          step={500}
          value={loadLb}
          onChange={(e) => setLoadLb(e.target.value)}
          className={inputClass}
          placeholder="30000"
          disabled={isSubmitting}
        />
        <p className="mt-1 text-xs text-brand-500">
          Gross vehicle + cargo weight in pounds. Typical max: 80,000 lb.
        </p>
        {Number(loadLb) > 80000 && (
          <p className="mt-1 text-xs text-amber-400" role="status">
            ⚠ Exceeds typical legal gross weight. Risk overrides may apply.
          </p>
        )}
      </div>

      {/* Checkpoint Interval */}
      <div>
        <fieldset>
          <legend className={labelClass}>Checkpoint Interval</legend>
          <div className="mt-2 flex gap-2">
            {INTERVAL_OPTIONS.map((opt) => (
              <label
                key={opt}
                className={`flex-1 cursor-pointer rounded-md border px-3 py-2 text-center text-sm font-medium transition-colors ${
                  intervalMiles === opt
                    ? "border-brand-400 bg-brand-800 text-white"
                    : "border-brand-700 bg-brand-900 text-brand-300 hover:border-brand-500"
                }`}
              >
                <input
                  type="radio"
                  name="interval"
                  value={opt}
                  checked={intervalMiles === opt}
                  onChange={() => setIntervalMiles(opt)}
                  className="sr-only"
                  disabled={isSubmitting}
                />
                {opt} mi
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full rounded-md bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow hover:bg-brand-400 disabled:opacity-50 transition-colors"
      >
        {isSubmitting ? "Finding safest routes…" : "Find Safest Routes"}
      </button>
    </form>
  );
}
