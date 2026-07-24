# TASK-GIT-002-R｜ASR 技术基线独立审核与质量评分

- 审核日期：2026-07-24（Asia/Shanghai）
- 项目目录：`<PROJECT_ROOT>`
- 审核性质：独立、只读 Git / 安全 / 质量审核
- 唯一正式写入：本报告
- 明确未执行：源码、测试、既有文档、Git 提交、标签、remote、push、下载、安装、完整 ASR 模型实验、人工准确率审核、TASK-003、`git clean`、`git reset --hard`

## 1. 审核结论

**结论：Git 基线通过。**

第二个本地提交真实存在；`baseline-task-002-tech` 是带说明标签，标签对象、说明和 peel 结果均正确；新提交的唯一父提交正是 `baseline-task-001` peel 后的 TASK-001 基线。提交范围为 38 个文本 blob，没有模型、环境、媒体、样本、缓存、识别结果、FFmpeg、大型二进制或高置信凭据。

审核开始和全部测试结束后，工作区与暂存区均干净；仓库无 remote、无 remote refs、无本地 push 配置和嵌套 Git 仓库。ASR 实验 37 项、基础测试 148 项、媒体验证 18 项全部通过，0 failed、0 skipped；四个环境 `pip check` 通过，三份 ASR freeze 与 lock 按 5/86/27 行逐行一致。

未发现阻断问题。唯一扣分项是 `docs/CURRENT_STATUS.md` 中两处 TASK-GIT-001 遗留表述仍把 TASK-002 描述为未提交或把 `baseline-task-001` 与“当前提交”并列，和真实第二基线矛盾；同一文档的 TASK-GIT-002 当前段落及其他核心报告均正确，因此这是局部文档一致性问题，不影响 Git 对象真实性或进入人工准确率审核。

## 2. 总分和等级

- **总分：98/100**
- **等级：通过**
- **是否存在一票否决项：否**

## 3. 七维评分及扣分原因

| 维度 | 满分 | 得分 | 扣分原因 |
|---|---:|---:|---|
| 需求实现程度 | 25 | 25 | 第二提交、带说明标签、排除范围、干净状态和无 remote 全部达成。 |
| 正确性与稳定性 | 20 | 20 | commit、唯一父提交、祖先关系、tag object、peel、线性历史和工作区状态均由 Git 对象独立验证。 |
| 测试与验证质量 | 15 | 15 | ASR 37、基础 148、媒体 18 全部真实重跑，0 failed、0 skipped；四个 `pip check` 与三组 freeze/lock 均通过。 |
| 代码简洁与可维护性 | 15 | 15 | 增量限于实验包、测试、lock 和任务文档；未修改正式 `src/liveclip`，未发现无关重构、重复工具或结果驱动的生产逻辑。 |
| 性能与资源影响 | 10 | 10 | Git 未纳入模型、环境、媒体、缓存、运行结果或大文件；新增来源顺序校验为线性轻量逻辑。 |
| 安全与任务边界 | 10 | 10 | 无敏感文件、remote、push、本次下载/安装、全长推理、人工审核、TASK-003 或破坏性 Git 操作。 |
| 文档与可追溯性 | 5 | 3 | 扣 2 分：`CURRENT_STATUS.md:26`、`:71` 保留与第二基线矛盾的 TASK-GIT-001 旧表述；当前 TASK-GIT-002 段落和其他核心文档正确。 |
| **总分** | **100** | **98** | **通过。** |

## 4. 完整与短 commit hash

- 完整 commit：`24b2496a23aa5fcf26f334fc18e5757c31bbba1f`
- 短 commit：`24b2496`
- 提交标题：`baseline: TASK-002 ASR technical validation`
- Author 时间：`2026-07-23T02:29:02+08:00`
- Committer 时间：`2026-07-23T02:29:02+08:00`
- 当前分支：`master`

## 5. 父 commit

