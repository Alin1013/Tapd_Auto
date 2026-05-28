"""HTML、Markdown、PNG 报表输出。"""

from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def public_report_url(config: dict[str, Any], report: dict[str, Any]) -> str:
    return public_report_asset_url(config["report"]["public_base_url"], report["date"], "index.html")


def public_report_asset_url(public_base_url: str, report_date: str, filename: str) -> str:
    return f"{public_base_url.rstrip('/')}/reports/{report_date}/{filename}"


def render_markdown(report: dict[str, Any], report_url: str, image_urls: list[str] | None = None) -> str:
    summary = report["summary"]
    lines = [
        f"### TAPD 每日复盘 {report['date']}",
        "",
        f"今日统计：{summary['project_count']} 个项目 / {summary['iteration_count']} 个迭代 / {summary['member_count']} 人",
        f"今日缺陷：未解决 {summary['bugs_open']}，今日新增 {summary['bugs_new']}，当日关闭 {summary['bugs_closed']}",
        "",
    ]
    for image_url in image_urls or []:
        lines.extend([f"![日报图]({image_url})", ""])
    lines.extend([f"[查看交互报表]({report_url})", ""])
    return "\n".join(lines)


def render_dingtalk_markdown(report: dict[str, Any], report_url: str, image_urls: list[str] | None = None) -> str:
    """生成钉钉推送用 Markdown：截图优先，然后按成员输出复盘解析。"""

    summary = report["summary"]
    lines = [
        f"### TAPD 每日复盘 {report['date']}",
        "",
    ]
    for image_url in image_urls or []:
        lines.extend([f"![当日复盘截图]({image_url})", ""])
    lines.extend(
        [
            f"今日统计：{summary['project_count']} 个项目 / {summary['iteration_count']} 个迭代 / {summary['member_count']} 人",
            f"今日缺陷：未解决 {summary['bugs_open']}，今日新增 {summary['bugs_new']}，当日关闭 {summary['bugs_closed']}",
            "",
            f"[查看交互报表]({report_url})",
            "",
            "#### 成员复盘",
            "",
        ]
    )
    member_lines = render_member_review_lines(report)
    if member_lines:
        for line in member_lines:
            lines.extend([line, ""])
    else:
        lines.extend(["当前范围内暂无成员复盘数据。", ""])
    return "\n".join(lines)


def render_member_review_lines(report: dict[str, Any]) -> list[str]:
    reviews: dict[str, dict[str, Any]] = {}
    for project in report.get("projects", []):
        for iteration in project.get("iterations", []):
            scope_name = f"{project.get('name', '')} / {iteration.get('name', '')}".strip(" /")
            for member in iteration.get("members", []):
                if member_bug_metrics_hidden(member):
                    continue
                key = str(member.get("tapd_user") or member.get("name") or "")
                if not key:
                    continue
                review = reviews.setdefault(
                    key,
                    {
                        "name": member.get("name", key),
                        "dingtalk_mobile": member.get("dingtalk_mobile", ""),
                        "bugs_open": 0,
                        "bugs_new": 0,
                        "bugs_closed": 0,
                        "scopes": [],
                    },
                )
                review["bugs_open"] += int(member.get("bugs_open", 0))
                review["bugs_new"] += int(member.get("bugs_new", 0))
                review["bugs_closed"] += int(member.get("bugs_closed", 0))
                if scope_name and scope_name not in review["scopes"]:
                    review["scopes"].append(scope_name)
                if not review["dingtalk_mobile"] and member.get("dingtalk_mobile"):
                    review["dingtalk_mobile"] = member.get("dingtalk_mobile")
    return [format_member_review(review) for review in reviews.values()]


def format_member_review(review: dict[str, Any]) -> str:
    name = str(review["name"])
    mobile = str(review.get("dingtalk_mobile", "")).strip()
    mention = f"@{mobile}" if mobile else f"@{name}"
    scope = "、".join(review.get("scopes", [])) or "当前范围"
    bugs_open = int(review.get("bugs_open", 0))
    bugs_new = int(review.get("bugs_new", 0))
    bugs_closed = int(review.get("bugs_closed", 0))
    if bugs_new or bugs_closed:
        analysis = "今日有缺陷流转，建议优先确认新增问题和关闭质量。"
    elif bugs_open:
        analysis = "当前仍有未解决缺陷，需要继续推进处理。"
    else:
        analysis = "当前范围内暂无缺陷压力。"
    return (
        f"{mention} {name}：{scope}，未解决 {bugs_open}，今日新增 {bugs_new}，"
        f"当日关闭 {bugs_closed}。{analysis}"
    )


