# TASK-GITHUB-002-FIX-R｜公开仓库与自动 PR 流程独立审核评分

- 审核日期：2026-07-25（Asia/Shanghai）
- 审核对象：`huangyongming0327-hash/live-stream-smart-clipping`
- Pull Request：`#2`
- base：`master`
- head：`chore/TASK-GITHUB-002-result`
- 审核性质：独立、只读实现审核；唯一允许的工作树写入为本报告
- 明确未执行：源码修复、测试修改、workflow 修改、脚本修改、结果报告修改、ruleset 修改、新 PR、直接推送 `master`、force push、auto-merge、Ready、合并、人工准确率审核、TASK-003、模型下载或完整 ASR

## 1. 最终结论

**总分：65/100。**

**最终结论：不通过，存在一票否决项。**

**最终建议：需要 TASK-GITHUB-002-FIX2，暂不合并 PR #2。**

公开历史隔离、全对象脱敏、许可证、PR 文件范围、普通分支 push、Draft、无 auto-merge、无 force push 和 `master` ruleset 配置本身均有真实证据支持。

但本次独立读取 Actions 日志发现，baseline、PR #1 和 PR #2 的 `lightweight-tests` 都真实出现了 `2 failed, 108 passed, 1 deselected`，job 和 required check 却被标记为 success。workflow 没有在每个外部测试命令后传播非零退出码，最后成功的 `pip check` 把步骤错误地标绿，required check 因而可被测试失败绕过。

此外，`Publish-CodexAudit.ps1` 在恰好一个变更文件时把 `$changed` 解包为字符串；Windows PowerShell 5.1 配合 `Set-StrictMode -Version Latest` 读取 `$changed.Count` 会直接失败。它无法完成本任务设计的“只提交一份审核报告”流程。现有环境没有 PowerShell 7，且任务禁止修改脚本或手工绕过，因此本报告不能按要求提交到 PR #2。

## 2. 七维评分

| 维度 | 满分 | 得分 | 说明 |
|---|---:|---:|---|
| 需求实现程度 | 25 | 16 | 新脱敏历史、公开仓库、PR、ruleset 和报告链已建立；审计发布器单报告不可用，handoff、启动同步、发布前测试等要求未完整实现。 |
| 正确性与稳定性 | 20 | 10 | 普通 push 与 PR 恢复逻辑有界且不 force；但 CI 把真实测试失败标为 success，审计发布器在正常单文件场景崩溃。 |
| 测试与验证质量 | 15 | 6 | 本地 source-only 测试通过，安全合成探针有效；三次在线测试均有 2 个真实失败且未使 job 失败，原结果未识别该事实。 |
| 代码简洁与可维护性 | 15 | 11 | 五个脚本短小、职责清楚；数组标量化、外部进程退出码和多个 handoff 缺项说明边界处理不足。 |
| 性能与资源影响 | 10 | 10 | 无模型、媒体、runtime、环境或大型依赖进入仓库；Actions 仅安装轻量锁定依赖。 |
| 安全与任务边界 | 10 | 8 | 脱敏、禁止 force/merge、Draft、scope regex 和 ruleset 均较强；假绿 required check 与任意 GitHub 仓库 URL 可被接受削弱发布边界。 |
| 文档与可追溯性 | 5 | 4 | 文档和结果报告完整；但把三项绿色状态当作通过，未披露 `lightweight-tests` 日志中的实际失败。 |
| **总分** | **100** | **65** | **一票否决，不通过。** |

## 3. 阻断问题

### B-01｜三次 `lightweight-tests` 真实失败但 required check 假绿

以下 run 的 API conclusion 均为 success，三个 job/step 也显示 success：

| 场景 | run ID | head SHA | API 状态 |
|---|---:|---|---|
| baseline `master` | `30107297389` | `001fee64bf48549592a6a533b8a249f27b56e564` | success |
| PR #1 smoke | `30107427185` | `f5baa7bec7133dc2ebe77266d835843931ad5b5f` | success |
| PR #2 审核前最新 | `30108314421` | `2d02d3947daf26eaea92ec6baa0c933bf88cb00e` | success |

但三份完整日志都包含：

- `FAILED tests/test_media_unit.py::test_process_runner_preserves_chinese_output`
- `FAILED tests/test_media_unit.py::test_process_runner_returns_structured_nonzero_failure`
- `2 failed, 108 passed, 1 deselected`

