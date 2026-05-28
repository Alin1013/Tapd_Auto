# TAPD 每日复盘链路设计

日期：2026-05-26  
状态：已确认，已进入第一版链路脚手架实现
目标：每天从 TAPD 同步多个项目、多个迭代的任务、缺陷、需求数据，生成一张以缺陷为核心的人员日报图，并通过钉钉机器人定时发送到群里。

## 已确认决策

- TAPD 认证使用个人访问令牌，令牌只放在 `.env`。
- 统计范围支持多项目、多迭代；live 模式按项目自动发现打开迭代，dry-run 可使用配置中的示例迭代。
- 钉钉主消息开头嵌入页面截图，后续发送 Markdown 文字复盘和内部 HTML 报表链接。
- 报表部署到内部服务器或内网域名。
- 当前日报不展示任务数、完成率或进展条。
- 团队人员主体信息按缺陷展示。
- 缺陷按人员展示：未解决、今日新增、当日关闭。
- 产品经理作为单独角色展示需求排期和需求内容。
- 主信息必须在一张图内直接可读，点击跳转 TAPD 只作为追详情的辅助路径。
- 仓库保持扁平结构，正式文件直接放在根目录。
- 文件名可以使用英文，文档内容、配置注释、代码注释和 commit message 尽量使用中文。
- TAPD 和钉钉接口落地规则单独沉淀在 `docs/operations/interface-rules.md`。

## 范围

第一版实现一个配置驱动的自动化链路，不做后台管理页面。新增或调整项目、成员、产品经理时，通过修改配置文件完成；live 模式的迭代列表由 TAPD 打开迭代接口自动发现。

第一版不依赖 TAPD 页面自动化，不保存用户 TAPD 登录态，不在 HTML 报表中保存 TAPD token。系统只使用服务端环境里的访问令牌拉取日报所需数据。

当前脚手架支持 dry-run 和 live 两种模式：dry-run 使用 `configs/config.example.yaml` 中的 `sample_data` 生成 PNG、HTML、Markdown 和 JSON，live 使用 TAPD OpenAPI 拉取真实数据并额外保存字段发现结果。钉钉发送必须显式传入 `--send-dingtalk`，避免调试时误发群消息。

接口接入规则：

- TAPD 鉴权优先使用 `Authorization: Bearer ${TAPD_ACCESS_TOKEN}`。
- TAPD 列表接口统一按 `limit=200&page=N` 翻页。
- TAPD 响应 `status = 1` 才算成功，失败时使用 `info` 输出错误原因。
- CLI 必须显式选择 `--dry-run` 或 `--live`。
- 任务归属字段默认 `owner`。
- 缺陷归属字段默认 `current_owner`，用于展示当前处理压力。
- 产品经理需求字段默认 `owner`。
- 钉钉首版使用群自定义机器人 Webhook，发送层保留未来切换应用机器人的适配边界。

## 配置

配置文件建议开发阶段使用 `configs/config.example.yaml`，真实部署时复制为 `configs/config.yaml`：

```yaml
timezone: Asia/Shanghai

tapd:
  base_url: https://api.tapd.cn

report:
  public_base_url: https://tapd-daily.internal.example.com
  output_dir: ./public/reports

dingtalk:
  webhook: ${DINGTALK_WEBHOOK}
  secret: ${DINGTALK_SECRET}

projects:
  - name: Deepexi Foil
    workspace_id: "33002756"
    iterations:  # dry-run 示例和 live 兜底使用；live 模式默认自动遍历打开迭代。
      - name: Deepexi Foil V1.0.0
        iteration_id: "1133002756001001828"
    members:
      - name: 雷艾琳
        tapd_user: leiailin
        role: 当前账号
        tapd_report_url: https://www.tapd.cn/33002756/prong/stories/stories_list
    product_managers: []
```

`.env` 保存敏感配置：

```bash
TAPD_ACCESS_TOKEN=your_tapd_personal_access_token
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxxxxxxxxxxxxxxx
DINGTALK_SECRET=SECxxxxxxxxxxxxxxxx
```

`.env`、临时草图目录、生成的报表目录都不进入 git。

## 数据获取

数据同步层按项目调用 TAPD API，live 模式先发现打开迭代，再逐个迭代拉取三类数据：

