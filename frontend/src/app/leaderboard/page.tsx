"use client";

import { useEffect, useState } from "react";
import { getLeaderboard, type LeaderboardResponse } from "@/lib/api";
import CategoryFilter from "@/components/CategoryFilter";
import RegionFilter from "@/components/RegionFilter";

export default function LeaderboardPage() {
  const [data, setData] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("");
  const [region, setRegion] = useState("");

  useEffect(() => {
    setLoading(true);
    getLeaderboard(50, category || undefined, region || undefined)
      .then(setData)
      .finally(() => setLoading(false));
  }, [category, region]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Elo Leaderboard</h1>
        <p className="text-muted text-sm mt-1">
          Team rankings based on match history Elo ratings
        </p>
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
        <div className="border border-border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-card border-b border-border text-muted text-xs uppercase tracking-wide">
                <th className="py-3 px-4 text-left w-12">#</th>
                <th className="py-3 px-4 text-left">Team</th>
                <th className="py-3 px-4 text-right">Elo</th>
                <th className="py-3 px-4 text-right">W</th>
                <th className="py-3 px-4 text-right">L</th>
                <th className="py-3 px-4 text-right">Win%</th>
              </tr>
            </thead>
            <tbody>
              {data.entries.map((e) => (
                <tr
                  key={e.team_id}
                  className="border-b border-border/50 hover:bg-card-hover transition-colors"
                >
                  <td className="py-3 px-4 text-muted font-mono">
                    {e.rank}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      {e.image_url && (
                        <img
                          src={e.image_url}
                          alt={e.team_name}
                          className="w-6 h-6 object-contain rounded"
                          loading="lazy"
                        />
                      )}
                      <div>
                        {e.vlr_url ? (
                          <a
                            href={e.vlr_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium hover:text-accent hover:underline"
                          >
                            {e.team_name}
                          </a>
                        ) : (
                          <p className="font-medium">{e.team_name}</p>
                        )}
                        <div className="flex gap-2 text-xs text-muted">
                          {e.acronym && <span>{e.acronym}</span>}
                          {e.region && (
                            <span className="text-foreground/40">
                              {e.region}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-right font-mono font-semibold text-accent">
                    {e.elo_rating.toFixed(0)}
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-win">
                    {e.win_count}
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-loss">
                    {e.loss_count}
                  </td>
                  <td className="py-3 px-4 text-right font-mono">
                    {(e.win_rate * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