- 父 commit：`59c1d895a92d9b8319e04dd1d7fa933ef894c1a7`
- `baseline-task-001^{commit}`：`59c1d895a92d9b8319e04dd1d7fa933ef894c1a7`
- 两者相等：是
- `git merge-base --is-ancestor baseline-task-001 baseline-task-002-tech`：退出码 0
- `baseline-task-001..baseline-task-002-tech` 可达提交数：1

因此当前提交直接以 TASK-001 基线为唯一父提交，不存在额外分叉、合并或中间提交。

## 6. tag object 和 peel 结果

- 标签：`baseline-task-002-tech`
- Git object type：`tag`，确认不是 lightweight tag
- tag object hash：`224fc1410c73aa3d1824208ebb59906d90a065a1`
- tag 内部目标：`24b2496a23aa5fcf26f334fc18e5757c31bbba1f`
- tag peel 后 commit：`24b2496a23aa5fcf26f334fc18e5757c31bbba1f`
- 与 HEAD 相等：是
- 标签说明：`Verified local baseline after TASK-002 ASR technical validation`
- Tagger 时间：`2026-07-23T02:29:16+08:00`

`baseline-task-001` 仍存在，未被移动或删除。

## 7. 分支与提交历史

```text
* 24b2496 (HEAD -> master, tag: baseline-task-002-tech) baseline: TASK-002 ASR technical validation
* 59c1d89 (tag: baseline-task-001) baseline: TASK-000 and TASK-001 verified
```

- 当前分支精确为 `master`。
- HEAD 不是旧 `59c1d89`，而是新的 TASK-GIT-002 提交。
- 当前提交只有一个父提交。
- 历史为两提交直线，没有 merge、意外分叉或可见历史改写。

## 8. 提交文件数量、类型和范围

`baseline-task-001` 到 `baseline-task-002-tech`：

- 文件总数：38
- 状态：35 个新增、3 个修改、0 个删除
- 类型：18 个 `.py`、16 个 `.md`、3 个 `.txt` lock、1 个 `.gitignore`
- 统计：4,490 insertions、6 deletions
- `git diff --check`：通过，无空白错误
- 最大增量文件：`tasks/reports/TASK-002-R_AUDIT.md`，26,065 bytes

范围仅为：

- `.gitignore` 的 `tools/asr/` 排除规则；
- `experiments/asr/` 的实验源码、测试、lock，以及父包初始化文件 `experiments/__init__.py`；
- TASK-002、FIX、FIX2 的任务、结果与独立审核报告；
- ASR 依赖计划、模型对比报告、当前状态和技术决策；
- TASK-GIT-002 任务与结果报告。

`experiments/__init__.py` 虽位于 `experiments/asr/` 的父目录，但只是 71-byte 的实验包初始化文件，计入报告所述 18 个 Python 文件，不属于无关功能。提交没有 TASK-003、正式 `timeline.json`、用户样本、识别结果或意外删除。

### 逐文件 Git 对象、大小和文本检查

下表均直接取自 HEAD tree；“文本”由当前干净工作树对应 blob 的字节检查确认，“NUL”与“>5 MiB”均逐文件检查。

