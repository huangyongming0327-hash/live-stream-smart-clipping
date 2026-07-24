# TASK-GIT-002｜建立 ASR 技术阶段本地 Git 基线

## 目标

在 TASK-002-FIX2-R 已最终通过的前提下，为 TASK-002 技术实验阶段创建第二个本地 Git 提交和带说明标签 `baseline-task-002-tech`，使后续人工准确率审核能够相对稳定技术基线审查和恢复。

## 允许范围

- 完整核对 TASK-002、FIX、FIX2 和 FIX2-R 的源码、测试、锁文件、文档与审核报告；
- 核验 `.gitignore`、非忽略候选、大文件、敏感信息和暂存清单；
- 运行 ASR 实验测试、基础测试、媒体验证、四个环境的 `pip check` 和三个 freeze/lock 对比；
- 更新 `docs/CURRENT_STATUS.md` 及必要的决策状态说明；
- 创建本任务记录和结果报告；
- 创建一个本地提交和一个本地带说明标签。

## 禁止范围

- 不修改 ASR 业务逻辑或测试逻辑；
- 不修改、下载或更新 SenseVoice、Paraformer、Faster-Whisper 模型或依赖；
- 不运行三套完整全长模型实验，不执行人工准确率审核；
- 不上传视频、音频、字幕或结果，不调用云端 ASR 或收费 API；
- 不执行 TASK-003，不生成正式 `timeline.json`；
- 不创建 remote，不执行 `git push`，不修改分支名或全局 Git 配置；
- 不执行 `git clean`、`git reset --hard`、历史改写或宽范围删除；
- 不提交模型、环境、样本、缓存、运行结果、FFmpeg 二进制、密钥或其他大文件。

## 提交前门禁

1. 初始 HEAD 为 `59c1d895a92d9b8319e04dd1d7fa933ef894c1a7`，分支为 `master`，`baseline-task-001` 存在且无 remote；
2. TASK-002-FIX2-R 结论为通过、100/100、无阻断问题；
3. ASR 实验 37 passed、基础测试 148 passed、媒体验证 18 passed，均为 0 failed、0 skipped；
4. 基础及三个 ASR 环境 `pip check` 通过，三个 freeze 与 lock 逐行一致；
5. 指定模型、环境、样本、缓存、审核包、结果与 FFmpeg 路径全部被 Git 忽略；
6. 非忽略候选没有禁止类型、超过 5 MiB 的文件、二进制、真实凭据、个人数据或 TASK-003 内容；
7. 暂存后文件清单、统计、范围和 `git diff --cached --check` 全部通过；
8. 目标标签开始前不存在，仓库继续保持无 remote。

## 本地 Git 对象

- 提交信息：`baseline: TASK-002 ASR technical validation`
- 标签：`baseline-task-002-tech`
- 标签说明：`Verified local baseline after TASK-002 ASR technical validation`

## 结果

完整执行证据与安全核验见 `tasks/reports/TASK-GIT-002_RESULT.md`。完成后停止；下一步仅为单独的人工准确率审核，不自动执行人工审核或 TASK-003。
