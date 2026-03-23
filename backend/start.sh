#!/bin/bash
set -e

echo "Running data seed..."
cd /app/backend
python seed.py

echo "=== ENV VAR NAMES ==="
env | cut -d= -f1 | sort
echo "=== END ==="
echo "OPENAI_API_KEY length: ${#OPENAI_API_KEY}"
echo "Starting server..."
uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
