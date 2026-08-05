# TASK-006-R AUDIT｜端到端一键流程与 Windows 启动器独立审核

## 1. 审核对象与边界

- 仓库：`huangyongming0327-hash/live-stream-smart-clipping`
- PR：`#8`
- 分支：`task/TASK-006-end-to-end-runner`
- 基线：`7ae8b89dfc92f5915030662e7a36bf048da14254`
- 审核前 HEAD：`428b73015bb57bd94b3955dbf88bc84021e3c2b9`
- 审核前 Actions Run：`30936057715`
- 审核方式：完整 PR diff 和指定文件审阅、真实长视频首次运行、失败后重跑、同 timeline 原始字节 SHA 的合法 analysis 恢复、真实浏览器审核与导出、第二次完整运行、Windows 原生启动器、专项/回归测试、tracked safety 和 Actions 完整日志
- 只读边界：没有修改实现、测试、RESULT、README、CURRENT_STATUS 或其他既有文档；没有创建新 PR、标记 Ready、合并、启用 auto-merge 或执行 TASK-007
- 隐私边界：本报告不公开真实绝对路径、用户名、API Key、访问 token、端口、候选标题、推荐理由或字幕正文

## 2. 总分和最终结论

- 总分：**92/100**
- 最终结论：**有条件通过**
- 阻断问题：**无**
- 是否要求 TASK-006-FIX：**否**
- 当前 PR：继续保持 Draft

TASK-006 的统一入口、失败保存、精确复用、人工确认和单次导出闭环均通过静态与真实验证。
没有发现一票否决项。当前唯一影响“新用户一次成功”的主要限制是：本次真实模型在首次
analysis 和失败后的再次 analysis 中分别返回了不同的 schema 非法结果，修复重试后仍失败。
PR 没有修改 TASK-004 的 prompt、请求或 schema；runner 仅调用既有 `run_analysis`，因此这不是
TASK-006 引入的实现回归。合法 exact-SHA analysis 的恢复闭环完整通过，故将模型稳定性列为
非阻断的重要限制，而不是要求 TASK-006-FIX。

最终建议：**有条件通过，可以由用户手动 Ready 并决定合并，非阻断项进入 backlog。**

## 3. 评分

| 维度 | 得分 | 满分 | 审核说明 |
|---|---:|---:|---|
| 统一端到端编排 | 24 | 25 | `run` 只编排既有 transcribe/analyze/review；预检、进度和退出码清楚；真实新 analysis 未走到候选 |
| 恢复、复用与状态正确性 | 20 | 20 | ASR 失败保留、exact-SHA analysis 恢复、completed review 复用和二次运行幂等全部通过 |
| Windows 启动器和普通用户可用性 | 14 | 15 | 实际双击入口、原生选择框、取消、中文/空格/`&`/圆括号路径通过；模型选择到完整新分析仍受真实模型稳定性限制 |
| 真实验证与测试 | 10 | 15 | 专项、回归、浏览器、真实导出和两次幂等充分；当前真实模型连续两次 schema 失败，未获得“新 timeline 直接成功”的样本 |
| 用户文件、隐私与失败安全 | 10 | 10 | 原视频和既有产物安全，状态无泄露，tracked safety 0 问题 |
| 代码简洁与维护性 | 9 | 10 | 无核心算法复制、数据库、队列或大型框架；runner 文件较集中但职责仍可追踪 |
| 文档与可追溯性 | 5 | 5 | TASK、RESULT、README、状态和决策记录完整，边界与验证证据可追踪 |
| **总分** | **92** | **100** | **有条件通过** |

## 4. 阻断问题

未发现阻断问题，也未发现以下一票否决行为：

- 没有错误复用其他视频的 timeline 或 analysis；
- 没有在 analysis 失败后写 `completed`；
- 失败重跑没有重复 ASR；
- 没有未经人工确认即可导出；
- 没有覆盖原视频、既有输出或不匹配的运行产物；
- `pipeline_status.json` 没有绝对路径、API Key、token 或用户内容；
- Windows 启动器可以接收普通中文和特殊字符路径；
- tracked tree 没有真实媒体、运行数据、凭据或 TASK-007 实现；
- Actions 没有失败却被报告为成功。

## 5. 统一入口静态审计

通过。

- CLI 新增 `run`，参数限定为一个 MP4、可选 workdir、ASR 模型、输出目录和浏览器开关。
- runner 直接调用既有 `run_transcription`、`run_analysis` 和 `launch_review`。
- PR 对 `src/liveclip/analysis/` 没有任何修改；没有复制分块 ASR、模型 prompt、candidate
  生成、FFmpeg 导出或 SRT 核心算法。
