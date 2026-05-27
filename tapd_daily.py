#!/usr/bin/env python3
"""兼容入口。

正式代码已经迁移到 `src/tapd_auto/`。保留这个文件是为了让旧命令
`python3 tapd_daily.py ...` 仍然可以继续使用。
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tapd_auto import *  # noqa: F401,F403,E402
from tapd_auto.cli import run_cli  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(run_cli())