| 文件 | Git 类型 | bytes | 扩展名 | 文本 | NUL | >5 MiB |
|---|---|---:|---|---|---|---|
| `.gitignore` | blob | 1,350 | `.gitignore` | 是 | 否 | 否 |
| `docs/ASR_DEPENDENCY_PLAN.md` | blob | 8,098 | `.md` | 是 | 否 | 否 |
| `docs/ASR_MODEL_COMPARISON_REPORT.md` | blob | 21,772 | `.md` | 是 | 否 | 否 |
| `docs/CURRENT_STATUS.md` | blob | 8,570 | `.md` | 是 | 否 | 否 |
| `docs/DECISIONS.md` | blob | 15,231 | `.md` | 是 | 否 | 否 |
| `experiments/__init__.py` | blob | 71 | `.py` | 是 | 否 | 否 |
| `experiments/asr/README.md` | blob | 974 | `.md` | 是 | 否 | 否 |
| `experiments/asr/__init__.py` | blob | 45 | `.py` | 是 | 否 | 否 |
| `experiments/asr/adapters/__init__.py` | blob | 45 | `.py` | 是 | 否 | 否 |
| `experiments/asr/adapters/base.py` | blob | 5,981 | `.py` | 是 | 否 | 否 |
| `experiments/asr/adapters/faster_whisper.py` | blob | 5,556 | `.py` | 是 | 否 | 否 |
| `experiments/asr/adapters/paraformer.py` | blob | 14,923 | `.py` | 是 | 否 | 否 |
| `experiments/asr/adapters/sensevoice.py` | blob | 6,538 | `.py` | 是 | 否 | 否 |
| `experiments/asr/benchmark.py` | blob | 6,554 | `.py` | 是 | 否 | 否 |
| `experiments/asr/common.py` | blob | 9,773 | `.py` | 是 | 否 | 否 |
| `experiments/asr/locks/faster-whisper.lock.txt` | blob | 444 | `.txt` | 是 | 否 | 否 |
| `experiments/asr/locks/funasr.lock.txt` | blob | 1,471 | `.txt` | 是 | 否 | 否 |
| `experiments/asr/locks/sherpa-onnx.lock.txt` | blob | 84 | `.txt` | 是 | 否 | 否 |
| `experiments/asr/metrics.py` | blob | 2,622 | `.py` | 是 | 否 | 否 |
| `experiments/asr/normalize.py` | blob | 2,144 | `.py` | 是 | 否 | 否 |
| `experiments/asr/resource_monitor.py` | blob | 4,367 | `.py` | 是 | 否 | 否 |
| `experiments/asr/review.py` | blob | 7,759 | `.py` | 是 | 否 | 否 |
| `experiments/asr/tests/test_benchmark.py` | blob | 533 | `.py` | 是 | 否 | 否 |
| `experiments/asr/tests/test_common.py` | blob | 1,700 | `.py` | 是 | 否 | 否 |
| `experiments/asr/tests/test_metrics.py` | blob | 1,263 | `.py` | 是 | 否 | 否 |
| `experiments/asr/tests/test_paraformer.py` | blob | 15,203 | `.py` | 是 | 否 | 否 |
| `experiments/asr/tests/test_review.py` | blob | 1,230 | `.py` | 是 | 否 | 否 |
| `tasks/TASK-002-FIX.md` | blob | 2,502 | `.md` | 是 | 否 | 否 |
| `tasks/TASK-002-FIX2.md` | blob | 2,343 | `.md` | 是 | 否 | 否 |
| `tasks/TASK-002.md` | blob | 1,859 | `.md` | 是 | 否 | 否 |
| `tasks/TASK-GIT-002.md` | blob | 2,661 | `.md` | 是 | 否 | 否 |
| `tasks/reports/TASK-002-FIX-R_AUDIT.md` | blob | 20,418 | `.md` | 是 | 否 | 否 |
| `tasks/reports/TASK-002-FIX2-R_AUDIT.md` | blob | 17,566 | `.md` | 是 | 否 | 否 |
| `tasks/reports/TASK-002-FIX2_RESULT.md` | blob | 11,004 | `.md` | 是 | 否 | 否 |
| `tasks/reports/TASK-002-FIX_RESULT.md` | blob | 9,305 | `.md` | 是 | 否 | 否 |
| `tasks/reports/TASK-002-R_AUDIT.md` | blob | 26,065 | `.md` | 是 | 否 | 否 |
| `tasks/reports/TASK-002_RESULT.md` | blob | 5,141 | `.md` | 是 | 否 | 否 |
| `tasks/reports/TASK-GIT-002_RESULT.md` | blob | 7,578 | `.md` | 是 | 否 | 否 |

## 9. 大文件、二进制和敏感信息

