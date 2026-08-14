"use client";

import { useEffect, useRef, useState } from "react";
import { getUpcoming, refreshMatches, type MatchListResponse } from "@/lib/api";
import MatchCard from "@/components/MatchCard";
import CategoryFilter from "@/components/CategoryFilter";
import RegionFilter from "@/components/RegionFilter";

export default function HomePage() {
  const [data, setData] = useState<MatchListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [category, setCategory] = useState("");
  const [region, setRegion] = useState("");
  const didSync = useRef(false);

  // Sync results from PandaScore once on mount, then fetch
  useEffect(() => {
    if (!didSync.current) {
      didSync.current = true;
      setSyncing(true);
      refreshMatches()
        .catch(() => {}) // best-effort
        .finally(() => setSyncing(false));
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    // Small delay on first load to let sync finish if it's quick
    const delay = syncing ? 1500 : 0;
    const timer = setTimeout(() => {
      getUpcoming(1, 50, category || undefined, region || undefined)
        .then(setData)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    }, delay);
    return () => clearTimeout(timer);
  }, [category, region, syncing]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Upcoming Matches</h1>
          <p className="text-muted text-sm mt-1">
            Live predictions for scheduled Valorant matches
          </p>
        </div>
        {syncing && (
          <div className="flex items-center gap-2 text-xs text-muted">
            <div className="h-3 w-3 border border-accent border-t-transparent rounded-full animate-spin" />
            Syncing results...
          </div>
        )}
      </div>

      <div className="space-y-3">
        <CategoryFilter value={category} onChange={setCategory} />
        <RegionFilter value={region} onChange={setRegion} />
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {error && (
        <div className="border border-loss/30 bg-loss/5 rounded-lg p-4 text-loss text-sm">
          {error}
        </div>
      )}

      {data && data.matches.length === 0 && !loading && (
        <div className="text-center py-20 text-muted">
          No upcoming matches found for this filter. Check back later!
        </div>
      )}

      {data && data.matches.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {data.matches.map((m) => (
            <MatchCard key={m.id} match={m} />
          ))}
        </div>
      )}
    </div>
  );
}
