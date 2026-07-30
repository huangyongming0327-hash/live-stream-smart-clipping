# TASK-003-R AUDIT｜字幕生产流程独立审核

## 审核结论

- 审核对象：PR #5，`task/TASK-003-asr-production-pipeline`
- 审核起始 head：`b15fccf1c3a762ecfd1fd4f70dffc66cb7a7f11f`
- 审核方式：独立只读代码复核、完整 PR diff、真实双模型 CLI、真实中断恢复、定向失败探针、本地测试、Git/隐私扫描和 latest-head Actions 日志复核
- 总分：89/100
- 最终结论：有条件通过，可以手动Ready并决定合并，非阻断项进入backlog

核心生产闭环实际可用：Paraformer 和 SenseVoice 均对同一段 22.067 秒真实 MP4
完成分块转写并生成合法 timeline、SRT、TXT 和 state；三种正式输出逐 segment
文本与时间完全一致；真实强制中断后从下一块恢复，没有重复已完成块；发布中途失败
不会留下伪完成 timeline；原视频 SHA-256 前后不变。

本次没有发现一票否决项。两个非阻断重要问题是：适配器错误会从 CLI 泄露完整
Python traceback；本 PR 对 TASK-002 实验适配器的复用改造留下两个未被测试发现的
`NameError`。二者不影响本次已真实验证的 TASK-003 生产 CLI 正常路径，因此按审核
原则不阻断，但应进入 backlog。

## 评分

| 维度 | 得分 | 满分 | 说明 |
|---|---:|---:|---|
| 核心功能实现 | 24 | 25 | 两模型真实 CLI、分块、四项输出和离线守卫通过；适配器失败的 CLI 错误边界扣 1 分 |
| 正确性与恢复稳定性 | 20 | 20 | 时间轴、恢复指纹、源复核、失败发布和预存文件保护均通过 |
| 测试与真实验证 | 11 | 15 | source-only、18 项专项和真实验证通过；实验适配器回归及 CLI 适配器失败覆盖不足 |
| 代码简洁与可维护性 | 11 | 15 | 生产模块职责清楚、无复杂框架；两个实验入口存在确定性 `NameError` |
| 性能与资源 | 9 | 10 | 顺序分块、单 WAV、四线程；Paraformer 约 5.98 GiB 峰值较高但已披露 |
| 安全和用户文件保护 | 10 | 10 | 原视频哈希不变、非覆盖发布、离线守卫、Git 忽略和安全扫描通过 |
| 文档与可追溯性 | 4 | 5 | RESULT 和决策记录完整；源码 checkout 的 CLI 安装/启动前提可写得更明确 |
| 总分 | 89 | 100 | 有条件通过 |

## 阻断问题

未发现阻断问题。

以下一票否决项均未出现：

- 两个宣称可用的模型都能完成真实 CLI；
- timeline/SRT 时间合法、升序、无重叠且不超视频时长；
- 恢复没有重复处理已完成块；
- 失败没有发布伪完成 timeline；
- 原视频没有被修改或删除；
- Git 没有纳入媒体、模型、运行字幕、状态或隐私数据；
- 本地测试和 Actions 没有失败后标绿。

## 重要问题

### I-1｜`ASRAdapterError` 未在 CLI 顶层收口

`cli.py` 捕获 `ASRPipelineError`、`StateFileError`、`MediaError`、`OSError` 和
`ValueError`，但没有捕获 `ASRAdapterError`。实际缺模型探针返回退出码 1，末行错误
也明确指出缺失的模型文件，但同时打印了完整 Python traceback。模型加载失败和识别
失败也由同一异常类型抛出，因此具有相同表现。

这不影响正常功能，也没有伪报成功，按审核指令记为重要问题而不阻断。后续可在 CLI
顶层将 `ASRAdapterError` 转为单行用户错误，同时保留非零退出码和 state 中的结构化
错误。

### I-2｜TASK-002 两个实验适配器入口发生非核心运行时回归

PR 将实验适配器复用到正式 adapter 后，删除了模块级 `funasr` / `sherpa_onnx`
导入，但仍在转写闭包中读取：

