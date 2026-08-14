"""Pydantic schemas for API request/response models."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


# -- Prediction --

class PredictionRequest(BaseModel):
    team_a_id: int
    team_b_id: int
    best_of: int = 3

class PredictionResponse(BaseModel):
    team_a_id: int
    team_b_id: int
    team_a_name: str
    team_b_name: str
    team_a_win_prob: float
    team_b_win_prob: float
    predicted_winner: str
    confidence: float
    features: dict[str, Any] = Field(default_factory=dict)


# -- Matches --

class MatchOut(BaseModel):
    id: int
    event_name: str | None = None
    event_category: str | None = None
    team_a_name: str | None = None
    team_b_name: str | None = None
    team_a_id: int | None = None
    team_b_id: int | None = None
    team_a_image: str | None = None
    team_b_image: str | None = None
    winner_name: str | None = None
    winner_id: int | None = None
    match_date: datetime | None = None
    best_of: int | None = None
    status: str
    score_a: int | None = None
    score_b: int | None = None
    enriched: bool = False
    vlr_url: str | None = None
    team_a_vlr_url: str | None = None
    team_b_vlr_url: str | None = None
    prediction: PredictionResponse | None = None

class MatchListResponse(BaseModel):
    matches: list[MatchOut]
    total: int
    page: int
    page_size: int


# -- Teams --

class TeamOut(BaseModel):
    id: int
    name: str
    acronym: str | None = None
    region: str | None = None
    country: str | None = None
    image_url: str | None = None
    current_rating: float
    vlr_url: str | None = None

class TeamListResponse(BaseModel):
    teams: list[TeamOut]
    total: int


# -- Leaderboard --

class LeaderboardEntry(BaseModel):
    rank: int
    team_id: int
    team_name: str
    acronym: str | None = None
    region: str | None = None
    image_url: str | None = None
    elo_rating: float
    win_count: int
    loss_count: int
    win_rate: float
    vlr_url: str | None = None

class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry]
    total: int


# -- Health --

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    match_count: int
    team_count: int


# -- Categories --

class CategoryListResponse(BaseModel):
    categories: list[dict[str, str]]


# -- Auth --

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    token: str
    user: "UserOut"

class UserOut(BaseModel):
    id: int
    email: str
    display_name: str | None = None


# -- Profile / saved items --

class SavedPredictionOut(BaseModel):
    id: int
    match_id: int | None = None
    team_a_id: int | None = None
    team_b_id: int | None = None
    team_a_name: str
    team_b_name: str
    prob_a: float
    prob_b: float
    predicted_winner: str
    best_of: int | None = None
    created_at: datetime | None = None

class SavePredictionRequest(BaseModel):
    match_id: int | None = None
    team_a_id: int
    team_b_id: int
    team_a_name: str
    team_b_name: str
    prob_a: float
    prob_b: float
    predicted_winner: str
    best_of: int | None = None

class RosterOut(BaseModel):
    id: int
    name: str
    player_ids: list[int] = Field(default_factory=list)
    created_at: datetime | None = None

class CreateRosterRequest(BaseModel):
    name: str
    player_ids: list[int] = Field(default_factory=list)

class PlayerOut(BaseModel):
    id: int
    name: str
    team_id: int | None = None
    team_name: str | None = None
    country: str | None = None
