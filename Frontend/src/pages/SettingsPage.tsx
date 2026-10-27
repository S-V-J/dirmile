import { useCallback, useEffect, useState } from "react";

import { getCurrentUser, updateSettings } from "../api/client";
import type { User } from "../types/api";

const INTERVAL_OPTIONS = [10, 25, 50] as const;
const METRIC_OPTIONS = [
  { value: "risk", label: "Combined Risk" },
  { value: "wind", label: "Wind" },
  { value: "rain", label: "Rain" },
  { value: "snow", label: "Snow" },
] as const;

interface SettingsForm {
  preferred_interval_miles: 10 | 25 | 50;
  default_load_lb: number;
  theme: "light" | "dark" | "system";
  heatmap_metric: "risk" | "wind" | "rain" | "snow";
  map_style: "streets" | "satellite" | "terrain";
}

export function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<SettingsForm>({
    preferred_interval_miles: 25,
    default_load_lb: 30000,
    theme: "system",
    heatmap_metric: "risk",
    map_style: "streets",
  });

  useEffect(() => {
    let cancelled = false;
    getCurrentUser()
      .then((user: User) => {
        if (cancelled) return;
        setForm({
          preferred_interval_miles: user.preferred_interval_miles ?? 25,
          default_load_lb: user.default_load_lb ?? 30000,
          theme: user.theme ?? "system",
          heatmap_metric: user.heatmap_metric ?? "risk",
          map_style: user.map_style ?? "streets",
        });
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) {
          setError("Failed to load settings.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleChange = useCallback(
    (field: keyof SettingsForm, value: number | string) => {
      setForm((prev) => ({ ...prev, [field]: value }) as SettingsForm);
    },
    []
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setSaving(true);
      setMessage(null);
      setError(null);
      try {
        await updateSettings(form);
        setMessage("Settings saved successfully.");
      } catch (err: unknown) {
        const detail =
          err && typeof err === "object" && "data" in err
            ? String(
                (err as { data?: { detail?: string } }).data?.detail ??
                  "Failed to save settings."
              )
            : "Failed to save settings.";
        setError(detail);
      } finally {
        setSaving(false);
      }
    },
    [form]
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-brand-400">
        Loading settings…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-bold text-brand-100">Settings</h1>
        <p className="mt-1 text-sm text-brand-400">
          Configure your default trip preferences and display options.
        </p>
      </header>

      {message && (
        <div className="rounded-lg border border-green-800/50 bg-green-950/40 px-4 py-3 text-sm text-green-300">
          {message}
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Checkpoint Interval */}
        <fieldset className="space-y-3 rounded-xl border border-brand-800/50 bg-brand-900/50 p-5">
          <legend className="px-2 text-sm font-semibold text-brand-200">
            Default Checkpoint Interval
          </legend>
          <div className="flex gap-3">
            {INTERVAL_OPTIONS.map((mi) => (
              <label
                key={mi}
                className={`flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 text-sm transition-colors ${
                  form.preferred_interval_miles === mi
                    ? "border-brand-500 bg-brand-800/60 text-brand-100"
                    : "border-brand-700/50 bg-brand-900/40 text-brand-400 hover:border-brand-600"
                }`}
              >
                <input
                  type="radio"
                  name="interval"
                  value={mi}
                  checked={form.preferred_interval_miles === mi}
                  onChange={() => handleChange("preferred_interval_miles", mi)}
                  className="sr-only"
                />
                {mi} miles
              </label>
            ))}
          </div>
          <p className="text-xs text-brand-500">
            Weather will be sampled at this distance interval along each route.
          </p>
        </fieldset>

        {/* Default Load Weight */}
        <fieldset className="space-y-3 rounded-xl border border-brand-800/50 bg-brand-900/50 p-5">
          <legend className="px-2 text-sm font-semibold text-brand-200">
            Default Load Weight
          </legend>
          <div className="flex items-center gap-3">
            <input
              type="number"
              min={0}
              max={120000}
              step={500}
              value={form.default_load_lb}
              onChange={(e) =>
                handleChange("default_load_lb", Number(e.target.value))
              }
              className="w-36 rounded-lg border border-brand-700/50 bg-brand-950 px-3 py-2 text-sm text-brand-100 focus:border-brand-500 focus:outline-none"
              aria-label="Default load weight in pounds"
            />
            <span className="text-sm text-brand-400">lb</span>
          </div>
          <p className="text-xs text-brand-500">
            Gross vehicle weight. Used for wind load overrides (≥30,000 lb and
            ≥40,000 lb thresholds).
          </p>
        </fieldset>


        {/* Heatmap Metric */}
        <fieldset className="space-y-3 rounded-xl border border-brand-800/50 bg-brand-900/50 p-5">
          <legend className="px-2 text-sm font-semibold text-brand-200">
            Default Heatmap Metric
          </legend>
          <div className="flex flex-wrap gap-3">
            {METRIC_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 text-sm transition-colors ${
                  form.heatmap_metric === opt.value
                    ? "border-brand-500 bg-brand-800/60 text-brand-100"
                    : "border-brand-700/50 bg-brand-900/40 text-brand-400 hover:border-brand-600"
                }`}
              >
                <input
                  type="radio"
                  name="heatmap_metric"
                  value={opt.value}
                  checked={form.heatmap_metric === opt.value}
                  onChange={() => handleChange("heatmap_metric", opt.value)}
                  className="sr-only"
                />
                {opt.label}
              </label>
            ))}
          </div>
          <p className="text-xs text-brand-500">
            The metric shown by default when viewing the weather heatmap.
          </p>
        </fieldset>


        {/* Submit */}
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-brand-500 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-400 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save Settings"}
          </button>
        </div>
      </form>
    </div>
  );
}
