# 直播智能切片（LiveClip）

LiveClip 是一个 Windows 本地优先的技术验证项目，目标是把长时间直播录像处理为可审核、可追踪的短视频候选，同时让媒体、模型和中间数据继续由用户控制。

## 当前阶段

- TASK-000 数据契约、TASK-001 FFmpeg 媒体链路和 TASK-002 本地 ASR 技术验证已经通过对应审核。
- 项目仍处于开发和技术验证阶段，尚无正式一键安装版本。
- 人工准确率审核尚未完成，因此不宣称准确率排名或最终生产模型。
- TASK-003 尚未开始。

## 本地组件

- 媒体处理基于项目本地 FFmpeg。
- ASR 技术验证覆盖本地 SenseVoice、Paraformer 和 Faster-Whisper 路线。
- 本仓库不包含 FFmpeg 二进制、模型权重、真实视频或音频、运行字幕、识别结果、虚拟环境、缓存、日志和用户配置。

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
