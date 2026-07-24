# TASK-002｜ASR 依赖与存储计划

- 计划日期：2026-07-20（Asia/Shanghai）
- 项目根目录：`<PROJECT_ROOT>`
- 任务范围：仅本地字幕识别模型对比验证
- 输入状态：`benchmark.mp4` 已存在，13 分 47.766 秒，418,420,241 bytes
- 参考字幕：不存在；本轮不得计算 CER/WER 或宣称准确率排名

## 1. 共同隔离规则

本轮不向基础 `.venv` 安装任何 ASR 依赖。所有命令只设置进程级环境变量，不修改用户/系统环境变量或 PATH：

| 环境变量 | D 盘路径 |
|---|---|
| `PIP_CACHE_DIR` | `runtime\cache\asr\pip` |
| `HF_HOME` | `runtime\cache\asr\hf` |
| `HUGGINGFACE_HUB_CACHE` | `runtime\cache\asr\hf\hub` |
| `MODELSCOPE_CACHE` | `runtime\cache\asr\modelscope` |
| `TORCH_HOME` | `runtime\cache\asr\torch` |
| `XDG_CACHE_HOME` | `runtime\cache\asr\xdg` |
| `TEMP` / `TMP` | `runtime\temp\asr` |

统一设置 `OMP_NUM_THREADS=4`、`MKL_NUM_THREADS=4`、`OPENBLAS_NUM_THREADS=4`。候选顺序执行、进程优先级为 Below Normal，不同时加载两个模型。

实际安装阶段还使用了 `runtime\asr-cache` 和 `runtime\asr-temp` 作为首次安装/模型下载的进程级缓存与临时目录；正式基准使用上表路径。两组路径都位于本项目 D 盘目录，没有设置永久环境变量或写入 C 盘模型缓存。

Python 使用现有 CPython 3.12.10 创建三个全新 D 盘实验环境；不修改系统 Python，也不需要便携 Python 3.11：

- `runtime\asr-envs\sherpa-onnx`
- `runtime\asr-envs\funasr`
- `runtime\asr-envs\faster-whisper`

## 2. SenseVoiceSmall 替代实现

### 路线决策

首选官方 FunASR llama.cpp / GGUF 路线已做只读核对。官方 `runtime-llamacpp-v0.1.7` 的 SenseVoice README 把 `timestamps` 列在 Roadmap，当前 Q8 CLI 不能提供本任务所需的最低可用时间轴。因此按 TASK-002 的明确替代条件，改用官方 sherpa-onnx SenseVoice INT8 Windows CPU 路线；不下载 GGUF Q8、F16 或 F32 模型。

### 固定依赖

| 项目 | 固定值 |
|---|---|
| 官方项目 | `k2-fsa/sherpa-onnx` |
| 运行时 | `sherpa-onnx==1.13.4`，Apache-2.0 |
| Python | 3.12.10，官方提供 `cp312-win_amd64` wheel |
| 模型 | `sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17` |
| 模型来源 | `https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17.tar.bz2` |
| VAD | sherpa-onnx 官方字幕示例使用的 `silero_vad.onnx` |
| VAD 来源 | `https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx` |
| 安装路径 | `runtime\asr-envs\sherpa-onnx`、`tools\asr\sherpa-onnx` |
| 模型路径 | `模型\asr\sensevoice-small` |
| 计算 | ONNX INT8、CPU、4 线程、ITN 开启、语言自动 |

模型由 SenseVoiceSmall 官方权重转换；运行时和转换模型均来自 k2-fsa 官方发布。sherpa-onnx 的长音频字幕示例使用 Silero VAD，不支持本任务首选 GGUF 路线的 FSMN-VAD，因此这是替代实现的已知差异。时间戳采用 VAD 语音片段起止时间；不伪造字级时间戳或置信度。语言、情绪和事件仅在运行时实际返回时保留。

预计下载约 250—300 MiB（INT8 ONNX、tokens、VAD、Windows wheel 及 NumPy）；不包含 PyTorch，不会拉取 CUDA。

## 3. Paraformer 中文生产基线

### 固定依赖

| 项目 | 固定值 |
|---|---|
| 官方项目 | `modelscope/FunASR` |
| Python 包 | `funasr==1.3.22`，MIT |
| FunASR tag / commit | `v1.3.22` / `38e421b0c49963a6f46ae2ebbaa24bc5168cc707` |
| Python | 3.12.10 |
| PyTorch / 音频桥 | `torch==2.11.0+cpu`、`torchaudio==2.11.0+cpu` Windows x64 CPU wheel（PyPI） |
| ASR | `iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch@v2.0.9` |
| VAD | `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch@v2.0.4` |
| 标点 | `iic/punc_ct-transformer_cn-en-common-vocab471067-large@v2.0.4` |
| 可选说话人 | `iic/speech_campplus_sv_zh-cn_16k-common@v2.0.2` |
| 环境路径 | `runtime\asr-envs\funasr` |
| 模型路径 | `模型\asr\paraformer-zh`、`fsmn-vad`、`ct-punc`、`cam-plus-plus` |