- 38 个增量文件全部为文本 blob，含 NUL 文件 0，超过 5 MiB 文件 0。
- 整个 HEAD tree 最大 blob 为 32,192 bytes，没有大型 Git 对象。
- 提交树内 `.venv/`、ASR 环境、`tools/ffmpeg/`、`tools/asr/`、`模型/asr/`、ASR 基准 input/output 均为 0。
- 禁止扩展名 `.mp4/.wav/.onnx/.pt/.bin/.gguf/.exe/.dll` 及模型/压缩包扩展名均为 0。
- TASK-003 文件 0；正式 `timeline.json` 0。
- 高置信敏感正则 `AKIA...`、`ghp_...`、`sk-...`、私钥头在 HEAD 中 0 命中。
- `.env`、证书、私钥、credential/secret/token 命名文件在 HEAD 中 0。

报告或安全规范内的普通 “API Key”“token”文字未被误判为真实凭据。

## 10. `.gitignore` 核验

八个指定路径均由 `git check-ignore -v` 实际命中：

| 路径 | 命中规则 |
|---|---|
| `项目/ASR基准/input/benchmark.mp4` | `.gitignore:92:项目/*` |
| `项目/ASR基准/output/人工审核对比.md` | `.gitignore:92:项目/*` |
| `runtime/asr-envs` | `.gitignore:21:runtime/*` |
| `runtime/asr-benchmark` | `.gitignore:21:runtime/*` |
| `tools/asr` | `.gitignore:43:tools/asr/` |
| `模型/asr` | `.gitignore:94:模型/*` |
| `.venv/Scripts/python.exe` | `.gitignore:18:.venv/` |
| `tools/ffmpeg/bin/ffmpeg.exe` | `.gitignore:42:tools/ffmpeg/` |

媒体、模型、runtime、压缩包、可执行文件和凭据规则也仍在 `.gitignore` 中。未发现允许禁止内容重新进入 Git 的反向规则。

## 11. 工作区、暂存区、remote 和嵌套仓库

报告写入前的审核开始状态及全部测试结束状态一致：

```text
## master
```

- `git diff --exit-code`：0
- `git diff --cached --exit-code`：0
- 工作区：干净
- 暂存区：干净
- `git remote -v`：无输出
- `refs/remotes`：0
- `branch.master.remote`：未配置
- `remote.pushDefault`：未配置
- 项目根之外的嵌套 `.git` 文件/目录：0

因此未发现 remote 或 push 的本地证据。由于本任务要求生成报告且禁止提交，写入本报告后预期唯一非忽略工作区项为 `?? tasks/reports/TASK-GIT-002-R_AUDIT.md`；该状态不代表被审核基线在报告前不干净，且暂存区仍为空。

## 12. 测试、依赖和 lock

| 检查 | 实际结果 |
|---|---|
| `experiments/asr/tests` | 37 passed、0 failed、0 skipped；0.45 秒；1 条既有 `audioop` 弃用 warning |
| `tools/Run-Tests.ps1 -ra --durations=10` | 148 passed、0 failed、0 skipped；pytest 32.62 秒；脚本内 `pip check` 通过 |
| `tools/Validate-Media.ps1` | 能力、合成端到端、同步和关键集成全部通过；18 passed、0 failed、0 skipped；`TRIM_VALID=True`、`BURN_VALID=True` |
| 基础 `.venv` `pip check` | `No broken requirements found.` |
| sherpa-onnx `pip check` | `No broken requirements found.` |
| funasr `pip check` | `No broken requirements found.` |
| faster-whisper `pip check` | `No broken requirements found.` |
| sherpa freeze vs lock | 5/5 行，顺序和内容完全一致 |
| funasr freeze vs lock | 86/86 行，顺序和内容完全一致 |
| faster-whisper freeze vs lock | 27/27 行，顺序和内容完全一致 |

