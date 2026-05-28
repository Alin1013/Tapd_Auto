"""TAPD OpenAPI 客户端和数据同步。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .config import merged_env
from .report import get_tapd_rules, normalize_record
from .scope import scoped_project_iterations


@dataclass
class TapdClient:
    """TAPD API 请求边界。"""

    base_url: str
    access_token: str
    auth_mode: str = "bearer"

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = self.build_headers()
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("status") not in (None, 1, "1"):
            raise RuntimeError(f"TAPD API 请求失败：{payload.get('info', '未知错误')}")
        return payload

    def get_paginated(self, path: str, params: dict[str, Any] | None = None, limit: int = 200) -> list[dict[str, Any]]:
        """读取 TAPD 分页列表。"""

        all_items: list[dict[str, Any]] = []
        page = 1
        while True:
            page_params = {**(params or {}), "limit": limit, "page": page}
            payload = self.get_json(path, page_params)
            items = extract_tapd_data(payload)
            all_items.extend(items)
            if len(items) < limit:
                return all_items
            page += 1

    def build_headers(self) -> dict[str, str]:
        if self.auth_mode != "bearer":
            raise ValueError("当前脚手架只启用 Bearer token；Basic/OAuth 作为后续兼容项。")
        return {"Authorization": f"Bearer {self.access_token}"}


def create_tapd_client(config: dict[str, Any], env: dict[str, str] | None = None) -> TapdClient:
    env_values = merged_env(env)
    access_token = env_values.get("TAPD_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise RuntimeError("缺少 TAPD_ACCESS_TOKEN，无法进入 live 同步模式。")

    tapd = config.get("tapd", {})
    return TapdClient(
        base_url=tapd.get("base_url", "https://api.tapd.cn"),
        access_token=access_token,
        auth_mode=tapd.get("auth_mode", "bearer"),
    )


def extract_tapd_data(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        data = payload.get("data", [])
    else:
        data = payload
    if isinstance(data, list):
        return [normalize_record(item) for item in data]
    if isinstance(data, dict):
        return [normalize_record(data)]
    return []


def unwrap_tapd_data(payload: Any) -> Any:
    """取出 TAPD 响应里的 `data`，保留字段发现这类字典结构。"""

    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def collect_live_data(config: dict[str, Any], client: TapdClient) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """按配置从 TAPD 拉取真实数据。"""

    raw_data: dict[str, list[dict[str, Any]]] = {"tasks": [], "bugs": [], "stories": []}
    field_info: dict[str, Any] = {
        "generated_at": datetime.now(ZoneInfo(config["timezone"])).isoformat(),
        "workspaces": {},
    }
    fields = get_tapd_rules(config)["fields"]

    for project in config["projects"]:
        workspace_id = str(project["workspace_id"])
        workspace_info = field_info["workspaces"].setdefault(
            workspace_id,
            {
                "tasks": None,
                "bugs": None,
                "stories": None,
                "iterations": [],
            },
        )

        if workspace_info["tasks"] is None:
            workspace_info["tasks"] = unwrap_tapd_data(client.get_json("tasks/get_fields_info", {"workspace_id": workspace_id}))
            workspace_info["bugs"] = unwrap_tapd_data(
                client.get_json("bugs/get_fields_info", {"workspace_id": workspace_id, "all_options": 1})
            )
            workspace_info["stories"] = unwrap_tapd_data(client.get_json("stories/get_fields_info", {"workspace_id": workspace_id}))

        project["iterations"] = discover_project_iterations(project, client, workspace_info)

        for iteration in project["iterations"]:
            iteration_id = str(iteration["iteration_id"])
            common_params = {"workspace_id": workspace_id, "iteration_id": iteration_id}
            raw_data["tasks"].extend(
                client.get_paginated(
                    "tasks",
                    {
                        **common_params,
                        "fields": join_fields(
                            [
                                "id",
                                "name",
                                "status",
                                fields["task_owner"],
                                "created",
                                "completed",
                                "iteration_id",
                                "story_id",
                                "begin",
                                "due",
                                "priority_label",
                            ]
                        ),
                    },
                )
            )
            raw_data["bugs"].extend(
                client.get_paginated(
                    "bugs",
                    {
                        **common_params,
                        "fields": join_fields(
                            [
                                "id",
                                "title",
                                "status",
                                "v_status",
                                fields["bug_owner"],
                                fields["bug_creator"],
                                "created",
                                "resolved",
                                "closed",
                                "iteration_id",
                                "priority_label",
                                "severity",
                            ]
                        ),
                    },
                )
            )
            raw_data["stories"].extend(
                client.get_paginated(
                    "stories",
                    {
                        **common_params,
                        "fields": join_fields(
                            [
                                "id",
                                "name",
                                "status",
                                "v_status",
                                fields["story_pm"],
                                "creator",
                                "developer",
                                "begin",
                                "due",
                                "created",
                                "modified",
                                "completed",
                                "iteration_id",
                                "priority_label",
                            ]
                        ),
                    },
                )
            )

    return raw_data, field_info


def discover_project_iterations(project: dict[str, Any], client: TapdClient, workspace_info: dict[str, Any]) -> list[dict[str, Any]]:
    """live 模式自动遍历项目下打开的迭代，未发现时回退到配置迭代。"""

    workspace_id = str(project["workspace_id"])
    discovered = client.get_paginated(
        "iterations",
        {
            "workspace_id": workspace_id,
            "status": "open",
            "fields": "id,name,workspace_id,startdate,enddate,status,created,modified,completed",
        },
    )
    workspace_info["iterations"] = discovered
    if not discovered:
        return scoped_project_iterations(project, project["iterations"])
    iterations = [
        {
            "name": item.get("name") or item.get("title") or str(item.get("id", "")),
            "iteration_id": str(item.get("id") or item.get("iteration_id")),
            "status": item.get("status", ""),
            "start": item.get("startdate", ""),
            "end": item.get("enddate", ""),
        }
        for item in discovered
        if item.get("id") or item.get("iteration_id")
    ]
    return scoped_project_iterations(project, iterations)


def join_fields(fields: list[str]) -> str:
    """去重后拼接 TAPD fields 参数，保持字段顺序稳定。"""

    result: list[str] = []
    for field in fields:
        if field and field not in result:
            result.append(field)
    return ",".join(result)
