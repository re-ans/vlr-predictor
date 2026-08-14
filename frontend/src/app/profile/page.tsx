"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  listFavorites,
  listSavedMatches,
  listPredictions,
  listRosters,
  removeFavorite,
  unsaveMatch,
  deletePrediction,
  deleteRoster,
  createRoster,
  searchPlayers,
  getMatch,
  type FavoriteTeam,
  type SavedPrediction,
  type RosterOut,
  type MatchOut,
  type PlayerOut,
} from "@/lib/api";

type Tab = "favorites" | "matches" | "predictions" | "rosters";

export default function ProfilePage() {
  const { user, token, loading: authLoading, logout } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("favorites");

  useEffect(() => {
    if (!authLoading && !user) router.push("/login");
  }, [authLoading, user, router]);

  if (authLoading || !user || !token) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "favorites", label: "Favorite Teams" },
    { key: "matches", label: "Saved Matches" },
    { key: "predictions", label: "Predictions" },
    { key: "rosters", label: "Rosters" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            {user.display_name || user.email}
          </h1>
          <p className="text-muted text-sm">{user.email}</p>
        </div>
        <button
          onClick={() => {
            logout();
            router.push("/");
          }}
          className="px-3 py-1.5 rounded-md border border-border text-sm text-muted hover:text-foreground hover:bg-card-hover transition-colors"
        >
          Sign out
        </button>
      </div>

      <div className="flex gap-1 border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t.key
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "favorites" && <FavoritesTab token={token} />}
      {tab === "matches" && <MatchesTab token={token} />}
      {tab === "predictions" && <PredictionsTab token={token} />}
      {tab === "rosters" && <RostersTab token={token} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Favorites
// ---------------------------------------------------------------------------

function FavoritesTab({ token }: { token: string }) {
  const [items, setItems] = useState<FavoriteTeam[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listFavorites(token)
      .then((r) => setItems(r.favorites))
      .finally(() => setLoading(false));
  }, [token]);

  async function handleRemove(teamId: number) {
    await removeFavorite(token, teamId);
    setItems((prev) => prev.filter((f) => f.team_id !== teamId));
  }

  if (loading) return <Spinner />;
  if (!items.length)
    return <Empty text="No favorite teams yet. Star teams from the Leaderboard!" />;

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map((f) => (
        <div
          key={f.team_id}
          className="flex items-center justify-between border border-border rounded-lg bg-card p-3"
        >
          <div className="flex items-center gap-3 min-w-0">
            {f.image_url && (
              <img
                src={f.image_url}
                alt=""
                className="w-8 h-8 rounded object-contain"
              />
            )}
            <div className="min-w-0">
              <p className="font-semibold truncate">{f.name}</p>
              <p className="text-xs text-muted">Elo {f.rating.toFixed(0)}</p>
            </div>
          </div>
          <button
            onClick={() => handleRemove(f.team_id)}
            className="text-xs text-muted hover:text-loss transition-colors"
          >
            Remove
          </button>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Saved Matches
// ---------------------------------------------------------------------------

function MatchesTab({ token }: { token: string }) {
  const router = useRouter();
  const [matchIds, setMatchIds] = useState<number[]>([]);
  const [matches, setMatches] = useState<MatchOut[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listSavedMatches(token)
      .then(async (r) => {
        setMatchIds(r.match_ids);
        const loaded = await Promise.all(
          r.match_ids.slice(0, 20).map((id) => getMatch(id).catch(() => null))
        );
        setMatches(loaded.filter(Boolean) as MatchOut[]);
      })
      .finally(() => setLoading(false));
  }, [token]);

  async function handleRemove(matchId: number) {
    await unsaveMatch(token, matchId);
    setMatchIds((prev) => prev.filter((id) => id !== matchId));
    setMatches((prev) => prev.filter((m) => m.id !== matchId));
  }

  if (loading) return <Spinner />;
  if (!matchIds.length)
    return <Empty text="No saved matches yet. Bookmark matches from the Upcoming or Results page!" />;

  return (
    <div className="space-y-3">
      {matches.map((m) => (
        <div
          key={m.id}
          onClick={() => router.push(`/matches/${m.id}`)}
          className="flex items-center justify-between border border-border rounded-lg bg-card p-3 cursor-pointer hover:bg-card-hover transition-colors"
        >
          <div className="min-w-0">
            <p className="font-semibold text-sm">
              {m.team_a_name} vs {m.team_b_name}
            </p>
            <p className="text-xs text-muted">
              {m.event_name} &middot; {m.status}
              {m.status === "finished" && ` (${m.score_a}-${m.score_b})`}
            </p>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleRemove(m.id);
            }}
            className="text-xs text-muted hover:text-loss transition-colors shrink-0 ml-2"
          >
            Remove
          </button>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Predictions
// ---------------------------------------------------------------------------

function PredictionsTab({ token }: { token: string }) {
  const [items, setItems] = useState<SavedPrediction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listPredictions(token)
      .then((r) => setItems(r.predictions))
      .finally(() => setLoading(false));
  }, [token]);

  async function handleDelete(id: number) {
    await deletePrediction(token, id);
    setItems((prev) => prev.filter((p) => p.id !== id));
  }

  if (loading) return <Spinner />;
  if (!items.length)
    return <Empty text="No saved predictions yet. Save predictions from match detail pages!" />;

  return (
    <div className="space-y-3">
      {items.map((p) => {
        const pctA = (p.prob_a * 100).toFixed(0);
        const pctB = (p.prob_b * 100).toFixed(0);
        return (
          <div
            key={p.id}
            className="border border-border rounded-lg bg-card p-3 space-y-2"
          >
            <div className="flex items-center justify-between">
              <p className="font-semibold text-sm">
                {p.team_a_name} vs {p.team_b_name}
              </p>
              <button
                onClick={() => handleDelete(p.id)}
                className="text-xs text-muted hover:text-loss transition-colors"
              >
                Delete
              </button>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className={p.prob_a > p.prob_b ? "text-win" : "text-muted"}>
                {p.team_a_name} {pctA}%
              </span>
              <div className="flex-1 h-1.5 rounded bg-border overflow-hidden">
                <div
                  className="h-full bg-accent"
                  style={{ width: `${pctA}%` }}
                />
              </div>
              <span className={p.prob_b > p.prob_a ? "text-win" : "text-muted"}>
                {pctB}% {p.team_b_name}
              </span>
            </div>
            {p.created_at && (
              <p className="text-[10px] text-muted">
                Saved {new Date(p.created_at).toLocaleDateString()}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rosters
// ---------------------------------------------------------------------------

function RostersTab({ token }: { token: string }) {
  const [rosters, setRosters] = useState<RosterOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState<PlayerOut[]>([]);
  const [selected, setSelected] = useState<PlayerOut[]>([]);

  useEffect(() => {
    listRosters(token)
      .then((r) => setRosters(r.rosters))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    if (searchQ.length < 2) {
      setSearchResults([]);
      return;
    }
    const t = setTimeout(() => {
      searchPlayers(searchQ, 10).then(setSearchResults).catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [searchQ]);

  async function handleCreate() {
    if (!newName.trim()) return;
    const roster = await createRoster(
      token,
      newName.trim(),
      selected.map((p) => p.id)
    );
    setRosters((prev) => [roster, ...prev]);
    setNewName("");
    setSelected([]);
    setSearchQ("");
    setShowCreate(false);
  }

  async function handleDelete(id: number) {
    await deleteRoster(token, id);
    setRosters((prev) => prev.filter((r) => r.id !== id));
  }

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <button
        onClick={() => setShowCreate(!showCreate)}
        className="px-3 py-1.5 rounded-md bg-accent text-white text-sm font-medium hover:bg-accent/90 transition-colors"
      >
        {showCreate ? "Cancel" : "+ New Roster"}
      </button>

      {showCreate && (
        <div className="border border-border rounded-lg bg-card p-4 space-y-3">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Roster name"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <input
            type="text"
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="Search players..."
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
          />
          {searchResults.length > 0 && (
            <div className="border border-border rounded-md max-h-40 overflow-y-auto">
              {searchResults
                .filter((p) => !selected.some((s) => s.id === p.id))
                .map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setSelected((prev) => [...prev, p])}
                    className="w-full text-left px-3 py-1.5 text-sm hover:bg-card-hover transition-colors"
                  >
                    {p.name}
                    {p.team_name && (
                      <span className="text-muted ml-2">({p.team_name})</span>
                    )}
                  </button>
                ))}
            </div>
          )}
          {selected.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {selected.map((p) => (
                <span
                  key={p.id}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-accent/10 text-accent text-xs"
                >
                  {p.name}
                  <button
                    onClick={() =>
                      setSelected((prev) => prev.filter((s) => s.id !== p.id))
                    }
                    className="hover:text-loss"
                  >
                    x
                  </button>
                </span>
              ))}
            </div>
          )}
          <button
            onClick={handleCreate}
            disabled={!newName.trim()}
            className="px-3 py-1.5 rounded-md bg-accent text-white text-sm font-medium hover:bg-accent/90 disabled:opacity-50 transition-colors"
          >
            Save Roster
          </button>
        </div>
      )}

      {rosters.length === 0 && !showCreate && (
        <Empty text="No rosters yet. Create one to save your favorite player lineups!" />
      )}

      {rosters.map((r) => (
        <div
          key={r.id}
          className="border border-border rounded-lg bg-card p-3"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold text-sm">{r.name}</p>
              <p className="text-xs text-muted">
                {r.player_ids.length} player{r.player_ids.length !== 1 ? "s" : ""}
              </p>
            </div>
            <button
              onClick={() => handleDelete(r.id)}
              className="text-xs text-muted hover:text-loss transition-colors"
            >
              Delete
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="h-6 w-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="text-center py-12 text-muted text-sm">{text}</div>;
}