- `experiments/asr/adapters/paraformer.py`：`getattr(funasr, "__version__", ...)`
- `experiments/asr/adapters/sensevoice.py`：`getattr(sherpa_onnx, "__version__", ...)`

独立隔离探针分别得到：

```text
NameError: name 'funasr' is not defined
NameError: name 'sherpa_onnx' is not defined
```

现有 91 项实验测试没有执行这两个真实闭包，因此 Actions 仍为绿色。TASK-003 正式
生产 adapter 和本次两模型真实 CLI 不走这两处代码，故不属于本审核的核心阻断；
但这是本 PR 引入的确定性非核心回归，不能写成“完整 diff 无问题”。

## Backlog

- 收口 `ASRAdapterError`，避免缺模型、模型加载失败和识别失败时输出完整 traceback。
- 修复两个 TASK-002 实验入口的运行时版本引用，并增加不加载大模型的闭包级回归测试。
- README 可明确写出先安装包（例如项目环境中的 editable install）或设置源码
  `PYTHONPATH` 的前提；本次审核通过源码 `PYTHONPATH` 调用，Actions 则执行
  `pip install --no-deps -e .`。
- 状态模型身份当前基于关键文件名、父目录、大小和 `mtime_ns`。若未来需要防御
  “内容被替换但大小和时间戳被刻意保持”的情况，可升级为内容哈希；正常 MVP 不阻断。
- 硬终止恰好发生在三个正式文件发布之间、用户手动修改完成输出、模型运行期间被外部
  替换等低概率文件系统竞态，维持既有 backlog，不为 TASK-003 连续追加 FIX。

## 开始状态与范围

- PR：Open、Draft、未合并，auto-merge 关闭。
- 本地分支、origin 分支和 PR head 起始时均为
  `b15fccf1c3a762ecfd1fd4f70dffc66cb7a7f11f`。
- 工作区和暂存区起始时干净；origin 为规范仓库。
- 完整 diff 为 19 个文件，2,196 additions、150 deletions，已逐文件读取。
- 未发现 TASK-004 文件或实现；本次未执行 TASK-004。
- 本次没有修改实现、测试、RESULT 或既有文档；只新增本审核报告。

## 两模型真实 CLI

输入为同一段 22.067 秒真实 MP4，审核前 SHA-256：

```text
6b39f62c868e1cce6d621a3ead273c681ec3777ba5dd175f9b9ddd45725ef445
```

使用既有 D 盘 FFmpeg、运行时和模型；未下载或更新模型。模型加载和每次识别均经过
socket 连接阻断。FunASR 虽打印 “download models from model hub” 的内部日志，
实际读取的是既有本地模型路径；如果发生 socket 连接，守卫会直接使运行失败。本次
Paraformer 成功，未发生网络连接。

### Paraformer

- 命令入口：`python -m liveclip transcribe`
- 引擎：默认/显式 `paraformer`
- 分块：10 秒，3/3 完成
- 总耗时：26.106970 秒
- 峰值工作集：6,420,492,288 bytes，约 5.98 GiB
- timeline segments：12
- state：`completed`
- timeline、SRT、TXT：存在、合法、逐项一致
- `.work`：成功后不存在

### SenseVoice

- 命令入口：`python -m liveclip transcribe --engine sensevoice`
- 分块：10 秒，3/3 完成
- 总耗时：2.333169 秒
- 峰值工作集：378,159,104 bytes，约 360.64 MiB
- timeline segments：6
- state：`completed`
- timeline、SRT、TXT：存在、合法、逐项一致
- `.work`：成功后不存在

两个真实输出目录均使用中文、空格和括号；资产根也包含中文和空格。fake adapter
专项测试另外覆盖了中文、空格和括号输入文件路径。

## 中断恢复

独立真实恢复探针使用 SenseVoice 和 5 秒分块：

1. 在 state 原子记录 2/5 块后强制终止精确识别进程；
2. 中断时 state 为 `running`，没有 timeline，`.work` 中只有当前受控 WAV；
3. 中断前前两块记录哈希为：

