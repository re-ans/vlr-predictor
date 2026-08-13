"use client";

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
        className={`${cls} hover:underline`}
      >
        {name ?? "TBD"}
      </a>
    );
  }
  return <p className={cls}>{name ?? "TBD"}</p>;
}

export default function MatchCard({ match }: { match: MatchOut }) {
  const isFinished = match.status === "finished";
  const isScheduled = match.status === "scheduled";
  const cat = match.event_category ?? "";

  const card = (
    <div className="border border-border rounded-lg bg-card hover:bg-card-hover transition-colors p-4 space-y-3">
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

  if (match.vlr_url) {
    return (
      <a
        href={match.vlr_url}
        target="_blank"
        rel="noopener noreferrer"
        className="block"
      >
        {card}
      </a>
    );
  }

  return card;
}
