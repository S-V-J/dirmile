import { useContext } from "react";

import { AuthContext, type AuthContextValue } from "./AuthContext";

/**
 * Convenience hook to consume the AuthContext.
 * Throws if used outside <AuthProvider>.
 */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used within an <AuthProvider>.");
  }
  return ctx;
}
