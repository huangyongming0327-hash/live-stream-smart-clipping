# 直播智能切片（LiveClip）

LiveClip 是一个 Windows 本地优先的技术验证项目，目标是把长时间直播录像处理为可审核、可追踪的短视频候选，同时让媒体、模型和中间数据继续由用户控制。

## 当前阶段

- TASK-000 数据契约、TASK-001 FFmpeg 媒体链路和 TASK-002 本地 ASR
  选型已经通过对应审核。
- TASK-003 的单 MP4 本地分块转写生产流程已合并。
- TASK-004 的单 timeline 顺序语义分析与候选生成已合并；模型推荐必须继续经过人工审核。
- TASK-005 已实现本地候选审核页面、原视频预览、毫秒级入出点调整，以及明确确认后的
  单片段 H.264 + AAC MP4 和独立 SRT 导出。
- TASK-006 已把现有转写、分析和审核能力串成单视频一键流程，并提供 Windows 双击启动器；
  它仍是源码运行的技术验证版本，不是安装包。
- 项目仍处于开发和技术验证阶段，尚无正式一键安装版本。
- MVP 默认模型为 Paraformer，用户可手动选择低资源 SenseVoice。

## 本地组件

- 媒体处理基于项目本地 FFmpeg。
- ASR 技术验证覆盖本地 SenseVoice、Paraformer 和 Faster-Whisper 路线。
- 本仓库不包含 FFmpeg 二进制、模型权重、真实视频或音频、运行字幕、识别结果、虚拟环境、缓存、日志和用户配置。

## 一键完整流程

普通 Windows 用户从仓库根目录双击 `Start-LiveClip.cmd`：

1. 在系统文件选择框中选择一个 MP4；取消选择会正常退出；
2. 选择 Paraformer（默认推荐）或 SenseVoice（低资源）；
3. 控制台依次显示“字幕识别”“爆点分析”“人工审核与导出”；
4. 分析完成后默认浏览器自动打开本地审核页；
5. 预览候选，调整入出点，明确勾选人工确认，再导出一个 MP4 和对应 SRT。

启动器会使用仓库 `.venv`，或 `LIVECLIP_ASSETS_ROOT` 下的 `.venv`。本地资产根还需包含
下文列出的 FFmpeg、ASR 运行环境和模型；文本分析使用以下三个进程环境变量：

```powershell
$env:LIVECLIP_ASSETS_ROOT = "<LOCAL_ASSETS_ROOT>"
$env:LIVECLIP_LLM_ENDPOINT = "<HTTPS_CHAT_COMPLETIONS_URL>"
$env:LIVECLIP_LLM_API_KEY = "<API_KEY>"
$env:LIVECLIP_LLM_MODEL = "<MODEL_NAME>"
```

也可以直接运行统一命令：

```powershell
python -m liveclip run --video "<VIDEO_PATH>\source.mp4"
```

可选 `--workdir`、`--output`、`--asr-model paraformer|sensevoice` 和
`--no-open-browser`。默认工作目录为视频旁的 `source_liveclip`，导出在其 `exports`：

```text
source_liveclip/
├─ timeline.json
├─ subtitles.srt
├─ transcript.txt
├─ task_state.json
├─ current_analysis.json
├─ analysis_history/
├─ review_current.json
├─ pipeline_status.json
└─ exports/
   ├─ source_<candidate-id>.mp4
   └─ source_<candidate-id>.srt
```

中断后使用相同视频、模型和工作目录重跑同一命令：合法 timeline 会跳过 ASR，SHA 匹配的
completed analysis 会跳过文本模型，未完成状态交给原有断点恢复逻辑继续；损坏或错配产物
不会被自动删除或覆盖。已完成审核仍会打开页面并显示此前导出的文件名和最终范围。

ASR、视频、音频、timeline、审核和导出始终留在本机。只有语义分析所需的 segment ID、
相对毫秒时间和必要字幕文本发送给用户配置的文本模型；本地路径和 API Key 不进入请求正文、
状态或报告。LiveClip 不自动上传或发布视频。

## 单视频本地转写

先确认本地资产根包含以下既有文件；程序不会下载或更新模型：

```text
tools/ffmpeg/bin/ffmpeg.exe
tools/ffmpeg/bin/ffprobe.exe
runtime/asr-envs/funasr/Scripts/python.exe
runtime/asr-envs/sherpa-onnx/Scripts/python.exe
模型/asr/paraformer-zh/model.pt
模型/asr/fsmn-vad/model.pt
模型/asr/ct-punc/model.pt
模型/asr/sensevoice-small/model.int8.onnx
模型/asr/sensevoice-small/tokens.txt
模型/asr/sensevoice-small/silero_vad.onnx
```

默认 Paraformer：

```powershell
$env:LIVECLIP_ASSETS_ROOT = "<LOCAL_ASSETS_ROOT>"
python -m liveclip transcribe `
  --input "<VIDEO_PATH>\sample.mp4" `
  --engine paraformer
```

低资源 SenseVoice：

```powershell
python -m liveclip transcribe `
  --input "<VIDEO_PATH>\sample.mp4" `
  --engine sensevoice
```

未指定 `--output` 时，输出到视频旁的 `sample_liveclip`：

```text
sample_liveclip/
├─ timeline.json
├─ subtitles.srt
├─ transcript.txt
└─ task_state.json
```

