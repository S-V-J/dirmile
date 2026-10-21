import { Link, Outlet, useLocation } from "react-router";

import { useAuth } from "../auth/useAuth";
import { InstallBanner } from "./InstallBanner";

/**
 * Top-level layout shell.
 *
 * Unauthenticated navigation:
 *   Login/Register | About Us
 *
 * Authenticated navigation:
 *   Web App | Settings | Account | About Us
 */
export function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();

  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(path + "/");

  const linkClass = (path: string) =>
    `px-3 py-2 text-sm font-medium rounded-md transition-colors ${
      isActive(path)
        ? "bg-brand-800 text-white"
        : "text-brand-200 hover:bg-brand-800/50 hover:text-white"
    }`;

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100">
      {/* ── Top navigation ─────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-brand-800/40 bg-brand-950/90 backdrop-blur">
        <nav
          className="mx-auto flex max-w-7xl items-center justify-between px-4 py-2"
          aria-label="Main navigation"
        >
          <Link
            to="/"
            className="flex items-center gap-2 text-lg font-bold tracking-tight text-brand-300 hover:text-brand-200"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 32 32"
              className="h-6 w-6"
              aria-hidden="true"
            >
              <rect width="32" height="32" rx="6" fill="currentColor" opacity="0.15" />
              <path
                d="M8 22 L16 8 L24 22 Z"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinejoin="round"
              />
              <circle cx="16" cy="18" r="2.5" fill="currentColor" />
            </svg>
            Dirmile
          </Link>

          <div className="flex items-center gap-1">
            {user ? (
              <>
                <Link to="/app" className={linkClass("/app")}>
                  Web App
                </Link>
                <Link to="/settings" className={linkClass("/settings")}>
                  Settings
                </Link>
                <Link to="/account" className={linkClass("/account")}>
                  Account
                </Link>
                <Link to="/about" className={linkClass("/about")}>
                  About Us
                </Link>
                <button
                  type="button"
                  onClick={() => void logout()}
                  className="ml-2 rounded-md border border-brand-700 px-3 py-2 text-sm font-medium text-brand-300 hover:bg-brand-800 hover:text-white transition-colors"
                >
                  Log out
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className={linkClass("/login")}>
                  Login / Register
                </Link>
                <Link to="/about" className={linkClass("/about")}>
                  About Us
                </Link>
              </>
            )}
          </div>
        </nav>
      </header>

      {/* ── Main content ───────────────────────────────────────── */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* ── Footer ─────────────────────────────────────────────── */}
      <footer className="border-t border-brand-800/40 bg-brand-950 py-4 text-center text-xs text-brand-400">
        Dirmile · Weather-aware truck routing · MIT License
      </footer>

      <InstallBanner />
    </div>
  );
}
