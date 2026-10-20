import { Link } from "react-router";

import { useAuth } from "../auth/useAuth";

/**
 * Public landing page shown at "/" when the visitor is not authenticated.
 * When authenticated, the router redirects to "/app".
 */
export function LandingPage() {
  const { user } = useAuth();

  // If already logged in, send to the web app.
  if (user) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-brand-300">
          Redirecting to{" "}
          <Link to="/app" className="underline hover:text-brand-200">
            Web App
          </Link>
          …
        </p>
      </div>
    );
  }

  return (
    <section className="mx-auto max-w-4xl px-4 py-20 text-center">
      <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
        Drive smarter.
        <br />
        <span className="text-brand-400">See the weather before you go.</span>
      </h1>

      <p className="mt-6 text-lg leading-relaxed text-brand-200">
        Dirmile helps truck drivers choose the safest route based on live
        weather forecasts, load weight, and estimated travel time — so you
        can avoid dangerous conditions before you hit the road.
      </p>

      <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
        <Link
          to="/login"
          className="rounded-lg bg-brand-500 px-6 py-3 text-base font-semibold text-white shadow hover:bg-brand-400 transition-colors"
        >
          Get Started
        </Link>
        <Link
          to="/about"
          className="rounded-lg border border-brand-600 px-6 py-3 text-base font-semibold text-brand-300 hover:bg-brand-800/50 hover:text-white transition-colors"
        >
          Learn More
        </Link>
      </div>

      {/* Feature highlights */}
      <div className="mt-20 grid gap-8 text-left sm:grid-cols-3">
        <FeatureCard
          title="3 Route Options"
          description="Compare alternative routes side by side, each scored for weather risk along every mile."
        />
        <FeatureCard
          title="Load-Aware Risk"
          description="Heavy loads change the danger threshold. Dirmile applies FMCSA-inspired wind overrides automatically."
        />
        <FeatureCard
          title="0–48 h Heatmap"
          description="Slide through the forecast window and watch risk evolve along your trip corridor."
        />
      </div>
    </section>
  );
}

function FeatureCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-xl border border-brand-800/50 bg-brand-900/40 p-6">
      <h3 className="text-lg font-semibold text-brand-200">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-brand-400">
        {description}
      </p>
    </div>
  );
}
