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
        f"任务整体完成率：{summary['task_completion_rate']}%",
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
        height += 42 + member_rows * 210 + 34 + requirement_rows * 30 + 34
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
        ("任务完成率", f"{summary['task_completion_rate']}%"),
        ("未解决缺陷", summary["bugs_open"]),
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
    columns = min(6, max(1, len(members)))
    cell_width = width // columns
    row_height = 210
    for index, member in enumerate(members):
        row = index // columns
        col = index % columns
        left = x + col * cell_width
        top = y + row * row_height
        rate = int(member["task_completion_rate"])
        bar_height = max(4, int(rate / 100 * 105))
        bar_left = left + cell_width // 2 - 20
        bar_bottom = top + 122
        color = "#d94841" if member["bugs_open"] > 0 else "#2f80ed"
        draw.rectangle((bar_left, top + 16, bar_left + 40, bar_bottom), fill="#e6edf7")
        draw.rounded_rectangle((bar_left, bar_bottom - bar_height, bar_left + 40, bar_bottom), radius=5, fill=color)
        draw.text((left + 10, top + 134), member["name"], fill="#172033", font=body_font)
        draw.text((left + 10, top + 160), f"任务 {member['task_done']}/{member['task_total']} · {rate}%", fill="#475569", font=small_font)
        draw.text(
            (left + 10, top + 182),
            f"缺陷 已关 {member['bugs_closed']} / 未解 {member['bugs_open']} / 新增 {member['bugs_new']}",
            fill="#475569",
            font=small_font,
        )
    rows = max(1, (len(members) + columns - 1) // columns)
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
