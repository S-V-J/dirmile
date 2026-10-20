import { useState } from "react";
import { useNavigate } from "react-router";

import { useAuth } from "../auth/useAuth";
import * as api from "../api/client";

/**
 * Account page (authenticated).
 * Shows profile summary, logout button, and delete-account flow.
 */
export function AccountPage() {
  const { user, logout, refreshUser } = useAuth();
  const navigate = useNavigate();

  const [showDelete, setShowDelete] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    setDeleteError(null);

    if (deleteConfirmation !== "DELETE") {
      setDeleteError('Type DELETE exactly to confirm.');
      return;
    }
    if (!deletePassword) {
      setDeleteError("Password is required.");
      return;
    }

    setIsDeleting(true);
    try {
      await api.deleteAccount(deletePassword, deleteConfirmation);
      await refreshUser();
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof api.ApiRequestError) {
        const detail = err.data;
        const msg =
          typeof detail.password === "string"
            ? detail.password
            : typeof detail.detail === "string"
              ? detail.detail
              : "Account deletion failed.";
        setDeleteError(msg);
      } else {
        setDeleteError("Account deletion failed.");
      }
    } finally {
      setIsDeleting(false);
    }
  };

  if (!user) {
    return (
      <section className="mx-auto max-w-2xl px-4 py-12">
        <p className="text-brand-400">Loading account…</p>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-2xl px-4 py-12">
      <h1 className="text-2xl font-bold text-white">Account</h1>

      {/* Profile summary */}
      <dl className="mt-8 grid gap-4 sm:grid-cols-2">
        <ProfileItem label="Name" value={user.name || "—"} />
        <ProfileItem label="Email" value={user.email} />
        <ProfileItem label="Username" value={user.username} />
        <ProfileItem label="Country Code" value={user.country_code || "—"} />
        <ProfileItem label="Phone" value={user.phone || "—"} />
        <ProfileItem
          label="Member since"
          value={new Date(user.date_joined).toLocaleDateString()}
        />
      </dl>

      {/* Actions */}
      <div className="mt-10 space-y-4">
        <button
          type="button"
          onClick={() => void logout()}
          className="rounded-md border border-brand-600 px-5 py-2.5 text-sm font-medium text-brand-300 hover:bg-brand-800 hover:text-white transition-colors"
        >
          Log out
        </button>

        {!showDelete ? (
          <button
            type="button"
            onClick={() => setShowDelete(true)}
            className="ml-4 rounded-md border border-red-800 px-5 py-2.5 text-sm font-medium text-red-400 hover:bg-red-950/50 hover:text-red-300 transition-colors"
          >
            Delete account
          </button>
        ) : (
          <div className="mt-6 rounded-xl border border-red-800 bg-red-950/30 p-6">
            <h2 className="text-lg font-semibold text-red-300">
              Delete your account permanently?
            </h2>
            <p className="mt-2 text-sm text-red-400/80">
              This cannot be undone. All trip plans and data will be erased.
            </p>

            {deleteError && (
              <div
                role="alert"
                className="mt-4 rounded-md border border-red-700 bg-red-900/50 px-4 py-3 text-sm text-red-300"
              >
                {deleteError}
              </div>
            )}

            <div className="mt-4 space-y-3">
              <div>
                <label htmlFor="del-password" className="block text-sm font-medium text-red-300">
                  Your password
                </label>
                <input
                  id="del-password"
                  type="password"
                  value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-red-800 bg-red-950 px-3 py-2 text-white placeholder-red-600 focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
                  placeholder="••••••••"
                />
              </div>
              <div>
                <label htmlFor="del-confirm" className="block text-sm font-medium text-red-300">
                  Type <code className="font-mono text-red-200">DELETE</code> to confirm
                </label>
                <input
                  id="del-confirm"
                  type="text"
                  value={deleteConfirmation}
                  onChange={(e) => setDeleteConfirmation(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-red-800 bg-red-950 px-3 py-2 text-white placeholder-red-600 focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
                  placeholder="DELETE"
                />
              </div>
            </div>

            <div className="mt-5 flex gap-3">
              <button
                type="button"
                onClick={() => void handleDelete()}
                disabled={isDeleting}
                className="rounded-md bg-red-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-50 transition-colors"
              >
                {isDeleting ? "Deleting…" : "Permanently delete account"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowDelete(false);
                  setDeleteError(null);
                  setDeletePassword("");
                  setDeleteConfirmation("");
                }}
                className="rounded-md border border-brand-700 px-5 py-2.5 text-sm font-medium text-brand-300 hover:bg-brand-800 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function ProfileItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-brand-800/50 bg-brand-900/30 px-4 py-3">
      <dt className="text-xs font-medium uppercase tracking-wide text-brand-500">
        {label}
      </dt>
      <dd className="mt-1 text-sm text-brand-200">{value}</dd>
    </div>
  );
}