FunASR 1.3.22 的固定别名表把 ModelScope `paraformer-zh` 映射到上述 SeACo Paraformer 模型，支持本任务的一次热词探针。模型全部为 `iic` 官方组织、Apache-2.0，运行时显式传本地绝对路径和固定 revision 下载，不运行未固定远程代码。

预计模型下载约 2.0—2.3 GiB（ASR 约 999 MB、VAD 约 4 MB、标点约 1 GiB；只有样本明显多说话人时再下载约 29 MB CAM++）。环境和包缓存预计 0.5—1.0 GiB。总预算约 2.5—3.3 GiB。

这是唯一包含 PyTorch 的候选。最初安装的 `torch==2.13.0+cpu` 在 FunASR 导入时暴露出未声明的 `torchaudio` 依赖；PyPI 没有匹配的 Windows `torchaudio==2.13.0`，因此未安装成功，也未进入识别。随后改用 PyPI 可用且版本精确匹配的 `torch==2.11.0+cpu` / `torchaudio==2.11.0+cpu`。安装后实测 `torch.version.cuda is None`、`torch.cuda.is_available() == false`，环境内没有 `nvidia-*` / CUDA 包。没有安装 CUDA toolkit、GPU wheel 或 NVIDIA 依赖。

## 4. faster-whisper 国际备用路线

### 固定依赖

| 项目 | 固定值 |
|---|---|
| 官方项目 | `SYSTRAN/faster-whisper` |
| Python 包 | `faster-whisper==1.2.1`，MIT |
| 模型 | `Systran/faster-whisper-small`，MIT |
| 模型 revision | `536b0662742c02347bc0e980a01041f333bce120` |
| 环境路径 | `runtime\asr-envs\faster-whisper` |
| 模型路径 | `模型\asr\faster-whisper-small` |
| 固定推理 | CPU、`int8`、4 线程、`language=zh`、`task=transcribe`、VAD、word timestamps、保守 beam size |

预计模型 486 MB；CTranslate2、ONNX Runtime、PyAV、tokenizers 等环境和缓存约 150—300 MiB，总预算约 650—800 MiB。该路线不依赖 PyTorch，不会安装 CUDA 包。

## 5. 预计总占用与下载顺序

预计网络下载合计约 3.4—4.4 GiB；解压后的环境、模型、缓存、两轮结果和日志预计占用约 7—10 GiB。开始前 D 盘可用空间约 606 GiB，空间充足。

下载和执行顺序固定为：

1. sherpa-onnx 环境、SenseVoice INT8、Silero VAD；
2. FunASR 环境、CPU PyTorch、Paraformer/VAD/标点；仅在明显多说话人时下载 CAM++；
3. faster-whisper 环境和固定 revision 的 small 模型。

候选不并行下载、不并行运行。每个下载完成后记录 URL、文件大小、本地 SHA-256；发布方有校验值时进行比对。模型下载完成后均以本地绝对路径执行离线复测，禁止回退网络。

## 6. 依赖锁定与远程代码

- 实际安装完成后生成 `experiments\asr\locks\sherpa-onnx.lock.txt`、`funasr.lock.txt`、`faster-whisper.lock.txt`。
- 锁文件来自各隔离环境的实际 `pip freeze --all`，并运行 `pip check`。
- 不使用 `trust_remote_code=True`；不执行模型仓库中的任意远程 Python 文件。
- ModelScope 和 Hugging Face 仅用于下载固定官方模型文件；推理阶段只传本地路径。
- 不自动更新运行时、依赖或模型。

## 7. 回滚范围

本任务不修改基础 `.venv`。如需回滚，只需在确认路径后移除以下 TASK-002 新增内容，不影响原视频和 TASK-001：

- `runtime\asr-envs\*`
- `runtime\cache\asr\*`
- `runtime\temp\asr\*`
- `runtime\logs\asr\*`
- `runtime\asr-benchmark\*`
- `tools\asr\*`
- `模型\asr\*`
- `experiments\asr\*`
- `项目\ASR基准\output\*`
- TASK-002 新增文档与报告

回滚绝不包含 `项目\ASR基准\input\benchmark.mp4`、任何参考字幕、基础 `.venv`、项目 FFmpeg 或正式 `src/liveclip`。

## 8. 安全确认

- 不上传视频、音频或字幕；网络请求只获取公开运行时、依赖和模型。
- 不调用云端 ASR、收费 API 或 OpenAI API。
- 不写入 API Key，不修改系统 PATH、电源计划或永久环境变量。
- 不安装 CUDA、GPU 版 PyTorch或 NVIDIA 依赖。
- 不生成正式 `timeline.json`，不开发 UI，不执行 TASK-003。
- 不创建 Git commit、remote 或 push。
