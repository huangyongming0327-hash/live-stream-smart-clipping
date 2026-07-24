# TASK-GIT-001｜首次本地 Git 基线结果报告

- 执行日期：2026-07-19（Asia/Shanghai）
- 项目目录：`<PROJECT_ROOT>`
- 任务范围：只建立 TASK-000 / TASK-001 验收后的第一次本地 Git 基线
- 任务状态：完成

## 1. 审核通过依据

`tasks/reports/TASK-001-FIX3-R_AUDIT.md` 已完整读取，其最终结论明确为“通过”，阻断问题为“无”。该报告确认：

- 148 项完整回归全部通过，0 failed、0 skipped；
- 18 项同步/集成验证全部通过，0 failed、0 skipped；
- UNC、远程 `file:` URI、设备/命名管道和重解析点逃逸被拒绝；
- 匹配真实 SHA-256 的损坏归档解压失败后未发布、未写标记且清理完整；
- 用户文件、真实 FFmpeg 安装和受保护项目文件未被改写。

因此 TASK-000 和 TASK-001 满足建立首次本地基线的前置条件，TASK-002 未开始。

## 2. 开始状态与环境盘点

- `git status --short --branch`：`## No commits yet on master`，全部项目候选为未跟踪状态；
- 当前分支：`master`，保持原名；
- `git log --oneline --all`：无输出，确认仓库没有提交；
- `git remote -v`：无输出，确认没有远程仓库；
- `baseline-task-001`：开始前不存在；
- 项目开始时共有 2,582 个文件，总大小 3,720,648,911 bytes（3,548.29 MiB）；
- 开始时非忽略候选 70 个，最大文件 32,192 bytes；
- 测试后被忽略的旧 pytest 临时产物按测试自身生命周期减少；最终复测后共有 2,580 个文件、2,275,241,241 bytes（2,169.84 MiB）；没有删除、移动或覆盖用户项目、模型、设置或原始媒体。

Machine/User/Process PATH 均在开始时完整读取；当前值与 `TASK-001-FIX3-R_AUDIT.md` 第 9.1 节记录的完整 PATH 相同。为避免在新报告重复持久化本机路径，仅记录确定性摘要：

| PATH scope | 字符数 | SHA-256 |
|---|---:|---|
| Machine | 160 | `015ee9c6aec4e4122f27fd6dfb16e7f7dd9fe8213b5f90548312d1606a5030b8` |
| User | 285 | `3dd925d5d202b7e9fad45620ab0cab4ec04e33c58f17f41365dd8c03c5e30e98` |
| Process | 808 | `e59a4902170551f123269fc02621ca7fa6bd424fb8e74809f274a01769c9bd23` |

## 3. FFmpeg 安装标记与二进制

现有安装标记记录 FFmpeg `8.1.2`、提供方 `gyan.dev`、历史发布方 SHA-256 比对通过且 `system_path_modified=false`。本任务没有运行安装脚本、没有下载或修改 FFmpeg。

| 对象 | SHA-256 |
|---|---|
| `tools/ffmpeg/.liveclip-ffmpeg-install.json` | `7d624c125324dc9f3f7f556a8d35de6261da7b4b1d57132708c9835ee1ec2353` |
| `tools/ffmpeg/bin/ffmpeg.exe` | `ad8f211bc894755e0061c55ab280ae00e8d3d4f15a8cc4372b24cfa247b5942e` |
| `tools/ffmpeg/bin/ffprobe.exe` | `9df3b0b5275e830961df6d94e1f7a71121a7abd5ff708e9fec8a0b6084a55015` |

## 4. 提交前测试结果

### 完整回归

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Run-Tests.ps1 -ra --durations=10
```

- 退出码：0；
- 结果：148 passed、0 failed、0 skipped；
- 最终复测 pytest 耗时：35.87 秒；
- 脚本附带 `pip check`：`No broken requirements found.`。

### 媒体验证

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\Validate-Media.ps1
```