流程按 60 秒顺序分块，每块完成后更新状态。按 `Ctrl+C` 中断后，使用完全相同的
输入、引擎、分块参数和输出目录重跑即可继续；已完成块不会再次识别。程序保持离线，
不会因电池供电自动暂停。

常见失败包括 MP4 不存在或无音轨、项目 FFmpeg 缺失、本地模型或对应 Python 环境
缺失、状态文件损坏、源视频/模型/关键参数变化、输出不可写或磁盘空间不足。发生失败时
不会发布伪完成的 `timeline.json`。

## 单 timeline 语义分析

只支持一个由用户配置的 OpenAI-compatible Chat Completions 文本模型接口：

```powershell
$env:LIVECLIP_LLM_ENDPOINT = "<HTTPS_CHAT_COMPLETIONS_URL>"
$env:LIVECLIP_LLM_API_KEY = "<API_KEY>"
$env:LIVECLIP_LLM_MODEL = "<MODEL_NAME>"

python -m liveclip analyze `
  --timeline "<PATH>\timeline.json"
```

未指定 `--output` 时，结果写入 timeline 同级目录：

```text
current_analysis.json
analysis_history/
```

流程按最多 10 分钟、约 12,000 字符的固定非重叠窗口顺序请求，每完成一个窗口原子保存
`.analysis_work/analysis_state.json`。中断后使用同一 timeline、模型、endpoint host 和
窗口参数重跑即可继续。模型只接收 segment ID、相对毫秒时间和必要字幕文本；视频、
音频、本地路径和 API Key 不会进入请求正文。时间、原句、总分、过滤和重叠去重均由
程序根据真实 timeline 计算。

## 单次候选审核与导出

准备相互匹配的原视频、已完成 timeline 和已完成 analysis 后运行：

```powershell
python -m liveclip review `
  --video "<PATH>\source.mp4" `
  --timeline "<PATH>\timeline.json" `
  --analysis "<PATH>\current_analysis.json" `
  --output "<OPTIONAL_OUTPUT_DIR>"
```

命令只在 `127.0.0.1` 启动带随机访问 token 的临时服务，并自动打开默认浏览器。页面左侧
列出全部待审核候选，右侧使用浏览器原生视频控件预览，可用滑块、数字输入和微调按钮修改
开始/结束时间。AI 排名、分数和 `recommended` 都不会自动批准候选；只有勾选“我已人工预览
并确认导出这个片段”后，服务端才接受一次导出。

切换候选或修改、微调、恢复入出点都会自动取消确认并重新禁用导出，用户需重新预览并确认。
导出成功后页面显示 MP4/SRT 文件名、最终时间范围、实际时长和输出文件夹名称，不显示绝对路径。

未提供 `--output` 时，MP4 和 SRT 写入原视频旁的 `<视频名>_exports`。输出采用 H.264 +
AAC，SRT 直接从 timeline 裁剪并平移到从 0 开始；成功后在 analysis 同级目录原子写入
`review_current.json`。既有同名输出不会被覆盖，原视频、timeline 和 analysis 不会被修改。
视频、字幕和审核数据不会由审核页面发送到互联网，页面也不加载第三方资源。

预览只支持当前浏览器能够直接解码的 MP4，本版本不生成代理。当前也不支持批量或多片段
导出、拼接、波形、缩略图、字幕烧录、竖屏转换、队列、自动发布、安装包或 TASK-007。

## 开发检查

在自行准备 Python 3.12 开发环境并安装 `requirements-dev.lock.txt` 后，可运行不依赖本地媒体或模型的测试：

```powershell
python -m pytest .\tests `
  --ignore .\tests\test_media_integration.py `
  --ignore .\tests\test_ffmpeg_install_source.py `
  -k "not probe_corrupt_file_returns_clear_error"

python -m pytest .\experiments\asr\tests `
  -k "not existing_399_sentence_info_result_is_byte_for_byte_reproducible"
```

需要 FFmpeg 二进制、模型或真实媒体的验证必须在用户明确准备的本地环境中单独执行，不会由 GitHub Actions 下载模型或读取用户数据。

## 资料

- `docs/ARCHITECTURE.md`：总体结构
- `docs/DATA_CONTRACTS.md`：JSON 接口
- `docs/CURRENT_STATUS.md`：当前状态
- `docs/ENVIRONMENT_REPORT_PUBLIC.md`：脱敏环境摘要
- `docs/CODEX_GITHUB_WORKFLOW.md`：任务、发布与独立审核流程
- `docs/PUBLIC_REPOSITORY_SANITIZATION_REPORT.md`：公开前脱敏扫描

## 数据安全

- 永不删除原视频。
- `runtime/`、`项目/`、`模型/`、`设置/` 和本机工具目录默认不进入 Git。
- `config.example.json` 只提供无密钥示例；真实配置和密钥文件必须保留在本地并由 `.gitignore` 排除。
- 所有变更通过任务分支和 Pull Request；自动化不会合并 PR，最终合并由用户手动决定。

## 许可证

仓库中的代码和仓库自有文档采用 Apache License 2.0，版权声明见 `NOTICE`。外部 FFmpeg、ASR 运行时和模型权重遵守各自许可证；它们不随本仓库分发。