第一个失败表现为中文子进程探针以退出码 1 结束；第二个失败表现为 stderr 得到转义序列而非预期中文文本。随后 ASR 子集为 `35 passed, 2 deselected`，最后 `pip check` 成功。

`.github/workflows/pr-checks.yml` 在同一个 PowerShell `run` block 中顺序执行两组 pytest 和 `pip check`，没有逐项检查 `$LASTEXITCODE`，也没有启用原生命令失败传播。最终成功命令使整个步骤返回成功。

影响：

- required check 可在基础测试失败时被错误满足；
- baseline、冒烟 PR 和 PR #2 的“绿色”不能证明 lightweight tests 通过；
- `master` ruleset 虽真实要求该 context，但该 context 本身不可靠；
- 触发“required checks 可绕过 / 必需检查实际失败”的一票否决。

### B-02｜`Publish-CodexAudit.ps1` 无法发布唯一审核报告

脚本把三个 Git 命令的输出放入 `@(...)`，再经 `Where-Object` 和 `Sort-Object -Unique` 管道赋给 `$changed`。当只有一个审核报告变化时，最终值是 `System.String`，不是数组。

Windows PowerShell 5.1、`Set-StrictMode -Version Latest` 下，随后访问 `$changed.Count` 报错：

`The property 'Count' cannot be found on this object.`

独立探针结果：

- 一个越界变更：在到达路径校验前即触发同一 `.Count` 错误；
- 两个越界变更：能到达并正确触发“只允许 `tasks/reports/*_AUDIT.md`”拒绝；
- 五个脚本语法解析均为 0 error；
- 环境不存在 `pwsh`，不能用另一 PowerShell 运行时验证或规避；
- 本任务要求恰好只有本报告一个变化，因此真实发布调用必然在 commit/push 前失败。

任务明确禁止修改脚本和手工绕过。故本报告只能保留在本地工作树，不能提交、不能推送，也不会触发新的 PR #2 Actions。

## 4. 重要问题

### I-01｜GitHub Windows 上的两个中文子进程测试实际不通过

相同 source-only 命令在现有 D 盘 Python 3.12 环境、公开工作副本中为 `110 passed, 1 deselected`；GitHub Windows runner 三次稳定重现上述 2 个失败。这不是瞬时网络问题，而是可重复的 runner 行为差异。FIX2 需要先让真实测试通过，再修正 workflow 的退出码传播。

### I-02｜workflow 没有并发取消

workflow 有最小 `contents: read` 权限、无 `pull_request_target`、无 secrets、无 artifact 上传，但没有 `concurrency` 配置，不满足要求中的同 PR/分支旧 run 取消。

### I-03｜`Start-CodexTask.ps1` 不执行或验证 `pull --ff-only`

脚本会检查干净工作树、`master`、分支命名和本地重名，然后直接 `switch -c`。它既没有 `pull --ff-only`，也没有验证本地 `master` 与远端同步，因此可以从过期 `master` 创建任务分支。

### I-04｜`Publish-CodexTask.ps1` 提交前不运行测试

脚本在 commit 前运行 publish-candidate 安全扫描、staged 安全扫描和 `git diff --cached --check`，但没有调用 source-only tests 或 `pip check`。测试只依赖后续 Actions，而当前 Actions 又会假绿。

### I-05｜remote URL 校验接受任意 GitHub 仓库

脚本只验证 URL 主机形状并从中提取任意 owner/repository。静态探针证明另一个 GitHub owner/repository 也能匹配并被派生为发布目标；没有与预期仓库或既定仓库标识比对。

### I-06｜`Get-PRHandoff.ps1` 输出字段不完整

实测可以输出 PR URL/number/title/state、Draft、base/head 分支、merge state、review、auto-merge 和 checks；但缺少：

- repository 标识字段；
- 最新 head SHA；
- RESULT/AUDIT 是否存在；
- 审核分数；
- 是否允许手动合并。

## 5. 一般问题

### G-01｜外部任务指令中的发布参数与现有脚本接口不一致

外部指令给出的 `-TaskId/-AuditReport` 不是仓库内脚本参数。仓库实际接口是 `-ConfirmScope/-CommitMessage`，并与 `docs/CODEX_GITHUB_WORKFLOW.md` 一致。本次只能按现有脚本真实接口尝试；即使使用真实接口，仍会被 B-02 阻断。

