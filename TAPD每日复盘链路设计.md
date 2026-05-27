# TAPD 每日复盘链路设计

日期：2026-05-26  
状态：已确认，已进入第一版链路脚手架实现
目标：每天从 TAPD 同步多个项目、多个迭代的任务、缺陷、需求数据，生成一张可直接阅读的人员竖条进度图，并通过钉钉机器人定时发送到群里。

## 已确认决策

- TAPD 认证使用个人访问令牌，令牌只放在 `.env`。
- 统计范围支持多项目、多迭代，由配置文件显式指定。
- 钉钉主消息发送 PNG 日报图、简短 Markdown 摘要、内部 HTML 报表链接。
- 报表部署到内部服务器或内网域名。
- 图表不是传统横向甘特图，而是按人员展示的竖条进度图。
- 每个人的任务进度按任务数量计算：完成任务数 / 总任务数。
- 缺陷按人员展示：已关闭、未解决、新增。
- 产品经理作为单独角色展示需求排期和需求内容。
- 主信息必须在一张图内直接可读，点击跳转 TAPD 只作为追详情的辅助路径。
- 仓库保持扁平结构，正式文件直接放在根目录。
- 文件名可以使用英文，文档内容、配置注释、代码注释和 commit message 尽量使用中文。
- TAPD 和钉钉接口落地规则单独沉淀在 `interface-rules.md`。

## 范围

第一版实现一个配置驱动的自动化链路，不做后台管理页面。新增或调整项目、迭代、成员、产品经理时，通过修改配置文件完成。

第一版不依赖 TAPD 页面自动化，不保存用户 TAPD 登录态，不在 HTML 报表中保存 TAPD token。系统只使用服务端环境里的访问令牌拉取日报所需数据。

当前脚手架先支持 dry-run：使用 `config.example.yaml` 中的 `sample_data` 生成 HTML、Markdown 和 JSON，确保配置、聚合和展示链路可验证。真实 TAPD 接口字段确认后，再用 API 返回数据替换 `sample_data`。

接口接入规则：

- TAPD 鉴权优先使用 `Authorization: Bearer ${TAPD_ACCESS_TOKEN}`。
- TAPD 列表接口统一按 `limit=200&page=N` 翻页。
- TAPD 响应 `status = 1` 才算成功，失败时使用 `info` 输出错误原因。
- 任务归属字段默认 `owner`。
- 缺陷归属字段默认 `current_owner`，用于展示当前处理压力。
- 产品经理需求字段默认 `owner`。
- 钉钉首版使用群自定义机器人 Webhook，发送层保留未来切换应用机器人的适配边界。

## 配置

配置文件建议开发阶段使用 `config.example.yaml`，真实部署时复制为 `config.yaml`：

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
    iterations:
      - name: 2026-05 Sprint
        iteration_id: "123456"
    members:
      - name: 张三
        tapd_user: zhangsan
        role: dev
        tapd_report_url: https://tapd.cn/33002756/bugtrace/bugreports/stat_general/general/systemreport-1000000000000000001
      - name: 李四
        tapd_user: lisi
        role: test
        tapd_report_url: https://tapd.cn/33002756/bugtrace/bugreports/stat_general/general/systemreport-1000000000000000002
    product_managers:
      - name: 产品A
        tapd_user: product_a
