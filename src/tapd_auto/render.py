"""HTML、Markdown、PNG 报表输出。"""

from __future__ import annotations

import html
import json
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
        f"缺陷：未解决 {summary['bugs_open']}，今日新增 {summary['bugs_new']}，今日关闭 {summary['bugs_closed']}",
        "",
    ]
    for image_url in image_urls or []:
        lines.extend([f"![日报图]({image_url})", ""])
    lines.extend([f"[查看交互报表]({report_url})", ""])
    return "\n".join(lines)


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


def write_field_info(field_info: dict[str, Any], output_dir: Path) -> Path:
    path = output_dir / "field-info.json"
    path.write_text(json.dumps(field_info, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def render_html(report: dict[str, Any]) -> str:
    project_sections = "\n".join(render_project(project) for project in report["projects"])
    summary = report["summary"]
    summary_metrics = render_html_summary_metrics(summary)
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
    section {{ padding: 18px; margin-top: 16px; }}
    .project-head, .iteration-head, .panel-head {{ display: flex; justify-content: space-between; gap: 14px; align-items: center; }}
    .iteration {{ margin-top: 18px; padding-top: 16px; border-top: 1px solid #e6ebf1; }}
    .work-grid {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(320px, .8fr); gap: 14px; margin-top: 14px; align-items: start; }}
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
    @media (max-width: 920px) {{ .summary {{ grid-template-columns: repeat(3, 1fr); }} .work-grid {{ grid-template-columns: 1fr; }} header {{ align-items: flex-start; flex-direction: column; }} }}
    @media (max-width: 560px) {{ main {{ padding: 20px 12px; }} .summary {{ grid-template-columns: repeat(2, 1fr); }} .project-head, .iteration-head, .panel-head {{ align-items: flex-start; flex-direction: column; }} th, td {{ padding: 9px 8px; }} }}
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


def render_html_summary_metrics(summary: dict[str, Any]) -> str:
    metrics = [
        ("项目", summary["project_count"]),
        ("迭代", summary["iteration_count"]),
        ("人员", summary["member_count"]),
        ("未解决缺陷", summary["bugs_open"]),
        ("今日新增缺陷", summary["bugs_new"]),
        ("今日关闭缺陷", summary["bugs_closed"]),
    ]
    return "\n".join(f"""<div class="metric"><span>{html.escape(str(label))}</span><strong>{html.escape(str(value))}</strong></div>""" for label, value in metrics)


def render_project(project: dict[str, Any]) -> str:
    iterations = "\n".join(render_iteration(iteration) for iteration in project["iterations"])
    return f"""<section>
  <div class="project-head">
    <h2>{html.escape(project["name"])}</h2>
    <div class="subtle">workspace_id: {html.escape(project["workspace_id"])}</div>
  </div>
  {iterations}
</section>"""


def render_iteration(iteration: dict[str, Any]) -> str:
    member_table = render_member_table(iteration["members"])
    requirements = render_requirements(iteration["requirements"])
    return f"""<div class="iteration">
  <div class="iteration-head">
    <h3>{html.escape(iteration["name"])}</h3>
    <div class="subtle">iteration_id: {html.escape(iteration["iteration_id"])}</div>
  </div>
  <div class="work-grid">
    <div class="panel">
      <div class="panel-head"><h4>团队缺陷</h4><div class="subtle">{len(iteration["members"])} 人</div></div>
      {member_table}
    </div>
    <div class="panel">
      <div class="panel-head"><h4>需求排期</h4><div class="subtle">{len(iteration["requirements"])} 条</div></div>
      {requirements}
    </div>
  </div>
</div>"""


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
    <thead><tr><th>成员</th><th>缺陷</th></tr></thead>
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
        return '<span class="pill pill-muted">缺陷不展示</span>'
    return (
        f'<span class="pill pill-warn">未解 {member["bugs_open"]}</span>'
        f'<span class="pill pill-info">新增 {member["bugs_new"]}</span>'
        f'<span class="pill pill-ok">已关 {member["bugs_closed"]}</span>'
    )


def member_bug_metrics_hidden(member: dict[str, Any]) -> bool:
    hidden_users = {"Tora", "nianqiongyue"}
    hidden_names = {"黄寅子", "粘琼月"}
    return bool(member.get("hide_bug_metrics")) or member.get("tapd_user") in hidden_users or member.get("name") in hidden_names


def render_requirements(requirements: list[dict[str, Any]]) -> str:
    if not requirements:
        return '<p class="empty">暂无产品需求排期。</p>'
    rows = "\n".join(
        f"""<tr>
  <td>{render_requirement_link(item)}</td>
  <td>{escape_html_value(item["product_manager"])}</td>
  <td>{escape_html_value(item["status"])}</td>
  <td>{escape_html_value(item["start"])}</td>
  <td>{escape_html_value(item["end"])}</td>
</tr>"""
        for item in requirements
    )
    return f"""<div class="table-wrap">
  <table class="requirement-table">
    <thead><tr><th>需求</th><th>产品经理</th><th>状态</th><th>开始</th><th>结束</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""


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
            y = draw_png_requirements(draw, iteration["requirements"], margin + 24, y, width - margin * 2 - 48, body_font, small_font)
            y += 18
        y = section_top + section_height + 22

    cropped = image.crop((0, 0, width, min(y + 20, estimated_height)))
    output_path = output_dir / "summary-1.png"
    cropped.save(output_path)
    return output_path


def estimate_png_height(report: dict[str, Any]) -> int:
    height = 190
    for project in report["projects"]:
        height += estimate_project_height(project) + 22
    return max(height + 40, 520)


def estimate_project_height(project: dict[str, Any]) -> int:
    height = 78
    for iteration in project["iterations"]:
        member_rows = max(1, (len(iteration["members"]) + 5) // 6)
        requirement_rows = max(1, len(iteration["requirements"]))
        height += 42 + member_rows * 112 + 34 + requirement_rows * 30 + 34
    return height


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
        ("今日关闭缺陷", summary["bugs_closed"]),
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
        if member_bug_metrics_hidden(member):
            draw.text((left + 10, top + 52), "缺陷不展示", fill="#64748b", font=small_font)
            continue
        draw.text((left + 10, top + 48), f"未解 {member['bugs_open']} / 新增 {member['bugs_new']}", fill="#a23b26", font=small_font)
        draw.text((left + 10, top + 72), f"已关 {member['bugs_closed']}", fill="#176b43", font=small_font)
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
    draw.text((x, y), "产品需求排期", fill="#172033", font=body_font)
    y += 30
    if not requirements:
        draw.text((x, y), "暂无产品需求排期。", fill="#64748b", font=small_font)
        return y + 28

    for requirement in requirements[:8]:
        title = truncate_text(requirement["title"], 32)
        line = f"{title}｜{requirement['product_manager']}｜{requirement['status']}｜{requirement['start']} - {requirement['end']}"
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
