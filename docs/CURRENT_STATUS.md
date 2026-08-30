# 当前状态

## TASK-000

- 状态：TASK-000 / TASK-000-FIX 已最终通过独立只读复核。
- 原独立审核发现的非有限数、未知版本、类型自动转换、分类值漂移、无时区时间和文本静默裁剪等问题已在 TASK-000-FIX 修复并复核。

## TASK-001

- 状态：TASK-001 及其修复已最终通过；TASK-001-FIX3-R 独立定向只读复核结论为“通过”，无阻断问题。
- 最终复核确认 UNC/远程 `file:` URI 和重解析点逃逸均被拒绝，匹配哈希的损坏归档不会发布或写标记，用户文件和真实 FFmpeg 安装保持不变。
- 最终完整回归为 148 passed、0 failed、0 skipped；媒体同步/集成为 18 passed、0 failed、0 skipped；`pip check` 通过。
- CPU `libx264` + AAC 精准裁切和字幕烧录是当前稳定基线；AMF 初始化失败仍是已知非阻断限制。

## TASK-002

- 状态：TASK-002 技术实验阶段正式通过；TASK-002-FIX2-R 最终独立复核评分为 100/100，无阻断问题，不需要 TASK-002-FIX3。
- Paraformer 整段伪时间戳及 `sentence_info` 条目之间、多个 raw item 之间的非单调漏检均已修复；异常条目会在适配器来源层结构化排除，公共排序不再把这些异常洗成正常 SRT。
- SenseVoiceSmall/sherpa-onnx INT8 热 RTF 0.02449、峰值 RSS 490.44 MiB；Paraformer/FSMN-VAD/CT-Punc 热 RTF 0.04827、峰值 RSS 5.979 GiB；Faster-Whisper small CPU int8 热 RTF 0.22376、峰值 RSS 655.27 MiB，并提供 3,033 个词级时间戳。
- 20 窗口人工审核和结果分析已经完成；MVP 主模型确定为 Paraformer，低资源备用为 SenseVoice。
- 所有 ASR 环境、模型、缓存和结果位于 D 盘并继续被 Git 忽略；基础 `.venv` 未污染；无 CUDA/NVIDIA 包。

## TASK-002-HUMAN-001

- 状态：20窗口本地人工听音审核包已生成并通过静态、结构和真实本地输入验证；用户已在后续TASK-002-HUMAN-002输入中完成20/20。
- 审核包完全离线，可直接使用 Chrome/Edge 打开；支持三候选并排比较、三模型严重度、错误标签、实际听写、备注、难辨认标记、localStorage 自动保存、JSON/CSV 导入导出和草稿/完成状态。
- 真实音频片段、运行时 `review-data.json`、用户审核结果、备注和导出文件只保存在被 Git 忽略的 `local-data/`，不会进入公开仓库。
- 本任务本身不形成模型结论；后续TASK-002-HUMAN-002已完成聚合分析和MVP基线推荐，仍未计算或伪造CER/WER；TASK-003尚未开始。

## TASK-002-HUMAN-002

- 状态：用户已完成20/20窗口人工听音；严格结果校验、双口径聚合分析、公开脱敏报告和本地完整结果已完成。
- 完成版JSON SHA-256为`160964ef19b136947663270e6dd401ea801884518a9364c47327ce2158698aef`，分析前后未变化；其`source_manifest_sha256`与真实`review-manifest.json`的`25e7d0a7c116b00b895eea0d5b67aa0ad62ff562c9d8c640685909867a9abf7b`精确匹配。
- Paraformer在20窗口中明确胜出18次，聚合质量分92.58；SenseVoice胜出2次、49.00；Faster-Whisper胜出0次、40.00。没有难辨认窗口，因此清晰音频子集结果与全量结果一致。
- MVP推荐主模型为Paraformer，备用模型为SenseVoice；决策状态为`confirmed_mvp_baseline`，置信度为高。
- 独立审核评分84/100并发现一个阻断：原实现先写正式结果、后复核输入SHA，输入在输出阶段变化时会留下误导性正式结果。
- FIX-LITE已完成最小修复：开始时固定读取JSON和manifest内存快照，全部结果先写同一临时目录，正式替换前复核双输入SHA；输入变化或生成失败会清理临时目录并保留原正式结果。
- FIX-LITE定向测试35 passed、0 failed；完整source-only为基础110 passed/1 deselected、ASR 91 passed/2 deselected，均0 failed，`pip check`通过。
- 真实本地聚合临时回归确认统计和决策不变：主模型仍为Paraformer，备用仍为SenseVoice，置信度仍为高。
- FIX-LITE 独立复核为 94/100、无阻断；PR #4 已由用户合并，merge commit 为
  `cbdf5632cc53e49ee1477797ba46d07f3fd62d74`，TASK-002 正式关闭。