ASR 测试只运行现有单元/回归测试和已有 399 段产物的字节级重建检查，没有加载或运行三套完整模型实验。未执行人工准确率审核。

## 13. 文档一致性

一致且有真实证据的核心事实：

- TASK-002 技术实验由 TASK-002-FIX2-R 以 100/100 最终通过；
- 不需要 FIX3；
- 人工准确率审核尚未开始；
- CER/WER 尚未计算；
- 最终生产模型尚未确定；
- TASK-003 尚未开始；
- 当前 commit 和 `baseline-task-002-tech` 是技术阶段稳定基线。

上述事实在 `DECISIONS.md`、`TASK-GIT-002.md`、`TASK-GIT-002_RESULT.md`、`TASK-002-FIX2-R_AUDIT.md` 以及 `CURRENT_STATUS.md` 的 TASK-002/TASK-GIT-002 当前段落中一致。

局部不一致：

1. `docs/CURRENT_STATUS.md:26` 仍写“TASK-002 结果仅存在于未提交工作树，没有创建新提交”，与真实 `24b2496` 提交冲突。
2. `docs/CURRENT_STATUS.md:71` 仍写首个基线由“当前提交”和 `baseline-task-001` 标识；当前提交实际已是 TASK-002 基线，首个基线应由原提交 `59c1d89` 与 `baseline-task-001` 标识。

同一文件的 `:32`、`:73` 已正确说明当前提交和 `baseline-task-002-tech` 是 TASK-002 技术稳定基线，因此此问题是 TASK-GIT-001 历史段落未改为历史时态，不是 TASK-GIT-002 结果报告或 Git 对象造假。

## 14. 代码简洁性与可维护性

- 未修改正式 `src/liveclip`。
- 实验代码通过独立 adapters、公共 artifact/校验、benchmark 编排、metrics、review 和 resource monitor 分责，结构与任务匹配。
- Paraformer FIX/FIX2 集中在来源顺序校验、结构化排除和必要测试；未把 399、正式文件哈希或样本时长硬编码进生产适配器逻辑。
- `common.py` 的公共排序保留，但 Paraformer 在进入公共层前校验来源异常；职责与既有 FIX2 审核一致。
- 未发现为建立 Git 基线新增多余工具、审核报告被程序引用、无关代码重构或重复执行脚本。
- 任务历史报告数量较多，但每份对应 TASK-002、R、FIX、FIX-R、FIX2、FIX2-R 和 Git 基线的独立审计链，有明确可追溯用途，不因数量本身扣分。
- 唯一已知维护提示是 Python 3.13 将移除 `audioop`；当前 Python 3.12 只产生弃用 warning，不阻断本基线。

## 15. 安全与任务边界

本次审核确认并遵守：

- 未删除、覆盖或修改原视频、统一 WAV、模型、人工审核包或既有识别结果；
- 未下载、安装、卸载或更新任何内容；
- 未上传视频、音频、字幕或结果；
- 未调用云端 ASR、收费 API 或 OpenAI API；
- 未运行三套完整 ASR 推理；
- 未执行人工准确率审核；
- 未执行 TASK-003，项目外除 `runtime/` 测试临时范围外没有正式 `timeline.json`；
- 未创建/修改 commit、tag、branch、remote 或 push；
- 未执行 fetch、pull 或其他 Git 网络操作；
- 未执行 `git clean`、reset、rebase、merge、amend、revert 或历史改写；
- 未修改 Machine/User PATH 或全局 Git 配置。

## 16. 文件与环境变化

测试前后下列受保护对象的 SHA-256、大小和修改时间均一致：

