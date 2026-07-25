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
- 当前准备进入单独的人工准确率审核；无参考字幕，因此 CER/WER 尚未计算，也尚未确定最终生产模型。20 窗口审核包已生成，但人工审核本身尚未执行。
- 所有 ASR 环境、模型、缓存和结果位于 D 盘并继续被 Git 忽略；基础 `.venv` 未污染；无 CUDA/NVIDIA 包；TASK-003 尚未开始。

## TASK-002-HUMAN-001

- 状态：20 窗口本地人工听音审核包已生成并通过静态、结构和真实本地输入验证；等待用户完成 20 个窗口的人工听音，当前进度为 0/20。
- 审核包完全离线，可直接使用 Chrome/Edge 打开；支持三候选并排比较、三模型严重度、错误标签、实际听写、备注、难辨认标记、localStorage 自动保存、JSON/CSV 导入导出和草稿/完成状态。
- 真实音频片段、运行时 `review-data.json`、用户审核结果、备注和导出文件只保存在被 Git 忽略的 `local-data/`，不会进入公开仓库。
- 尚未形成最终人工准确率结论，未计算或伪造 CER/WER，尚未确定生产 ASR 模型；TASK-003 尚未开始。

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
- TASK-002 技术阶段已经通过，但人工准确率审核尚未完成，TASK-003 尚未开始。

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
- 20 窗口离线审核包已生成，当前等待用户完成人工听音；CER/WER、准确率排名和最终生产模型仍未确定，TASK-003 尚未开始。

## 建议下一个任务

- 下一步由用户在本地完成 20 窗口人工听音并保留 `asr-human-review-completed.json`；在该文件交回前不宣布准确率冠军，也不执行 TASK-003。

## 约束核验

- 未删除原始视频或其他用户文件，未覆盖无关文件；
- FFmpeg 仍是原有项目内 8.1.2 安装；FIX3 前后现有安装标记、`ffmpeg.exe` 和 `ffprobe.exe` 哈希完全不变，未访问 UNC/网络共享，未下载归档，未重新安装 FFmpeg；
- TASK-002 只下载公开依赖和官方 ASR 模型到 D 盘；样本、音频、字幕和结果未上传，未调用云端 ASR、收费 API 或 OpenAI API，未写入 API Key；
- TASK-002-FIX/FIX2 未下载或更新模型、未安装或更新依赖，未修改 SenseVoice/Faster-Whisper 适配器或正式 `src/liveclip`，也未重跑三套全长实验；
- 原始样本前后 SHA-256 一致；未修改用户或系统 PATH、永久环境变量或电源计划；基础 `.venv` 未污染；未安装 CUDA、GPU PyTorch 或 NVIDIA 包；
- 未执行人工准确率审核或 TASK-003，未生成正式 `timeline.json`；只创建 TASK-002 技术阶段的本地 commit 和 tag，未创建 remote 或执行 push。