## 6. 原私有仓库只读证据

审核前后只读状态一致：

- HEAD：`24b2496a23aa5fcf26f334fc18e5757c31bbba1f`
- HEAD tree：`153d601e0cb5817063af97e6bc678d31f00e03b3`
- 当前分支：`master`
- remote：0
- refs：3，分别为 `master`、`baseline-task-001`、`baseline-task-002-tech`
- tracked diff：0
- cached diff：0
- 唯一非忽略项：既有 `TASK-GIT-002-R_AUDIT.md`

指令给出的 refs manifest SHA-256 为 `7EFA7BD0173B43037ED5154251311290D9EC1C1B952984898ECD3BEBB6379833`，结果报告记录前后相同。本次指令未给出该 manifest 的字节序列化规则，因此没有把另一种自建序列化哈希冒充为复算值；本次直接逐项验证了完整 refs、HEAD、tree、branch、remote 和 tracked/index 状态。

公开仓库 API 无法读取上述私有 commit、两个私有 tag object SHA 或 TASK-001 私有 commit；公开可达集合也不包含它们。未发现原私有仓库新增 commit、tag、branch、remote、tracked 修改、历史重写或上传证据。

## 7. 全新公开历史与全对象扫描

在线和本地 Git 对象证据一致：

- 唯一 root commit：`001fee64bf48549592a6a533b8a249f27b56e564`
- root parent：0
- root message：`chore: publish sanitized project baseline`
- root tree：`01fad12e07e8e76e1ad12e94402d54b0944689b7`
- annotated tag：`public-baseline-task-002-tech`
- tag object：`9bdd28a39b7fac918556802ff38f4dd374a692e8`
- tag peel：`001fee64bf48549592a6a533b8a249f27b56e564`
- 在线 `master` tree：117 blobs，完整、未截断，最大 blob 32,192 bytes
- 本地全部 refs 可达集合：1 个 root、7 个 commits、127 个唯一 blobs、最大 blob 32,192 bytes

对 `master`、当前公开分支、public tag、PR #2 head 和本地保留的 smoke remote-tracking ref 的全部可达 blob 扫描结果：

- 大于 5 MiB：0
- NUL：0
- 禁止媒体/模型/二进制/压缩包扩展：0
- 禁止环境/runtime/cache/user-data 路径：0
- 个人 Windows/POSIX home、真实用户、机器标识、私有项目绝对路径、Codex 私有路径：0
- 私人邮箱、私有 IP、高置信 token、私钥：0
- 旧私有 commit/tag object 可达：0

安全脚本合成探针：

- 安全中文、所有允许占位符和普通文字 “API Key”：通过；
- 合成私钥、合成高置信 token、模型扩展、MP4 扩展、真实格式 Windows user-home 路径：分别被拒绝。

未发现模型、媒体、环境、runtime、缓存、日志、字幕、识别结果、用户数据或大型异常 blob 被上传。

## 8. 许可证与 README

- GitHub license API：`Apache-2.0`
- 本地 `LICENSE` 与 API 内容逐字节一致
- bytes：11,357
- SHA-256：`C71D239DF91726FC519C6EB72D318EC65820627232B2F796219E87DCF35D0AB4`
- `NOTICE` 首行：`Copyright 2026 live-stream-smart-clipping contributors`
- 无私人邮箱
- README 明确仓库代码和自有文档采用 Apache-2.0，外部 FFmpeg、ASR runtime 和模型遵守各自许可证且不随仓库分发
- README 明确尚无正式一键安装版、不宣称准确率冠军、人工准确率审核未完成、TASK-003 尚未开始

许可证和第三方分发边界通过。

## 9. PR #2 定向审核

在线状态：

- state：open
- Draft：true
- merged：false
- auto-merge：null/disabled
- base：`master`
- head：`chore/TASK-GITHUB-002-result`
- 审核前 head SHA：`2d02d3947daf26eaea92ec6baa0c933bf88cb00e`
- title：`TASK-GITHUB-002-FIX: publish sanitized repository result`
- commits：5，线性父链
- changed files：4

