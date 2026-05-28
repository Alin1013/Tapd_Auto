"""日报聚合模型。"""

from __future__ import annotations

import re
from typing import Any

from .scope import scoped_project_iterations, scoped_project_members


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
HIDDEN_BUG_USERS = {"Tora", "nianqiongyue"}
HIDDEN_BUG_NAMES = {"黄寅子", "粘琼月"}


def build_report(config: dict[str, Any], raw_data: dict[str, list[dict[str, Any]]], report_date: str) -> dict[str, Any]:
    tapd_rules = get_tapd_rules(config)
    done_task_statuses = tapd_rules["task_done_statuses"]
    closed_bug_statuses = tapd_rules["bug_closed_statuses"]
    fields = tapd_rules["fields"]
    status_labels = tapd_rules["status_labels"]
    normalized_data = {
        data_type: [normalize_record(item) for item in items]
        for data_type, items in raw_data.items()
    }

    report_projects: list[dict[str, Any]] = []
    unique_users: set[str] = set()
    summary = {
        "project_count": 0,
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

        for iteration in scoped_project_iterations(project, project["iterations"]):
            member_results = []
            iteration_task_total = 0
            iteration_task_done = 0
            iteration_summary = {
                "member_count": 0,
                "bugs_closed": 0,
                "bugs_open": 0,
                "bugs_new": 0,
            }

            for member in scoped_project_members(project):
                user = member["tapd_user"]

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
                bugs_closed = sum(1 for bug in member_bugs if bug_closed_on_day(bug, closed_bug_statuses, report_date))
                bugs_open = sum(1 for bug in member_bugs if str(bug.get("status", "")) not in closed_bug_statuses)
                bugs_new = sum(1 for bug in member_bugs if is_same_day(bug.get("created"), report_date))
                hide_bug_metrics = member_hides_bug_metrics(member)

                iteration_task_total += task_total
                iteration_task_done += task_done
                if not hide_bug_metrics:
                    iteration_summary["member_count"] += 1
                    iteration_summary["bugs_closed"] += bugs_closed
                    iteration_summary["bugs_open"] += bugs_open
                    iteration_summary["bugs_new"] += bugs_new

                member_results.append(
                    {
                        "name": member["name"],
                        "tapd_user": user,
                        "role": member.get("role", ""),
                        "tapd_report_url": member.get("tapd_report_url", ""),
                        "dingtalk_mobile": first_non_empty_text(
                            member.get("dingtalk_mobile"),
                            member.get("mobile"),
                            member.get("phone"),
                        ),
                        "hide_bug_metrics": hide_bug_metrics,
                        "task_total": task_total,
                        "task_done": task_done,
                        "task_completion_rate": percent(task_done, task_total),
                        "bugs_closed": bugs_closed,
                        "bugs_open": bugs_open,
                        "bugs_new": bugs_new,
                    }
                )

            requirements = build_requirements(
                normalized_data.get("stories", []),
                project,
                iteration,
                product_managers,
                fields["story_pm"],
                status_labels.get("stories", {}),
            )
            product_requirements = build_product_requirements(requirements)
            active_product_requirements = [
                requirement for requirement in product_requirements if requirement_active_on_day(requirement, report_date)
            ]
            if not iteration_has_daily_activity(iteration_summary, active_product_requirements):
                continue

            summary["task_total"] += iteration_task_total
            summary["task_done"] += iteration_task_done
            summary["bugs_closed"] += iteration_summary["bugs_closed"]
            summary["bugs_open"] += iteration_summary["bugs_open"]
            summary["bugs_new"] += iteration_summary["bugs_new"]
            summary["iteration_count"] += 1
            unique_users.update(member["tapd_user"] for member in member_results)
            project_result["iterations"].append(
                {
                    "name": iteration["name"],
                    "iteration_id": str(iteration["iteration_id"]),
                    "summary": iteration_summary,
                    "members": member_results,
                    "requirements": requirements,
                    "product_requirements": product_requirements,
                }
            )

        if project_result["iterations"]:
            report_projects.append(project_result)

    summary["project_count"] = len(report_projects)
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
    status_labels: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    requirements = []
    status_labels = status_labels or {}
    for story in stories:
        if not is_in_scope(story, project, iteration):
            continue
        matched_user = first_matching_value(story, pm_field, set(product_managers.keys()))
        if matched_user is None:
            continue
        raw_status = str(story.get("v_status") or story.get("status", ""))
        requirements.append(
            {
                "title": first_non_empty_text(story.get("title"), story.get("name")),
                "product_manager": product_managers.get(matched_user, matched_user),
                "product_manager_user": matched_user,
                "status": status_labels.get(raw_status, raw_status),
                "start": first_non_empty_text(story.get("start"), story.get("begin")),
                "end": first_non_empty_text(story.get("end"), story.get("due")),
                "created": first_non_empty_text(story.get("created")),
                "modified": first_non_empty_text(story.get("modified")),
                "completed": first_non_empty_text(story.get("completed")),
                "url": first_non_empty_text(story.get("url")),
            }
        )
    return sorted(requirements, key=lambda item: (item["start"], item["end"], item["title"]))


def build_product_requirements(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        requirement
        for requirement in requirements
        if not requirement_is_published(requirement)
    ]


def iteration_has_daily_activity(summary: dict[str, int], product_requirements: list[dict[str, Any]]) -> bool:
    return any(int(summary[key]) > 0 for key in ["bugs_closed", "bugs_new"]) or bool(product_requirements)


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
        "status_labels": tapd.get("status_labels", {}),
    }


def member_hides_bug_metrics(member: dict[str, Any]) -> bool:
    return bool(member.get("hide_bug_metrics")) or member.get("tapd_user") in HIDDEN_BUG_USERS or member.get("name") in HIDDEN_BUG_NAMES


def bug_closed_on_day(bug: dict[str, Any], closed_statuses: set[str], report_date: str) -> bool:
    if str(bug.get("status", "")) not in closed_statuses:
        return False
    for field_name in ["closed", "resolved", "completed"]:
        if is_same_day(bug.get(field_name), report_date):
            return True
    return False


def requirement_active_on_day(requirement: dict[str, Any], report_date: str) -> bool:
    for field_name in ["created", "modified", "completed"]:
        if is_same_day(requirement.get(field_name), report_date):
            return True
    return date_range_includes(requirement.get("start"), requirement.get("end"), report_date)


def requirement_is_published(requirement: dict[str, Any]) -> bool:
    return str(requirement.get("status", "")).strip() in {"发布", "已发布", "status_21"}


def date_range_includes(start: Any, end: Any, report_date: str) -> bool:
    start_date = date_part(start)
    end_date = date_part(end)
    if start_date and end_date:
        return start_date <= report_date <= end_date
    if start_date:
        return start_date == report_date
    if end_date:
        return end_date == report_date
    return False


def date_part(value: Any) -> str:
    if value is None:
        return ""
    match = re.match(r"\d{4}-\d{2}-\d{2}", str(value))
    return match.group(0) if match else ""


def field_matches(item: dict[str, Any], field_name: str, user: str) -> bool:
    return first_matching_value(item, field_name, {user}) is not None


def first_matching_value(item: dict[str, Any], field_name: str, users: set[str]) -> str | None:
    for value_text in split_people(item.get(field_name)):
        if value_text in users:
            return value_text
    return None


def first_non_empty_text(*values: Any) -> str:
    for value in values:
        if value is not None and value != "":
            return str(value)
    return ""


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
