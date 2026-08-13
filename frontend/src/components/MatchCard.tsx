"use client";

import { useRouter } from "next/navigation";
import type { MatchOut } from "@/lib/api";
import ProbBar from "./ProbBar";

function formatDate(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const CATEGORY_COLORS: Record<string, string> = {
  "vct-intl": "bg-yellow-500/10 text-yellow-400",
  vct: "bg-blue-500/10 text-blue-400",
  gc: "bg-pink-500/10 text-pink-400",
  challengers: "bg-emerald-500/10 text-emerald-400",
  tier3: "bg-zinc-500/10 text-zinc-400",
};

const CATEGORY_SHORT: Record<string, string> = {
  "vct-intl": "INTL",
  vct: "VCT",
  gc: "GC",
  challengers: "T2",
  tier3: "T3",
};

function TeamName({
  name,
  vlrUrl,
  isWinner,
  align,
}: {
  name: string | null;
  vlrUrl: string | null;
  isWinner: boolean;
  align: "left" | "right";
}) {
  const cls = `font-semibold truncate ${isWinner ? "text-win" : ""} ${
    align === "right" ? "text-right" : "text-left"
  }`;
  if (vlrUrl) {
    return (
      <a
        href={vlrUrl}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
        className={`${cls} hover:underline`}
      >
        {name ?? "TBD"}
      </a>
    );
  }
  return <p className={cls}>{name ?? "TBD"}</p>;
}

export default function MatchCard({ match }: { match: MatchOut }) {
  const router = useRouter();
  const isFinished = match.status === "finished";
  const isScheduled = match.status === "scheduled";
  const cat = match.event_category ?? "";

  return (
    <div
      onClick={() => router.push(`/matches/${match.id}`)}
      className="border border-border rounded-lg bg-card hover:bg-card-hover transition-colors p-4 space-y-3 cursor-pointer"
    >
      {/* Header */}
      <div className="flex items-center justify-between text-xs text-muted gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {cat && (
            <span
              className={`shrink-0 px-1.5 py-0.5 rounded font-semibold ${
                CATEGORY_COLORS[cat] ?? ""
              }`}
            >
              {CATEGORY_SHORT[cat] ?? cat}
            </span>
          )}
          <span className="truncate">{match.event_name ?? ""}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {match.vlr_url && (
            <a
              href={match.vlr_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-muted hover:text-accent transition-colors"
              title="View on vlr.gg"
            >
              <svg
                className="w-3.5 h-3.5"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-4.5-6H21m0 0v7.5m0-7.5l-9 9"
                />
              </svg>
            </a>
          )}
          {match.best_of && (
            <span className="px-1.5 py-0.5 rounded bg-border text-foreground/70">
              Bo{match.best_of}
            </span>
          )}
          <span
            className={`px-1.5 py-0.5 rounded font-medium ${
              isFinished
                ? "bg-win/10 text-win"
                : isScheduled
                ? "bg-accent/10 text-accent"
                : "bg-border text-muted"
            }`}
          >
            {match.status}
          </span>
        </div>
      </div>

      {/* Teams */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1">
          <TeamName
            name={match.team_a_name}
            vlrUrl={match.team_a_vlr_url}
            isWinner={isFinished && match.winner_id === match.team_a_id}
            align="left"
          />
        </div>
        <div className="text-center shrink-0">
          {isFinished ? (
            <span className="font-mono font-bold text-lg">
              {match.score_a} &ndash; {match.score_b}
            </span>
          ) : (
            <span className="text-xs text-muted">
              {formatDate(match.match_date)}
            </span>
          )}
        </div>
        <div className="flex-1">
          <TeamName
            name={match.team_b_name}
            vlrUrl={match.team_b_vlr_url}
            isWinner={isFinished && match.winner_id === match.team_b_id}
            align="right"
          />
        </div>
      </div>

      {/* Prediction bar */}
      {match.prediction && (
        <ProbBar
          probA={match.prediction.team_a_win_prob}
          probB={match.prediction.team_b_win_prob}
          nameA={match.prediction.team_a_name}
          nameB={match.prediction.team_b_name}
        />
      )}
    </div>
  );
}