- runner 新增的逻辑只负责输入/目录预检、源视频绑定、artifact 校验、SHA 复用、阶段状态和
  已完成 review 的一致性检查。
- 未引入数据库、后台队列、多用户状态、任务代理、前端框架或 TASK-007 功能。
- 预检在长任务前完成配置、FFmpeg/ffprobe、模型资产、MP4、目录可写性和路径冲突检查。
- 非法或损坏的已有 timeline/analysis/review 会明确停止，不会静默删除或重建后覆盖。

## 6. 首次真实运行结果

使用真实长 MP4、真实本地 ASR 和真实模型配置运行统一 `run`：

1. ASR 实际执行并完成，生成 `timeline.json`；
2. timeline 含 169 个 segment，ASR state 为 `completed`，共 14 个 chunk；
3. analysis 请求及修复重试执行后失败，错误为 candidate 未完整属于 topic；
4. 进程以退出码 1 结束，没有 traceback、API Key、请求体、响应正文或用户内容泄露；
5. `timeline.json` 和 ASR state 保留，`current_analysis.json`、history 和临时 analysis state
   均未伪造；
6. `pipeline_status.json` 正确记录 `transcribe=completed`、`analyze=pending`、`review=pending`。

失败后用同一命令再次运行：

- 输出明确显示 ASR“已复用”；
- 没有重新执行长时间转写；
- timeline SHA 和 ASR state SHA 保持不变；
- analysis 再次发起，修复重试后以另一种 schema 错误失败：candidate 时长不在 15—180 秒；
- 状态仍为 transcribe completed、analyze/review pending。

这证明 analysis 失败不会丢失 ASR，且重跑从失败阶段继续。

## 7. 模型 schema 失败的独立判断

判断：**不是 TASK-006 造成。**

依据：

- 基线到 HEAD 的 diff 没有修改 analysis 包、prompt、请求参数、解析器或 schema；
- runner 把同一个 `timeline.json`、output directory、environment 和 progress callback 交给既有
  `run_analysis`，没有改写 timeline 或模型返回值；
- 两次真实请求分别违反 topic 包含关系和 15—180 秒时长约束，错误类型不同，符合外部模型
  输出不稳定，而不是 runner 的固定转换错误；
- TASK-004 的严格校验和修复重试正确阻止非法 analysis 落盘；
- 错误消息只报告 schema 原因，没有泄露响应正文或凭据。

处理：非阻断的重要限制。当前模型/provider 组合没有在本次审核中证明“新 timeline 一次走到
候选”的可靠性；后续应单独提高 TASK-004 模型输出稳定性或验证兼容模型，但不应在 TASK-006
中复制或放宽核心 schema。

## 8. 同 timeline 原始字节 SHA 的合法 analysis 恢复闭环

通过。

- 首次运行生成的 timeline 原始字节 SHA-256 为
  `35f5731bde534b53eb11b5d38d6fdd6efaa523749932002c8f088924ae6e93cc`。
- 独立准备的合法 completed analysis 的 `source.timeline_sha256` 与该原始字节 SHA 完全一致；
  同时通过 analysis schema、源视频文件名/SHA、timeline 文件名/SHA 和 candidate 范围校验。
- 统一 `run` 明确显示 ASR“已复用”、analysis“已复用”，随后进入既有 review 页面。
- 页面显示 6 个候选，确认框默认未选，导出按钮默认禁用。
- 真实视频 `readyState=4`；点击预览后播放时间实际推进，未发现媒体错误。
- 勾选确认后导出按钮启用；入点 `+0.1 秒` 后确认自动清空、导出重新禁用。
- 重新预览调整后范围并再次确认后，真实导出成功且只产生一个 MP4 和一个 SRT。
- completed review 记录原始范围、最终范围、`approved=true`、`export.completed=true`、文件名和
  timeline/analysis SHA 绑定；状态在 review 服务正常结束后成为三个阶段全部 completed。
- 导出完成提示显示 MP4/SRT 文件名、最终范围、实际时长、输出文件夹和字幕条数。

恢复安全性：analysis 必须同时满足 schema 和当前 timeline 原始字节 SHA；只同名、只同视频或
重序列化后内容近似都不能通过。损坏、不匹配或跨视频 artifact 会停止并提示用户移走或更换
workdir，不会被静默当作合法复用。

## 9. 第二次完整运行复用

在 completed review 和两个输出文件都存在后再次运行同一统一命令：

