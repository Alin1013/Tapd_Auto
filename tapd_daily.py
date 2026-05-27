#!/usr/bin/env python3
"""TAPD 每日复盘生成器。

第一版先把链路打通：读取配置和本地环境变量，聚合任务、缺陷、需求数据，
再输出 HTML、Markdown 和 JSON。真实 TAPD 字段映射后续可以在同一入口继续补充。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import html
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import requests
import yaml


DEFAULT_DONE_TASK_STATUSES = {"已完成", "已关闭", "完成", "关闭", "Done", "Closed"}
DEFAULT_CLOSED_BUG_STATUSES = {"已解决", "已关闭", "无需解决", "关闭", "Done", "Closed", "Resolved"}
DEFAULT_TAPD_FIELDS = {
    "task_owner": "owner",
    "bug_owner": "current_owner",
    "story_pm": "owner",
}

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


@dataclass
class TapdClient:
    """TAPD API 请求边界。

    这里不把具体任务、缺陷、需求接口写死，是为了等工作区字段和接口口径确认后再接入。
    这样 token、base_url、错误处理先有清晰边界，后续扩展不会影响报表聚合逻辑。
    """

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
        """读取 TAPD 分页列表。

        TAPD 列表接口每页默认 30 条，最大 200 条；只有当本页达到 limit 时才继续翻页。
        """

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


def load_config(path: Path | str, env: dict[str, str] | None = None) -> dict[str, Any]:
    config_path = Path(path)
    return load_config_from_text(config_path.read_text(encoding="utf-8"), env=env)


def load_config_from_text(text: str, env: dict[str, str] | None = None) -> dict[str, Any]:
    merged_env = {**load_dotenv(), **os.environ}
    if env is not None:
        merged_env.update(env)

    config = yaml.safe_load(text) or {}
    config = resolve_env(config, merged_env)
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


def build_report(config: dict[str, Any], raw_data: dict[str, list[dict[str, Any]]], report_date: str) -> dict[str, Any]:
    tapd_rules = get_tapd_rules(config)
    done_task_statuses = tapd_rules["task_done_statuses"]
    closed_bug_statuses = tapd_rules["bug_closed_statuses"]
    fields = tapd_rules["fields"]
    normalized_data = {
        data_type: [normalize_record(item) for item in items]
        for data_type, items in raw_data.items()
    }

    report_projects: list[dict[str, Any]] = []
    unique_users: set[str] = set()
    summary = {
        "project_count": len(config["projects"]),
        "iteration_count": 0,
        "member_count": 0,
        "task_total": 0,
        "task_done": 0,
        "task_completion_rate": 0,
        "bugs_closed": 0,
        "bugs_open": 0,
        "bugs_new": 0,
    }

    for project in config["projects"]:
        project_result = {
            "name": project["name"],
            "workspace_id": str(project["workspace_id"]),
            "iterations": [],
        }
        product_managers = {pm["tapd_user"]: pm["name"] for pm in project.get("product_managers", [])}

        for iteration in project["iterations"]:
            summary["iteration_count"] += 1
            iteration_id = str(iteration["iteration_id"])
            member_results = []

            for member in project["members"]:
                user = member["tapd_user"]
                unique_users.add(user)

                member_tasks = [
                    task
                    for task in normalized_data.get("tasks", [])
                    if is_in_scope(task, project, iteration) and field_matches(task, fields["task_owner"], user)
                ]
                member_bugs = [
                    bug
                    for bug in normalized_data.get("bugs", [])
                    if is_in_scope(bug, project, iteration) and field_matches(bug, fields["bug_owner"], user)
                ]

                task_total = len(member_tasks)
                task_done = sum(1 for task in member_tasks if str(task.get("status", "")) in done_task_statuses)
                bugs_closed = sum(1 for bug in member_bugs if str(bug.get("status", "")) in closed_bug_statuses)
                bugs_open = len(member_bugs) - bugs_closed
                bugs_new = sum(1 for bug in member_bugs if is_same_day(bug.get("created"), report_date))

                summary["task_total"] += task_total
                summary["task_done"] += task_done
                summary["bugs_closed"] += bugs_closed
                summary["bugs_open"] += bugs_open
                summary["bugs_new"] += bugs_new

                member_results.append(
                    {
                        "name": member["name"],
                        "tapd_user": user,
                        "role": member.get("role", ""),
                        "tapd_report_url": member.get("tapd_report_url", ""),
                        "task_total": task_total,
                        "task_done": task_done,
                        "task_completion_rate": percent(task_done, task_total),
                        "bugs_closed": bugs_closed,
                        "bugs_open": bugs_open,
                        "bugs_new": bugs_new,
                    }
                )

            requirements = build_requirements(normalized_data.get("stories", []), project, iteration, product_managers, fields["story_pm"])
            project_result["iterations"].append(
                {
                    "name": iteration["name"],
                    "iteration_id": iteration_id,
                    "members": member_results,
                    "requirements": requirements,
                }
            )

        report_projects.append(project_result)

    summary["member_count"] = len(unique_users)
    summary["task_completion_rate"] = percent(summary["task_done"], summary["task_total"])

    return {
        "date": report_date,
        "timezone": config["timezone"],
        "summary": summary,
        "projects": report_projects,
    }


def build_requirements(
    stories: list[dict[str, Any]],
    project: dict[str, Any],
    iteration: dict[str, Any],
    product_managers: dict[str, str],
    pm_field: str,
) -> list[dict[str, Any]]:
    requirements = []
    for story in stories:
        if not is_in_scope(story, project, iteration):
            continue
        matched_user = first_matching_value(story, pm_field, set(product_managers.keys()))
        if matched_user is None:
            continue
        requirements.append(
            {
                "title": story.get("title") or story.get("name", ""),
                "product_manager": product_managers.get(matched_user, matched_user),
                "status": story.get("v_status") or story.get("status", ""),
                "start": story.get("start") or story.get("begin", ""),
                "end": story.get("end") or story.get("due", ""),
                "url": story.get("url", ""),
            }
        )
    return sorted(requirements, key=lambda item: (item["start"], item["end"], item["title"]))


def normalize_record(item: dict[str, Any]) -> dict[str, Any]:
    """展开 TAPD 常见的 `Task`、`Bug`、`Story`、`Iteration` 包装。"""

    if not isinstance(item, dict):
        return {}
    for wrapper in ["Task", "Bug", "Story", "Iteration", "Workspace"]:
        nested = item.get(wrapper)
        if isinstance(nested, dict):
            return nested
    return item


def is_in_scope(item: dict[str, Any], project: dict[str, Any], iteration: dict[str, Any]) -> bool:
    workspace_id = str(project["workspace_id"])
    iteration_id = str(iteration["iteration_id"])
    item_workspace = str(item.get("workspace_id", workspace_id))
    item_iteration = str(item.get("iteration_id", iteration_id))
    return item_workspace == workspace_id and item_iteration == iteration_id


def get_tapd_rules(config: dict[str, Any]) -> dict[str, Any]:
    tapd = config.get("tapd", {})
    legacy_status = config.get("status_mapping", {})
    return {
        "task_done_statuses": set(tapd.get("task_done_statuses") or legacy_status.get("done_tasks", DEFAULT_DONE_TASK_STATUSES)),
        "bug_closed_statuses": set(tapd.get("bug_closed_statuses") or legacy_status.get("closed_bugs", DEFAULT_CLOSED_BUG_STATUSES)),
        "fields": {**DEFAULT_TAPD_FIELDS, **tapd.get("fields", {})},
    }


def field_matches(item: dict[str, Any], field_name: str, user: str) -> bool:
    return first_matching_value(item, field_name, {user}) is not None


def first_matching_value(item: dict[str, Any], field_name: str, users: set[str]) -> str | None:
    for value_text in split_people(item.get(field_name)):
        if value_text in users:
            return value_text
    return None


def split_people(raw_value: Any) -> list[str]:
    """兼容 TAPD 人员字段的单值、列表、逗号、分号和竖线分隔格式。"""

    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        values = raw_value
    else:
        values = re.split(r"[;,|]", str(raw_value))
    return [str(value).strip() for value in values if str(value).strip()]


def is_same_day(value: Any, report_date: str) -> bool:
    if value is None:
        return False
    return str(value)[:10] == report_date


def percent(done: int, total: int) -> int:
    if total == 0:
        return 0
    return round(done / total * 100)


def render_markdown(report: dict[str, Any], report_url: str) -> str:
    summary = report["summary"]
    return "\n".join(
        [
            f"### TAPD 每日复盘 {report['date']}",
            "",
            f"今日统计：{summary['project_count']} 个项目 / {summary['iteration_count']} 个迭代 / {summary['member_count']} 人",
            f"任务整体完成率：{summary['task_completion_rate']}%",
            f"缺陷：未解决 {summary['bugs_open']}，今日新增 {summary['bugs_new']}，今日关闭 {summary['bugs_closed']}",
            "",
            f"[查看交互报表]({report_url})",
            "",
        ]
    )


def build_dingtalk_signed_url(webhook: str, secret: str, timestamp: int | None = None) -> str:
    """按钉钉群自定义机器人规则生成加签 URL。"""

    if not secret:
        return webhook
    timestamp = timestamp or int(time.time() * 1000)
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    sign = quote_plus(base64.b64encode(digest).decode("utf-8"))
    separator = "&" if "?" in webhook else "?"
    return f"{webhook}{separator}timestamp={timestamp}&sign={sign}"


def build_dingtalk_markdown_payload(
    title: str,
    markdown: str,
    at_mobiles: list[str] | None = None,
    is_at_all: bool = False,
) -> dict[str, Any]:
    return {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": markdown,
        },
        "at": {
            "atMobiles": at_mobiles or [],
            "isAtAll": is_at_all,
        },
    }


def render_html(report: dict[str, Any]) -> str:
    project_sections = "\n".join(render_project(project) for project in report["projects"])
    summary = report["summary"]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>TAPD 每日复盘 {html.escape(report["date"])}</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #172033; background: #f6f8fb; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 20px 44px; }}
    h1, h2, h3 {{ margin: 0; }}
    .summary {{ display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap: 12px; margin: 18px 0 24px; }}
    .metric, section {{ background: #fff; border: 1px solid #dfe5ee; border-radius: 8px; }}
    .metric {{ padding: 14px; }}
    .metric strong {{ display: block; font-size: 22px; margin-top: 4px; }}
    section {{ padding: 18px; margin-top: 16px; }}
    .iteration {{ margin-top: 18px; }}
    .bars {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 14px; align-items: end; min-height: 230px; margin-top: 16px; }}
    .person {{ display: grid; grid-template-rows: 130px auto; gap: 8px; align-items: end; text-align: center; }}
    .bar-wrap {{ height: 130px; display: flex; align-items: flex-end; justify-content: center; border-bottom: 1px solid #ccd5e1; }}
    .bar {{ width: 42px; min-height: 4px; border-radius: 6px 6px 0 0; background: #2f80ed; }}
    .bar.warn {{ background: #d94841; }}
    .name {{ font-weight: 700; }}
    .meta {{ color: #5d6b82; font-size: 13px; line-height: 1.45; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid #e7ecf3; text-align: left; }}
    th {{ color: #44546a; background: #f8fafc; }}
    a {{ color: #1d6fd8; text-decoration: none; }}
    @media (max-width: 760px) {{ .summary {{ grid-template-columns: repeat(2, 1fr); }} main {{ padding: 20px 12px; }} }}
  </style>
</head>
<body>
<main>
  <h1>TAPD 每日复盘 {html.escape(report["date"])}</h1>
  <div class="summary">
    <div class="metric">项目<strong>{summary["project_count"]}</strong></div>
    <div class="metric">迭代<strong>{summary["iteration_count"]}</strong></div>
    <div class="metric">人员<strong>{summary["member_count"]}</strong></div>
    <div class="metric">任务完成率<strong>{summary["task_completion_rate"]}%</strong></div>
    <div class="metric">未解决缺陷<strong>{summary["bugs_open"]}</strong></div>
  </div>
  {project_sections}
</main>
</body>
</html>
"""


