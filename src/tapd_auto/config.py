"""配置和环境变量读取。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml


ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def load_dotenv(path: Path = Path(".env")) -> dict[str, str]:
    """读取本地 `.env`，只返回键值，不打印敏感信息。"""

    if not path.exists():
        return {}

    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def merged_env(env: dict[str, str] | None = None) -> dict[str, str]:
    result = {**load_dotenv(), **os.environ}
    if env is not None:
        result.update(env)
    return result


def load_config(path: Path | str, env: dict[str, str] | None = None) -> dict[str, Any]:
    config_path = Path(path)
    return load_config_from_text(config_path.read_text(encoding="utf-8"), env=env)


def load_config_from_text(text: str, env: dict[str, str] | None = None) -> dict[str, Any]:
    config = yaml.safe_load(text) or {}
    config = resolve_env(config, merged_env(env))
    validate_config(config)
    return config


def resolve_env(value: Any, env: dict[str, str]) -> Any:
    """递归解析配置中的 `${NAME}` 占位符。"""

    if isinstance(value, dict):
        return {key: resolve_env(item, env) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_env(item, env) for item in value]
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda match: env.get(match.group(1), ""), value)
    return value


def validate_config(config: dict[str, Any]) -> None:
    required_top_keys = ["timezone", "tapd", "report", "projects"]
    for key in required_top_keys:
        if key not in config:
            raise ValueError(f"配置缺少必填字段：{key}")

    if not config["projects"]:
        raise ValueError("配置至少需要一个项目")

    for project in config["projects"]:
        for key in ["name", "workspace_id", "iterations", "members"]:
            if key not in project:
                raise ValueError(f"项目配置缺少必填字段：{key}")
        if not project["iterations"]:
            raise ValueError(f"项目 {project['name']} 至少需要一个迭代")
