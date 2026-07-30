# 直播智能切片（LiveClip）

LiveClip 是一个 Windows 本地优先的技术验证项目，目标是把长时间直播录像处理为可审核、可追踪的短视频候选，同时让媒体、模型和中间数据继续由用户控制。

## 当前阶段

- TASK-000 数据契约、TASK-001 FFmpeg 媒体链路和 TASK-002 本地 ASR
  选型已经通过对应审核。
- TASK-003 的单 MP4 本地分块转写生产流程已合并。
- TASK-004 已实现单个 timeline 的顺序语义分析，并使用用户配置的低成本文本模型完成
  一份真实 827.766 秒 timeline 验证；候选仍需人工审核后才能进入后续剪辑。
- 项目仍处于开发和技术验证阶段，尚无正式一键安装版本。
- MVP 默认模型为 Paraformer，用户可手动选择低资源 SenseVoice。

## 本地组件

- 媒体处理基于项目本地 FFmpeg。
- ASR 技术验证覆盖本地 SenseVoice、Paraformer 和 Faster-Whisper 路线。
- 本仓库不包含 FFmpeg 二进制、模型权重、真实视频或音频、运行字幕、识别结果、虚拟环境、缓存、日志和用户配置。

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

当前不支持 GUI、批量任务、队列、模型下载/自动切换、说话人分离、翻译、候选审核、
视频导出或 TASK-005。

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
