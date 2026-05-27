#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CONFIG_PATH="${TAPD_AUTO_CONFIG:-configs/config.yaml}"
export PYTHONPATH="$ROOT_DIR/src:${PYTHONPATH:-}"

python3 -m tapd_auto --config "$CONFIG_PATH" --live --send-dingtalk "$@"
