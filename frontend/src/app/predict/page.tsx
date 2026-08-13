"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getTeams, predict, type Prediction, type TeamOut } from "@/lib/api";
import ProbBar from "@/components/ProbBar";

function TeamSearch({
  label,
  selected,
  onSelect,
}: {
  label: string;
  selected: TeamOut | null;
  onSelect: (t: TeamOut) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<TeamOut[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined);

  const search = useCallback((q: string) => {
    if (q.length < 2) {
      setResults([]);
      return;
    }
    getTeams(q, 1, 10).then((r) => {
      setResults(r.teams);
      setOpen(true);
    });
  }, []);

  useEffect(() => {
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => search(query), 250);
    return () => clearTimeout(debounce.current);
  }, [query, search]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div ref={ref} className="relative flex-1">
      <label className="text-xs text-muted font-medium uppercase tracking-wide">
        {label}
      </label>
      {selected ? (
        <div className="mt-1 flex items-center justify-between border border-border rounded-lg bg-card p-3">
          <div>
            <p className="font-semibold">{selected.name}</p>
            <p className="text-xs text-muted">
              {selected.acronym} &middot; Elo {selected.current_rating.toFixed(0)}
            </p>
          </div>
          <button
            onClick={() => {
              onSelect(null as unknown as TeamOut);
              setQuery("");
            }}
            className="text-muted hover:text-foreground text-sm"
          >
            Change
          </button>
        </div>
      ) : (
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search team..."
          className="mt-1 w-full border border-border rounded-lg bg-card p-3 text-sm focus:outline-none focus:ring-1 focus:ring-accent placeholder:text-muted"
        />
      )}
      {open && results.length > 0 && !selected && (
        <ul className="absolute z-10 mt-1 w-full border border-border rounded-lg bg-card shadow-lg max-h-60 overflow-y-auto">
          {results.map((t) => (
            <li key={t.id}>
              <button
                onClick={() => {
                  onSelect(t);
                  setOpen(false);
                }}
                className="w-full text-left px-4 py-2 hover:bg-card-hover transition-colors text-sm"
              >
                <span className="font-medium">{t.name}</span>
                <span className="text-muted ml-2">
                  ({t.acronym ?? "?"}) &middot; Elo{" "}
                  {t.current_rating.toFixed(0)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function PredictPage() {
  const [teamA, setTeamA] = useState<TeamOut | null>(null);
  const [teamB, setTeamB] = useState<TeamOut | null>(null);
  const [bestOf, setBestOf] = useState(3);
  const [result, setResult] = useState<Prediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handlePredict() {
    if (!teamA || !teamB) return;
    setLoading(true);
    setError(null);
    try {
      const pred = await predict(teamA.id, teamB.id, bestOf);
      setResult(pred);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Prediction failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold">Match Predictor</h1>
        <p className="text-muted text-sm mt-1">
          Select two teams to get a win probability prediction
        </p>
      </div>

      <div className="border border-border rounded-xl bg-card p-6 space-y-5">
        <div className="flex gap-4 items-end">
          <TeamSearch label="Team A" selected={teamA} onSelect={setTeamA} />
          <span className="text-muted font-bold pb-3">vs</span>
          <TeamSearch label="Team B" selected={teamB} onSelect={setTeamB} />
        </div>

        <div className="flex items-center gap-4">
          <label className="text-xs text-muted font-medium uppercase tracking-wide">
            Format
          </label>
          <div className="flex gap-2">
            {[1, 3, 5].map((n) => (
              <button
                key={n}
                onClick={() => setBestOf(n)}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                  bestOf === n
                    ? "bg-accent text-white"
                    : "bg-border text-muted hover:text-foreground"
                }`}
              >
                Bo{n}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={handlePredict}
          disabled={!teamA || !teamB || loading || teamA?.id === teamB?.id}
          className="w-full py-3 rounded-lg font-semibold text-sm bg-accent hover:bg-accent-light disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors"
        >
          {loading ? "Predicting..." : "Get Prediction"}
        </button>
      </div>

      {error && (
        <div className="border border-loss/30 bg-loss/5 rounded-lg p-4 text-loss text-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="border border-border rounded-xl bg-card p-6 space-y-5">
          <h2 className="text-lg font-bold text-center">Prediction</h2>
          <ProbBar
            probA={result.team_a_win_prob}
            probB={result.team_b_win_prob}
            nameA={result.team_a_name}
            nameB={result.team_b_name}
          />
          <div className="text-center">
            <p className="text-sm text-muted">Predicted winner</p>
            <p className="text-xl font-bold text-accent mt-1">
              {result.predicted_winner}
            </p>
            <p className="text-xs text-muted mt-1">
              {(result.confidence * 100).toFixed(1)}% confidence
            </p>
          </div>

          {/* Feature breakdown */}
          <details className="text-sm">
            <summary className="text-muted cursor-pointer hover:text-foreground">
              Feature details
            </summary>
            <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs font-mono">
              {Object.entries(result.features).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-muted">{k}</span>
                  <span>{typeof v === "number" ? v.toFixed(3) : v}</span>
                </div>
              ))}
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