- transcribe：明确“已复用”；
- analyze：明确“已复用”；
- review/export：明确“已复用，打开此前审核结果”；
- completed 页面 HTTP 返回正常，关闭服务后进程正常退出；
- timeline、analysis、review、MP4 和 SRT 的 SHA-256、字节长度和最后修改时间逐项不变；
- 没有重复 ASR、没有模型请求、没有重复 FFmpeg 导出、没有覆盖输出；
- 只有 `pipeline_status.json.updated_at` 随本次状态确认更新，三个阶段仍准确为 completed。

## 10. Windows 启动器

通过，带一项验证范围说明。

- 从位于含空格路径的仓库实际双击/打开 `Start-LiveClip.cmd`，成功进入
  `Start-LiveClip.ps1` 并弹出原生单选 MP4 对话框。
- 真实取消选择后启动器进程正常退出，没有失败暂停、管理员提示或残留进程。
- 使用一个 Git 忽略的占位 MP4，真实输入并回读含中文、空格、`&` 和圆括号的路径；路径逐字符
  一致，对话框接受并进入模型选择阶段。
- `.cmd` 使用带引号的 `%~dp0` 定位脚本；PowerShell 使用 `-LiteralPath`/`Join-Path` 和参数数组
  调用 `& $python -m liveclip run --video $videoPath`，不会由空格、`&` 或圆括号重新解析命令。
- 模型选择默认索引为 0，即 Paraformer；第二项为 SenseVoice；测试固定了两个选项、默认行为和
  `--asr-model` 参数。
- Python 选择顺序为仓库 `.venv`、`LIVECLIP_ASSETS_ROOT` 下 `.venv`、最后 PATH；不要求管理员。
- `PYTHONPATH` 只在子进程调用期间修改并在 finally 恢复，没有永久写系统环境变量。

验证范围说明：为遵守桌面自动化边界，没有自动操作命令行模型选择界面；默认索引和最终参数
传递由完整源码审计与专项测试验证。真实长视频的中文/空格路径已通过统一 CLI，特殊字符路径已
通过启动器原生选择框并进入模型选择阶段。

## 11. pipeline_status

通过。

- schema 固定为 `1.0`，只包含 source 文件名/SHA、三个阶段状态、固定 artifact 文件名和 UTC
  更新时间。
- 首次 analysis 失败：`completed/pending/pending`。
- exact-SHA 恢复进入 review 前：`completed/completed/pending`。
- 导出且服务结束后：`completed/completed/completed`。
- 第二次运行仍为三个 completed，不把 review 启动或页面打开误写成新导出。
- 两份真实 status 的独立扫描均未发现盘符绝对路径、API Key/Authorization/Bearer、token、
  字幕短语、候选标题或推荐理由。
- 写入使用临时文件和 `os.replace` 原子替换；损坏旧 status 不作为 artifact 复用依据，状态由
  实际 timeline/analysis/review 重新推导。

## 12. TASK-005 两项修正

两项均已修正并通过真实验证。

1. 修改入出点或切换候选自动取消确认：候选选择、slider、数字输入、±0.1/±1 秒和恢复范围都
   走 `setRange`；该函数清空确认并禁用导出。真实入点 `+0.1 秒` 已复现此行为。
2. 导出完成显示文件名和最终范围：完成消息真实显示 MP4、SRT、最终时间范围、实际时长、输出
   文件夹和字幕条数。

低优先级显示问题：导出完成后禁用的范围控件回到 AI 原始范围，而完成消息显示正确最终范围；
review 和输出均绑定正确最终毫秒值。建议 backlog 中让禁用控件也保留 final range，减少视觉歧义。

## 13. 用户文件、失败安全与隐私

通过。

- 原视频审核前后 SHA-256 一致；runner 和 review 都不会删除或覆盖输入视频。
- 首次失败保留 timeline 和 ASR state，没有伪造 analysis/review/output。
- 第二次完整运行前后 timeline、analysis、review、MP4、SRT 的 SHA、大小和 mtime 全部一致。
- 不匹配/损坏 artifact 明确拒绝；已有未绑定输出由 exporter 的目标占用检查拒绝，不会覆盖。
- workdir 和 output 不能与源视频路径冲突；输出只创建在用户选择或默认工作目录中。
- 本次真实媒体、timeline、analysis、review、status、日志和输出全部位于 Git 忽略目录。
- tracked tree 没有 MP4、音频、SRT、真实 timeline/analysis/review/status、模型、凭据或 token。
- tracked safety 扫描 186 个文件，186 个均为文本，0 问题。
- 完整 PR 未发现真实本地路径、用户名、用户字幕/候选内容或 TASK-007 实现。

## 14. 代码复杂度与维护性

整体通过。

- `pipeline/runner.py` 负责预检、artifact 验证、复用和阶段编排；`pipeline/status.py` 只负责
  最小状态模型和原子写入。
