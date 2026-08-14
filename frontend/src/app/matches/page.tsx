"use client";

import { useEffect, useRef, useState } from "react";
import { getMatches, refreshMatches, type MatchListResponse } from "@/lib/api";
import MatchCard from "@/components/MatchCard";
import CategoryFilter from "@/components/CategoryFilter";
import RegionFilter from "@/components/RegionFilter";

export default function MatchesPage() {
  const [data, setData] = useState<MatchListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState("");
  const [region, setRegion] = useState("");
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const didSync = useRef(false);

  // Sync results from PandaScore once on mount
  useEffect(() => {
    if (!didSync.current) {
      didSync.current = true;
      setSyncing(true);
      refreshMatches()
        .catch(() => {})
        .finally(() => setSyncing(false));
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    const delay = syncing ? 1500 : 0;
    const timer = setTimeout(() => {
      getMatches(page, 20, "finished", category || undefined, region || undefined)
        .then(setData)
        .finally(() => setLoading(false));
    }, delay);
    return () => clearTimeout(timer);
  }, [page, category, region, syncing]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [category, region]);

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Match Results</h1>
          <p className="text-muted text-sm mt-1">
            {data ? `${data.total} finished matches` : "Loading..."}
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

      {data && !loading && (
        <>
          {data.matches.length === 0 ? (
            <div className="text-center py-20 text-muted">
              No matches found for this filter.
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {data.matches.map((m) => (
                <MatchCard key={m.id} match={m} />
              ))}
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 rounded border border-border text-sm disabled:opacity-30 hover:bg-card-hover transition-colors"
              >
                Prev
              </button>
              <span className="text-sm text-muted px-3">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 rounded border border-border text-sm disabled:opacity-30 hover:bg-card-hover transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
