"""日报展示范围筛选。"""

from __future__ import annotations

from typing import Any


def scoped_project_members(project: dict[str, Any]) -> list[dict[str, Any]]:
    """按项目 report_scope 过滤成员；未配置时保留全量成员。"""

    scope = project.get("report_scope", {})
    member_names = normalized_values(scope.get("member_names"))
    member_users = normalized_values(scope.get("member_users"))
    members = list(project.get("members", []))
    if not member_names and not member_users:
        return members
    return [
        member
        for member in members
        if matches_exact(member.get("name"), member_names) or matches_exact(member.get("tapd_user"), member_users)
    ]


def scoped_project_iterations(project: dict[str, Any], iterations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按项目 report_scope 过滤迭代；名称支持 V1.0.0 这类短名称包含匹配。"""

    scope = project.get("report_scope", {})
    iteration_names = normalized_values(scope.get("iteration_names"))
    iteration_ids = normalized_values(scope.get("iteration_ids"))
    if not iteration_names and not iteration_ids:
        return list(iterations)
    return [
        iteration
        for iteration in iterations
        if matches_contains(iteration.get("name"), iteration_names)
        or matches_exact(iteration.get("iteration_id"), iteration_ids)
        or matches_exact(iteration.get("id"), iteration_ids)
    ]


def normalized_values(values: Any) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, (str, int, float)):
        raw_values = [values]
    else:
        raw_values = values
    return {str(value).strip() for value in raw_values if str(value).strip()}


def matches_exact(value: Any, expected_values: set[str]) -> bool:
    if not expected_values or value is None:
        return False
    return str(value).strip() in expected_values


def matches_contains(value: Any, expected_values: set[str]) -> bool:
    if not expected_values or value is None:
        return False
    actual = str(value).strip().casefold()
    return any(expected.casefold() in actual for expected in expected_values)