- 原始人工JSON、用户备注、实际听写和`local-data/`仍只保存在本地且被Git忽略。

## TASK-003

- 状态：单 MP4 → 分块音频 → 本地 ASR → `timeline.json` / `subtitles.srt` /
  `transcript.txt` 已完成实现、fake adapter 单测、真实验证和独立审核；PR #5 已合并，
  merge commit 为 `0e619b6fbb3e34250f10b1719dfb5a666ea7020f`。
- 默认 Paraformer，SenseVoice 为用户手动选择的低资源模式；模型加载和推理均由 socket
  守卫保持离线，不下载或更新模型。
- 默认 60 秒顺序分块，每块完成后原子保存 `task_state.json`；真实异常终止验证从
  3/5 块继续，首块记录哈希不变，最终 5/5 完成。
- 22.067 秒真实短视频：Paraformer 33.59 秒、峰值工作集约 5.98 GiB；
  SenseVoice 5.53 秒、约 362.90 MiB。两者 timeline/SRT/TXT 均有效。
- 827.766 秒较长视频使用 SenseVoice 完成 14/14 块，耗时 38.54 秒、峰值工作集
  约 408.63 MiB，生成 169 条 timeline/SRT；原视频 SHA-256 未变化。
- source-only 回归：基础 128 passed/1 deselected、ASR 91 passed/2 deselected，
  均 0 failed；`pip check` 通过。
- 真实媒体、模型、字幕、状态、缓存和 `local-data/` 保持 Git 忽略；未执行 TASK-004。

## TASK-004

- 状态：单 timeline 顺序语义分析、fake HTTP client 单测、真实 timeline 离线贯通、
  中断恢复、最近 3 版本、真实文本模型 API 验证和最终 source-only 已完成；独立审计
  89/100、无阻断，PR #6 已合并，merge commit 为
  `a1e8921abb8d43d289e28282ef63e058b86e6470`。
- CLI 为 `python -m liveclip analyze --timeline "<PATH>\timeline.json"`；只支持一个
  用户配置的 OpenAI-compatible Chat Completions HTTPS 接口，不安装厂商 SDK，不自动
  切换或比较模型。
- 固定窗口最多 10 分钟且约 12,000 字幕字符，不重叠、不拆 segment、顺序请求；
  每窗口完成后原子保存状态，不并发、不做全文第二轮模型重排或 embeddings。
- 模型只提出真实连续 segment 范围、标题、摘要、理由、quote segment ID 和原始分值；
  程序计算时间、复制 quote、计算总分、执行 15—180 秒与 60 分门槛、60% 重叠去重和
  全局 20 个上限。
- TASK-004 专项为 30 passed、0 failed；与 TASK-003/既有 analysis 定向合计
  59 passed、0 failed。827.766 秒真实 timeline 的离线 fake-client 贯通为
  169 segments、2 windows、2 topics、0 candidates。
- 完整 source-only 为基础 158 passed/1 deselected、ASR 91 passed/2 deselected，
  均 0 failed；`pip check` 通过。PublishCandidates 安全扫描 167 files、0 issues，
  本地任务报告门禁通过。
