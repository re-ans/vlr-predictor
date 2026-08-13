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

    args = parser.parse_args(argv)
    result = train_and_evaluate(
        min_matches_per_team=args.min_matches,
        test_fraction=args.test_frac,
        calibrate=not args.no_calibrate,
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