```text
b23cabf685465edad757c5eb035bc72e769b9b7f55eafc4fc2927d6370a587d0
06ae6b9fc7bcf35d0411c88cd4659186c337aeca44c51de45cd6adca90eaf4f5
```

4. 重跑明确输出“从分块 3/5 继续”，只识别 3、4、5 块；
5. 完成后前两块记录哈希逐字一致，证明没有重复或改写；
6. 最终 state 为 `completed`、5/5，生成 6 个一致 segment；
7. 成功后 `.work` 不存在。

现有 RESULT 的既有恢复证据也显示从 3/5 继续、首块记录哈希不变；本次独立探针与其
一致。

## 状态绑定与旧状态拒绝

代码和运行验证确认 task fingerprint 包含：

- 源 SHA-256；
- 源大小；
- 媒体时长；
- 引擎；
- 分块毫秒数；
- 本地模型身份。

已有专项测试验证源内容变化和模型身份变化会拒绝旧 state。独立真实输出上再次验证：

- 将 5 秒分块改为 6 秒：退出码 1，明确报告 state 不匹配；
- 将 SenseVoice 改为 Paraformer：退出码 1，明确报告 state 不匹配；
- 两次拒绝前后 state、timeline、SRT、TXT 哈希均不变。

损坏 state 的专项测试确认原损坏内容不会被静默覆盖。

## timeline、SRT、TXT 一致性

对本次真实 Paraformer、SenseVoice 和恢复输出逐 segment 解析并比较：

- segment 按时间升序；
- 所有 `end_ms > start_ms`；
- 无重叠；
- 不超 22,067 ms；
- 跨分块全局偏移合法；
- `text_raw` 保留原输出，`text` 仅压缩/清理空白；
- `speaker` 全部为 `null`；
- SRT 序号、开始时间、结束时间、文本与 timeline 完全相同；
- TXT 开始时间、结束时间、文本与 timeline 完全相同；
- SRT 可以完整解析。

生产实现只从同一个 `timeline["segments"]` 渲染 SRT 和 TXT，timeline 经结构校验后
最后发布。

## CLI 错误处理

实际 CLI 定向探针：

| 场景 | 退出码 | 完整 traceback | 结果 |
|---|---:|---|---|
| 输入不存在 | 1 | 否 | 明确指出文件不存在 |
| 非 MP4 | 1 | 否 | 明确要求单个 `.mp4` |
| 无音轨 MP4 | 1 | 否 | 明确指出没有音轨；无 timeline |
| 缺 FFmpeg/ffprobe | 1 | 否 | 明确列出缺失的本地工具 |
| 缺模型 | 1 | 是 | 末行明确指出缺失文件，但有完整 traceback |
| 分块参数变化 | 1 | 否 | 明确拒绝不匹配 state |
| 引擎变化 | 1 | 否 | 明确拒绝不匹配 state |

模型加载和识别失败由 `ASRAdapterError` 抛出，代码路径与缺模型相同；state 会记录
`failed` 和错误信息，但 CLI 顶层不会消除 traceback。这是 I-1，不影响非零退出码和
失败可追溯性。

专项测试还覆盖输出写入失败、adapter 识别失败、损坏 state、已有正式输出和异常
FFmpeg partial 清理。

## 正式输出发布

代码与独立故障注入确认：

- 只有全部块完成、源 SHA-256 复核通过、timeline 校验通过后才发布；
- 发布顺序为 SRT、TXT、timeline；
- 在第二个正式文件发布时注入失败，已发布 SRT 被清理，TXT/timeline 均不存在；
- 未留下 `asr.completed=true` 的伪完成 timeline；
- 预先存在的用户 `transcript.txt` 触发拒绝，文件字节不变，其他正式文件未创建；
- 处理中篡改临时源副本会得到
  `Source MP4 changed during processing; formal outputs were not published.`；
- 源恢复为原字节后重跑，已完成三块没有重新识别，随后成功发布；
- 正常成功后 `.work` 清理。

## 原视频保护

本次审核使用的真实 MP4 在双模型运行、强制中断恢复和失败探针后的 SHA-256 仍为：

