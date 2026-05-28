# TAPD Daily Review Implementation Plan

> **执行约定：** 文件名保持英文，所有说明、注释、配置解释和 commit message 尽量使用中文。仓库继续保持扁平结构，正式文件直接放在项目根目录。

**目标：** 先搭建一条可以本地运行、可配置、可验证的 TAPD 每日复盘链路骨架，后续补充项目、迭代、成员、钉钉机器人和真实 TAPD 字段映射后即可接入真实数据。

**架构：** 第一版使用单个 Python 入口文件承载配置读取、环境变量读取、数据模型、日报聚合、HTML/Markdown 输出和命令行入口。TAPD API 客户端先封装认证和请求边界，但默认不强依赖真实工作区信息，避免在配置未补齐时误请求。生成结果输出到 `public/reports/<日期>/`，该目录不进入 Git。

**技术栈：** Python 3.12、PyYAML、requests、unittest、标准库 pathlib/dataclasses/html/json。

---

## 文件结构

- `src/tapd_auto/`：生产代码包，按配置、TAPD 客户端、聚合、渲染、钉钉通知和 CLI 分模块。
- `tapd_daily.py`：兼容入口，旧命令仍可使用。
- `tests/`：标准库单元测试，覆盖配置校验、任务/缺陷/需求聚合、输出路径、入口和 Markdown 摘要。
- `configs/config.example.yaml`：可提交的示例配置，不包含任何真实 token。
- `README.md`：中文使用说明，说明如何补配置、运行脚本、查看输出、后续接入钉钉。
- `requirements.txt`：运行依赖。
- `.env`：本地敏感配置，只保存在本机，不提交。

## 任务 1：保存本地敏感配置

- [x] 在 `.env` 保存 `TAPD_ACCESS_TOKEN`。
- [x] 保持 `.env` 在 `.gitignore` 中，确保 token 不进入 Git。
- [x] 预留 `DINGTALK_WEBHOOK` 和 `DINGTALK_SECRET`，后续补齐。

## 任务 2：写第一轮失败测试

- [x] 新建 `test_tapd_daily.py`。
- [x] 测试配置读取会解析项目、迭代、成员和输出目录。
- [x] 测试聚合逻辑会按人员计算未解决、今日新增、当日关闭，并保留产品总需求合并规则。
- [x] 测试 Markdown 摘要包含日期、项目数、迭代数、人员数和缺陷统计。
- [x] 运行 `python3 -m unittest test_tapd_daily.py -v`，确认因为 `tapd_daily.py` 尚不存在而失败。

## 任务 3：实现最小可运行链路

- [x] 新建 `tapd_daily.py`。
- [x] 实现 `.env` 读取，但不打印 token。
- [x] 实现 YAML 配置读取和基础校验。
- [x] 实现内存数据聚合函数，先支持测试数据和后续 API 数据共用同一模型。
- [x] 实现 HTML 和 Markdown 渲染。
- [x] 实现 CLI：`python3 tapd_daily.py --config configs/config.example.yaml --date 2026-05-26 --dry-run`。

## 任务 4：补充示例配置和说明

- [x] 新建 `configs/config.example.yaml`，保留真实项目、迭代、当前账号成员和后续成员补充位置。
- [x] 新建 `requirements.txt`。
- [x] 新建 `README.md`，用中文写清楚本地运行、配置补充、输出位置和后续待补信息。

## 任务 5：验证、提交和推送

- [x] 运行 `python3 -m unittest discover -s tests -v`。
- [x] 运行 `python3 tapd_daily.py --config configs/config.example.yaml --date 2026-05-26 --dry-run`。
- [ ] 检查 `git status --short --branch`，确认 `.env` 和 `public/reports/` 未进入提交。
- [ ] 使用中文 commit message 提交。
- [ ] 推送到 `origin/main`。

## 任务 6：同步接口调研并制定规则

- [x] 阅读 `docs/research/tapd-dingtalk-api-research.md`。
- [x] 新增 `docs/operations/interface-rules.md`，沉淀 TAPD 鉴权、分页、字段映射、状态映射和钉钉 Webhook 规则。
- [x] 更新 `configs/config.example.yaml`，将缺陷归属字段默认设为 `current_owner`，需求产品经理字段默认设为 `owner`。
- [x] 更新生产代码，支持配置化字段映射、TAPD 响应状态校验、分页读取、钉钉加签和 Markdown payload。
- [x] 更新 `README.md` 和设计文档，说明接口规则和后续待确认项。

## 任务 7：补全真实同步和通知边界

- [x] 新增 live 模式测试，覆盖字段发现、迭代校验、任务/缺陷/需求列表拉取。
- [x] 新增 token 校验测试，live 模式缺少 `TAPD_ACCESS_TOKEN` 时明确失败。
- [x] 新增钉钉发送测试，覆盖加签 URL、Markdown payload 和通知配置。
- [x] 实现 `--live`，从 TAPD OpenAPI 拉取真实数据。
- [x] 实现 `--send-dingtalk`，仅在显式传入时发送钉钉消息。
- [x] 实现 `summary-1.png` 日报图输出，并在 Markdown 中嵌入图片 URL。
- [x] live 模式写入 `field-info.json`，用于核对工作区字段和状态枚举。

## 任务 8：整理为生产级工具结构

- [x] 将生产代码拆分到 `src/tapd_auto/`。
- [x] 将测试迁移到 `tests/`，并新增 `python3 -m tapd_auto` 入口测试。
- [x] 将配置迁移到 `configs/`。
- [x] 将设计、接口规则和调研资料迁移到 `docs/`。
- [x] 新增 `pyproject.toml`，支持 `pip install -e .` 和 `tapd-daily` 命令。
- [x] 新增 `.env.example`、`scripts/run_daily.sh` 和 `scripts/crontab.example`。
- [x] 新增 `docs/operations/production-runbook.md`，说明部署、验证、定时任务和回滚。
- [x] 新增 `scripts/preview.sh` 和预览 URL 测试，用于本地查看生成报表。
