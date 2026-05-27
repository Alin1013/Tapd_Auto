"""日报聚合模型。"""

from __future__ import annotations

import re
from typing import Any


DEFAULT_DONE_TASK_STATUSES = {"done", "已完成", "已关闭", "完成", "关闭", "Done", "Closed"}
DEFAULT_CLOSED_BUG_STATUSES = {
    "resolved",
    "verified",
    "rejected",
    "closed",
    "已解决",
    "已验证",
    "已关闭",
    "无需解决",
    "关闭",
    "Done",
    "Closed",
    "Resolved",
}
DEFAULT_TAPD_FIELDS = {
    "task_owner": "owner",
    "bug_owner": "current_owner",
    "story_pm": "owner",
}


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
                    "iteration_id": str(iteration["iteration_id"]),
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
