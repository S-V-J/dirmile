import { Link } from "react-router";

import { useAuth } from "../auth/useAuth";

/**
 * About Us page.
 * Visible to both authenticated and unauthenticated visitors.
 * Contains multiple CTAs to encourage sign-up / usage.
 */
export function AboutPage() {
  const { user } = useAuth();

  return (
    <section className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-3xl font-bold text-white">About Dirmile</h1>

      <div className="mt-8 space-y-6 text-brand-200 leading-relaxed">
        <p>
          <strong className="text-white">Dirmile</strong> is a weather-aware
          truck routing tool built to help professional drivers make safer
          route decisions before they leave the yard.
        </p>

        <h2 className="text-xl font-semibold text-white">Why we built it</h2>
        <p>
          Every year, adverse weather contributes to thousands of
          weather-related crashes involving large trucks. Wind gusts,
          heavy rain, and snowfall affect handling differently depending
          on load weight. Existing routing apps treat all drivers the
          same. Dirmile was built to close that gap by combining live
          weather forecasts, truck-specific load rules, and route
          alternatives into a single, clear safety picture.
        </p>

        <h2 className="text-xl font-semibold text-white">How it works</h2>
        <ol className="list-decimal space-y-2 pl-6">
          <li>You enter your origin, destination, departure time, and load weight.</li>
          <li>Dirmile generates up to three route options using OpenStreetMap routing data.</li>
          <li>Weather is sampled at configurable checkpoints (every 10, 25, or 50 miles) using your estimated arrival time at each point.</li>
          <li>Each checkpoint is classified as Low, Moderate, High, Severe, or No Travel using wind, rain, and snow thresholds — with load-based overrides.</li>
          <li>Routes are ranked by safety first, then travel time, and the best option is recommended with human-readable reasons.</li>
          <li>Everything is displayed on an interactive map with a 0–48 hour weather heatmap slider.</li>
        </ol>

        <h2 className="text-xl font-semibold text-white">Data sources</h2>
        <ul className="list-disc space-y-1 pl-6">
          <li><strong>Routing:</strong> OSRM (Open Source Routing Machine) on OpenStreetMap data</li>
          <li><strong>Weather:</strong> Open-Meteo free hourly forecast API</li>
          <li><strong>Geocoding:</strong> Open-Meteo Geocoding API</li>
          <li><strong>Basemap:</strong> OpenStreetMap tiles via Leaflet</li>
        </ul>

        <h2 className="text-xl font-semibold text-white">Privacy</h2>
        <p>
          Dirmile stores only the trip plans you create. We do not track
          your real-time location, sell data, or share personal information
          with third parties. All external API calls are made server-side
          so your browser never talks directly to weather or routing
          providers.
        </p>

        <h2 className="text-xl font-semibold text-white">Open source</h2>
        <p>
          Dirmile is released under the MIT License. The source code is
          available on{" "}
          <a
            href="https://github.com/S-V-J/dirmile"
            target="_blank"
            rel="noopener noreferrer"
            className="text-brand-400 underline hover:text-brand-300"
          >
            GitHub
          </a>.
        </p>
      </div>

      {/* CTA */}
      <div className="mt-12 rounded-xl border border-brand-700 bg-brand-900/50 p-8 text-center">
        <h2 className="text-2xl font-bold text-white">
          Ready to drive smarter?
        </h2>
        <p className="mt-2 text-brand-300">
          Create a free account and plan your next trip with full weather
          risk visibility.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-4">
          {user ? (
            <Link
              to="/app"
              className="rounded-lg bg-brand-500 px-6 py-3 text-base font-semibold text-white shadow hover:bg-brand-400 transition-colors"
            >
              Open Web App
            </Link>
          ) : (
            <>
              <Link
                to="/register"
                className="rounded-lg bg-brand-500 px-6 py-3 text-base font-semibold text-white shadow hover:bg-brand-400 transition-colors"
              >
                Create Account
              </Link>
              <Link
                to="/login"
                className="rounded-lg border border-brand-600 px-6 py-3 text-base font-semibold text-brand-300 hover:bg-brand-800/50 hover:text-white transition-colors"
              >
                Log In
              </Link>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
