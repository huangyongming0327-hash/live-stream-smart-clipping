# TASK-006 RESULT｜端到端一键流程与 Windows 启动器

## 1. 状态与边界

- 从包含 TASK-005 合并提交的最新 `master` 创建规定任务分支；
- 单 MP4 顺序编排、阶段复用/恢复、Windows 双击启动器和两项限定易用性修正已实现；
- 没有复制 ASR、文本分析、审核或 FFmpeg 导出核心算法；
- 没有实现批量、队列、安装包、自动发布或 TASK-007；
- 本地自动测试和真实媒体闭环已完成，GitHub latest-head 状态以 PR handoff 为准。

## 2. 统一入口

```powershell
python -m liveclip run --video "<PATH>\source.mp4"
```

可选 `--workdir`、`--output`、`--asr-model paraformer|sensevoice` 和
`--no-open-browser`。默认 Paraformer、视频旁 `<视频名>_liveclip` 工作目录和其下
`exports`。控制台只按三阶段显示开始、恢复、复用、完成或失败；失败信息给出当前阶段、
直接原因、下一步和同命令能否继续，不输出 traceback、API Key 或模型响应正文。

## 3. 启动检查与模块复用

启动检查在 ASR 前验证 MP4、音视频流、FFmpeg/ffprobe、本地 ASR 模型、文本分析三个环境
变量和目录可写，避免缺少分析配置时先做长时间识别。runner 直接调用现有
`run_transcription`、`run_analysis` 和 `launch_review`，并把未完成的 TASK-003/TASK-004
状态原样交给对应模块恢复。

合法 timeline 必须绑定当前视频文件名、SHA-256 和时长；合法 analysis 必须通过 schema
且绑定当前 timeline 字节 SHA-256；completed review 必须绑定同一组输入、合法候选/范围，
并且两个输出文件实际存在。损坏或错配文件会安全停止并要求用户先移走，不自动删除或覆盖。

## 4. 工作目录与 pipeline 状态

默认工作目录集中保存 timeline、SRT、transcript、TASK-003 状态、analysis、TASK-004 状态、
review、`pipeline_status.json` 和 `exports`，但不复制原视频。

`pipeline_status.json` 使用临时文件加原子替换，仅包含源文件名/SHA、三个阶段的
pending/completed、固定产物文件名和 UTC 更新时间；不含绝对路径、API Key、字幕正文、
候选标题或推荐理由。文件损坏时会从现有可信产物重新推导。

## 5. Windows 启动器

双击 `Start-LiveClip.cmd` 后，PowerShell 使用 Windows 原生 MP4 文件选择框，再显示
Paraformer（默认推荐）和 SenseVoice（低资源）两个选项，最后调用统一 `run` 命令。路径含
中文和空格由参数数组直接传递；取消选择退出码为 0；失败时控制台保留并等待按键。启动器
不需要管理员权限、不修改系统环境变量、不安装 GUI 框架，也不是安装包或常驻服务。

## 6. 两项限定易用性修正

- 切换候选、修改开始/结束、点击任一微调按钮或恢复 AI 范围，都会立即取消人工确认并
  重新禁用导出；服务端严格布尔确认和合法范围门禁保持不变。
- 导出成功或重开 completed review 后，页面显示 MP4/SRT 文件名、最终开始/结束、实际时长
  和输出文件夹名称，不显示完整绝对路径，也没有新增历史列表或文件管理器。

## 7. 自动测试

- TASK-006 runner：14 passed、0 failed；
- runner + TASK-005 review/export 定向：54 passed、0 failed；
- source-only base-schema-media：212 passed、1 deselected、0 failed；
- source-only asr-experiments：91 passed、2 deselected、1 个既有 deprecation warning、
  0 failed；
- `pip check`：`No broken requirements found.`；
- source-only 三阶段退出码均为 0，最终 `SOURCE_ONLY_RESULT.status=passed`。

测试使用 fake transcribe/analyze/review 和临时文件，不处理真实长视频。覆盖 CLI 参数、默认和
自定义目录、两个 ASR 选择、环境变量前置失败、阶段调用/跳过/恢复、SHA 变化、损坏产物保留、
状态原子重推导、中文空格路径、启动器取消、completed review、确认撤销、完成提示和原服务端
门禁。GitHub 三项 Actions 不在本报告中预先宣称，最终以 latest-head handoff 为准。

## 8. 真实端到端验证

使用 Git 忽略目录中的一段 827.766 秒真实 MP4：

- 首次统一入口完成 SenseVoice 本地 ASR，生成 169 个 timeline segments；
- 文本模型首次输出以及一次修复输出都包含不属于 topic 的 candidate，既有 TASK-004 schema
  门禁使分析阶段安全失败，没有发布伪完成 analysis；
- 对同一 timeline 字节 SHA 完全一致的既有已审核 completed analysis 做无覆盖复用后，同一
  统一入口跳过 ASR/模型分析并自动打开本地审核页；该恢复事实不冒充一次新的模型成功；
- 页面显示 6 个候选，原视频 `readyState=4`、无媒体错误，Range 预览时间持续前进；
- 勾选确认后把入点调整 100 ms，确认立即自动取消、导出重新禁用；重新预览并再次确认后
  成功导出一个 MP4 和一个 SRT；
- 页面显示两个文件名、最终范围 51.676 秒、实际时长和 `exports` 文件夹名称；
- ffprobe：H.264 + AAC，容器时长 51.721 秒，与目标相差 45 ms；开头、中间和结尾各解码
  1 秒均退出码 0；
- SRT 共 14 条，从 timeline 对最终范围独立重算后与输出逐字符一致；
- 原视频 SHA-256 不变，timeline 和 analysis 前后哈希不变，`pipeline_status.json` 最终三阶段
  均为 completed 且不含绝对路径；关闭页面后无残留审核 Python 进程。

再次运行完全相同的命令时，控制台依次显示字幕识别已复用、爆点分析已复用、人工审核与
导出已复用；退出码 0，timeline/analysis 哈希不变，没有再次调用 ASR 或文本模型，也没有
重复导出。

## 9. 隐私、Git 与用户文件

真实输入、timeline、analysis、review、状态、SRT 和导出均位于 Git 忽略目录；
`git check-ignore` 已确认运行产物命中规则。公开文档不包含真实路径、字幕、候选标题、推荐理由、
API Key、访问 token 或本地端口。原视频、timeline 和 analysis 始终只读；既有输出不覆盖，
LiveClip 不自动上传或发布视频。

## 10. 已知限制与下一步

- 本版本仍依赖源码 Python 环境、本地 FFmpeg/模型和用户配置的文本接口，不是安装包；
- 输入 MP4 必须含可读取音视频且能被浏览器直接解码；不生成代理；
- 真实模型这次产生了 schema 不合规候选，安全停止行为正确，但候选生成质量仍取决于用户
  配置的模型；本次最终闭环使用的是 exact-SHA 匹配的既有已审核 analysis；
- 只处理一个视频并最多导出一个片段，不做批量、队列、常驻服务或自动发布。

下一步只对 Draft PR latest head、RESULT、完整 diff、真实验证边界和三项 Actions 做独立审核；
继续保持 Draft，不 auto-merge、不 merge，不执行 TASK-007。