| 文件 | 安全性与必要性 | 结论 |
|---|---|---|
| `.github/workflows/pr-checks.yml` | 只更新官方 Actions 的完整固定 SHA；`actions/checkout`=`d23441a48e516b6c34aea4fa41551a30e30af803`，`actions/setup-python`=`ece7cb06caefa5fff74198d8649806c4678c61a1`，两者均为官方仓库、40 位 SHA、GitHub verified commit。 | 文件范围合理；但 workflow 原有假绿缺陷未修复，阻断合并。 |
| `docs/CURRENT_STATUS.md` | 只增加本任务状态段，没有人工准确率或 TASK-003 越界。 | 安全、必要。 |
| `tasks/reports/TASK-GITHUB-002-FIX_RESULT.md` | 记录历史、脱敏、Actions、ruleset、smoke 和边界；无隐私或大对象。 | 范围必要；对绿色 Actions 的解释遗漏真实失败。 |
| `tools/github/Publish-CodexTask.ps1` | 增加最多 3 次普通 push、2 秒间隔；无 force、无历史删除、无 merge/auto-merge；PR create 失败后只查询唯一同 head/base 的既有 open PR，不再次 create。 | 网络恢复逻辑总体安全；但缺少预期仓库绑定和提交前测试。 |

四文件没有模型、媒体、用户数据或 TASK-003 越界；但 B-01 属于该 PR 应阻断合并的 correctness/CI 问题。

## 10. 五个自动化脚本

| 脚本 | 通过项 | 未通过项 |
|---|---|---|
| `Start-CodexTask.ps1` | 拒绝脏工作树、非 `master`、非法分支名、本地同名分支；仅正常 `switch -c`。 | 不执行/验证 `pull --ff-only`，不保证从最新 `master` 启动。 |
| `Invoke-RepositorySafetyCheck.ps1` | 路径、扩展、5 MiB、NUL、UTF-8、个人路径、邮箱、IP、token、私钥等检查有效；合成正负探针符合预期。 | 本次未发现阻断性漏检。 |
| `Publish-CodexTask.ps1` | 拒绝 base/current 分支；安全扫描、staged 扫描、diff check、普通 push、有界重试、Draft、同 PR 恢复、REST 复核；无 force/merge/auto-merge。 | 不运行测试；remote 接受任意 GitHub 仓库。 |
| `Publish-CodexAudit.ps1` | 路径规则只接受 `tasks/reports/*_AUDIT.md`；两个越界文件能被拒绝；仅普通 `git push`，无 merge/auto-merge。 | 单一变更时 `.Count` 崩溃，正常一报告发布不可用。 |
| `Get-PRHandoff.ps1` | PR #2 的 URL、Draft、base/head、merge、review、auto-merge、三项 checks 可读。 | 缺 repository、head SHA、RESULT/AUDIT、分数和是否允许合并。 |

五个 PowerShell 文件均通过 AST 语法解析，0 errors；运行时和需求缺陷如上。

## 11. GitHub Actions 与日志

workflow 通过项：

- trigger：`push` 到 `master`、`pull_request` 到 `master`、`workflow_dispatch`
- 无 `pull_request_target`
- 顶层权限仅 `contents: read`
- Windows runner、Python 3.12
- 不下载模型、真实媒体或大型 ASR runtime
- 不上传 artifact
- 三个 job 名称与 ruleset contexts 一致
- checkout/setup-python 为官方 Action、完整 SHA、verified commits
- `repository-safety` 和 `task-report-gate` 日志有真实执行证据

workflow 未通过项：

- `lightweight-tests` 三次真实失败却 conclusion success；
- 没有逐原生命令退出码传播；
- 没有 concurrency cancellation；
- 完整日志只有 GitHub 托管 runner 的临时缓存路径，没有本地用户身份、私有项目路径、机器身份、私人 IP、密钥或 token。

三项 Actions 的 API 绿色结果不等于三项检查真实可靠。B-01 触发一票否决。

## 12. master ruleset 与仓库设置

官方 API 和 `gh ruleset check master` 一致：

- visibility：public
- default branch：`master`
- `master` 在线显示 protected
- ruleset：`Protect master`
- ID：`19696285`
- enforcement：active
- bypass actors：0
- current user bypass：never
- required PR：enabled
- required conversation resolution：true
- required checks：`repository-safety`、`lightweight-tests`、`task-report-gate`
- strict up-to-date：true
- deletion：prohibited
- non-fast-forward/force push：prohibited
- repository auto-merge：false