- 任务：保留接口采集能力，用于后续扩展或排查，不在当前日报中展示任务数、完成率或进展。
- 缺陷：用于统计每个人的未解决、今日新增、当日关闭缺陷数。
- 需求：用于展示产品经理负责或提出的需求排期和内容。

API 查询应尽量在服务端过滤项目、迭代、人员、日期范围。如果某个 TAPD 接口不能一次性表达所有条件，则先按项目和打开迭代拉取，再在本地聚合过滤。没有当日动作的迭代不进入最终日报；如果项目下没有任何当日活跃迭代，则整个项目也不展示。

## 数据口径

### 任务数据

- 范围：配置中的项目和成员，以及 live 模式发现的打开迭代。
- 归属：任务负责人等于配置中的 `tapd_user`。
- 当前日报展示规则：不展示任务数、完成任务数、任务完成率或进展条。
- 保留原因：后续如果需要追溯任务接口字段或恢复任务视图，可以沿用同一套采集链路。

完成类状态需要配置或映射，例如 `已完成`、`已关闭`、`Done`。第一版提供默认映射，并允许后续在配置中覆盖。

### 缺陷统计

- 范围：配置中的项目和成员，以及 live 模式发现的打开迭代。
- 归属：缺陷处理人或负责人等于配置中的 `tapd_user`，具体字段以当前 TAPD 工作区实际字段为准。
- 未解决：不属于关闭类的缺陷数。
- 新增：当天创建的缺陷数。
- 当日关闭：状态属于关闭类，且 `closed`、`resolved` 或 `completed` 任一关闭时间落在当天的缺陷数。
- 当天范围：`Asia/Shanghai` 的 `00:00:00` 到 `23:59:59`。
- 展示例外：`Tora`（黄寅子）和 `nianqiongyue`（粘琼月）配置 `hide_bug_metrics: true`，不进入缺陷成员表。
- 迭代活跃判定只看今日新增和当日关闭；历史未解决缺陷会在活跃迭代内展示，但不会单独让一个迭代进入当日日报。

关闭类状态需要配置或映射，例如 `已解决`、`已关闭`、`无需解决`。第一版提供默认映射，并允许后续在配置中覆盖。

### 产品总需求

- 范围：已进入当日日报的项目迭代内，所有未发布需求。
- 归属：需求负责人、创建人或产品经理字段等于配置中的 `tapd_user`，具体字段以当前 TAPD 工作区实际字段为准。
- 展示：需求标题、产品经理、状态、TAPD 链接。
- 排序：优先按开始时间，再按结束时间。
- 数量控制：每个项目迭代展示全部未发布需求；图片过长时自动分页，HTML 页面在对应迭代卡片中展示完整列表。
- 迭代进入日报的当日判定仍参考需求当天创建、修改、完成，或排期开始到结束覆盖当天；进入日报后，“产品总需求”不再按当天动作裁剪。
- 发布过滤：状态为 `发布`、`已发布` 或原始状态 `status_21` 的需求不展示。

## 日报模型

聚合后的日报模型按日期生成：

- 日期
- 项目列表
- 每个项目下的迭代列表
- 每个迭代下的人员统计
- 每个迭代下的产品总需求
- 整体摘要
- 失败项目或异常信息

人员统计包含：

- 姓名
- TAPD 用户标识
- 角色
- 缺陷隐藏标记
- 缺陷当日关闭数
- 缺陷未解决数
- 缺陷新增数
- TAPD 详情链接

## 展示设计

### PNG 日报图

PNG 是本地归档和快速预览用的摘要图；钉钉群内首图使用页面截图，解析部分保持 Markdown 文字。

结构：

- 顶部：日报日期、项目数量、迭代数量、人员数量、整体缺陷统计。
- 主体：按项目和迭代分区。
- 每个分区：展示人员缺陷卡片和缺陷统计。
- 产品区：展示当前迭代全部未发布产品总需求。

人员缺陷卡片：

- 每个人一张卡片。
- 默认显示缺陷 `未解 / 今日新增 / 当日关闭`。
- `hide_bug_metrics: true` 的成员不进入 PNG 缺陷卡片。
- 未解决缺陷较多的人靠前排序。

图片过长时按项目或迭代拆成多张 PNG，作为本地报表归档资源保留；钉钉首图由 HTML 页面截图生成。

### 内部 HTML 报表

HTML 报表与 PNG 使用同一份日报数据，部署在内部服务器。

