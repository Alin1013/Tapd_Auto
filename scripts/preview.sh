#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${TAPD_AUTO_PREVIEW_PORT:-8765}"
HOST="${TAPD_AUTO_PREVIEW_HOST:-127.0.0.1}"

echo "本地预览服务：http://${HOST}:${PORT}/"
echo "日报示例路径：http://${HOST}:${PORT}/public/reports/YYYY-MM-DD/index.html"
python3 -m http.server "$PORT" --bind "$HOST"
