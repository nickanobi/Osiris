#!/bin/bash

# Kill any existing Gunicorn process on port 5000
echo "Checking for existing Gunicorn processes..."
pkill -f "gunicorn" 2>/dev/null && echo "Stopped existing Gunicorn process." || echo "No existing Gunicorn process found."

# Wait for port 5000 to be released before starting
for i in $(seq 1 10); do
  if ! lsof -i :5000 -sTCP:LISTEN -t > /dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Activate virtual environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"

# Suppress macOS fork safety check (required for Gunicorn on macOS)
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

echo "Starting Osiris..."
exec gunicorn app:app \
  --workers 1 \
  --threads 4 \
  --bind 0.0.0.0:5000 \
  --timeout 300
