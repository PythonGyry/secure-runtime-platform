#!/bin/bash
# Виправити "Failed to decrypt payload": перезапустити backend і очистити кеш клієнта (Linux/macOS).
# З кореня проекту: bash fix_client_decrypt.sh

set -e
echo "Stopping backend on port 8000..."
pkill -f "uvicorn backend.src.main:app" 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true
sleep 1

echo ""
echo "Clearing client state..."
rm -rf dist/.runtime_data .runtime_data 2>/dev/null || true
echo "Removed .runtime_data (if present)."

echo ""
echo "Starting backend..."
cd "$(dirname "$0")"
python -m uvicorn backend.src.main:app --host 127.0.0.1 --port 8000 &
echo ""
echo "Done. Run ./dist/wishlist_bootstrap (or your client binary) and enter your license key again."