- transcribe、analyze、review/export 继续由既有模块拥有，TASK-006 没有形成第二套算法。
- review 的两项 UI 修正局限于确认状态和完成消息，没有引入前端框架。
- 未发现数据库、任务队列、后台服务、多视频批处理、代理媒体、波形、缩略图或 TASK-007 扩张。
- `runner.py` 较集中，但错误边界、校验函数和返回对象清晰，专项测试能注入 fake 阶段。

## 15. 测试与 Actions

本地独立执行：

- `pytest tests/test_pipeline_runner.py -q`：**14 passed，0 failed**；
- `pytest tests/test_pipeline_runner.py tests/test_review_and_export.py -q`：**54 passed，0 failed**；
- SourceOnly `base-schema-media`：**212 passed，1 deselected，0 failed**；
- SourceOnly `asr-experiments`：**91 passed，2 deselected，1 deprecation warning，0 failed**；
- `pip check`：**No broken requirements found**；
- SourceOnly 三阶段 exit code 均为 0；
- `git diff --check`：0；
- tracked repository safety：**186 files，0 issues**。

审核前 latest-head Actions Run `30936057715` 对应 HEAD
`428b73015bb57bd94b3955dbf88bc84021e3c2b9`。三项 job：

- `repository-safety`：SUCCESS，186 files，0 issues；
- `lightweight-tests`：SUCCESS，212 + 91 passed，0 failed，pip check 通过；
- `task-report-gate`：SUCCESS，检测到 1 份任务报告。

三份完整日志均已读取。日志中的 `failed with exit code` 只出现在工作流回显的预置 `throw`
文本中，没有触发；没有 `##[error]`、实际 FAILED、ERROR 或非零退出。审核报告提交后仍必须等待
审核提交对应 latest HEAD 的三项 Actions 全部完成，最终状态由交接脚本重新读取。

## 16. 是否达到用户初步使用

结论：**达到受限的初步自用水平，但不能把当前模型组合的一次成功率表述为已验证。**

已达到：

- 普通用户可以双击启动器、选一个 MP4 和本地 ASR 模型；
- runner 能从 MP4 编排 ASR、analysis、review 和一次人工确认导出；
- 失败不会丢 ASR，重跑不会重复长任务；
- 合法 exact-SHA analysis 可以安全恢复到真实候选、预览、调整、确认和输出；
- 完成后再次运行不会重复 ASR、模型请求或导出。

当前限制：本次新 timeline 的真实模型输出连续两次未通过既有 schema，即使各自进行了修复重试。
因此使用同一模型/provider 的新用户不能被保证“一次从 MP4 到候选”；需要兼容且稳定的模型输出，
或后续单独改善 TASK-004 的模型可靠性。该限制不破坏 TASK-006 的编排、恢复或文件安全。

## 17. 重要问题与 backlog

### I-1｜真实模型 schema 稳定性未达到一次成功

处理：重要、非 TASK-006 回归、非阻断。不要在 runner 中放宽 schema 或复制 prompt；后续以独立
任务验证稳定模型/provider，或改善 TASK-004 的结构化输出约束和可观测性。

### B-1｜完成态禁用控件应保留最终范围

完成消息和 review 已正确显示/记录最终范围，但禁用的数字/slider 控件回到 AI 原范围。建议让
控件与完成消息一致；不影响导出文件、SRT、review 或二次复用。

### B-2｜补充启动器特殊路径的自动化回归

本次真实验证已覆盖中文、空格、`&` 和圆括号；当前提交测试主要做静态契约断言。后续可用小型
host/fake Python 固定“选择结果到 argv”的特殊字符回归，无需改变产品入口。

## 18. 最终决定与后续边界

1. run 只编排既有阶段：**通过**
2. schema 失败归因：**不是 TASK-006 造成**
3. analysis 失败保存 ASR、状态和重跑：**通过**
4. exact-SHA analysis 恢复：**通过**
5. 第二次运行不重复长任务/导出：**通过**
6. Windows 启动器普通与特殊路径：**通过**
7. pipeline_status 准确与隐私：**通过**
8. TASK-005 两项修正：**通过**
9. 原视频、artifact 和既有输出安全：**通过**
10. 阻断问题：**无**
11. 总分：**92/100，有条件通过，不要求 TASK-006-FIX**

当前继续保持 Draft。只允许将本报告提交到现有 PR #8。提交后等待 latest-head 的
`repository-safety`、`lightweight-tests`、`task-report-gate` 全部成功，再运行
`Get-PRHandoff.ps1`。由项目总指挥决定是否手动 Ready 和是否合并；本次不执行 TASK-007。