def write_report(report: dict[str, Any], output_root: Path | str, public_base_url: str) -> Path:
    output_dir = Path(output_root) / report["date"]
    output_dir.mkdir(parents=True, exist_ok=True)

    report_url = public_report_asset_url(public_base_url, report["date"], "index.html")
    image_url = public_report_asset_url(public_base_url, report["date"], "summary-1.png")
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary_png(report, output_dir)
    (output_dir / "summary.md").write_text(render_markdown(report, report_url, image_urls=[image_url]), encoding="utf-8")
    (output_dir / "index.html").write_text(render_html(report), encoding="utf-8")
    return output_dir


def write_page_screenshot(
    html_path: Path | str,
    output_dir: Path | str,
    browser_path: str | None = None,
    filename: str = "page-screenshot.png",
    window_size: str = "1280,1800",
    timeout_seconds: int = 15,
) -> Path:
    """用无头浏览器生成 HTML 页面截图。"""

    browser = browser_path or find_browser_path()
    if not browser:
        raise RuntimeError("未找到 Chrome/Chromium，无法生成页面实时截图。")

    html_file = Path(html_path).resolve()
    output_path = Path(output_dir) / filename
    with tempfile.TemporaryDirectory(prefix="tapd-auto-chrome-") as user_data_dir:
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-background-networking",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=1000",
            "--no-first-run",
            "--no-default-browser-check",
            "--hide-scrollbars",
            "--allow-file-access-from-files",
            f"--user-data-dir={user_data_dir}",
            f"--window-size={window_size}",
            f"--screenshot={output_path}",
            html_file.as_uri(),
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            if not output_path.exists():
                raise
    if not output_path.exists():
        raise RuntimeError(f"页面截图生成失败：{output_path}")
    return output_path


def find_browser_path() -> str:
    env_path = os.environ.get("TAPD_AUTO_BROWSER_PATH", "").strip()
    if env_path:
        return env_path
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "google-chrome",
        "chromium",
        "chromium-browser",
    ]
    for candidate in candidates:
        candidate_path = Path(candidate)
        if candidate_path.is_absolute() and candidate_path.exists():
            return str(candidate_path)
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return ""


