"use client";

import { useEffect, useState } from "react";
import { getMatches, type MatchListResponse } from "@/lib/api";
import MatchCard from "@/components/MatchCard";
import CategoryFilter from "@/components/CategoryFilter";

export default function MatchesPage() {
  const [data, setData] = useState<MatchListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getMatches(page, 20, "finished", category || undefined)
      .then(setData)
      .finally(() => setLoading(false));
  }, [page, category]);

  // Reset page when category changes
  useEffect(() => {
    setPage(1);
  }, [category]);

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Match Results</h1>
        <p className="text-muted text-sm mt-1">
          {data ? `${data.total} finished matches` : "Loading..."}
        </p>
      </div>

      <CategoryFilter value={category} onChange={setCategory} />

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