- 退出码：0；
- FFmpeg 强制能力全部通过；
- `TRIM_VALID=True`；
- `BURN_VALID=True`；
- 18 项同步/集成测试全部通过且未跳过；
- 只处理 `runtime/` 下生成的合成媒体，没有读取用户真实视频。

### 独立依赖检查

```powershell
.\.venv\Scripts\python.exe -m pip check
```

- 退出码：0；
- 输出：`No broken requirements found.`。

## 5. `.gitignore` 核验

原规则已覆盖 `.venv/`、FFmpeg、三个本地用户数据目录、Python/pytest 缓存、模型格式和常见密钥容器。本任务仅补齐明确缺少的安全兜底：

- `runtime/*` 默认拒绝，仅允许三个目录及其 `.gitkeep`；
- 通用日志、临时文件、partial；
- `.exe`、`.dll` 和常见压缩包；
- 指令列出的媒体格式及常见补充格式；
- GGUF/GGML/TFLite 模型；
- 常见凭据文件名和额外密钥容器。

指定命令均已实际运行：

- `.venv/Scripts/python.exe` 命中 `.venv/`；
- `tools/ffmpeg/bin/ffmpeg.exe` 命中 `tools/ffmpeg/`；
- `runtime/logs` 和 `runtime/temp` 命中为允许目录本身存在的否定规则；目录内除 `.gitkeep` 外的内容继续被 `runtime/*`、子目录规则及通用日志/临时规则忽略；
- 额外探针确认任意根目录媒体文件、模型文件、私钥容器、runtime 日志和临时文件均被忽略。

`项目/`、`模型/`、`设置/` 中各只有一个 1-byte `.gitkeep` 进入候选；没有用户项目、字幕、真实视频、导出结果或模型进入提交。`samples/` 仅白名单提交 `README.md`。

## 6. 大文件、禁止类型与敏感信息检查

开始时识别到 16 个不小于 5 MiB 的文件，全部已忽略：

- `tools/ffmpeg/bin/` 中 `ffplay.exe`、`ffmpeg.exe`、`ffprobe.exe` 共 3 个，约 231.07–232.72 MiB；
- `runtime/temp/pytest-of-<LOCAL_USER>/pytest-{46,47}/` 的三个隔离用例中复制的 `ffmpeg.exe` / `ffprobe.exe` 共 12 个，约 231.07–231.26 MiB；
- `.venv/Lib/site-packages/pydantic_core/_pydantic_core.cp312-win_amd64.pyd` 1 个，5.01 MiB。

完整测试清理旧 pytest 临时目录并生成本轮隔离目录后，提交前被忽略的大文件为 10 个：上述项目内 FFmpeg 三个、`.venv` 的 `.pyd` 一个，以及 `runtime/temp/pytest-of-<LOCAL_USER>/pytest-51/` 三个隔离用例中的六个 FFmpeg/ffprobe 副本。它们均未进入候选或暂存区。

非忽略候选中：

- 大于 5 MiB：0；
- `.exe`、`.dll`、`.7z`、`.zip`、媒体或模型文件：0；
- 最大文件：32,192 bytes；
- 高置信云/API/GitHub/Slack/OpenAI 密钥格式：0 命中；
- 邮箱、手机号、身份证号：0 命中；
- 关键词扫描仅命中安全规范和历史审核报告中的说明文字，没有疑似真实凭据。

## 7. Git 身份配置

仓库级和全局级均已有可用的 `user.name` / `user.email`。本任务未修改仓库身份，未写入后备身份，也未修改全局 Git 配置。为避免把用户个人邮箱新增到项目报告，报告只记录“已存在且未修改”。

## 8. 暂存内容

计划并最终暂存 72 个小型文本/源码占位文件：

| 类型 | 数量 |
|---|---:|
| Python `.py` | 34 |
| Markdown `.md` | 24 |
| `.gitkeep` | 7 |
| PowerShell `.ps1` | 3 |
| JSON | 1 |
| TOML | 1 |
| TXT | 1 |
| `.gitignore` | 1 |
| 合计 | 72 |

