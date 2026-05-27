# TAPD 自动日报

这个项目用于生成 TAPD 每日复盘报表。第一版已经打通本地链路和真实接口边界：读取配置、拉取 TAPD 数据、聚合任务/缺陷/需求、生成 PNG 日报图、HTML 交互报表、Markdown 摘要和 JSON 数据文件。钉钉发送需要显式打开，避免调试时误发群消息。

## 目录结构

```text
src/tapd_auto/             生产代码
tests/                     自动化测试
configs/                   配置示例
docs/design/               设计文档
docs/operations/           运行规则和实施计划
docs/research/             接口调研资料
scripts/                   部署和定时任务脚本
tapd_daily.py              兼容入口，旧命令仍可使用
```

## 本地配置

先从示例文件创建本地 `.env`：

```bash
cp .env.example .env
```

`.env` 字段：

```bash
TAPD_ACCESS_TOKEN=你的 TAPD 个人访问令牌
DINGTALK_WEBHOOK=
DINGTALK_SECRET=
```

注意：不要把 `.env` 提交到 Git。当前 `.gitignore` 已经忽略 `.env`、真实配置 `configs/config.yaml`、日志和生成报表。

## 运行依赖

```bash
python3 -m pip install -r requirements.txt
```

也可以按可安装工具方式运行：

```bash
python3 -m pip install -e .
```

安装后会得到命令：

```bash
tapd-daily --help
```

## 本地验证

先使用示例数据生成报表：

```bash
python3 tapd_daily.py --config configs/config.example.yaml --date 2026-05-26 --dry-run
```

或使用包入口：

```bash
PYTHONPATH=src python3 -m tapd_auto --config configs/config.example.yaml --date 2026-05-26 --dry-run
```

安装后也可以直接运行：

```bash
tapd-daily --config configs/config.example.yaml --date 2026-05-26 --dry-run
```

生成文件位置：

```text
public/reports/2026-05-26/index.html
public/reports/2026-05-26/summary-1.png
public/reports/2026-05-26/summary.md
public/reports/2026-05-26/report.json
```

启动本地预览服务：

```bash
bash scripts/preview.sh
```

打开：

```text
http://127.0.0.1:8765/public/reports/2026-05-26/index.html
```

测试命令：

```bash
python3 -m unittest discover -s tests -v
```

## 真实同步

真实运行前，先复制示例配置并补齐项目、迭代、成员和产品经理：

```bash
cp configs/config.example.yaml configs/config.yaml
```

只生成报表，不发送钉钉：

```bash
python3 tapd_daily.py --config configs/config.yaml --live
```

生成报表并发送钉钉：

```bash
python3 tapd_daily.py --config configs/config.yaml --live --send-dingtalk
```

live 模式会额外生成：

```text
public/reports/YYYY-MM-DD/field-info.json
```

这个文件用于核对 TAPD 工作区的状态枚举和自定义字段，方便后续调整 `task_done_statuses`、`bug_closed_statuses` 和字段映射。

## 定时部署

部署到服务器后，建议固定项目路径，例如：

```text
/opt/tapd-auto/
```

准备文件：

```bash
cp .env.example .env
cp configs/config.example.yaml configs/config.yaml
mkdir -p logs
python3 -m pip install -r requirements.txt
```

运行脚本：

```bash
bash scripts/run_daily.sh
```

cron 示例见 `scripts/crontab.example`。

更完整的生产部署和回滚流程见 `docs/operations/production-runbook.md`。

## 当前已同步信息

- 当前 TAPD 账号：`leiailin` / 雷艾琳。
- 当前真实项目：Deepexi Foil，`workspace_id=33002756`。
- 当前配置迭代：Deepexi Foil V1.0.0，`iteration_id=1133002756001001828`。
- 本地真实运行配置在 `configs/config.yaml`，该文件不提交到 Git。

## 后续需要补充的信息

- 其他成员姓名、TAPD 用户标识、角色、详情链接。
- 产品经理姓名和 TAPD 用户标识。
- 钉钉机器人 webhook 和加签 secret。
- 如后续新增项目，需要补充对应 `workspace_id` 和 `iteration_id`。

## 接口规则

- TAPD 默认使用 `Authorization: Bearer ${TAPD_ACCESS_TOKEN}`。
- TAPD 返回 `status = 1` 才算成功，否则使用 `info` 作为错误原因。
- TAPD 列表统一使用 `limit=200&page=N` 翻页。
- 任务归属字段默认 `owner`。
- 缺陷归属字段默认 `current_owner`。
- 需求产品经理字段默认 `owner`。
- 钉钉首版使用群自定义机器人 Webhook，开启加签时按 `timestamp + "\n" + secret` 生成 `sign`。
- 详细规则见 `docs/operations/interface-rules.md`。

## 当前链路

1. 从 `.env` 读取 TAPD token 和钉钉敏感配置。
2. 从配置文件读取项目、迭代、成员、字段映射和状态映射。
3. dry-run 模式使用 `sample_data`；live 模式调用 TAPD OpenAPI。
4. live 模式先拉字段发现信息，再拉迭代、任务、缺陷、需求列表。
5. 按人员计算任务完成率、已关闭缺陷、未解决缺陷、当天新增缺陷。
6. 按产品经理展示需求排期。
7. 输出 PNG、HTML、Markdown 和 JSON。
8. 只有传入 `--send-dingtalk` 时才发送钉钉 Markdown。