| 对象 | SHA-256 |
|---|---|
| 原 MP4 | `DA2CD4041C7FB59A1DFC08C80B0358C28DBBDC59608A469EB1A0A8AC63694BFF` |
| 统一 WAV | `9625C4ED1A2A501DE580BB7713ABEC3F964B93EFFFE6AF3735F719964B4E0CEA` |
| 人工审核 Markdown | `4077FFE5834902B9B6B28F45DA0CE8CF3F28E0A12BCB3EE92292E2D71E2EE504` |
| 人工审核 CSV | `3A31CEA90B97BBF7DFF032627E0B344A26EF09490964D3E37F7CE78ECED7421B` |
| SenseVoice 主权重 | `C71F0CE00BEC95B07744E116345E33D8CBBE08CEF896382CF907BF4B51A2CD51` |
| Paraformer 主权重 | `3D491689244EC5DFBF9170EF3827C358AA10F1F20E42A7C59E15E688647946D1` |
| FSMN-VAD 主权重 | `B3BE75BE477F0780277F3BAE0FE489F48718F585F3A6E45D7DD1FBB1A4255FC5` |
| CT-Punc 主权重 | `7176CAE922A872E130E6B88AEF9A1153581711BAF79C9124C7C95BE383CD6F81` |
| Faster-Whisper 主权重 | `3E305921506D8872816023E4C273E75D2419FB89B24DA97B4FE7BCE14170D671` |

环境/配置文本指纹前后相同：

- Machine PATH：`A2386B8D82237BD778BD2549B779BFB291AEFF6BBA708DEABBFE9F96C8EC30A4`
- User PATH：`3DD925D5D202B7E9FAD45620AB0CAB4EC04E33C58F17F41365DD8C03C5E30E98`
- 全局 Git 配置：`5D498D8C33A2522F73E29642407BB2F0A3D65DB7A7B029FF16AF1FB768146921`

现有测试按设计在被忽略范围内更新了 `.pytest_cache/v/cache/nodeids`，并在 `runtime/temp/pytest-*`、`runtime/temp/媒体 测试/20260724-160819-889480d3/`、`runtime/logs/media-validation-20260724-160819-889480d3.json`、`runtime/logs/ffmpeg-capabilities-20260724-160818-915.txt` 产生临时/日志文件。这些均未进入 Git，按指令保留，未执行删除。

本报告是唯一正式新增文件；没有修改其他源码、测试、文档或 Git 元数据。

## 17. 阻断问题

**无。**

未触发任一一票否决项：

- tag 精确指向预期 commit；
- 新 commit 直接以 TASK-001 基线为父提交；
- 未提交模型、环境、媒体、样本、密钥或大型二进制；
- 报告前工作区和暂存区干净；
- 关键测试无失败或跳过；
- 无 remote 或 push 本地证据；
- TASK-003 未开始；
- TASK-GIT-002 结果报告与真实 Git 对象一致。

## 18. 重要问题

### I-01｜`CURRENT_STATUS.md` 两处 TASK-GIT-001 遗留语句与当前第二基线冲突

证据为 `docs/CURRENT_STATUS.md:26` 和 `:71`。这两处把“当前提交”仍描述为首个基线，或称 TASK-002 尚未提交；真实 Git 已有 `24b2496` 和 `baseline-task-002-tech`。

影响限于历史段落措辞和可追溯性。同一文件的 TASK-GIT-002 当前段落、TASK-GIT-002 任务/结果、DECISIONS、FIX2-R 报告及 Git 对象均正确；不影响标签、提交内容、安全边界或测试结果，因此不阻断通过，也不触发 TASK-GIT-002-FIX。

## 19. 一般建议

在后续获得明确文档修改授权时，将 `CURRENT_STATUS.md:26`、`:71` 改为历史时态并明确首个基线 commit 为 `59c1d895...`。该清理可独立完成，不需要 TASK-GIT-002-FIX，也不阻止现在进入人工准确率审核。

不要在人工审核前宣布 CER/WER、准确率冠军或最终生产模型；继续保持 TASK-003 未开始。

## 20. 最终建议

**Git基线通过，进入人工准确率审核**

本报告完成后停止；不在本任务中执行人工准确率审核或 TASK-003，不创建新提交、标签、remote 或 push。
