# TAPD Daily Review Implementation Plan

> **执行约定：** 文件名保持英文，所有说明、注释、配置解释和 commit message 尽量使用中文。仓库继续保持扁平结构，正式文件直接放在项目根目录。

**目标：** 先搭建一条可以本地运行、可配置、可验证的 TAPD 每日复盘链路骨架，后续补充项目、迭代、成员、钉钉机器人和真实 TAPD 字段映射后即可接入真实数据。

**架构：** 第一版使用单个 Python 入口文件承载配置读取、环境变量读取、数据模型、日报聚合、HTML/Markdown 输出和命令行入口。TAPD API 客户端先封装认证和请求边界，但默认不强依赖真实工作区信息，避免在配置未补齐时误请求。生成结果输出到 `public/reports/<日期>/`，该目录不进入 Git。

**技术栈：** Python 3.12、PyYAML、requests、unittest、标准库 pathlib/dataclasses/html/json。

---

## 文件结构

- `tapd_daily.py`：主程序，包含配置读取、环境变量读取、TAPD 客户端边界、日报聚合、HTML/Markdown 渲染和 CLI。
- `test_tapd_daily.py`：标准库单元测试，覆盖配置校验、任务/缺陷/需求聚合、输出路径和 Markdown 摘要。
- `config.example.yaml`：可提交的示例配置，不包含任何真实 token。
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
- [x] 测试聚合逻辑会按人员计算任务完成率、缺陷已关闭、未解决、新增。
- [x] 测试 Markdown 摘要包含日期、项目数、迭代数、人员数和缺陷统计。
- [x] 运行 `python3 -m unittest test_tapd_daily.py -v`，确认因为 `tapd_daily.py` 尚不存在而失败。

## 任务 3：实现最小可运行链路

- [x] 新建 `tapd_daily.py`。
- [x] 实现 `.env` 读取，但不打印 token。
- [x] 实现 YAML 配置读取和基础校验。
- [x] 实现内存数据聚合函数，先支持测试数据和后续 API 数据共用同一模型。
- [x] 实现 HTML 和 Markdown 渲染。
- [x] 实现 CLI：`python3 tapd_daily.py --config config.example.yaml --date 2026-05-26 --dry-run`。

## 任务 4：补充示例配置和说明

- [x] 新建 `config.example.yaml`，保留示例项目、迭代、成员和产品经理字段。
- [x] 新建 `requirements.txt`。
- [x] 新建 `README.md`，用中文写清楚本地运行、配置补充、输出位置和后续待补信息。

## 任务 5：验证、提交和推送

- [x] 运行 `python3 -m unittest test_tapd_daily.py -v`。
- [x] 运行 `python3 tapd_daily.py --config config.example.yaml --date 2026-05-26 --dry-run`。
- [ ] 检查 `git status --short --branch`，确认 `.env` 和 `public/reports/` 未进入提交。
- [ ] 使用中文 commit message 提交。
- [ ] 推送到 `origin/main`。

## 任务 6：同步接口调研并制定规则

- [x] 阅读 `TAPD钉钉接口调研.md`。
- [x] 新增 `interface-rules.md`，沉淀 TAPD 鉴权、分页、字段映射、状态映射和钉钉 Webhook 规则。
- [x] 更新 `config.example.yaml`，将缺陷归属字段默认设为 `current_owner`，需求产品经理字段默认设为 `owner`。
- [x] 更新 `tapd_daily.py`，支持配置化字段映射、TAPD 响应状态校验、分页读取、钉钉加签和 Markdown payload。
- [x] 更新 `README.md` 和设计文档，说明接口规则和后续待确认项。
