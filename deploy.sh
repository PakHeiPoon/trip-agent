#!/usr/bin/env bash
#
# Deploy trip-agent to a remote server via Docker.
# Run this FROM YOUR MAC (where `ssh achat-hk` works).
#
#   ./deploy.sh
#
# One-time prerequisite: create the env file on the server (see README / handoff).
#
# Override defaults with env vars, e.g.:  HOST=achat-hk PORT=8800 ./deploy.sh

set -euo pipefail

HOST="${HOST:-achat-hk}"
PORT="${PORT:-8800}"
APPDIR="${APPDIR:-/opt/trip-agent}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> [1/4] ensure app dir + env file on $HOST"
ssh "$HOST" "mkdir -p $APPDIR && test -f $APPDIR/.env" || {
  echo "ERROR: $APPDIR/.env is missing on the server."
  echo "Create it once with your secrets, then re-run. Example:"
  echo "  ssh $HOST 'cat > $APPDIR/.env' <<'EOF'"
  echo "  VIVO_API_KEY=sk-xuanji-..."
  echo "  VIVO_APP_ID=your_app_id"
  echo "  EOF"
  exit 1
}

echo "==> [2/4] sync code to $HOST:$APPDIR"
rsync -az --delete \
  --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.git' --exclude='.env' --exclude='data' \
  --exclude='.pytest_cache' --exclude='.langgraph_api' \
  "$HERE"/ "$HOST:$APPDIR"/

echo "==> [3/4] build image + (re)start container on port $PORT"
ssh "$HOST" "set -e; cd $APPDIR; \
  docker build -t trip-agent . ; \
  docker rm -f trip-agent 2>/dev/null || true ; \
  docker run -d --name trip-agent --restart unless-stopped \
    -p ${PORT}:8000 --env-file .env trip-agent ; \
  sleep 4 ; docker ps --filter name=trip-agent --format '  {{.Names}}  {{.Status}}  {{.Ports}}'"

echo "==> [4/4] health check"
ssh "$HOST" "curl -sf http://127.0.0.1:${PORT}/health && echo '  <- OK' || echo '  (not ready, check: docker logs trip-agent)'"

echo ""
echo "Done. Public URL:  http://124.156.170.240:${PORT}"
echo "Test:  curl -X POST http://124.156.170.240:${PORT}/api/chat -H 'Content-Type: application/json' -d '{\"message\":\"你好\"}'"