```

`.env` 保存敏感配置：

```bash
TAPD_ACCESS_TOKEN=your_tapd_personal_access_token
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxxxxxxxxxxxxxxx
DINGTALK_SECRET=SECxxxxxxxxxxxxxxxx
```

`.env`、临时草图目录、生成的报表目录都不进入 git。

## 数据获取

数据同步层按项目和迭代调用 TAPD API，拉取三类数据：

- 任务：用于统计每个人的任务总数、完成数、未完成数。
- 缺陷：用于统计每个人的已关闭、未解决、新增缺陷数。
- 需求：用于展示产品经理负责或提出的需求排期和内容。

API 查询应尽量在服务端过滤项目、迭代、人员、日期范围。如果某个 TAPD 接口不能一次性表达所有条件，则先按项目和迭代拉取，再在本地聚合过滤。

## 数据口径

### 任务进度

- 范围：配置中的项目、迭代、成员。
- 归属：任务负责人等于配置中的 `tapd_user`。
- 总任务数：该成员在该项目迭代下的任务数量。
- 完成任务数：状态属于完成类的任务数量。
- 进度：`完成任务数 / 总任务数`。
- 无任务人员：仍展示，显示 `0/0`，避免误判为漏统计。

完成类状态需要配置或映射，例如 `已完成`、`已关闭`、`Done`。第一版提供默认映射，并允许后续在配置中覆盖。

### 缺陷统计

- 范围：配置中的项目、迭代、成员。
- 归属：缺陷处理人或负责人等于配置中的 `tapd_user`，具体字段以当前 TAPD 工作区实际字段为准。
- 已关闭：状态属于关闭类的缺陷数。
- 未解决：不属于关闭类的缺陷数。
- 新增：当天创建的缺陷数。
- 当天范围：`Asia/Shanghai` 的 `00:00:00` 到 `23:59:59`。

关闭类状态需要配置或映射，例如 `已解决`、`已关闭`、`无需解决`。第一版提供默认映射，并允许后续在配置中覆盖。

### 产品需求排期

- 范围：配置中的项目、迭代、产品经理。
- 归属：需求负责人、创建人或产品经理字段等于配置中的 `tapd_user`，具体字段以当前 TAPD 工作区实际字段为准。
- 展示：需求标题、产品经理、开始时间、结束时间、状态、TAPD 链接。
- 排序：优先按开始时间，再按结束时间。
- 数量控制：每个项目迭代展示重点需求，默认展示全部配置内产品经理相关需求；图片过长时自动分页。

## 日报模型

聚合后的日报模型按日期生成：

- 日期
- 项目列表
- 每个项目下的迭代列表
- 每个迭代下的人员统计
- 每个迭代下的产品需求排期
- 整体摘要
- 失败项目或异常信息

人员统计包含：

- 姓名
- TAPD 用户标识
- 角色
- 任务总数
- 完成任务数
- 任务完成率
- 缺陷已关闭数
- 缺陷未解决数
- 缺陷新增数
- TAPD 详情链接

## 展示设计

### PNG 日报图

PNG 是钉钉群里的主阅读内容。

结构：

- 顶部：日报日期、项目数量、迭代数量、人员数量、整体任务完成率、整体缺陷统计。
- 主体：按项目和迭代分区。
- 每个分区：展示人员竖条图和缺陷统计小表。
- 产品区：展示产品经理需求排期和需求内容。

人员竖条：

- 每个人一根竖条。
- 柱高代表任务完成率。
- 柱下直接显示 `完成/总数`。
- 柱下或旁边直接显示缺陷 `已关 / 未解 / 新增`。
- 未解决缺陷较多的人使用醒目颜色标记。

图片过长时按项目或迭代拆成多张 PNG，并在钉钉消息中按顺序引用。

### 内部 HTML 报表

HTML 报表与 PNG 使用同一份日报数据，部署在内部服务器。

功能：

- hover 人员竖条时展示个人摘要：任务总数、完成数、未完成数、缺陷已关闭、未解决、新增。
- 点击人员竖条时打开配置中的 TAPD 详情链接。
- 产品需求区域可以展示比 PNG 更多的内容。
- 点击产品需求时打开 TAPD 需求详情。

TAPD 详情链接建议使用保存好的 TAPD 报表或筛选视图，例如缺陷状态分布图，日期条件使用 TAPD 的动态时间“当天到当天”。主信息仍以本系统的一张图为准，TAPD 链接只用于追踪详情。

## 钉钉消息

钉钉发送 Markdown 消息，包含文本摘要、日报图片、内部报表链接。

示例：

```markdown
### TAPD 每日复盘 2026-05-26

今日统计：3 个项目 / 5 个迭代 / 18 人
任务整体完成率：72%
缺陷：未解决 24，今日新增 6，今日关闭 9

![日报图](https://tapd-daily.internal.example.com/reports/2026-05-26/summary-1.png)

[查看交互报表](https://tapd-daily.internal.example.com/reports/2026-05-26/index.html)
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
        index.html
```

Nginx 暴露 `public` 下的报表资源：

```text
https://tapd-daily.internal.example.com/reports/2026-05-26/summary-1.png
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
- 图片过长：自动拆图。
- 成员无数据：显示 `0/0` 和 `0/0/0`。

## 安全边界

- 不提交 `.env`。
- 不在 HTML 或 PNG 中暴露 TAPD token、钉钉 webhook、secret。
- 内部 HTML 报表只暴露统计结果和 TAPD 跳转链接。
- 用户点击 TAPD 链接后使用自己的 TAPD 登录态和权限查看详情。
- 服务端日志不打印完整 token、webhook 或签名。

## 验证策略

实现时需要覆盖以下验证：

- 配置解析和必填字段校验。
- 任务进度聚合：完成数、总数、0 任务成员。
- 缺陷聚合：已关闭、未解决、新增。
- 产品需求排期排序和筛选。
- 多项目多迭代分区。
- PNG 和 HTML 文件生成。
- 钉钉签名和 Markdown payload 生成。
- TAPD API 失败、单项目失败、全部失败的异常路径。

第一版可以先用本地 fixture 数据验证渲染和聚合，再接入真实 TAPD API 做端到端测试。