按指令未执行破坏性 push 测试。规则集本身真实存在并应用 4 条规则；但 `lightweight-tests` 假绿使 required-check 质量保证可被绕过，因此不能据此建议合并。

## 13. 冒烟 PR #1

- PR #1：closed、Draft、merged=false、auto-merge=null
- base：`master`
- head：`chore/TASK-GITHUB-002-workflow-smoke`
- changed files：1
- commits：1
- 只新增一份脱敏 smoke report
- 在线 smoke branch：已删除
- 本地实际 branch：仅 `master` 和 `chore/TASK-GITHUB-002-result`；没有 smoke 本地 branch
- 同 result head/base 的 open PR：只有 PR #2
- 未发现 force、重复 PR、自动合并或错误合并

但是 smoke Actions run `30107427185` 的 `lightweight-tests` 同样真实有 2 个失败，只是被错误标绿。故“冒烟 PR 三项真实通过”不成立。

## 14. 本地测试

全部命令在公开工作副本目录执行；未安装或更新依赖，使用现有 D 盘 Python 3.12 环境：

| 检查 | 结果 |
|---|---|
| 五个 PowerShell 脚本语法 | 5/5，0 parse errors |
| safety 安全中文/占位符/普通 “API Key” | passed |
| safety 合成私钥/token/模型/MP4/user-home | 5/5 rejected |
| `Publish-CodexTask` current=base 拒绝 | rejected before commit/push |
| `Publish-CodexAudit` 两个越界文件 | 正确拒绝 |
| `Publish-CodexAudit` 一个越界文件 | `.Count` 运行时错误，暴露 B-02 |
| `Get-PRHandoff` PR #2 | 成功读取，但字段不完整 |
| source-only 基础测试 | `110 passed, 1 deselected` |
| source-only ASR 实验测试 | `35 passed, 2 deselected, 1 warning` |
| `pip check` | `No broken requirements found.` |

系统 Python 没有 pytest，按禁止安装依赖的边界未安装；随后使用既有 D 盘环境重跑成功。未运行 FFmpeg 集成、模型、完整 ASR 或人工准确率审核。

## 15. 安全边界与在线最终状态

审核确认：

- 原私有归档 tracked/index/refs/remote 未变化；
- 原始视频、模型、环境、用户数据未删除、覆盖或上传；
- 未创建新分支或新 PR；
- 未直接 push `master`；
- 未 force push、merge、auto-merge、Ready；
- 未修改 ruleset；
- 未修改 PR #2 的四个原变更文件；
- 未修改结果报告；
- 未执行人工准确率审核或 TASK-003。

由于 B-02，本报告发布前后的远端状态保持不变：

- PR #2 最新远端 head SHA：`2d02d3947daf26eaea92ec6baa0c933bf88cb00e`
- Draft：true
- merged：false
- auto-merge：disabled
- `repository-safety`：API success
- `lightweight-tests`：API success，但日志真实失败，不能视为通过
- `task-report-gate`：API success
- 新审核报告 commit：无
- 新审核报告 push：无
- 新 Actions run：无

## 16. FIX2 必须完成的最小范围

1. 修复 GitHub Windows 上两个真实失败的中文子进程测试或实现，使测试本身通过。
2. 让 workflow 在任一 pytest/pip 命令非零时立即失败，并增加 concurrency cancellation。
3. 修复 `Publish-CodexAudit.ps1` 单元素数组标量化，补充单一合法报告和单一越界文件的运行测试。
4. 补齐 `Start-CodexTask.ps1` 的 `pull --ff-only`/up-to-date 保证。
5. 在 `Publish-CodexTask.ps1` 提交前运行要求的 source-only 测试，并绑定预期仓库。
6. 补齐 `Get-PRHandoff.ps1` 的 repository、head SHA、RESULT/AUDIT、审核分数和是否允许合并字段。
7. 重新运行并逐日志确认三项 required checks；不得只读取绿色 conclusion。

## 17. 最终建议

**需要 TASK-GITHUB-002-FIX2，暂不合并 PR #2。**

本次不把 PR 改为 Ready，不启用 auto-merge，不合并，不执行人工准确率审核，不执行 TASK-003。