```text
6b39f62c868e1cce6d621a3ead273c681ec3777ba5dd175f9b9ddd45725ef445
```

与审核前完全一致。代码只以只读方式打开输入并向独立输出目录写 WAV/state/正式输出；
未发现删除、覆盖或替换原视频的路径。

RESULT 记录的 827.766 秒既有长视频前后 SHA-256 同为
`DA2CD4041C7FB59A1DFC08C80B0358C28DBBDC59608A469EB1A0A8AC63694BFF`。
本次按指令没有重新跑该长视频，既有 14/14 块、169 segments 证据与短视频结果没有
矛盾。

## 代码简洁性

生产代码职责符合任务约定：

- `cli.py`：参数、引擎运行时选择和离线子进程环境；
- `adapters.py`：Paraformer/SenseVoice 模型差异和真实时间证据；
- `pipeline.py`：输入检查、分块、state、恢复、源复核和发布编排；
- `timeline.py`：文本规范化、统一 segment 和时间轴校验；
- `exporters.py`：state 原子写入、SRT/TXT 渲染和非覆盖发布；
- `media/audio.py`：单 WAV 块 FFmpeg 提取。

未发现插件系统、通用工作流、后台服务或 TASK-004 框架。`pipeline.py` 和
`adapters.py` 较长，但边界清楚，不因行数阻断。I-2 是实验兼容改造中的明确回归，
不是生产职责混乱。

## 测试

本地实际运行：

```text
Invoke-SourceOnlyTests.ps1
base-schema-media: 128 passed, 1 deselected, 0 failed
asr-experiments: 91 passed, 2 deselected, 1 existing warning, 0 failed
pip check: No broken requirements found.
SOURCE_ONLY_RESULT.status=passed

pytest tests/test_asr_production.py -q
18 passed, 0 failed
```

第一次调用 source-only 时系统 Python 没有 pytest，脚本正确返回非零；未安装或更新
依赖。改用项目既有 D 盘 `.venv` 后按相同脚本重跑并全部通过。这是本机解释器选择，
不是测试失败，也没有被隐瞒。

PR 起始 head `b15fccf...` 的 Actions run `30532218933`：

- `repository-safety`：SUCCESS；159 个 tracked text files，0 issues；
- `lightweight-tests`：SUCCESS；
  - 128 passed、1 deselected、0 failed；
  - 91 passed、2 deselected、1 warning、0 failed；
  - 三阶段 exit code 均为 0；
  - `pip check`：No broken requirements found；
- `task-report-gate`：SUCCESS；找到 1 个任务报告。

`lightweight-tests` 完整日志已逐行读取；未发现隐藏 FAILED/ERROR，checkout 的
merge ref 明确包含 head `b15fccf...`。

## 隐私与 Git 边界

- 本地 `Invoke-RepositorySafetyCheck.ps1 -Scope Tracked`：
  159 files scanned、159 text files、0 issues；
- tracked 文件中禁止媒体/音频/SRT/模型扩展名数量：0；
- tracked 文件中 `local-data/`、真实 runtime、`.venv/`、`模型/`、`项目/`、
  `设置/` 内容数量：0；
- `.gitignore` 实际匹配 MP4、WAV、SRT、`*_liveclip/`、`.work/`、timeline、
  transcript、state、模型、日志、`local-data/` 和 `.venv/`；
- 本次真实媒体、字幕、state、日志和审核运行输出均位于 Git 忽略目录；
- 未发现真实用户名、邮箱、IP、API key、token 或本地资产绝对路径进入 tracked diff；
- 未下载/更新模型，未调用云端 ASR，未上传本地媒体。

## 最终建议

有条件通过，可以手动Ready并决定合并，非阻断项进入backlog。

PR 应继续保持 Draft，直到用户阅读本报告并自行决定是否标记 Ready。自动化不得
标记 Ready、不得启用 auto-merge、不得 merge。I-1 和 I-2 不构成本次核心生产链路
阻断，不要求创建 TASK-003-FIX；若用户希望在合并前消除这两个问题，应另行明确授权，
当前审核不修改实现。