功能：

- 团队成员表只展示成员和缺陷，不展示任务数、完成率或进展。
- 页面按迭代纵向滚动展示，每个迭代是一张卡片。
- 同一迭代卡片内包含两个区域：`今日缺陷` 和 `产品总需求`。
- `产品总需求` 展示当前迭代全部未发布需求内容。
- 点击人员名称时打开配置中的 TAPD 详情链接。
- 产品需求区域可以展示比 PNG 更多的内容。
- 点击产品需求时打开 TAPD 需求详情。

TAPD 详情链接建议使用保存好的 TAPD 报表或筛选视图，例如缺陷状态分布图，日期条件使用 TAPD 的动态时间“当天到当天”。主信息仍以本系统的一张图为准，TAPD 链接只用于追踪详情。

## 钉钉消息

钉钉发送 Markdown 消息，开头嵌入页面截图，后续包含文本摘要、成员复盘和内部报表链接。

示例：

```markdown
### TAPD 每日复盘 2026-05-26

![当日复盘截图](https://tapd-daily.internal.example.com/reports/2026-05-26/page-screenshot.png)

今日统计：3 个项目 / 5 个迭代 / 18 人
今日缺陷：未解决 24，今日新增 6，当日关闭 9

[查看交互报表](https://tapd-daily.internal.example.com/reports/2026-05-26/index.html)

#### 成员复盘

雷艾琳：Deepexi Foil / Deepexi Foil V1.0.0，未解决 3，今日新增 1，当日关闭 2。
```

钉钉机器人需要加签时，发送层根据 `DINGTALK_SECRET` 生成签名。

## 调度和部署

第一版部署在内部服务器，通过 `cron` 定时执行。

目录示例：

```text
/opt/tapd-daily-review/
  .env
  projects.yaml
  public/
    reports/
      2026-05-26/
        summary-1.png
        page-screenshot.png
        index.html
```

Nginx 暴露 `public` 下的报表资源：

```text
https://tapd-daily.internal.example.com/reports/2026-05-26/page-screenshot.png
https://tapd-daily.internal.example.com/reports/2026-05-26/index.html
```

推荐每日工作日固定时间发送，例如 `18:30 Asia/Shanghai`。调度时间由服务器 cron 配置，不写死在业务代码中。

## 执行流程

1. 加载 `.env` 和 `projects.yaml`。
2. 校验 TAPD token、钉钉 webhook、报表基础 URL、项目迭代配置。
3. 按项目和迭代拉取任务、缺陷、需求。
4. 聚合为日报模型。
5. 渲染 HTML 报表。
6. 用同一份 HTML 或模板渲染 PNG 图片。
7. 写入 `public/reports/YYYY-MM-DD/`。
8. 发送钉钉 Markdown 消息。
9. 写入执行日志和结果摘要。

## 异常处理

- TAPD API 请求失败：重试 3 次，仍失败则记录错误。
- 单个项目失败：不中断其他项目，在日报里标注该项目失败。
- 全部项目失败：发送“日报生成失败”钉钉消息。
- 钉钉发送失败：记录错误并返回非 0 退出码。
- 配置或凭证缺失：启动时失败，不发送半成品日报。
- 图片过长：PNG 自动拆图作为本地归档资源；钉钉首图使用页面截图。
- 成员无数据：缺陷口径显示未解决、今日新增、当日关闭均为 0。

## 安全边界

- 不提交 `.env`。
- 不在 HTML 或 PNG 中暴露 TAPD token、钉钉 webhook、secret。
- 内部 HTML 报表只暴露统计结果和 TAPD 跳转链接。
- 用户点击 TAPD 链接后使用自己的 TAPD 登录态和权限查看详情。
- 服务端日志不打印完整 token、webhook 或签名。

## 验证策略

实现时需要覆盖以下验证：

- 配置解析和必填字段校验。
- 任务接口采集：保留数据链路，但页面和通知不展示任务进度。
- 缺陷聚合：未解决、今日新增、当日关闭。
- 产品总需求排序和筛选。
- 多项目多迭代分区。
- PNG 和 HTML 文件生成。
- 钉钉签名和 Markdown payload 生成。
- TAPD API 失败、单项目失败、全部失败的异常路径。

第一版可以先用本地 fixture 数据验证渲染和聚合，再接入真实 TAPD API 做端到端测试。
