#!/usr/bin/env bash
#
# Deploy trip-agent to a remote server via Docker (rsync code -> remote build/run).
# Run from a machine where `ssh $HOST` works.
#
#   HOST=your-server ./deploy.sh
#
# One-time prerequisite: create $APPDIR/.env on the server with your secrets.

set -euo pipefail

HOST="${HOST:?set HOST to your server's ssh host/alias, e.g. HOST=my-server}"
PORT="${PORT:-8800}"
APPDIR="${APPDIR:-/opt/trip-agent}"
DOCKER="${DOCKER:-docker}"            # set DOCKER='sudo docker' if your user needs sudo
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> [1/4] ensure app dir + env file on \$HOST"
ssh "$HOST" "mkdir -p $APPDIR && test -f $APPDIR/.env" || {
  echo "ERROR: $APPDIR/.env is missing on the server."
  echo "Create it once with your secrets, then re-run. Example:"
  echo "  ssh \$HOST 'cat > $APPDIR/.env' <<'EOF'"
  echo "  VIVO_API_KEY=sk-xuanji-..."
  echo "  VIVO_APP_ID=your_app_id"
  echo "  EOF"
  exit 1
}

echo "==> [2/4] sync code to server:$APPDIR"
rsync -az --delete \
  --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.git' --exclude='.env' --exclude='data' \
  --exclude='.pytest_cache' --exclude='.langgraph_api' \
  "$HERE"/ "$HOST:$APPDIR"/

echo "==> [3/4] build image + (re)start container on port $PORT"
ssh "$HOST" "set -e; cd $APPDIR; \
  $DOCKER build -t trip-agent . ; \
  $DOCKER rm -f trip-agent 2>/dev/null || true ; \
  $DOCKER run -d --name trip-agent --restart unless-stopped \
    -p ${PORT}:8000 --env-file .env \
    -v ${APPDIR}/data:/app/data \
    trip-agent ; \
  sleep 4 ; $DOCKER ps --filter name=trip-agent --format '  {{.Names}}  {{.Status}}  {{.Ports}}'"

echo "==> [4/4] health check"
ssh "$HOST" "curl -sf http://127.0.0.1:${PORT}/health && echo '  <- OK' || echo '  (not ready, check: $DOCKER logs trip-agent)'"

echo ""
echo "Done. Service listening on port ${PORT} of your server."
