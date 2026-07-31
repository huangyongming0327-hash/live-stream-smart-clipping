# TASK-004-R AUDIT｜语义分段与爆点识别独立审计

## 1. 审计对象

- 仓库：`huangyongming0327-hash/live-stream-smart-clipping`
- PR：`#6`
- 分支：`task/TASK-004-semantic-highlight-analysis`
- 基线：`0e619b6fbb3e34250f10b1719dfb5a666ea7020f`
- 审计 HEAD：`9b71c4b134b1a3d65c5d0d6a3b1530c28e6ea007`
- Actions Run：`30568745169`
- 审计方式：最新 HEAD 静态代码复核、完整 PR 变更复核、任务与 RESULT 对照、测试实现复核、latest-head Actions 与日志核读
- 审计边界：未读取或公开用户真实字幕、真实候选标题、推荐理由、API Key 或本地分析文件

## 2. 审计结论

- 总分：**89/100**
- 等级：**有条件通过**
- 阻断问题：**无**
- 是否要求 TASK-004-FIX：**否**
- 当前 PR：继续保持 Draft
- 当前不得标记 Ready 或合并：审计报告尚未提交到 PR，审核后 latest-head Actions 尚未产生
- 审计报告提交并且三项 Actions 再次全部成功后：可以由用户手动标记 Ready，并决定执行 Squash and merge
- TASK-005：PR #6 合并前继续禁止

TASK-004 已经形成真实可运行的候选生成闭环。程序能够读取一个已完成的
`timeline.json`，顺序调用一个用户配置的 OpenAI-compatible 文本模型接口，输出话题、
候选、标题、推荐理由、程序计算的时间、quote、分数和 `current_analysis.json`。

真实 `qwen-flash` 运行证明接口和生产流程可用。但候选质量并不稳定：抽查前三项仅一项
基本可直接进入人工剪辑，一项需要调整，一项不宜直接采用。因此本功能适合作为
“人工审核前的候选生成器”，不能作为自动发布或自动剪辑决策器。该限制与当前 MVP
保留人工审核门禁的设计一致，不构成合并阻断。

## 3. 评分

| 维度 | 得分 | 满分 | 审计说明 |
|---|---:|---:|---|
| 核心功能实现 | 23 | 25 | 真实 API、话题、候选、评分、恢复、版本发布均完成；候选可用率和风险评分校准仍有限 |
| 正确性与恢复稳定性 | 18 | 20 | 连续 segment、派生时间、程序总分、状态指纹、恢复和普通发布回滚可靠；缺少发布前 timeline 再哈希 |
| 测试与真实验证 | 13 | 15 | 专项、组合、source-only 和真实 API 均有证据；无法独立读取私有候选全文复核语义质量 |
| 代码简洁与可维护性 | 12 | 15 | 无 Agent、RAG、插件或工作流框架，职责清楚；`pipeline.py` 与 `schema.py` 已较长 |
| 性能与资源 | 9 | 10 | 827.766 秒 timeline 仅 2 个顺序请求，16.282 秒完成；未引入并发和大型 SDK |
| 安全和隐私边界 | 10 | 10 | Key 只进 Authorization header，媒体与路径不发送，真实数据不进 Git，安全扫描通过 |
| 文档与可追溯性 | 4 | 5 | TASK、RESULT、README、状态和决策记录完整；生产使用注意事项仍可更直接 |
| **总分** | **89** | **100** | **有条件通过** |

## 4. 核心功能审计

### 4.1 输入与窗口

通过：

- 复用 TASK-003 的 timeline 校验；
- 只处理一个 timeline；
- 600,000 ms 和约 12,000 字符双上限；
- 不拆分单个 segment；
- 窗口按时间顺序且不重叠；
- 顺序请求，不并发；
- 空 timeline 不调用 API。

### 4.2 模型输出约束

通过：

- 模型必须且只能返回 `topics` 和 `candidates`；
- 每窗口最多 3 个 candidate；
- topic 与 candidate 只能引用当前窗口真实 segment；
- segment 范围连续；
- candidate 必须完整属于一个 topic；
- quote segment 必须在候选范围内；
- candidate 时长必须为 15—180 秒；
- 分值必须有限且在固定范围内；
- 非法 JSON 或结构错误只修复重试一次。

### 4.3 程序可信字段

通过：

- topic/candidate 的 `start_ms` 与 `end_ms`由 timeline 计算；
- `duration_ms`由程序计算；
- quote 从 timeline 原文复制；
- `total_score`由程序计算并限制在 0—100；
- 60 分以下过滤；
- 75 分以上标记推荐；
- 超过 60% 重叠只保留高分项；
- 最终最多 20 个；
- 排序稳定。

因此模型不能直接伪造时间、quote 或总分。

## 5. 恢复和版本发布

### 5.1 中断恢复

通过：

- 状态绑定 timeline SHA、endpoint host、model 和窗口参数；
- 每完成一个窗口原子保存；
- 已完成窗口结果重新读取时再次校验；
- 恢复从下一窗口继续；
- timeline/model/host 改变时拒绝旧状态；
- API Key 不进入状态；
- 成功后清理 `.analysis_work`。

### 5.2 最近 3 个版本

通过：

- 新结果先写 staging 并完整校验；
- 旧 current 进入 history；
- current + history 最多保留 3 份；
- 普通替换、删除或写入失败时恢复旧 current 和旧 history；
- staging 最终清理；
- 用户其他非 JSON 文件不在清理范围内。

### 5.3 非阻断缺口

运行开始时读取 timeline 快照并计算 SHA，但正式发布前没有重新读取磁盘上的 timeline
确认 SHA 未变化。极端情况下，用户在 API 分析过程中替换 timeline，程序仍可能发布
基于旧快照的结果。

