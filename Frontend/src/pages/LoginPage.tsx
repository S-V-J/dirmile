import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import { useAuth } from "../auth/useAuth";

/**
 * Login form. Accepts email or username as the identifier.
 */
export function LoginPage() {
  const { login, isLoading, error, clearError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from =
    (location.state as { from?: { pathname?: string } })?.from?.pathname ??
    "/app";

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    clearError();

    if (!identifier.trim()) {
      setLocalError("Please enter your email or username.");
      return;
    }
    if (!password) {
      setLocalError("Please enter your password.");
      return;
    }

    try {
      await login({ identifier: identifier.trim(), password });
      navigate(from, { replace: true });
    } catch {
      // Error is already set in auth context.
    }
  };

  const displayError = localError ?? error;

  return (
    <section className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4 py-12">
      <h1 className="text-2xl font-bold text-white">Log in to Dirmile</h1>
      <p className="mt-2 text-sm text-brand-400">
        Don&apos;t have an account?{" "}
        <Link to="/register" className="text-brand-300 underline hover:text-brand-200">
          Register
        </Link>
      </p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-5" noValidate>
        {displayError && (
          <div
            role="alert"
            className="rounded-md border border-red-800 bg-red-950/60 px-4 py-3 text-sm text-red-300"
          >
            {displayError}
          </div>
        )}

        <div>
          <label htmlFor="identifier" className="block text-sm font-medium text-brand-200">
            Email or Username
          </label>
          <input
            id="identifier"
            type="text"
            autoComplete="username"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            className="mt-1 block w-full rounded-md border border-brand-700 bg-brand-900 px-3 py-2 text-white placeholder-brand-500 focus:border-brand-400 focus:outline-none focus:ring-1 focus:ring-brand-400"
            placeholder="driver@example.com"
          />
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium text-brand-200">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 block w-full rounded-md border border-brand-700 bg-brand-900 px-3 py-2 text-white placeholder-brand-500 focus:border-brand-400 focus:outline-none focus:ring-1 focus:ring-brand-400"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full rounded-md bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow hover:bg-brand-400 disabled:opacity-50 transition-colors"
        >
          {isLoading ? "Logging in…" : "Log in"}
        </button>
      </form>
    </section>
  );
}
