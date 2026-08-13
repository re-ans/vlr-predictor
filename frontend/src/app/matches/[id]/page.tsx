"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getMatch, type MatchOut } from "@/lib/api";
import ProbBar from "@/components/ProbBar";

const CATEGORY_LABELS: Record<string, string> = {
  "vct-intl": "VCT International",
  vct: "VCT Leagues",
  gc: "Game Changers",
  challengers: "Challengers",
  tier3: "Tier 3",
};

const CATEGORY_COLORS: Record<string, string> = {
  "vct-intl": "bg-yellow-500/10 text-yellow-400",
  vct: "bg-blue-500/10 text-blue-400",
  gc: "bg-pink-500/10 text-pink-400",
  challengers: "bg-emerald-500/10 text-emerald-400",
  tier3: "bg-zinc-500/10 text-zinc-400",
};

// Human-readable labels for model features
const FEATURE_EXPLAIN: Record<
  string,
  { label: string; format: (v: number) => string; description: string }
> = {
  elo_a: {
    label: "Elo Rating",
    format: (v) => v.toFixed(0),
    description: "Current strength rating based on match history",
  },
  elo_b: {
    label: "Elo Rating",
    format: (v) => v.toFixed(0),
    description: "Current strength rating based on match history",
  },
  elo_diff: {
    label: "Elo Difference",
    format: (v) => (v > 0 ? "+" : "") + v.toFixed(0),
    description: "Positive = Team A is stronger by Elo",
  },
  elo_expected_a: {
    label: "Elo Win Expectancy",
    format: (v) => (v * 100).toFixed(1) + "%",
    description: "Based purely on Elo rating gap",
  },
  elo_expected_b: {
    label: "Elo Win Expectancy",
    format: (v) => (v * 100).toFixed(1) + "%",
    description: "Based purely on Elo rating gap",
  },
  form_a_3: {
    label: "Last 3 Win Rate",
    format: (v) => (v * 100).toFixed(0) + "%",
    description: "Recent form over last 3 matches",
  },
  form_b_3: {
    label: "Last 3 Win Rate",
    format: (v) => (v * 100).toFixed(0) + "%",
    description: "Recent form over last 3 matches",
  },
  form_a_5: {
    label: "Last 5 Win Rate",
    format: (v) => (v * 100).toFixed(0) + "%",
    description: "Recent form over last 5 matches",
  },
  form_b_5: {
    label: "Last 5 Win Rate",
    format: (v) => (v * 100).toFixed(0) + "%",
    description: "Recent form over last 5 matches",
  },
  form_a_10: {
    label: "Last 10 Win Rate",
    format: (v) => (v * 100).toFixed(0) + "%",
    description: "Medium-term form over last 10 matches",
  },
  form_b_10: {
    label: "Last 10 Win Rate",
    format: (v) => (v * 100).toFixed(0) + "%",
    description: "Medium-term form over last 10 matches",
  },
  form_a_20: {
    label: "Last 20 Win Rate",
    format: (v) => (v * 100).toFixed(0) + "%",
    description: "Long-term form over last 20 matches",
  },
  form_b_20: {
    label: "Last 20 Win Rate",
    format: (v) => (v * 100).toFixed(0) + "%",
    description: "Long-term form over last 20 matches",
  },
  h2h_a_wins: {
    label: "H2H Wins",
    format: (v) => v.toString(),
    description: "Head-to-head victories",
  },
  h2h_b_wins: {
    label: "H2H Wins",
    format: (v) => v.toString(),
    description: "Head-to-head victories",
  },
  h2h_total: {
    label: "H2H Matches Played",
    format: (v) => v.toString(),
    description: "Total head-to-head encounters",
  },
  days_since_last_a: {
    label: "Days Since Last Match",
    format: (v) => v.toFixed(1),
    description: "Lower = more active / match-fit",
  },
  days_since_last_b: {
    label: "Days Since Last Match",
    format: (v) => v.toFixed(1),
    description: "Lower = more active / match-fit",
  },
  score_diff_avg_a: {
    label: "Avg Map Diff (20)",
    format: (v) => (v > 0 ? "+" : "") + v.toFixed(2),
    description: "Average map score differential over last 20 matches",
  },
  score_diff_avg_b: {
    label: "Avg Map Diff (20)",
    format: (v) => (v > 0 ? "+" : "") + v.toFixed(2),
    description: "Average map score differential over last 20 matches",
  },
  best_of: {
    label: "Format",
    format: (v) => `Bo${v}`,
    description: "Best-of series format",
  },
  tier_encoded: {
    label: "Event Tier",
    format: (v) => v.toString(),
    description: "Event importance (higher = more prestigious)",
  },
};

