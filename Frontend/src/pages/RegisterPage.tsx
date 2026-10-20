import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import { useAuth } from "../auth/useAuth";

/**
 * Registration form.
 * Required: name, email, username, password, confirm password.
 * Optional: country code, phone, OTP preference.
 */
export function RegisterPage() {
  const { register, isLoading, error, clearError } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: "",
    email: "",
    username: "",
    password: "",
    confirm_password: "",
    country_code: "",
    phone: "",
    otp_enabled: false,
  });
  const [localError, setLocalError] = useState<string | null>(null);

  const update = (field: string, value: string | boolean) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    clearError();

    if (!form.name.trim()) {
      setLocalError("Name is required.");
      return;
    }
    if (!form.email.trim()) {
      setLocalError("Email is required.");
      return;
    }
    if (!form.username.trim()) {
      setLocalError("Username is required.");
      return;
    }
    if (form.password.length < 8) {
      setLocalError("Password must be at least 8 characters.");
      return;
    }
    if (form.password !== form.confirm_password) {
      setLocalError("Passwords do not match.");
      return;
    }

    try {
      await register({
        name: form.name.trim(),
        email: form.email.trim(),
        username: form.username.trim(),
        password: form.password,
        confirm_password: form.confirm_password,
        country_code: form.country_code.trim() || undefined,
        phone: form.phone.trim() || undefined,
        otp_enabled: form.otp_enabled,
      });
      navigate("/app", { replace: true });
    } catch {
      // Error is already set in auth context.
    }
  };

  const displayError = localError ?? error;

  const inputClass =
    "mt-1 block w-full rounded-md border border-brand-700 bg-brand-900 px-3 py-2 text-white placeholder-brand-500 focus:border-brand-400 focus:outline-none focus:ring-1 focus:ring-brand-400";
  const labelClass = "block text-sm font-medium text-brand-200";

  return (
    <section className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-4 py-12">
      <h1 className="text-2xl font-bold text-white">Create your Dirmile account</h1>
      <p className="mt-2 text-sm text-brand-400">
        Already have an account?{" "}
        <Link to="/login" className="text-brand-300 underline hover:text-brand-200">
          Log in
        </Link>
      </p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-4" noValidate>
        {displayError && (
          <div
            role="alert"
            className="rounded-md border border-red-800 bg-red-950/60 px-4 py-3 text-sm text-red-300"
          >
            {displayError}
          </div>
        )}

        <div>
          <label htmlFor="reg-name" className={labelClass}>Full Name *</label>
          <input id="reg-name" type="text" autoComplete="name" value={form.name}
            onChange={(e) => update("name", e.target.value)} className={inputClass}
            placeholder="Jane Driver" />
        </div>

        <div>
          <label htmlFor="reg-email" className={labelClass}>Email *</label>
          <input id="reg-email" type="email" autoComplete="email" value={form.email}
            onChange={(e) => update("email", e.target.value)} className={inputClass}
            placeholder="jane@example.com" />
        </div>

        <div>
          <label htmlFor="reg-username" className={labelClass}>Username *</label>
          <input id="reg-username" type="text" autoComplete="username" value={form.username}
            onChange={(e) => update("username", e.target.value)} className={inputClass}
            placeholder="janedriver" />
        </div>

        <div>
          <label htmlFor="reg-password" className={labelClass}>Password *</label>
          <input id="reg-password" type="password" autoComplete="new-password"
            value={form.password} onChange={(e) => update("password", e.target.value)}
            className={inputClass} placeholder="Min. 8 characters" />
        </div>

        <div>
          <label htmlFor="reg-confirm" className={labelClass}>Confirm Password *</label>
          <input id="reg-confirm" type="password" autoComplete="new-password"
            value={form.confirm_password}
            onChange={(e) => update("confirm_password", e.target.value)}
            className={inputClass} placeholder="Re-enter password" />
        </div>

        <div>
          <label htmlFor="reg-country" className={labelClass}>Country Code (optional)</label>
          <input id="reg-country" type="text" value={form.country_code}
            onChange={(e) => update("country_code", e.target.value)}
            className={inputClass} placeholder="US" maxLength={10} />
        </div>

        <div>
          <label htmlFor="reg-phone" className={labelClass}>Phone Number (optional)</label>
          <input id="reg-phone" type="tel" autoComplete="tel" value={form.phone}
            onChange={(e) => update("phone", e.target.value)}
            className={inputClass} placeholder="+15551234567" />
        </div>

        <label className="flex items-center gap-2 text-sm text-brand-300">
          <input
            type="checkbox"
            checked={form.otp_enabled}
            onChange={(e) => update("otp_enabled", e.target.checked)}
            className="h-4 w-4 rounded border-brand-600 bg-brand-900 text-brand-500 focus:ring-brand-400"
          />
          Enable OTP login (optional)
        </label>

        <button
          type="submit"
          disabled={isLoading}
          className="w-full rounded-md bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white shadow hover:bg-brand-400 disabled:opacity-50 transition-colors"
        >
          {isLoading ? "Creating account…" : "Create Account"}
        </button>
      </form>
    </section>
  );
}