def render_project(project: dict[str, Any]) -> str:
    iterations = "\n".join(render_iteration(iteration) for iteration in project["iterations"])
    return f"""<section>
  <h2>{html.escape(project["name"])}</h2>
  {iterations}
</section>"""


def render_iteration(iteration: dict[str, Any]) -> str:
    bars = "\n".join(render_member(member) for member in iteration["members"])
    requirements = render_requirements(iteration["requirements"])
    return f"""<div class="iteration">
  <h3>{html.escape(iteration["name"])}</h3>
  <div class="bars">{bars}</div>
  {requirements}
</div>"""


def render_member(member: dict[str, Any]) -> str:
    rate = member["task_completion_rate"]
    warn_class = " warn" if member["bugs_open"] > 0 else ""
    name = html.escape(member["name"])
    link_start = f'<a href="{html.escape(member["tapd_report_url"])}" target="_blank" rel="noreferrer">' if member["tapd_report_url"] else ""
    link_end = "</a>" if member["tapd_report_url"] else ""
    return f"""<div class="person" title="任务 {member["task_done"]}/{member["task_total"]}，缺陷 已关 {member["bugs_closed"]} / 未解 {member["bugs_open"]} / 新增 {member["bugs_new"]}">
  <div class="bar-wrap"><div class="bar{warn_class}" style="height:{max(rate, 3)}%"></div></div>
  <div>
    <div class="name">{link_start}{name}{link_end}</div>
    <div class="meta">任务 {member["task_done"]}/{member["task_total"]} · {rate}%</div>
    <div class="meta">缺陷 已关 {member["bugs_closed"]} / 未解 {member["bugs_open"]} / 新增 {member["bugs_new"]}</div>
  </div>
</div>"""


