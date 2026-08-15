#!/bin/bash
set -e

MODEL_DIR=/app/models
MODEL_FILE="$MODEL_DIR/latest.joblib"

mkdir -p "$MODEL_DIR"

# If the symlink or model is missing, grab it from MODEL_URL or train
if [ ! -e "$MODEL_FILE" ] || [ ! -s "$MODEL_FILE" ]; then
  if [ -n "$MODEL_URL" ]; then
    echo "Downloading model from MODEL_URL..."
    curl -L -o "$MODEL_FILE" "$MODEL_URL"
  else
    echo "No model found. Training on startup (this will take ~2 minutes)..."
    python -m scripts.train
  fi
else
  echo "Model found at $MODEL_FILE"
fi

exec uvicorn app.api.main:app --host 0.0.0.0 --port 8000