输出内保存了原 timeline SHA，下游可以检测不匹配；真实分析仅约 16 秒，该竞态概率较低。
本项进入 backlog，不要求 TASK-004-FIX。

## 6. API 与隐私审计

通过：

- 仅支持 HTTPS；
- 使用标准库 HTTP，不安装厂商 SDK；
- Key 只从环境变量读取；
- Key 只进入 Bearer Authorization header；
- 请求正文只有 segment ID、相对时间和字幕文本；
- 不发送视频、音频、本地路径、timeline 文件名或视频文件名；
- 不在正常错误中打印 API 响应正文或请求正文；
- 401/403 不重试；
- 429、5xx、超时或网络错误最多重试一次；
- 响应大小限制为 1,000,000 bytes；
- Git 忽略 current、history 和 analysis state；
- latest-head 安全扫描 167 个 tracked 文本文件，0 问题。

非阻断建议：

- API Key 环境变量当前不主动拒绝前后空格或换行；错误配置会表现为 401 或 Header 错误。
  用户已经在真实验证中遇到过一次。后续可做一条简单格式检查，但不阻断当前正确配置下运行。

## 7. 候选实际价值

真实运行聚合数据：

- timeline：827.766 秒，169 segments
- 模型：`qwen-flash`
- 2 个窗口，2 个完成态请求
- 16.282 秒
- 11 topics
- 6 candidates
- 6 recommended
- 分数范围 89—94

前 3 高分项人工抽查：

- 1 项基本具备剪辑价值，但营销价格主张仍需合规复核；
- 1 项存在标题外推、弱 quote 和结尾不完整，不适合直接使用；
- 1 项主题可理解但结尾略截断，家庭健康和隐私风险扣分不足。

结论：

- 候选生成能力真实存在；
- 结果可以减少人工从长视频中寻找片段的时间；
- `recommended=true` 与 89—94 高分目前明显偏乐观；
- 模型的风险扣分不能替代营销、隐私和健康内容人工复核；
- TASK-005 必须保留人工预览、调整入出点和取消候选能力。

该质量水平对第一版“候选发现”可接受，但不适合无人审核自动剪辑或发布。

## 8. 代码简洁与维护性

生产结构清楚：

- `client.py`：单一 HTTP 客户端；
- `prompt.py`：固定分析提示；
- `schema.py`：模型与正式输出校验；
- `pipeline.py`：窗口、状态、恢复、合并、发布；
- `cli.py`：增加 `analyze` 入口。

未发现：

- 多 Agent；
- embeddings/RAG；
- provider 插件体系；
- 数据库；
- 通用 DAG 或工作流引擎；
- TASK-005 代码；
- 对 TASK-003 backlog 的顺手扩张。

`pipeline.py` 和 `schema.py` 合计接近 900 行，仍属于可理解的单任务模块，但后续
TASK-005 不应继续向这两个文件堆 UI、视频预览或导出逻辑。

## 9. 测试与 GitHub Actions

审计确认：

- TASK-004 专项：30 passed，0 failed；
- 定向组合：59 passed，0 failed；
- latest-head Actions Run：`30568745169`；
- `repository-safety`：SUCCESS；
- `lightweight-tests`：SUCCESS；
  - base-schema-media：158 passed，1 deselected，0 failed；
  - asr-experiments：91 passed，2 deselected，1 warning，0 failed；
  - pip check：No broken requirements found；
  - 三阶段 exit code 均为 0；
- `task-report-gate`：SUCCESS；
- PR 当前 Open、Draft、未合并、mergeable。

测试已覆盖输入校验、窗口切分、Key 不进状态和进度、修复重试、segment 范围、时长、
分值、总分、过滤、去重、quote、恢复、状态指纹、发布失败、最近 3 版本、HTTP 重试和
CLI 单行错误。

## 10. 重要问题与 backlog

### I-1｜模型推荐分数与人工可用性偏离

6 个候选全部被推荐且分数为 89—94，但前三名中只有一项基本可用。当前
`recommended` 只代表模型评分门槛，不代表人工验收通过。

处理：不阻断；TASK-005 UI 必须明显保留人工审核状态，不默认全选发布。

### I-2｜风险扣分不足

营销价格、家庭健康和隐私内容未得到足够风险扣分。

处理：不阻断；后续可优化 prompt 或增加“需人工复核”标签，但不要在当前 PR
引入合规模型或复杂规则系统。

### I-3｜timeline 发布前未再次校验 SHA

处理：低概率竞态，进入 backlog。

### I-4｜API Key 空白字符缺少前置检查

处理：后续可用小范围输入校验改善错误提示，当前不阻断正确配置。

## 11. 最终决定

1. TASK-004 功能真实可用：**是**
2. 候选有实际切片价值：**有，但质量混合，必须人工审核**
3. 连续 segment、程序时间/总分、恢复和 3 版本：**代码和测试证据充分**
4. API 与隐私边界：**符合任务要求**
5. 代码简洁性：**总体合格，无过度架构；两个核心文件偏长**
6. 阻止 Ready 或合并的问题：**未发现代码阻断**
7. 审计结论：**89/100，有条件通过，不要求 TASK-004-FIX**

## 12. 后续操作边界

当前继续保持 Draft。只允许将本报告提交到：

```text
tasks/reports/TASK-004-R_AUDIT.md
```

提交审核报告后：

1. 等待审核后 latest-head 三项 Actions 全部成功；
2. 再次运行 `Get-PRHandoff.ps1`；
3. 由项目总指挥复核最新 head、AUDIT 和 Actions；
4. 之后才可以由用户手动标记 Ready；
5. 之后才可以由用户手动执行 Squash and merge；
6. PR #6 合并前继续禁止 TASK-005。
