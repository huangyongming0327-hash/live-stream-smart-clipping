# TASK-GIT-002｜ASR 技术阶段本地 Git 基线结果报告

- 执行日期：2026-07-23（Asia/Shanghai）
- 项目目录：`<PROJECT_ROOT>`
- 任务范围：只建立 TASK-002 技术实验阶段的第二个本地 Git 基线
- 任务状态：完成

## 1. TASK-002 最终审核结论

`tasks/reports/TASK-002-FIX2-R_AUDIT.md` 已完整读取。最终结论为“通过”，总分 100/100，无阻断问题、重要问题或需要触发 FIX3 的建议。审核确认 Paraformer 来源顺序修复、结构化排除、SRT 抑制、399 段回归、人工审核包保护、测试、环境、锁文件和安全边界全部通过。

因此 TASK-002 技术实验阶段正式结束。该结论不包含人工准确率审核，不计算 CER/WER，不宣布准确率冠军或最终生产模型。

## 2. 提交前 Git 状态

- 完整 HEAD：`59c1d895a92d9b8319e04dd1d7fa933ef894c1a7`；短 HEAD：`59c1d89`；
- 分支：`master`；HEAD 上标签：`baseline-task-001`；
- `git remote -v`：无输出；
- 暂存区：空，没有未知 staged 文件；
- 工作区开始时有 36 个非忽略候选，均与 TASK-002/FIX/FIX2/FIX2-R 的源码、测试、锁文件、文档和审核报告一致；
- 候选文件名中没有 TASK-003 或正式 `timeline.json`。

## 3. 测试结果

| 检查 | 结果 |
|---|---|
| `experiments/asr/tests` | 37 passed、0 failed、0 skipped；0.36 秒；仅 1 条既有 `audioop` 弃用 warning |
| `tools/Run-Tests.ps1 -ra --durations=10` | 148 passed、0 failed、0 skipped；pytest 31.02 秒；脚本内 `pip check` 通过 |
| `tools/Validate-Media.ps1` | 18 passed、0 failed、0 skipped；能力检查、合成端到端流程、同步及关键集成通过；`TRIM_VALID=True`、`BURN_VALID=True` |
| 基础 `.venv` `pip check` | `No broken requirements found.` |
| 三个 ASR 环境 `pip check` | 全部 `No broken requirements found.` |
| freeze 与 lock | sherpa-onnx 5/5、funasr 86/86、faster-whisper 27/27，均按顺序逐行一致 |

本任务没有运行任何完整全长模型实验，也没有执行 SenseVoice、Paraformer 或 Faster-Whisper 全长推理。

## 4. `.gitignore` 核验

指令指定的八个路径均已实际运行 `git check-ignore -v` 并命中：

- `项目/ASR基准/input/benchmark.mp4` 与 `项目/ASR基准/output/人工审核对比.md` 命中 `项目/*`；
- `runtime/asr-envs` 与 `runtime/asr-benchmark` 命中 `runtime/*`；
- `tools/asr` 命中 `tools/asr/`；
- `模型/asr` 命中 `模型/*`；
- `.venv/Scripts/python.exe` 命中 `.venv/`；
- `tools/ffmpeg/bin/ffmpeg.exe` 命中 `tools/ffmpeg/`。

`.gitignore` 本阶段只增加 `tools/asr/` 规则；既有媒体、模型、环境、runtime、用户项目和凭据规则继续生效。

## 5. 排除内容

本提交明确排除：

- `.venv/`、三个 ASR 虚拟环境和所有 runtime；
- `tools/ffmpeg/`、`tools/asr/`、全部 FFmpeg 二进制及模型运行时；
- `模型/asr/` 的模型权重和缓存；
- `项目/ASR基准/input/` 的原 MP4、统一 WAV 及其他样本；
- `项目/ASR基准/output/` 的 raw、unified、SRT、TXT、metrics、人工审核 Markdown/CSV 运行副本及其他识别结果；
- `.env`、API Key、token、证书、私钥、二进制、压缩包、媒体和模型格式。

## 6. 大文件与敏感信息检查

加入本任务记录和报告前的 36 个候选均在允许范围内：

