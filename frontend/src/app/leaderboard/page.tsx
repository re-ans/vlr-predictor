"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getLeaderboard,
  addFavorite,
  removeFavorite,
  listFavorites,
  type LeaderboardResponse,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import CategoryFilter from "@/components/CategoryFilter";
import RegionFilter from "@/components/RegionFilter";

export default function LeaderboardPage() {
  const router = useRouter();
  const { token } = useAuth();
  const [data, setData] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("");
  const [region, setRegion] = useState("");
  const [favIds, setFavIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    setLoading(true);
    getLeaderboard(50, category || undefined, region || undefined)
      .then(setData)
      .finally(() => setLoading(false));
  }, [category, region]);

  useEffect(() => {
    if (token) {
      listFavorites(token)
        .then((r) => setFavIds(new Set(r.favorites.map((f) => f.team_id))))
        .catch(() => {});
    }
  }, [token]);

  async function handleToggleFav(teamId: number) {
    if (!token) {
      router.push("/login");
      return;
    }
    if (favIds.has(teamId)) {
      await removeFavorite(token, teamId);
      setFavIds((prev) => {
        const next = new Set(prev);
        next.delete(teamId);
        return next;
      });
    } else {
      await addFavorite(token, teamId);
      setFavIds((prev) => new Set(prev).add(teamId));
    }
  }

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
                <th className="py-3 px-2 w-8" />
              </tr>
            </thead>
            <tbody>
              {data.entries.map((e) => {
                const faved = favIds.has(e.team_id);
                return (
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
                    <td className="py-3 px-2">
                      <button
                        onClick={() => handleToggleFav(e.team_id)}
                        className={`transition-colors ${
                          faved ? "text-accent" : "text-muted hover:text-accent"
                        }`}
                        title={faved ? "Remove favorite" : "Add favorite"}
                      >
                        <svg
                          className="w-4 h-4"
                          fill={faved ? "currentColor" : "none"}
                          stroke="currentColor"
                          strokeWidth={2}
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z"
                          />
                        </svg>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