- 真实 `qwen-flash` 完成态运行：827.766 秒、169 segments、2 windows、2 requests、
  16.282 秒、11 topics、6 candidates、6 recommended，分数范围 89—94；timeline SHA、
  schema、范围、时间、quote、总分和状态清理全部回溯通过。
- 前 3 候选人工抽查：3/3 quote 来自真实 segment；一项标题/理由/范围基本一致但营销
  价格主张需合规复核，一项存在标题外推、弱 quote 和结尾不完整，不宜直接采用；一项
  主题和理由基本一致但结尾略截断，且家庭健康隐私风险扣分偏低。真实候选必须继续经过
  人工审核，不把模型推荐标记视为直接发布许可。
- 真实视频、音频、timeline、analysis、state、字幕、API Key 和 `local-data/` 不进入
  Git；离线 fake-client 结果不冒充真实 API 或候选质量证据。

## TASK-005

- 状态：单视频本地候选审核、浏览器预览、毫秒级入出点调整、明确人工确认、单片段
  MP4/SRT 导出、`review_current.json` 和真实媒体验证已完成；独立审核 93/100、无阻断，
  PR #7 已合并，merge commit 为 `7ae8b89dfc92f5915030662e7a36bf048da14254`。
- CLI 为 `python -m liveclip review --video ... --timeline ... --analysis ...`，可选
  `--output`；只绑定一个相互匹配的视频、timeline 和 analysis。
- 标准库临时服务只监听 `127.0.0.1`，页面、session、媒体 Range 和导出 API 使用运行时
  随机 token；页面资源全在项目内，不加载 CDN 或第三方脚本。
- 候选全部默认“待审核”；导出按钮默认禁用，只有用户明确勾选人工预览确认并提交合法
  的 1—180 秒范围后，服务端才执行一次导出。
- FFmpeg 使用 `libx264`、`veryfast`、CRF 20、AAC 160k 与 faststart；临时 MP4 通过
  ffprobe 的 H.264/AAC 和时长校验后才与 timeline 派生 SRT 一起无覆盖发布，最后原子
  替换 review。任何失败都不生成 completed review。
- 真实 827.766 秒输入显示 6 个候选；一个候选从 51.776 秒人工调整为 51.276 秒，导出
  约 18.573 秒，MP4 为 27,639,402 bytes，ffprobe 为 51.321 秒、H.264/AAC；14 条 SRT
  从 0 开始并与 timeline 裁剪结果一致。导出视频在浏览器中播放无解码错误。
- 原视频、timeline 和 analysis 前后 SHA-256 完全一致；浏览器硬关闭后服务在心跳超时内
  停止且没有残留 Python 审核进程。真实输入、review、MP4、SRT 和运行状态继续被 Git
  忽略。

## TASK-006

- 状态：单 MP4 端到端统一入口、阶段复用/恢复、隐私最小化 `pipeline_status.json`、
  Windows 双击启动器和两项 TASK-005 易用性修正已通过审核并合并；PR #8 merge commit 为
  `97fdcd5bb782a5fafef188a1c6f8f34839d0d24a`。
- CLI 为 `python -m liveclip run --video ...`；默认 Paraformer、视频旁工作目录和其下
  `exports`，可选 SenseVoice、自定义工作/导出目录和不自动打开浏览器。
- 启动检查在 ASR 前验证 MP4、FFmpeg/ffprobe、ASR 模型、文本模型环境变量和目录写入；
  三阶段直接调用现有 transcribe、analyze 和 review，不复制核心算法。
- 同视频重跑会验证视频 SHA、timeline SHA、analysis SHA 和 completed review 的输出文件；
  合法产物复用，未完成状态交给既有恢复逻辑，损坏或错配文件停止并要求用户自行移走。
- 双击 `Start-LiveClip.cmd` 使用系统 MP4 选择框和两个 ASR 选项，不需要管理员权限、
  不修改系统环境变量，也没有引入 GUI 框架、安装包或常驻服务。
- 真实 827.766 秒输入首次完成 SenseVoice 本地 ASR；文本模型两次返回不满足 schema 的
  candidate，流程安全停止且未发布伪结果。随后对 exact-SHA 匹配的既有已审核 analysis
  进行合法复用，统一入口打开 6-candidate 审核页并完成一次人工调整、重新确认和导出。
