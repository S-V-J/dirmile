import { useEffect, useRef, useState, type FormEvent } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";

import * as api from "../api/client";
import type { Place, TripPlanDetail } from "../types/api";

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

const DEBOUNCE_MS = 300;
const MIN_QUERY_CHARS = 2;

interface PlaceComboboxProps {
  id: string;
  label: string;
  value: string;
  onChange: (next: string) => void;
  inputClass: string;
  labelClass: string;
  placeholder: string;
  disabled?: boolean;
}

/**
 * Autocomplete input backed by GET /api/places/?q=...
 * Debounced, race-guarded, keyboard-navigable. Free text stays valid:
 * the backend geocodes whatever is submitted, so a suggestion is only a
 * convenience that guarantees an unambiguous display_name.
 */
function PlaceCombobox({
  id,
  label,
  value,
  onChange,
  inputClass,
  labelClass,
  placeholder,
  disabled = false,
}: PlaceComboboxProps) {
  const [places, setPlaces] = useState<Place[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const requestIdRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectedRef = useRef<string | null>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);

    const query = value.trim();

    // A pick just filled the input — don't re-search our own selection.
    if (selectedRef.current !== null && query === selectedRef.current) {
      selectedRef.current = null;
      setPlaces([]);
      setOpen(false);
      setLoading(false);
      return;
    }

    if (query.length < MIN_QUERY_CHARS) {
      setPlaces([]);
      setOpen(false);
      setLoading(false);
      return;
    }

    setLoading(true);
    const requestId = ++requestIdRef.current;

    timerRef.current = setTimeout(async () => {
      const results = await api.searchPlaces(query);
      if (requestId !== requestIdRef.current) return; // stale response
      setLoading(false);
      setPlaces(results);
      setActiveIndex(-1);
      setOpen(results.length > 0);
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [value]);

  const selectPlace = (place: Place) => {
    selectedRef.current = place.display_name;
    onChange(place.display_name);
    setPlaces([]);
    setOpen(false);
    setLoading(false);
  };

  const listId = `${id}-places`;

  return (
    <div className="relative">
      <label htmlFor={id} className={labelClass}>
        {label}
      </label>
      <input
        id={id}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={
          open && activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined
        }
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e: ReactKeyboardEvent<HTMLInputElement>) => {
          if (!open || places.length === 0) {
            if (e.key === "Escape") setOpen(false);
            return;
          }
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActiveIndex((i) => (i + 1) % places.length);
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActiveIndex((i) => (i <= 0 ? places.length - 1 : i - 1));
          } else if (e.key === "Enter") {
            const picked = places[activeIndex];
            if (picked) {
              e.preventDefault();
              selectPlace(picked);
            }
            // else: let the form submit with the free text as typed
          } else if (e.key === "Escape") {
            e.preventDefault();
            setOpen(false);
            setActiveIndex(-1);
          }
        }}
        onBlur={() => {
          setOpen(false);
          setActiveIndex(-1);
        }}
        className={inputClass}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
      />
      {loading && (
        <p className="mt-1 text-xs text-brand-500" role="status">
          Searching…
        </p>
      )}
      {open && places.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          aria-label={`${label} suggestions`}
          className="absolute z-20 mt-1 w-full overflow-hidden rounded-md border border-brand-700 bg-brand-900 shadow-lg"
        >
          {places.map((place, index) => (
            <li
              key={`${place.id}-${index}`}
              id={`${id}-option-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              onMouseDown={(e) => {
                e.preventDefault(); // keep focus on the input through the click
                selectPlace(place);
              }}
              onMouseEnter={() => setActiveIndex(index)}
              className={`cursor-pointer px-3 py-2 text-sm ${
                index === activeIndex
                  ? "bg-brand-800 text-white"
                  : "text-brand-200 hover:bg-brand-800 hover:text-white"
              }`}
            >
              <span className="block truncate">{place.display_name}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
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
        <PlaceCombobox
          id="trip-origin"
          label="Origin *"
          value={origin}
          onChange={setOrigin}
          inputClass={inputClass}
          labelClass={labelClass}
          placeholder="e.g. Cincinnati, OH"
          disabled={isSubmitting}
        />

      {/* Destination */}
        <PlaceCombobox
          id="trip-destination"
          label="Destination *"
          value={destination}
          onChange={setDestination}
          inputClass={inputClass}
          labelClass={labelClass}
          placeholder="e.g. Chicago, IL"
          disabled={isSubmitting}
        />

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
