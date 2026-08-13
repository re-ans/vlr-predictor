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

export function getUpcoming(page = 1, pageSize = 20, category?: string) {
  let url = `/upcoming?page=${page}&page_size=${pageSize}`;
  if (category) url += `&category=${encodeURIComponent(category)}`;
  return fetchJson<MatchListResponse>(url);
}

export function getMatches(
  page = 1,
  pageSize = 20,
  status?: string,
  category?: string
) {
  let url = `/matches?page=${page}&page_size=${pageSize}`;
  if (status) url += `&status=${status}`;
  if (category) url += `&category=${encodeURIComponent(category)}`;
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
