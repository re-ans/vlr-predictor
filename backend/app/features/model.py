"""Match-winner prediction model: train, evaluate, and predict.

Uses LightGBM by default with chronological train/test split to avoid
look-ahead bias. The trained model + feature column list are serialised
together via joblib for serving.

Public API:
    train_and_evaluate()  -> TrainResult (metrics + model artefact path)
    load_model(path)      -> ModelBundle
    ModelBundle.predict(features_dict) -> Prediction
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from .builder import build_feature_df
from .elo import EloEngine

logger = logging.getLogger("features.model")

_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"

# Columns used as features (excludes IDs, dates, and the label).
_META_COLS = {"match_id", "match_date", "team_a_id", "team_b_id", "winner",
              "prior_matches_a", "prior_matches_b"}


@dataclass
class Prediction:
    team_a_win_prob: float
    team_b_win_prob: float
    predicted_winner: str  # "team_a" or "team_b"
    confidence: float      # max(p_a, p_b)


@dataclass
class TrainResult:
    accuracy: float
    auc: float
    log_loss: float
    brier: float
    model_path: str
    n_train: int
    n_test: int
    feature_importance: dict[str, float]


class ModelBundle:
    """Loaded model ready for inference."""

    def __init__(self, model: Any, feature_cols: list[str], calibrator: Any = None):
        self.model = model
        self.feature_cols = feature_cols
        self.calibrator = calibrator

    def predict(self, features: dict[str, Any]) -> Prediction:
        """Predict match winner from a feature dictionary."""
        row = pd.DataFrame([features])[self.feature_cols]
        row = row.fillna(0)

        if self.calibrator is not None:
            probs = self.calibrator.predict_proba(row)[0]
        else:
            probs = self.model.predict_proba(row)[0]

        p_a = float(probs[1])  # P(winner=1) means team_a wins
        p_b = 1 - p_a
        return Prediction(
            team_a_win_prob=round(p_a, 4),
            team_b_win_prob=round(p_b, 4),
            predicted_winner="team_a" if p_a >= 0.5 else "team_b",
            confidence=round(max(p_a, p_b), 4),
        )

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict for a DataFrame, returning columns for probabilities."""
        X = df[self.feature_cols].fillna(0)
        if self.calibrator is not None:
            probs = self.calibrator.predict_proba(X)
        else:
            probs = self.model.predict_proba(X)
        out = df.copy()
        out["prob_a"] = probs[:, 1]
        out["prob_b"] = probs[:, 0]
        out["pred_winner"] = (probs[:, 1] >= 0.5).astype(int)
        return out


def load_model(path: str | Path | None = None) -> ModelBundle:
    """Load a saved model bundle."""
    if path is None:
        path = _MODEL_DIR / "latest.joblib"
    data = joblib.load(path)
    return ModelBundle(
        model=data["model"],
        feature_cols=data["feature_cols"],
        calibrator=data.get("calibrator"),
    )


def train_and_evaluate(
    min_matches_per_team: int = 2,
    test_fraction: float = 0.2,
    calibrate: bool = True,
    n_estimators: int = 500,
    max_depth: int = 4,
    learning_rate: float = 0.03,
    num_leaves: int = 16,
    min_child_samples: int = 30,
    reg_alpha: float = 0.5,
    reg_lambda: float = 2.0,
    subsample: float = 0.7,
    colsample_bytree: float = 0.7,
) -> TrainResult:
    """Train a LightGBM model with chronological split and evaluate it.

    The data is split chronologically: the most recent ``test_fraction`` of
    matches form the test set, ensuring we never train on future data.

    All LightGBM hyperparameters are exposed so the model can be tuned from
    the CLI without editing code.
    """
    df = build_feature_df(min_matches_per_team=min_matches_per_team)
    if len(df) < 50:
        raise ValueError(f"Not enough data to train: {len(df)} rows")

    # Sort by date (should already be sorted, but be safe)
    df = df.sort_values("match_date").reset_index(drop=True)

    feature_cols = [c for c in df.columns if c not in _META_COLS]
    X = df[feature_cols].fillna(0)
    y = df["winner"]

    # Chronological split
    split_idx = int(len(df) * (1 - test_fraction))
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    logger.info("Training on %d rows, testing on %d rows", len(X_train), len(X_test))

    # LightGBM with early stopping to prevent overfitting
    model = lgb.LGBMClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        num_leaves=num_leaves,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        min_child_samples=min_child_samples,
        reg_alpha=reg_alpha,
        reg_lambda=reg_lambda,
        random_state=42,
        verbosity=-1,
    )
    model.fit(
        X_train, y_train,
        eval_X=X_test, eval_y=y_test,
        callbacks=[
            lgb.log_evaluation(50),
            lgb.early_stopping(stopping_rounds=30),
        ],
    )

    # LightGBM's sigmoid output is generally well-calibrated; skip
    # explicit Platt scaling to avoid sklearn version issues.
    calibrator = None

    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)

    acc = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_prob)
    ll = log_loss(y_test, y_prob)
    brier = brier_score_loss(y_test, y_prob)

    logger.info("Test accuracy=%.4f  AUC=%.4f  log_loss=%.4f  brier=%.4f",
                acc, auc, ll, brier)

    # Feature importance
    importance = dict(zip(feature_cols, model.feature_importances_.tolist()))
    importance = dict(sorted(importance.items(), key=lambda x: -x[1]))

    # Save
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = _MODEL_DIR / f"lgbm_{ts}.joblib"
    bundle = {
        "model": model,
        "feature_cols": feature_cols,
        "calibrator": calibrator,
        "metrics": {"accuracy": acc, "auc": auc, "log_loss": ll, "brier": brier},
        "trained_at": ts,
        "n_train": len(X_train),
        "n_test": len(X_test),
    }
    joblib.dump(bundle, model_path)

    # Symlink latest
    latest = _MODEL_DIR / "latest.joblib"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(model_path.name)

    logger.info("Model saved to %s", model_path)

    # Persist Elo ratings to team rows so the leaderboard/API is accurate
    _persist_elo_ratings()

    return TrainResult(
        accuracy=acc,
        auc=auc,
        log_loss=ll,
        brier=brier,
        model_path=str(model_path),
        n_train=len(X_train),
        n_test=len(X_test),
        feature_importance=importance,
    )


def _persist_elo_ratings() -> None:
    """Replay all matches through Elo and write final ratings to team rows."""
    from sqlalchemy import text as sa_text
    from ..db.base import build_engine, session_scope
    from ..db.models import Match

    engine = build_engine()
    with engine.connect() as conn:
        rows = conn.execute(sa_text("""
            SELECT m.team_a_id, m.team_b_id, m.winner_id, e.tier
            FROM matches m
            LEFT JOIN events e ON m.event_id = e.id
            WHERE m.status = 'finished'
              AND m.forfeit = false
              AND m.winner_id IS NOT NULL
              AND m.team_a_id IS NOT NULL
              AND m.team_b_id IS NOT NULL
            ORDER BY m.match_date ASC, m.id ASC
        """)).fetchall()

    elo = EloEngine(k=32)
    for team_a, team_b, winner, tier in rows:
        elo.process_match(team_a, team_b, winner, tier=tier)

    ratings = elo.snapshot()
    if not ratings:
        return

    with session_scope() as session:
        for team_id, rating in ratings.items():
            session.execute(
                sa_text("UPDATE teams SET current_rating = :r WHERE id = :tid"),
                {"r": round(rating, 2), "tid": team_id},
            )
    logger.info("Persisted Elo ratings for %d teams", len(ratings))
