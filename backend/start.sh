#!/bin/bash
set -e

echo "Running data seed..."
cd /app/backend
python seed.py

echo "OPENAI_API_KEY length: ${#OPENAI_API_KEY}"
echo "Starting server..."
uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
