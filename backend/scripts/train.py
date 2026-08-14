"""CLI for training and evaluating the match prediction model.

Examples:
    python -m backend.scripts.train
    python -m backend.scripts.train --min-matches 2 --test-frac 0.2
"""
from __future__ import annotations

import argparse
import logging
import sys

from backend.app.features.model import train_and_evaluate


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="Train match prediction model")
    parser.add_argument("--min-matches", type=int, default=2,
                        help="min prior matches per team to include (default 2)")
    parser.add_argument("--test-frac", type=float, default=0.2,
                        help="fraction of data for test set (default 0.2)")
    parser.add_argument("--no-calibrate", action="store_true",
                        help="skip probability calibration")

    # -- LightGBM hyperparameters (for tuning) --
    hp = parser.add_argument_group("hyperparameters")
    hp.add_argument("--n-estimators", type=int, default=500)
    hp.add_argument("--max-depth", type=int, default=4)
    hp.add_argument("--learning-rate", type=float, default=0.03)
    hp.add_argument("--num-leaves", type=int, default=16)
    hp.add_argument("--min-child-samples", type=int, default=30)
    hp.add_argument("--reg-alpha", type=float, default=0.5)
    hp.add_argument("--reg-lambda", type=float, default=2.0)
    hp.add_argument("--subsample", type=float, default=0.7)
    hp.add_argument("--colsample-bytree", type=float, default=0.7)

    args = parser.parse_args(argv)
    result = train_and_evaluate(
        min_matches_per_team=args.min_matches,
        test_fraction=args.test_frac,
        calibrate=not args.no_calibrate,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        num_leaves=args.num_leaves,
        min_child_samples=args.min_child_samples,
        reg_alpha=args.reg_alpha,
        reg_lambda=args.reg_lambda,
        subsample=args.subsample,
        colsample_bytree=args.colsample_bytree,
    )

    print(f"\n{'='*50}")
    print(f"  Train: {result.n_train}  Test: {result.n_test}")
    print(f"  Accuracy:  {result.accuracy:.4f}")
    print(f"  AUC:       {result.auc:.4f}")
    print(f"  Log Loss:  {result.log_loss:.4f}")
    print(f"  Brier:     {result.brier:.4f}")
    print(f"  Model:     {result.model_path}")
    print(f"{'='*50}")
    print("\nTop 10 features by importance:")
    for i, (feat, imp) in enumerate(list(result.feature_importance.items())[:10], 1):
        print(f"  {i:2d}. {feat:<25s} {imp:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
