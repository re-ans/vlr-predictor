const BASE = "/api";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

// -- Types --

export interface Prediction {
  team_a_id: number;
  team_b_id: number;
  team_a_name: string;
  team_b_name: string;
  team_a_win_prob: number;
  team_b_win_prob: number;
  predicted_winner: string;
  confidence: number;
  features: Record<string, number>;
}

export interface MatchOut {
  id: number;
  event_name: string | null;
  event_category: string | null;
  team_a_name: string | null;
  team_b_name: string | null;
  team_a_id: number | null;
  team_b_id: number | null;
  team_a_image: string | null;
  team_b_image: string | null;
  winner_name: string | null;
  winner_id: number | null;
  match_date: string | null;
  best_of: number | null;
  status: string;
  score_a: number | null;
  score_b: number | null;
  enriched: boolean;
  vlr_url: string | null;
  team_a_vlr_url: string | null;
  team_b_vlr_url: string | null;
  prediction: Prediction | null;
}

export interface MatchListResponse {
  matches: MatchOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface TeamOut {
  id: number;
  name: string;
  acronym: string | null;
  region: string | null;
  country: string | null;
  image_url: string | null;
  current_rating: number;
  vlr_url: string | null;
}

export interface TeamListResponse {
  teams: TeamOut[];
  total: number;
}

export interface LeaderboardEntry {
  rank: number;
  team_id: number;
  team_name: string;
  acronym: string | null;
  region: string | null;
  image_url: string | null;
  elo_rating: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
  vlr_url: string | null;
}

export interface LeaderboardResponse {
  entries: LeaderboardEntry[];
  total: number;
}

export interface HealthResponse {
  status: string;
  model_loaded: boolean;
  match_count: number;
  team_count: number;
}

export interface Category {
  value: string;
  label: string;
}

export interface CategoryListResponse {
  categories: Category[];
}

// -- API calls --

export function getHealth() {
  return fetchJson<HealthResponse>("/health");
}

export function getCategories() {
  return fetchJson<CategoryListResponse>("/categories");
}

export function getUpcoming(
  page = 1,
  pageSize = 20,
  category?: string,
  region?: string
) {
  let url = `/upcoming?page=${page}&page_size=${pageSize}`;
  if (category) url += `&category=${encodeURIComponent(category)}`;
  if (region) url += `&region=${encodeURIComponent(region)}`;
  return fetchJson<MatchListResponse>(url);
}

export function getMatches(
  page = 1,
  pageSize = 20,
  status?: string,
  category?: string,
  region?: string
) {
  let url = `/matches?page=${page}&page_size=${pageSize}`;
  if (status) url += `&status=${status}`;
  if (category) url += `&category=${encodeURIComponent(category)}`;
  if (region) url += `&region=${encodeURIComponent(region)}`;
  return fetchJson<MatchListResponse>(url);
}

export function getLeaderboard(
  limit = 25,
  category?: string,
  region?: string
) {
  let url = `/leaderboard?limit=${limit}`;
  if (category) url += `&category=${encodeURIComponent(category)}`;
  if (region) url += `&region=${encodeURIComponent(region)}`;
  return fetchJson<LeaderboardResponse>(url);
}

export function getMatch(matchId: number) {
  return fetchJson<MatchOut>(`/matches/${matchId}`);
}

export function refreshMatches() {
  return fetchJson<{ synced: boolean; rows_updated?: number; message?: string }>(
    "/refresh",
    { method: "POST" }
  );
}

export function getTeams(search?: string, page = 1, pageSize = 50) {
  let url = `/teams?page=${page}&page_size=${pageSize}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  return fetchJson<TeamListResponse>(url);
}

export function predict(teamAId: number, teamBId: number, bestOf = 3) {
  return fetchJson<Prediction>("/predict", {
    method: "POST",
    body: JSON.stringify({
      team_a_id: teamAId,
      team_b_id: teamBId,
      best_of: bestOf,
    }),
  });
}

// -- Auth --

export interface UserOut {
  id: number;
  email: string;
  display_name: string | null;
}

export interface AuthResponse {
  token: string;
  user: UserOut;
}

function authedHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export function register(email: string, password: string, displayName?: string) {
  return fetchJson<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
}

export function login(email: string, password: string) {
  return fetchJson<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getMe(token: string) {
  return fetchJson<UserOut>("/auth/me", { headers: authedHeaders(token) });
}

// -- Favorites --

export function addFavorite(token: string, teamId: number) {
  return fetchJson<{ ok: boolean }>(`/profile/favorites/${teamId}`, {
    method: "POST",
    headers: authedHeaders(token),
  });
}

export function removeFavorite(token: string, teamId: number) {
  return fetchJson<{ ok: boolean }>(`/profile/favorites/${teamId}`, {
    method: "DELETE",
    headers: authedHeaders(token),
  });
}

export interface FavoriteTeam {
  team_id: number;
  name: string;
  image_url: string | null;
  rating: number;
}

export function listFavorites(token: string) {
  return fetchJson<{ favorites: FavoriteTeam[] }>("/profile/favorites", {
    headers: authedHeaders(token),
  });
}

// -- Saved matches --

export function saveMatch(token: string, matchId: number) {
  return fetchJson<{ ok: boolean }>(`/profile/matches/${matchId}`, {
    method: "POST",
    headers: authedHeaders(token),
  });
}

export function unsaveMatch(token: string, matchId: number) {
  return fetchJson<{ ok: boolean }>(`/profile/matches/${matchId}`, {
    method: "DELETE",
    headers: authedHeaders(token),
  });
}

export function listSavedMatches(token: string) {
  return fetchJson<{ match_ids: number[] }>("/profile/matches", {
    headers: authedHeaders(token),
  });
}

// -- Saved predictions --

export interface SavedPrediction {
  id: number;
  match_id: number | null;
  team_a_id: number | null;
  team_b_id: number | null;
  team_a_name: string;
  team_b_name: string;
  prob_a: number;
  prob_b: number;
  predicted_winner: string;
  best_of: number | null;
  created_at: string | null;
}

export interface SavePredictionReq {
  match_id?: number | null;
  team_a_id: number;
  team_b_id: number;
  team_a_name: string;
  team_b_name: string;
  prob_a: number;
  prob_b: number;
  predicted_winner: string;
  best_of?: number | null;
}

export function savePrediction(token: string, body: SavePredictionReq) {
  return fetchJson<SavedPrediction>("/profile/predictions", {
    method: "POST",
    headers: authedHeaders(token),
    body: JSON.stringify(body),
  });
}

export function listPredictions(token: string) {
  return fetchJson<{ predictions: SavedPrediction[] }>("/profile/predictions", {
    headers: authedHeaders(token),
  });
}

export function deletePrediction(token: string, id: number) {
  return fetchJson<{ ok: boolean }>(`/profile/predictions/${id}`, {
    method: "DELETE",
    headers: authedHeaders(token),
  });
}

// -- Rosters --

export interface RosterOut {
  id: number;
  name: string;
  player_ids: number[];
  created_at: string | null;
}

export interface PlayerOut {
  id: number;
  name: string;
  team_id: number | null;
  team_name: string | null;
  country: string | null;
}

export function createRoster(token: string, name: string, playerIds: number[]) {
  return fetchJson<RosterOut>("/profile/rosters", {
    method: "POST",
    headers: authedHeaders(token),
    body: JSON.stringify({ name, player_ids: playerIds }),
  });
}

export function listRosters(token: string) {
  return fetchJson<{ rosters: RosterOut[] }>("/profile/rosters", {
    headers: authedHeaders(token),
  });
}

export function deleteRoster(token: string, id: number) {
  return fetchJson<{ ok: boolean }>(`/profile/rosters/${id}`, {
    method: "DELETE",
    headers: authedHeaders(token),
  });
}

export function searchPlayers(q: string, limit = 20) {
  return fetchJson<PlayerOut[]>(`/players?q=${encodeURIComponent(q)}&limit=${limit}`);
}