- 禁止扩展名：0；
- 超过 5 MiB：0；最大文件为 26,065 bytes；
- 含 NUL 的二进制文件：0；重解析点文件：0；
- 常见高置信云/API/GitHub/Slack/OpenAI 密钥格式：0 命中；
- 邮箱、手机号和本机用户目录绝对路径模式：0 命中；
- 模型、媒体、环境、runtime、用户样本、结果和 TASK-003 实现文件候选：0。

本任务文件创建后按相同门禁再次核验，并在暂存后复查全部对象。

## 7. 暂存文件数量与类型

最终计划并实际暂存 38 个 TASK-002 技术阶段文件：

| 类型 | 数量 |
|---|---:|
| Python `.py` | 18 |
| Markdown `.md` | 16 |
| lock `.txt` | 3 |
| `.gitignore` | 1 |
| 合计 | 38 |

范围仅包括 `.gitignore`、`experiments/asr/` 源码/测试/锁文件、TASK-002/FIX/FIX2 任务和结果、独立审核报告、ASR 依赖与模型对比文档、当前状态、决策状态及本 Git 基线任务文档。没有意外删除。

暂存后已复核 `git status --short`、`git diff --cached --stat`、`git diff --cached --name-only`、`git diff --cached --check`，并再次执行类型、大小、二进制、敏感信息和范围检查。

## 8. 提交信息

- 提交命令：`git commit -m "baseline: TASK-002 ASR technical validation"`；
- 提交类型：仅本地普通提交；
- 完整 commit hash 不预写入本报告，按指令在 Codex 最终回复中单独提供；
- 未使用 `--no-verify`，未改写历史，未修改分支名称。

## 9. 本地标签

- 标签名：`baseline-task-002-tech`；
- 类型：带说明的本地 tag；
- 说明：`Verified local baseline after TASK-002 ASR technical validation`；
- 标签指向本次 TASK-002 技术阶段提交；
- 开始前标签不存在，没有使用 `-f`，没有推送。

## 10. 最终 Git 状态

- 当前分支：`master`；
- `git status --short --branch`：`## master`，工作区干净；
- `baseline-task-001` 保留在原 TASK-001 基线；
- `baseline-task-002-tech` 指向新提交；
- 模型、环境、样本、缓存、运行结果和 FFmpeg 继续被忽略；
- TASK-003 尚未开始，没有正式 `timeline.json`。

## 11. remote 状态

`git remote -v` 最终无输出。没有创建 remote、远程仓库或第二个仓库，没有执行 `git push` 或任何 Git 网络操作。

## 12. 安全边界

- 未修改 ASR 业务逻辑、测试逻辑或三个模型；
- 未下载、安装、更新或删除模型与依赖；
- 未运行三套完整全长模型实验，未执行人工准确率审核；
- 未上传视频、音频、字幕、审核包或识别结果；
- 未调用云端 ASR、收费 API 或 OpenAI API；
- 未删除或改写原视频、统一 WAV、正式结果或用户文件；
- 未执行 TASK-003，未创建正式 `timeline.json`；
- 未执行 `git clean`、`git reset --hard`、历史改写、分支重命名或全局 Git 配置修改。

## 13. 如何查看基线

查看带说明标签及提交：

```powershell
git show --no-patch --decorate baseline-task-002-tech
```

查看 TASK-001 到 TASK-002 技术基线的差异：

```powershell
git diff baseline-task-001 baseline-task-002-tech
```

## 14. 如何恢复单个文件

恢复单个已跟踪文件到 TASK-002 技术基线：

```powershell
git restore --source baseline-task-002-tech -- "相对文件路径"
```

执行前应先用 `git diff -- "相对文件路径"` 检查未提交修改。本任务没有实际恢复或覆盖任何文件。

## 15. 下一步

下一步仅为另开单独任务执行人工准确率审核：逐窗对照原音频，必要时形成参考字幕，再计算 CER/WER、漏句和重复。人工审核完成前不宣布准确率冠军或最终生产模型；TASK-003 仍不开始。

## 16. 回滚说明

本任务未执行回滚。若以后只需恢复单个文件，使用第 14 节的精确路径命令；若需要撤销整个基线提交，应由用户另行明确授权并优先使用保留历史的 `git revert 'baseline-task-002-tech^{commit}'`。删除本地标签也必须单独确认。不得用 `git reset --hard`、`git clean` 或宽范围删除替代可审计回滚，任何回滚都不得删除原媒体、模型、环境或用户数据。
