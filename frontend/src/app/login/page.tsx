"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { login, register } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { setAuth } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = isRegister
        ? await register(email, password, displayName || undefined)
        : await login(email, password);
      setAuth(res.token, res.user);
      router.push("/profile");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-md mx-auto mt-16">
      <h1 className="text-2xl font-bold mb-6">
        {isRegister ? "Create Account" : "Sign In"}
      </h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        {isRegister && (
          <div>
            <label className="block text-sm text-muted mb-1">Display Name</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
              placeholder="Optional"
            />
          </div>
        )}
        <div>
          <label className="block text-sm text-muted mb-1">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
            placeholder="you@example.com"
          />
        </div>
        <div>
          <label className="block text-sm text-muted mb-1">Password</label>
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
            placeholder="At least 6 characters"
          />
        </div>

        {error && (
          <div className="text-loss text-sm border border-loss/30 bg-loss/5 rounded-md p-3">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50 transition-colors"
        >
          {loading ? "..." : isRegister ? "Register" : "Sign In"}
        </button>
      </form>

      <p className="text-sm text-muted mt-4 text-center">
        {isRegister ? "Already have an account?" : "Don't have an account?"}{" "}
        <button
          onClick={() => {
            setIsRegister(!isRegister);
            setError(null);
          }}
          className="text-accent hover:underline"
        >
          {isRegister ? "Sign in" : "Register"}
        </button>
      </p>
    </div>
  );
}
