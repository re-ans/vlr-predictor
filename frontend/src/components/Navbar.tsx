"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const links = [
  { href: "/", label: "Upcoming" },
  { href: "/predict", label: "Predict" },
  { href: "/matches", label: "Results" },
  { href: "/leaderboard", label: "Leaderboard" },
];

export default function Navbar() {
  const pathname = usePathname();
  const { user, loading } = useAuth();

  return (
    <nav className="border-b border-border bg-card/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 flex items-center h-14 gap-8">
        <Link href="/" className="font-bold text-lg tracking-tight">
          <span className="text-accent">VLR</span>
          <span className="text-foreground/70"> Predictor</span>
        </Link>
        <div className="flex gap-1 flex-1">
          {links.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  active
                    ? "bg-accent/10 text-accent"
                    : "text-muted hover:text-foreground hover:bg-card-hover"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
        {!loading && (
          <div className="flex items-center">
            {user ? (
              <Link
                href="/profile"
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  pathname === "/profile"
                    ? "bg-accent/10 text-accent"
                    : "text-muted hover:text-foreground hover:bg-card-hover"
                }`}
              >
                {user.display_name || user.email.split("@")[0]}
              </Link>
            ) : (
              <Link
                href="/login"
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  pathname === "/login"
                    ? "bg-accent/10 text-accent"
                    : "text-muted hover:text-foreground hover:bg-card-hover"
                }`}
              >
                Sign In
              </Link>
            )}
          </div>
        )}
      </div>
    </nav>
  );
}