def render_requirements(requirements: list[dict[str, Any]]) -> str:
    if not requirements:
        return "<p class=\"meta\">暂无产品需求排期。</p>"
    rows = "\n".join(
        f"""<tr>
  <td>{render_requirement_link(item)}</td>
  <td>{html.escape(item["product_manager"])}</td>
  <td>{html.escape(item["status"])}</td>
  <td>{html.escape(item["start"])}</td>
  <td>{html.escape(item["end"])}</td>
</tr>"""
        for item in requirements
    )
    return f"""<table>
  <thead><tr><th>需求</th><th>产品经理</th><th>状态</th><th>开始</th><th>结束</th></tr></thead>
  <tbody>{rows}</tbody>
</table>"""


def render_requirement_link(item: dict[str, Any]) -> str:
    title = html.escape(item["title"])
    if item["url"]:
        return f'<a href="{html.escape(item["url"])}" target="_blank" rel="noreferrer">{title}</a>'
    return title


def write_report(report: dict[str, Any], output_root: Path | str, public_base_url: str) -> Path:
    output_dir = Path(output_root) / report["date"]
    output_dir.mkdir(parents=True, exist_ok=True)

    report_url = f"{public_base_url.rstrip('/')}/reports/{report['date']}/index.html"
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "summary.md").write_text(render_markdown(report, report_url), encoding="utf-8")
    (output_dir / "index.html").write_text(render_html(report), encoding="utf-8")
    return output_dir


def load_sample_data(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    sample_data = config.get("sample_data")
    if sample_data is None:
        return {"tasks": [], "bugs": [], "stories": []}
    return {
        "tasks": list(sample_data.get("tasks", [])),
        "bugs": list(sample_data.get("bugs", [])),
        "stories": list(sample_data.get("stories", [])),
    }


def today_in_timezone(timezone: str) -> str:
    return datetime.now(ZoneInfo(timezone)).strftime("%Y-%m-%d")


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 TAPD 每日复盘报表")
    parser.add_argument("--config", default="config.example.yaml", help="配置文件路径")
    parser.add_argument("--date", default=None, help="报表日期，格式 YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="使用配置里的 sample_data 生成本地报表")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    report_date = args.date or today_in_timezone(config["timezone"])

    if not args.dry_run:
        raise SystemExit("当前版本请先使用 --dry-run；真实 TAPD 接口字段确认后再开启 live 同步。")

    raw_data = load_sample_data(config)
    report = build_report(config, raw_data, report_date=report_date)
    output_dir = write_report(report, config["report"]["output_dir"], config["report"]["public_base_url"])
    print(f"已生成 TAPD 每日复盘：{output_dir / 'index.html'}")
    print(f"钉钉 Markdown 摘要：{output_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