- 真实输出目标 51.676 秒，ffprobe 为 51.721 秒、H.264/AAC，开头/中间/结尾均可解码；
  14 条 SRT 与 timeline 独立重算逐字符一致。原视频、timeline、analysis 哈希保持不变，
  二次运行三阶段均复用且无残留审核进程。
- source-only 为基础 212 passed/1 deselected、ASR 91 passed/2 deselected，均 0 failed；
  `pip check` 通过。真实媒体、状态、分析、review 和输出继续被 Git 忽略。

## TASK-007

- 状态：独立审核为 84/100，并要求修复单引号字幕路径阻断与完成态/SRT 一致性；TASK-007-FIX
  已完成最小本地实现、自动测试和真实 Windows FFmpeg 验证，等待同一 Draft PR latest-head
  三项 Actions，之后仍必须再次独立复审。
- 非空最终 SRT 与裁剪视频在同一次 FFmpeg H.264/AAC 导出中烧录；字幕固定为微软雅黑优先、
  白字、黑色描边、底部居中和安全边距，目标字号按视频高度取 24/28/32 px 三档并换算为
  libass 坐标。没有新增样式编辑、动画、翻译、纠错、改写、ASR 或文本模型调用。
- MP4、独立同名 SRT 与 `review_current.json` 只在 FFmpeg/ffprobe、输入 SHA 复核及输出校验
  全部成功后无覆盖发布；完成态现在同时校验严格布尔值和正式 SRT 内容：true 必须对应至少
  1 个合法 cue，false 必须对应合法空 SRT，不一致、损坏或缺字段均不复用且不删除旧产物。
- 启动器只选择一个真实 Python，优先仓库/资产根虚拟环境，再取 PATH 中首个非 WindowsApps
  Application；资产根缺失时列出缺失项并给出可复制的用户级 `LIVECLIP_ASSETS_ROOT` 示例，
  不再要求用户关闭 Windows 应用执行别名。
- 真实验证复用既有 827.766 秒视频、169-segment timeline 和 completed analysis，没有重跑
  ASR 或文本模型。最终输出 51.821 秒、H.264/AAC、14 条独立 SRT；开头/中间/结尾画面均
  可见基本同步的底部字幕，最长抽查字幕自然换为两行且未明显遮挡主体。
- 原视频、timeline、analysis 前后 SHA-256 不变；真实媒体、review、输出与三点抽帧均被
  Git 忽略。受控 PATH 同时放入真实 Python 与 WindowsApps 路径 Python 后，生产解析器只
  选中一个真实 Python，且 `liveclip --help` 启动成功。
- FIX 使用两层 FFmpeg filtergraph 转义并保持 `shell=False`；盘符冒号、中文、空格、`&`、
  圆括号和单引号组合路径已通过生产 exporter 的 15 秒真实烧录，移走 SRT 后 MP4 字幕像素
  仍存在，SRT 与 timeline 一致，三项输入哈希不变且无 `.part`。
- FIX 后定向回归 75 passed、媒体集成 2 passed；source-only 为基础 233 passed/1 deselected、
  ASR 91 passed/2 deselected，均 0 failed，`pip check` 通过。未执行 TASK-008。

## TASK-GIT-001

- 状态：首次私有本地 Git 基线已按 TASK-GIT-001 建立；其历史只保留在原本地私有归档中。
- 原私有仓库的 `baseline-task-001` 标识 TASK-000 和 TASK-001 的首个稳定基线。
- 该私有历史包含本机环境信息，不会上传或并入公开仓库。

## TASK-GIT-002

- 状态：TASK-002 技术阶段的第二个稳定私有本地 Git 基线已建立并通过审核。
- 原私有仓库的 `baseline-task-002-tech` 代表 TASK-002、TASK-002-FIX、TASK-002-FIX2 和 TASK-002-FIX2-R 已验收的技术阶段状态。
- 本基线不代表人工准确率审核完成，不宣布准确率冠军或最终生产模型；TASK-003 尚未开始。
- 该私有 Git 历史不上传；模型、环境、样本、缓存、识别结果、人工审核运行副本和媒体也不进入公开仓库。