def write_field_info(field_info: dict[str, Any], output_dir: Path) -> Path:
    path = output_dir / "field-info.json"
    path.write_text(json.dumps(field_info, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def render_html(report: dict[str, Any]) -> str:
    project_sections = "\n".join(render_project(project) for project in report["projects"])
    summary_metrics = render_html_summary_metrics(report)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>TAPD 每日复盘 {html.escape(report["date"])}</title>
  <style>
    :root {{ color-scheme: light; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2933; background: #f4f6f8; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 28px 20px 44px; }}
    header {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-end; margin-bottom: 18px; }}
    h1, h2, h3, h4 {{ margin: 0; letter-spacing: 0; }}
    h1 {{ font-size: 30px; line-height: 1.18; }}
    h2 {{ font-size: 22px; }}
    h3 {{ font-size: 18px; }}
    h4 {{ font-size: 15px; color: #334155; }}
    .subtle, .meta {{ color: #667085; font-size: 13px; line-height: 1.45; }}
    .summary {{ display: grid; grid-template-columns: repeat(6, minmax(132px, 1fr)); gap: 12px; margin: 18px 0 18px; }}
    .metric, section, .panel {{ background: #fff; border: 1px solid #d9e1ea; border-radius: 8px; }}
    .metric {{ padding: 14px 16px; min-height: 86px; }}
    .metric span {{ display: block; color: #667085; font-size: 13px; }}
    .metric strong {{ display: block; font-size: 25px; line-height: 1; margin-top: 10px; color: #111827; }}
    .metric-text strong {{ font-size: 16px; line-height: 1.4; white-space: normal; }}
    .metric-project {{ grid-column: span 2; }}
    .metric-iterations {{ grid-column: span 4; }}
    section {{ padding: 18px; margin-top: 16px; }}
    .project-head, .iteration-head, .panel-head {{ display: flex; justify-content: space-between; gap: 14px; align-items: center; }}
    .iteration-list {{ display: grid; gap: 14px; margin-top: 14px; }}
    .iteration-card {{ border: 1px solid #d9e1ea; border-radius: 8px; padding: 14px; background: #fff; }}
    .iteration-grid {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(320px, .8fr); gap: 14px; margin-top: 12px; align-items: start; }}
    .defect-metrics {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 10px; margin: 10px 0 12px; }}
    .mini-metric {{ background: #f8fafc; border: 1px solid #e0e7ef; border-radius: 8px; padding: 10px 12px; }}
    .mini-metric span {{ display: block; color: #667085; font-size: 12px; }}
    .mini-metric strong {{ display: block; color: #111827; font-size: 20px; margin-top: 4px; }}
    .panel {{ padding: 14px; overflow: hidden; }}
    .table-wrap {{ overflow-x: auto; margin-top: 10px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 11px 10px; border-bottom: 1px solid #e6ebf1; text-align: left; vertical-align: middle; white-space: nowrap; }}
    th {{ color: #475467; background: #f8fafb; font-weight: 700; }}
    tbody tr:hover {{ background: #f9fbfd; }}
    .member-name {{ font-weight: 700; color: #111827; }}
    .role {{ color: #667085; font-size: 12px; margin-top: 2px; }}
    .pill {{ display: inline-flex; align-items: center; min-height: 24px; padding: 3px 8px; border-radius: 999px; font-size: 12px; margin-right: 5px; border: 1px solid transparent; }}
    .pill-ok {{ color: #176b43; background: #eaf7ef; border-color: #c7ead2; }}
    .pill-warn {{ color: #a23b26; background: #fff1e8; border-color: #ffd5bd; }}
    .pill-info {{ color: #315a94; background: #eef5ff; border-color: #d4e6ff; }}
    .pill-muted {{ color: #667085; background: #f2f4f7; border-color: #d0d5dd; }}
    .empty {{ margin: 12px 0 0; padding: 14px; border: 1px dashed #ccd6e0; border-radius: 8px; color: #667085; background: #fbfcfd; }}
    a {{ color: #1769c2; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    @media (max-width: 920px) {{ .summary {{ grid-template-columns: repeat(3, 1fr); }} .metric-project, .metric-iterations {{ grid-column: 1 / -1; }} .iteration-grid {{ grid-template-columns: 1fr; }} .defect-metrics {{ grid-template-columns: repeat(2, 1fr); }} header {{ align-items: flex-start; flex-direction: column; }} }}
    @media (max-width: 560px) {{ main {{ padding: 20px 12px; }} .summary {{ grid-template-columns: repeat(2, 1fr); }} .defect-metrics {{ grid-template-columns: 1fr; }} .project-head, .iteration-head, .panel-head {{ align-items: flex-start; flex-direction: column; }} th, td {{ padding: 9px 8px; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>TAPD 每日复盘 {html.escape(report["date"])}</h1>
      <div class="subtle">按项目、迭代和团队成员聚合缺陷、需求信息</div>
    </div>
    <div class="subtle">{html.escape(report["timezone"])}</div>
  </header>
  <div class="summary">{summary_metrics}</div>
  {project_sections}
</main>
</body>
</html>
"""


def render_html_summary_metrics(report: dict[str, Any]) -> str:
    summary = report["summary"]
    scope = report_scope_summary(report)
    scope_metrics = [
        ("项目名称", scope["projects"], "metric metric-text metric-project"),
        ("迭代名称", scope["iterations"], "metric metric-text metric-iterations"),
    ]
    metrics = [
        ("项目", summary["project_count"]),
        ("迭代", summary["iteration_count"]),
        ("人员", summary["member_count"]),
        ("未解决缺陷", summary["bugs_open"]),
        ("今日新增缺陷", summary["bugs_new"]),
        ("当日关闭缺陷", summary["bugs_closed"]),
    ]
    scope_cards = "\n".join(
        f"""<div class="{css_class}"><span>{html.escape(str(label))}</span><strong>{html.escape(str(value))}</strong></div>"""
        for label, value, css_class in scope_metrics
    )
    metric_cards = "\n".join(
        f"""<div class="metric"><span>{html.escape(str(label))}</span><strong>{html.escape(str(value))}</strong></div>"""
        for label, value in metrics
    )
    return "\n".join([scope_cards, metric_cards])


def report_scope_summary(report: dict[str, Any]) -> dict[str, str]:
    project_names = unique_non_empty(project.get("name") for project in report.get("projects", []))
    iteration_names = unique_non_empty(
        iteration.get("name")
        for project in report.get("projects", [])
        for iteration in project.get("iterations", [])
    )
    return {
        "projects": "、".join(project_names) or "-",
        "iterations": "、".join(iteration_names) or "-",
    }


def unique_non_empty(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def render_project(project: dict[str, Any]) -> str:
    iterations = "\n".join(render_iteration(iteration) for iteration in project["iterations"])
    return f"""<section>
  <div class="project-head">
    <h2>{html.escape(project["name"])}</h2>
  </div>
  <div class="iteration-list">{iterations}</div>
</section>"""


def render_iteration(iteration: dict[str, Any]) -> str:
    visible_members = [member for member in iteration["members"] if not member_bug_metrics_hidden(member)]
    defects = render_defect_panel(visible_members, iteration.get("summary"))
    product_requirements = render_product_requirements_panel(iteration_product_requirements(iteration))
    return f"""<div class="iteration-card">
  <div class="iteration-head">
    <h3>{html.escape(iteration["name"])}</h3>
  </div>
  <div class="iteration-grid">
    {defects}
    {product_requirements}
  </div>
</div>"""


def render_product_requirements_panel(requirements: list[dict[str, Any]]) -> str:
    return f"""<div class="panel">
  <div class="panel-head"><h4>产品总需求</h4><div class="subtle">{len(requirements)} 条</div></div>
  {render_requirements(requirements, empty_message="暂无产品总需求。")}
</div>"""


def render_defect_panel(members: list[dict[str, Any]], summary: dict[str, Any] | None = None) -> str:
    summary = summary or summarize_visible_members(members)
    metrics = [
        ("当前成员", summary["member_count"]),
        ("未解决", summary["bugs_open"]),
        ("今日新增", summary["bugs_new"]),
        ("当日关闭", summary["bugs_closed"]),
    ]
    metric_cards = "\n".join(
        f"""<div class="mini-metric"><span>{html.escape(str(label))}</span><strong>{html.escape(str(value))}</strong></div>"""
        for label, value in metrics
    )
    return f"""<div class="panel">
  <div class="panel-head"><h4>今日缺陷</h4><div class="subtle">按当天时间统计</div></div>
  <div class="defect-metrics">{metric_cards}</div>
  {render_member_table(members)}
</div>"""


def summarize_visible_members(members: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "member_count": len(members),
        "bugs_open": sum(int(member["bugs_open"]) for member in members),
        "bugs_new": sum(int(member["bugs_new"]) for member in members),
        "bugs_closed": sum(int(member["bugs_closed"]) for member in members),
    }


def render_member_table(members: list[dict[str, Any]]) -> str:
    if not members:
        return '<p class="empty">暂无成员数据。</p>'
    ordered_members = sorted(
        members,
        key=lambda member: (
            member_bug_metrics_hidden(member),
            -int(member["bugs_open"]),
            -int(member["bugs_new"]),
            -int(member["bugs_closed"]),
            member["name"],
        ),
    )
    rows = "\n".join(render_member_row(member) for member in ordered_members)
    return f"""<div class="table-wrap">
  <table class="member-table">
    <thead><tr><th>成员</th><th>今日缺陷</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""


def render_member_row(member: dict[str, Any]) -> str:
    name = html.escape(member["name"])
    role = html.escape(member.get("role", "") or "团队成员")
    link_start = f'<a href="{html.escape(member["tapd_report_url"])}" target="_blank" rel="noreferrer">' if member["tapd_report_url"] else ""
    link_end = "</a>" if member["tapd_report_url"] else ""
    bug_metrics = render_member_bug_metrics(member)
    return f"""<tr>
  <td><div class="member-name">{link_start}{name}{link_end}</div><div class="role">{role}</div></td>
  <td>{bug_metrics}</td>
</tr>"""


def render_member_bug_metrics(member: dict[str, Any]) -> str:
    if member_bug_metrics_hidden(member):
        return ""
    return (
        f'<span class="pill pill-warn">未解 {member["bugs_open"]}</span>'
        f'<span class="pill pill-info">新增 {member["bugs_new"]}</span>'
        f'<span class="pill pill-ok">当日关闭 {member["bugs_closed"]}</span>'
    )


def member_bug_metrics_hidden(member: dict[str, Any]) -> bool:
    hidden_users = {"Tora", "nianqiongyue"}
    hidden_names = {"黄寅子", "粘琼月"}
    return bool(member.get("hide_bug_metrics")) or member.get("tapd_user") in hidden_users or member.get("name") in hidden_names


def render_requirements(requirements: list[dict[str, Any]], empty_message: str = "暂无产品总需求。") -> str:
    if not requirements:
        return f'<p class="empty">{html.escape(empty_message)}</p>'
    rows = "\n".join(
        f"""<tr>
  <td>{render_requirement_link(item)}</td>
  <td>{escape_html_value(item["product_manager"])}</td>
  <td>{escape_html_value(item["status"])}</td>
</tr>"""
        for item in requirements
    )
    return f"""<div class="table-wrap">
  <table class="requirement-table">
    <thead><tr><th>需求</th><th>产品经理</th><th>状态</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""


def iteration_product_requirements(iteration: dict[str, Any]) -> list[dict[str, Any]]:
    if "product_requirements" in iteration:
        return list(iteration["product_requirements"])
    return [
        requirement
        for requirement in iteration.get("requirements", [])
        if str(requirement.get("status", "")).strip() not in {"发布", "已发布", "status_21"}
    ]


def render_requirement_link(item: dict[str, Any]) -> str:
    title = escape_html_value(item["title"])
    if item["url"]:
        return f'<a href="{escape_html_value(item["url"])}" target="_blank" rel="noreferrer">{title}</a>'
    return title


def escape_html_value(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def write_summary_png(report: dict[str, Any], output_dir: Path) -> Path:
    width = 1200
    margin = 48
    y = 36
    estimated_height = estimate_png_height(report)
    image = Image.new("RGB", (width, estimated_height), "#f6f8fb")
    draw = ImageDraw.Draw(image)

    title_font = load_font(38, bold=True)
    h2_font = load_font(26, bold=True)
    h3_font = load_font(20, bold=True)
    body_font = load_font(17)
    small_font = load_font(14)

    draw.text((margin, y), f"TAPD 每日复盘 {report['date']}", fill="#172033", font=title_font)
    y += 64
    y = draw_png_scope_summary(draw, report, margin, y, width - margin * 2, body_font, small_font)
    y += 14
    y = draw_png_summary_metrics(draw, report["summary"], margin, y, width - margin * 2, body_font, h2_font)
    y += 24

    for project in report["projects"]:
        section_top = y
        section_height = estimate_project_height(project)
        draw.rounded_rectangle((margin, section_top, width - margin, section_top + section_height), radius=12, fill="#ffffff", outline="#dfe5ee")
        y += 22
        draw.text((margin + 24, y), project["name"], fill="#172033", font=h2_font)
        y += 42
        for iteration in project["iterations"]:
            draw.text((margin + 24, y), iteration["name"], fill="#334155", font=h3_font)
            y += 36
            y = draw_png_members(draw, iteration["members"], margin + 24, y, width - margin * 2 - 48, body_font, small_font)
            y += 14
            y = draw_png_requirements(
                draw,
                iteration_product_requirements(iteration),
                margin + 24,
                y,
                width - margin * 2 - 48,
                body_font,
                small_font,
            )
            y += 18
        y = section_top + section_height + 22

    cropped = image.crop((0, 0, width, min(y + 20, estimated_height)))
    output_path = output_dir / "summary-1.png"
    cropped.save(output_path)
    return output_path


def estimate_png_height(report: dict[str, Any]) -> int:
    height = 292
    for project in report["projects"]:
        height += estimate_project_height(project) + 22
    return max(height + 40, 520)


def estimate_project_height(project: dict[str, Any]) -> int:
    height = 78
    for iteration in project["iterations"]:
        member_rows = max(1, (len(iteration["members"]) + 5) // 6)
        requirement_rows = max(1, len(iteration_product_requirements(iteration)))
        height += 42 + member_rows * 112 + 34 + requirement_rows * 30 + 34
    return height


def draw_png_scope_summary(
    draw: ImageDraw.ImageDraw,
    report: dict[str, Any],
    x: int,
    y: int,
    width: int,
    body_font: ImageFont.ImageFont,
    small_font: ImageFont.ImageFont,
) -> int:
    scope = report_scope_summary(report)
    card_height = 88
    draw.rounded_rectangle((x, y, x + width, y + card_height), radius=10, fill="#ffffff", outline="#dfe5ee")
    draw.text((x + 16, y + 14), "项目名称", fill="#64748b", font=small_font)
    draw.text((x + 100, y + 12), truncate_text(scope["projects"], 54), fill="#172033", font=body_font)
    draw.text((x + 16, y + 50), "迭代名称", fill="#64748b", font=small_font)
    draw.text((x + 100, y + 48), truncate_text(scope["iterations"], 86), fill="#172033", font=body_font)
    return y + card_height


def draw_png_summary_metrics(
    draw: ImageDraw.ImageDraw,
    summary: dict[str, Any],
    x: int,
    y: int,
    width: int,
    body_font: ImageFont.ImageFont,
    value_font: ImageFont.ImageFont,
) -> int:
    metrics = [
        ("项目", summary["project_count"]),
        ("迭代", summary["iteration_count"]),
        ("人员", summary["member_count"]),
        ("未解决缺陷", summary["bugs_open"]),
        ("今日新增缺陷", summary["bugs_new"]),
        ("当日关闭缺陷", summary["bugs_closed"]),
    ]
    gap = 12
    card_width = (width - gap * (len(metrics) - 1)) // len(metrics)
    for index, (label, value) in enumerate(metrics):
        left = x + index * (card_width + gap)
        draw.rounded_rectangle((left, y, left + card_width, y + 78), radius=10, fill="#ffffff", outline="#dfe5ee")
        draw.text((left + 16, y + 12), str(label), fill="#64748b", font=body_font)
        draw.text((left + 16, y + 38), str(value), fill="#172033", font=value_font)
    return y + 78


def draw_png_members(
    draw: ImageDraw.ImageDraw,
    members: list[dict[str, Any]],
    x: int,
    y: int,
    width: int,
    body_font: ImageFont.ImageFont,
    small_font: ImageFont.ImageFont,
) -> int:
    members = [member for member in members if not member_bug_metrics_hidden(member)]
    ordered_members = sorted(
        members,
        key=lambda member: (
            -int(member["bugs_open"]),
            -int(member["bugs_new"]),
            -int(member["bugs_closed"]),
            member["name"],
        ),
    )
    columns = min(6, max(1, len(ordered_members)))
    cell_width = width // columns
    row_height = 112
    for index, member in enumerate(ordered_members):
        row = index // columns
        col = index % columns
        left = x + col * cell_width
        top = y + row * row_height
        right = left + cell_width - 10
        draw.rounded_rectangle((left, top + 4, right, top + 96), radius=8, fill="#f8fafc", outline="#dfe5ee")
        draw.text((left + 10, top + 16), member["name"], fill="#172033", font=body_font)
        draw.text((left + 10, top + 48), f"未解 {member['bugs_open']} / 新增 {member['bugs_new']}", fill="#a23b26", font=small_font)
        draw.text((left + 10, top + 72), f"当日关闭 {member['bugs_closed']}", fill="#176b43", font=small_font)
    rows = max(1, (len(ordered_members) + columns - 1) // columns)
    return y + rows * row_height


def draw_png_requirements(
    draw: ImageDraw.ImageDraw,
    requirements: list[dict[str, Any]],
    x: int,
    y: int,
    width: int,
    body_font: ImageFont.ImageFont,
    small_font: ImageFont.ImageFont,
) -> int:
    draw.text((x, y), "产品总需求", fill="#172033", font=body_font)
    y += 30
    if not requirements:
        draw.text((x, y), "暂无产品总需求。", fill="#64748b", font=small_font)
        return y + 28

    for requirement in requirements[:8]:
        title = truncate_text(requirement["title"], 32)
        line = f"{title}｜{requirement['product_manager']}｜{requirement['status']}"
        draw.text((x, y), line, fill="#475569", font=small_font)
        y += 30
    if len(requirements) > 8:
        draw.text((x, y), f"还有 {len(requirements) - 8} 条需求，请查看 HTML 报表。", fill="#64748b", font=small_font)
        y += 30
    return y


def truncate_text(text: str, max_chars: int) -> str:
    text = str(text)
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1]}..."


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size, index=1 if bold else 0)
            except OSError:
                continue
    return ImageFont.load_default()