function ExternalLinkIcon() {
  return (
    <svg
      className="w-3.5 h-3.5 inline-block ml-1"
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
  );
}

function formatDate(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-US", {
    weekday: "short",
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Grouped comparison rows for the feature table
const COMPARISON_ROWS = [
  { label: "Elo Rating", a: "elo_a", b: "elo_b" },
  { label: "Elo Win Expectancy", a: "elo_expected_a", b: "elo_expected_b" },
  { label: "Last 3 Form", a: "form_a_3", b: "form_b_3" },
  { label: "Last 5 Form", a: "form_a_5", b: "form_b_5" },
  { label: "Last 10 Form", a: "form_a_10", b: "form_b_10" },
  { label: "Last 20 Form", a: "form_a_20", b: "form_b_20" },
  { label: "H2H Wins", a: "h2h_a_wins", b: "h2h_b_wins" },
  { label: "Days Since Match", a: "days_since_last_a", b: "days_since_last_b" },
  { label: "Avg Map Diff", a: "score_diff_avg_a", b: "score_diff_avg_b" },
];

function FeatureComparison({
  features,
  teamAName,
  teamBName,
}: {
  features: Record<string, number>;
  teamAName: string;
  teamBName: string;
}) {
  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <table className="w-full text-sm table-fixed">
        <colgroup>
          <col className="w-[30%]" />
          <col className="w-[40%]" />
          <col className="w-[30%]" />
        </colgroup>
        <thead>
          <tr className="bg-card border-b border-border text-xs text-muted uppercase tracking-wide">
            <th className="py-2.5 px-4 text-left">{teamAName}</th>
            <th className="py-2.5 px-4 text-center">Stat</th>
            <th className="py-2.5 px-4 text-right">{teamBName}</th>
          </tr>
        </thead>
        <tbody>
          {COMPARISON_ROWS.map((row) => {
            const valA = features[row.a];
            const valB = features[row.b];
            if (valA === undefined || valB === undefined) return null;
            const fmtA = FEATURE_EXPLAIN[row.a]?.format(valA) ?? valA.toFixed(2);
            const fmtB = FEATURE_EXPLAIN[row.b]?.format(valB) ?? valB.toFixed(2);

            // Determine which side is "better" for color hints
            let aWins = false;
            let bWins = false;
            if (row.a.includes("days_since")) {
              // lower is better for activity
              aWins = valA < valB;
              bWins = valB < valA;
            } else {
              aWins = valA > valB;
              bWins = valB > valA;
            }

            return (
              <tr
                key={row.label}
                className="border-b border-border/50 hover:bg-card-hover transition-colors"
              >
                <td
                  className={`py-2.5 px-4 font-mono text-left ${
                    aWins ? "text-win" : "text-foreground/70"
                  }`}
                >
                  {fmtA}
                </td>
                <td className="py-2.5 px-4 text-center text-muted text-xs">
                  {row.label}
                </td>
                <td
                  className={`py-2.5 px-4 font-mono text-right ${
                    bWins ? "text-win" : "text-foreground/70"
                  }`}
                >
                  {fmtB}
                </td>
              </tr>
            );
          })}
          {/* Shared features */}
          {features.h2h_total !== undefined && (
            <tr className="border-b border-border/50">
              <td colSpan={3} className="py-2.5 px-4 text-center text-muted text-xs">
                {features.h2h_total} head-to-head matches played
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function MatchDetailPage() {
  const params = useParams<{ id: string }>();
  const [match, setMatch] = useState<MatchOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!params.id) return;
    setLoading(true);
    getMatch(Number(params.id))
      .then(setMatch)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !match) {
    return (
      <div className="space-y-4">
        <Link
          href="/"
          className="text-sm text-muted hover:text-foreground transition-colors"
        >
          &larr; Back
        </Link>
        <div className="border border-loss/30 bg-loss/5 rounded-lg p-4 text-loss text-sm">
          {error ?? "Match not found"}
        </div>
      </div>
    );
  }

  const isFinished = match.status === "finished";
  const cat = match.event_category ?? "";
  const pred = match.prediction;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Back link */}
      <Link
        href={isFinished ? "/matches" : "/"}
        className="text-sm text-muted hover:text-foreground transition-colors inline-flex items-center gap-1"
      >
        &larr; {isFinished ? "Results" : "Upcoming"}
      </Link>

      {/* Event header */}
      <div className="flex items-center gap-3 text-sm">
        {cat && (
          <span
            className={`px-2 py-1 rounded font-semibold text-xs ${
              CATEGORY_COLORS[cat] ?? ""
            }`}
          >
            {CATEGORY_LABELS[cat] ?? cat}
          </span>
        )}
        <span className="text-muted">{match.event_name}</span>
        {match.best_of && (
          <span className="px-2 py-0.5 rounded bg-border text-foreground/70 text-xs">
            Bo{match.best_of}
          </span>
        )}
        <span
          className={`px-2 py-0.5 rounded text-xs font-medium ${
            isFinished
              ? "bg-win/10 text-win"
              : "bg-accent/10 text-accent"
          }`}
        >
          {match.status}
        </span>
      </div>

      {/* Match date */}
      <p className="text-muted text-sm">{formatDate(match.match_date)}</p>

      {/* Teams hero */}
      <div className="border border-border rounded-xl bg-card p-6">
        <div className="flex items-center justify-between gap-6">
          {/* Team A */}
          <div className="flex-1 text-center space-y-3">
            {match.team_a_image && (
              <img
                src={match.team_a_image}
                alt={match.team_a_name ?? ""}
                className="w-16 h-16 object-contain mx-auto"
              />
            )}
            <div>
              {match.team_a_vlr_url ? (
                <a
                  href={match.team_a_vlr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-bold text-lg hover:text-accent hover:underline"
                >
                  {match.team_a_name}
                  <ExternalLinkIcon />
                </a>
              ) : (
                <p className="font-bold text-lg">{match.team_a_name ?? "TBD"}</p>
              )}
            </div>
            {isFinished && (
              <p
                className={`text-4xl font-bold font-mono ${
                  match.winner_id === match.team_a_id
                    ? "text-win"
                    : "text-foreground/30"
                }`}
              >
                {match.score_a}
              </p>
            )}
          </div>

          {/* VS */}
          <div className="text-muted font-bold text-xl shrink-0">vs</div>

          {/* Team B */}
          <div className="flex-1 text-center space-y-3">
            {match.team_b_image && (
              <img
                src={match.team_b_image}
                alt={match.team_b_name ?? ""}
                className="w-16 h-16 object-contain mx-auto"
              />
            )}
            <div>
              {match.team_b_vlr_url ? (
                <a
                  href={match.team_b_vlr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-bold text-lg hover:text-accent hover:underline"
                >
                  {match.team_b_name}
                  <ExternalLinkIcon />
                </a>
              ) : (
                <p className="font-bold text-lg">{match.team_b_name ?? "TBD"}</p>
              )}
            </div>
            {isFinished && (
              <p
                className={`text-4xl font-bold font-mono ${
                  match.winner_id === match.team_b_id
                    ? "text-win"
                    : "text-foreground/30"
                }`}
              >
                {match.score_b}
              </p>
            )}
          </div>
        </div>

        {/* Winner banner for finished matches */}
        {isFinished && match.winner_name && (
          <div className="mt-4 pt-4 border-t border-border text-center">
            <p className="text-xs text-muted uppercase tracking-wide">Winner</p>
            <p className="text-lg font-bold text-win">{match.winner_name}</p>
          </div>
        )}
      </div>

      {/* Prediction section */}
      {pred && (
        <div className="space-y-4">
          <h2 className="text-lg font-bold">Prediction</h2>

          <div className="border border-border rounded-xl bg-card p-6 space-y-5">
            <ProbBar
              probA={pred.team_a_win_prob}
              probB={pred.team_b_win_prob}
              nameA={pred.team_a_name}
              nameB={pred.team_b_name}
            />
            <div className="text-center">
              <p className="text-xs text-muted uppercase tracking-wide">
                Predicted Winner
              </p>
              <p className="text-xl font-bold text-accent mt-1">
                {pred.predicted_winner}
              </p>
              <p className="text-sm text-muted mt-1">
                {(pred.confidence * 100).toFixed(1)}% confidence
              </p>
            </div>
          </div>

          {/* Feature comparison */}
          {pred.features && Object.keys(pred.features).length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-muted uppercase tracking-wide">
                Why these odds?
              </h3>
              <FeatureComparison
                features={pred.features}
                teamAName={pred.team_a_name}
                teamBName={pred.team_b_name}
              />
              <p className="text-xs text-muted">
                The model uses Elo ratings, recent form, head-to-head record,
                activity level, and map score differentials to estimate win
                probability.
              </p>
            </div>
          )}
        </div>
      )}

      {/* External links */}
      {match.vlr_url && (
        <div className="pt-2">
          <a
            href={match.vlr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-accent transition-colors"
          >
            View on vlr.gg
            <ExternalLinkIcon />
          </a>
        </div>
      )}
    </div>
  );
}