## 公开工作副本

- 公开工作副本从 TASK-002 已验收源码快照重新开始，不继承原私有 `.git` 或旧提交。
- 所有公开文本使用 `<PROJECT_ROOT>`、`<USER_HOME>`、`<LOCAL_USER>`、`<LOCAL_MACHINE>`、`<LOCAL_IP>`、`<REDACTED_PATH>` 和 `<REDACTED_EMAIL>` 等占位符脱敏。
- 公开仓库不包含模型、媒体、虚拟环境、runtime、缓存、日志、运行字幕、密钥或用户数据。
- 后续开发只允许使用 `task/`、`fix/` 或 `chore/` 分支，并通过 Draft PR、自动检查和独立审核报告流转；不会自动合并。
- TASK-002 技术与人工选型阶段已经通过；TASK-003 当前通过独立任务分支交付。

## TASK-GITHUB-002-FIX

- 已从 TASK-002 验收快照建立全新的脱敏公开 Git 历史；原私有仓库和旧 Git 对象保持本地归档状态，没有重写或上传。
- 公开基线已通过文件、个人信息、凭据、媒体、模型、二进制和大文件扫描。
- GitHub Actions 提供 `repository-safety`、`lightweight-tests` 和 `task-report-gate` 三项检查。
- `master` ruleset 要求 PR、三项检查和会话解决，并禁止删除和非快进更新；仓库 auto-merge 关闭。
- 自动提交、普通 push、Draft PR 和 handoff 冒烟验证已经通过；冒烟 PR 已关闭且未合并。
- 本结果通过单独 Draft PR 交付，等待独立审核和用户手动决定是否合并。
- 未执行人工准确率审核，未执行 TASK-003。

## TASK-GITHUB-002-FIX2

- TASK-GITHUB-002-FIX-R 独立审核为 65/100、不通过，并确认 CI 假绿和单审核报告发布器崩溃两项阻断；PR #2 继续保持 Draft，暂不合并。
- FIX2 已在公开工作副本完成本地实现：统一 source-only 测试入口会逐项传播原生命令退出码，GitHub Windows 中文子进程测试改为确定性 UTF-8 字节输出，workflow 已增加 concurrency cancellation。
- Start、Publish、Audit 和 Handoff 脚本现由 `.github/liveclip-workflow.json` 绑定规范仓库；Start 同步最新 `master`，Publish 提交前运行测试，Audit 支持单一报告，Handoff 输出审核分数、head SHA、报告和合并资格。
- Windows PowerShell 5.1 临时 Git 仓库行为矩阵为 23 passed、0 failed；本地 source-only 为基础 110 passed/1 deselected、ASR 35 passed/2 deselected、均为 0 failed，`pip check` 通过。
- FIX2 实现提交 `465cab37bece9d4ee8c679d792f6c472bd9825b4` 的三项 Actions 已实际执行并通过；`lightweight-tests` 完整 259 行日志确认基础与 ASR 均为 0 failed、三个阶段退出码为 0、`pip check` 通过。最终证据提交仍须按同一标准复核最新 run。
- 当前只等待最终 latest-head Actions 复核和 TASK-GITHUB-002-FIX2-R 独立审核；不得写成已经通过在线审核或已经可合并。
- 未执行人工准确率审核，未执行 TASK-003。
- 后续状态：PR #2 已由用户手动标记 Ready 并 Squash and merge；远端 `master` 已包含 canonical repository 策略、三项 Actions、任务发布器和 handoff 工具，GitHub 工作流现已建立。

## TASK-000-FIX 完成内容