这是仓库的第一次提交，因此既有已验收源码和测试虽然此前均为“未跟踪”，也作为稳定基线内容纳入；本任务没有修改业务源码或测试逻辑。

暂存后实际复核：

- `git status --short`；
- `git diff --cached --stat`；
- `git diff --cached --name-only`；
- `git diff --cached --check`；
- 再次检查暂存对象大小、扩展名和敏感模式。

首次 `git diff --cached --check` 发现 13 个既有文件在 EOF 多出空白行。仅移除这些末尾空行，不改变业务源码或测试逻辑；随后重新运行完整测试、重新暂存并复核。最终所有检查均通过，没有意外删除、二进制、媒体、模型、runtime 产物、FFmpeg、虚拟环境、用户数据或密钥。

## 9. 排除内容

- `.venv/` 与 Python/pytest 缓存；
- `runtime/` 中除三个 `.gitkeep` 外的全部日志、缓存、临时与合成媒体；
- `tools/ffmpeg/` 的安装标记、可执行文件和附带文件；
- `项目/`、`模型/`、`设置/` 的真实内容；
- `samples/` 中除说明文件外的内容；
- 本地真实配置、`.env`、凭据、私钥和证书容器；
- 二进制、压缩包、媒体和模型文件。

## 10. 提交信息

- 提交命令：`git commit -m "baseline: TASK-000 and TASK-001 verified"`；
- 提交类型：第一次本地提交；
- 完整 commit hash 不写入本报告，按指令在 Codex 最终回复中单独提供；
- 未使用 `--no-verify`，未改写历史。

## 11. 本地标签

- 标签名：`baseline-task-001`；
- 类型：带说明的本地 tag；
- 说明：`Verified local baseline after TASK-000 and TASK-001`；
- 标签指向本次首次基线提交；
- 没有覆盖既有标签，没有推送。

## 12. 最终工作区与远程状态

- 最终分支：`master`；
- 工作区：干净；
- `git log`：有且只有预期的首次基线提交；
- `baseline-task-001`：指向该提交；
- `git remote -v`：无输出；
- 未创建远程仓库，未执行 `git push`。

## 13. 安全边界

- 未执行 TASK-002；
- 未修改业务源码或测试逻辑；
- 未下载、安装或联网；
- 未运行 FFmpeg 安装脚本；
- 未删除原始视频或用户文件；
- 未修改 Machine/User/Process PATH；
- 未执行 `git reset --hard`、`git clean`、宽范围删除、分支重命名或全局 Git 配置修改；
- 未创建第二个仓库、远程仓库或推送。

## 14. 查看和使用基线

查看基线提交与标签：

```powershell
git show baseline-task-001
```

查看当前工作区相对基线的差异：

```powershell
git diff baseline-task-001
```

恢复单个已跟踪文件：

```powershell
git restore --source baseline-task-001 -- "相对文件路径"
```

恢复整个项目到基线属于高风险操作，用户未明确要求时不得执行。本任务没有实际运行 `git reset --hard` 或 `git clean`。

## 15. 已知限制

1. 本基线代表 TASK-000 和 TASK-001 的本地 Windows 技术验证状态，不代表完整桌面产品已经实现。
2. AMF 仍不可用；CPU `libx264` 是已验证稳定基线。
3. 未验证真实长视频性能、ASR、LLM、桌面 UI、数据库或完整产品导出流程。
4. Git 提交和标签仅存在于本机；没有远程备份。
5. `README.md` 中的历史状态文字未在本任务修改，因为允许修改范围仅包含 `docs/CURRENT_STATUS.md` 和本任务记录；当前权威状态以 `docs/CURRENT_STATUS.md` 与本报告为准。

## 16. 下一步建议

下一步仅建议另开一个边界明确的任务来规划 TASK-002；本任务不会自动开始或执行 TASK-002。