- 三个顶层 Schema 版本冻结为 `1.0`，启用严格类型、有限数和未知字段拒绝；
- 分类字段统一为稳定英文内部值，`updated_at` 强制带时区并规范为 UTC；
- 文本字段不再被全局裁剪；补齐 ID、引用、范围、视频时长、评分等级和 segment 重叠容差校验；
- 新增真实 JSON 文件往返、中文与空格路径、严格类型、非有限数、时区和文本保真回归测试；
- 新增轻量依赖锁定文件、D 盘缓存测试脚本并加强 `.gitignore`。

## 已通过测试

- 命令：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1`
- 结果：65 项通过，0 项失败，0 项跳过（2026-07-18）。
- `pip check`：通过，`No broken requirements found.`
- TASK-001 最近完整运行：90 项通过，0 项失败，0 项跳过（pytest 1.58 秒，2026-07-19）。
- TASK-001-FIX 最近完整运行：117 项通过，0 项失败，0 项跳过（pytest 3.88 秒，2026-07-19）；`pip check` 通过。
- TASK-001-FIX2 来源链专项：21 项通过，0 项失败，0 项跳过（pytest 7.50 秒，2026-07-19）；`pip check` 通过。
- TASK-001-FIX2 最终完整运行：133 项通过，0 项失败，0 项跳过（pytest 9.55 秒，2026-07-19）；`pip check` 通过。
- TASK-001-FIX3 来源链专项：36 项通过，0 项失败，0 项跳过（pytest 24.28 秒，2026-07-19）；junction 和文件 symlink 均真实创建并被拒绝；`pip check` 通过。
- TASK-001-FIX3 最终完整运行：148 项通过，0 项失败，0 项跳过（pytest 26.31 秒，2026-07-19）；`pip check` 通过。
- `tools/Validate-Media.ps1`：强制组件、合成媒体端到端流程、17 项同步单元测试和 1 项关键集成测试通过；关键同步集成测试未跳过。
- 精准裁切 2.3—8.7 秒：目标 6.4 秒，容器 6.422 秒；输出 A/V 起始差 -62.000 ms，流时长差 +61.333 ms，目标时长差 +22.000 ms，均在冻结容差内。
- TASK-002 实验专项：12 passed（2026-07-20）。
- TASK-002 最终基础回归：148 passed、0 failed、0 skipped，pytest 25.92 秒；基础 `.venv` `pip check` 通过（2026-07-20）。
- TASK-002 媒体验证：能力检查、合成端到端流程和 18 项同步/集成测试通过；`TRIM_VALID=True`、`BURN_VALID=True`（2026-07-20）。
- 三个独立 ASR 环境 `pip check` 通过，实际 freeze 与锁文件一致；三候选均完成完整冷/热、静音和离线复测。
- TASK-002-FIX 实验专项：31 passed、0 failed、0 skipped（2026-07-23）；当时覆盖单项异常和顶层 `timestamp` 数组内部非单调，但未覆盖 FIX-R 后续发现的 sentence_info 条目间/跨 raw 非单调。
- TASK-002-FIX 基础回归：148 passed、0 failed、0 skipped，pytest 36.93 秒；媒体验证 18 passed，`TRIM_VALID=True`、`BURN_VALID=True`；基础及三个 ASR 环境 `pip check` 均通过。
- TASK-002-FIX Paraformer 本地离线探针：30 秒为 18 个真实有效 segment，20 秒静音为 0 segment；两次 socket guard 均通过。
- TASK-002-FIX2 实验专项：37 passed、0 failed、0 skipped（2026-07-23）；新增 sentence_info 倒序、end 回退、跨 raw 倒序、异常后恢复、全不可用和正常空结果行为覆盖，cold/warm 399 段逐字节回归继续通过。
- TASK-002-FIX2 基础回归：148 passed、0 failed、0 skipped，pytest 39.71 秒；媒体验证 18 passed，`TRIM_VALID=True`、`BURN_VALID=True`；基础及三个 ASR 环境 `pip check` 均通过。
- TASK-002-FIX2 Paraformer 本地离线探针：30 秒为 18 个真实有效 segment、0 warning/error，20 秒静音为 0 segment、0 warning/error；两次 socket guard 均通过。
- TASK-GIT-002 提交门禁复测：ASR 37 passed、基础 148 passed、媒体验证 18 passed，均为 0 failed、0 skipped；基础及三个 ASR 环境 `pip check` 通过，三个 freeze 与 lock 按 5/86/27 行逐行一致（2026-07-23）。

## 当前状态与待办

- TASK-000 和 TASK-001 已验收；其原私有基线不进入公开历史。
- AMF 实际编码初始化失败是已知非阻断限制；精准裁切稳定基线为已通过的 CPU `libx264`。
- TASK-002 技术实验已由 TASK-002-FIX2-R 以 100/100 最终通过；公开仓库从该已验收快照建立新的干净历史。
- 20窗口人工听音与结果分析已完成；MVP主模型为Paraformer、备用模型为SenseVoice，决策为高置信`confirmed_mvp_baseline`。
- TASK-002-HUMAN-002 的发布完整性阻断已修复并复核；PR #4 已合并，TASK-002 已关闭。
- TASK-003 已通过独立审核并合并；其非阻断 backlog 未在 TASK-004 或 TASK-005 顺手修复。
- TASK-004 已通过独立审核并合并；其候选在 TASK-005 中仍全部默认待审核。
- TASK-005 已通过独立审核并合并。
- TASK-006 已通过独立审核并合并；PR #8 是 TASK-007 的最新 `master` 基线。
- TASK-007-FIX 本地实现、自动测试和真实特殊路径验证已完成；等待同一 Draft PR 三项检查，
  之后仍需新的独立复审结论。

## 建议下一步

- 下一步只继续 TASK-007-FIX 的 Draft PR 三项 Actions 与交接，再进行独立复审；保持 Draft，
  不执行 TASK-008。

## 约束核验

- 未删除原始视频或其他用户文件，未覆盖无关文件；
- FFmpeg 仍是原有项目内 8.1.2 安装；FIX3 前后现有安装标记、`ffmpeg.exe` 和 `ffprobe.exe` 哈希完全不变，未访问 UNC/网络共享，未下载归档，未重新安装 FFmpeg；
- TASK-002 只下载公开依赖和官方 ASR 模型到 D 盘；样本、音频、字幕和结果未上传，未调用云端 ASR、收费 API 或 OpenAI API，未写入 API Key；
- TASK-002-FIX/FIX2 未下载或更新模型、未安装或更新依赖，未修改 SenseVoice/Faster-Whisper 适配器或正式 `src/liveclip`，也未重跑三套全长实验；
- 原始样本前后 SHA-256 一致；未修改用户或系统 PATH、永久环境变量或电源计划；基础 `.venv` 未污染；未安装 CUDA、GPU PyTorch 或 NVIDIA 包；
- TASK-003 真实输入、临时 WAV、正式字幕、状态和模型仍只位于 Git 忽略目录；
  原视频前后 SHA-256 一致，TASK-004 未读取或上传视频和音频；
- TASK-004 真实请求只发送必要字幕字段，视频和音频未发送；API Key 未进入请求正文、
  状态、日志、结果、报告或 Git；真实 timeline/analysis/state 均未上传；
- TASK-005 没有向互联网发送视频、字幕或审核数据；原视频、timeline 和 analysis 未修改，
  真实 review、导出 MP4/SRT、运行数据和项目本地 FFmpeg 均未上传。
- TASK-007 复用现有 timeline/analysis，不重新调用 ASR 或文本模型；原视频、timeline、
  analysis SHA 不变，真实烧录 MP4、独立 SRT、review 和抽帧均留在 Git 忽略目录。没有下载
  或移动模型，没有修改系统执行别名，没有执行 TASK-008。
- TASK-007 导出将最终 SRT 同时用于固定样式烧录和独立文件；临时 MP4/SRT 通过 ffprobe、
  输入 SHA 和输出校验后才无覆盖发布，最后原子写 review。失败不发布伪完成产物。
- 产品边界继续不含批量、多片段拼接、字幕样式编辑、翻译/纠错/改写、竖屏、队列、自动
  发布、TASK-003/TASK-004 backlog 或 TASK-008。
