# TASK-002-HUMAN-001 RESULT｜20窗口本地人工听音审核包

## 1. 任务状态

- 状态：本地实现、真实生成、专项测试和 source-only 回归已完成。
- 分支：`task/TASK-002-HUMAN-001-review-package`。
- 基线：使用 `Start-CodexTask.ps1` 从远端最新 `master` 的 `12ec0b96e772a6d21b6bc98a99f73d47881e24d8` 创建。
- 范围：只完成20窗口本地听音审核包；未执行人工准确率判断，未执行 TASK-003。

## 2. 输入检查

只读输入：

```text
<PRIVATE_ARCHIVE>\项目\ASR基准\output\人工审核对比.csv
<PRIVATE_ARCHIVE>\runtime\asr-benchmark\input\benchmark-16k-mono.wav
```

- CSV 存在，UTF-8 BOM，8列标题严格匹配既有格式，SHA-256 为 `3A31CEA90B97BBF7DFF032627E0B344A26EF09490964D3E37F7CE78ECED7421B`。
- WAV 存在，为未压缩 PCM、16 kHz、单声道、16-bit、13,243,051帧、827.6906875秒，SHA-256 为 `9625C4ED1A2A501DE580BB7713ABEC3F964B93EFFFE6AF3735F719964B4E0CEA`。
- 生成前后两份输入的 SHA-256 均未变化。
- CSV 的最后一个显示端点为827.691秒，比精确 WAV 时长高0.0003125秒，属于三位小数向上舍入。解析器明确只接受不超过0.0005秒的该类表示差，保留原值并将实际PCM帧钳制到WAV末尾；更大越界直接拒绝。

## 3. 20窗口解析

- 数据行：20。
- 唯一窗口编号：20，编号为1—20。
- 时间范围：0.000—827.691秒。
- 开始/结束时间均为有限数，`start >= 0`、`end > start`。
- SenseVoice、Paraformer、Faster-Whisper 三列均存在，20行候选文本均非空。
- 解析器不自动改列名、编号、候选文本或错误时间。

## 4. WAV裁切规则

- 使用 Python 标准库 `wave`，不依赖 FFmpeg。
- 每个原窗口默认增加前0.8秒、后0.8秒。
- 实际帧范围使用向下取整的开始帧和向上取整的结束帧，首端不小于0，末端不超过源WAV最后一帧。
- 输出保持 PCM、16 kHz、单声道、16-bit。
- 文件名固定为 `window-001.wav` 至 `window-020.wav`。
- `review-manifest.json` 记录窗口编号、原始时间、实际时间、片段时长、相对文件名和SHA-256。
- 写入使用同目录临时文件后原子替换；重复生成哈希一致时复用既有片段。

## 5. 本地审核页面

生成 `<LOCAL_REVIEW_OUTPUT>\review.html`，可直接使用 Chrome/Edge 打开，无需本地服务器。

页面提供：

- 原窗口编号、时间、类型和相对路径音频播放器；
- SenseVoice、Paraformer、Faster-Whisper 三候选文本；
- 最佳结果：三个模型、并列、都不可用；
- 三模型各自0—3错误严重度；
- 各模型错误标签、实际听写文本、备注、难辨认标记；
- 本窗口完成状态、上一个/下一个、窗口列表和仅显示未完成；
- 已完成X/20进度。

模板和生成页面不含CDN、HTTP/HTTPS资源、API调用、fetch或上传逻辑。

## 6. 本地保存和导出

- 表单修改后通过 localStorage 自动保存；
- 提供手动保存；
- 清空全部结果需要连续两次确认；
- 支持导入同一manifest的JSON恢复；
- 未完成时导出 `asr-human-review-draft.json` / `.csv`；
- 全部完成时导出 `asr-human-review-completed.json` / `.csv`；
- 所有保存、导入和导出均在浏览器本地完成。

## 7. JSON/CSV结构

JSON顶层包含：

- `schema_version = "1.0"`；
- `review_type = "asr_human_listening_review"`；
- `source_manifest_sha256`；
- `completed`、`completed_window_count`、`total_window_count`；
- `windows`。

每个窗口包含 `window_id`、`start`、`end`、`best_candidate`、三模型 `severity`、三模型 `error_tags`、`reference_text`、`audio_hard_to_hear`、`notes` 和 `reviewed`。

导入校验拒绝未知/重复窗口、未知候选、0—3之外的严重度、未知/重复错误标签、时间或manifest不一致及完成统计不一致。CSV使用与JSON对应的审核列，错误标签以 `|` 分隔。

## 8. 新增测试

新增21项测试，覆盖：

- 正常20窗口、缺列、重复编号；
- 非有限、负数、逆序和真实越界时间；
- 三位小数末端舍入边界；
- WAV声道、采样宽度、采样率；
- 首尾padding和帧边界；
- 输出参数、SHA-256和重复运行确定性；
- JSON草稿/完成状态；
- 未知候选、严重度越界、未知/重复窗口；
- 3窗口标准库合成WAV集成；
- 20窗口HTML嵌入、相对音频引用、离线资源；
- review-data、manifest和模板CSV字段/窗口一致性。

结果：`21 passed`、`0 failed`。

## 9. source-only回归

执行 `tools/github/Invoke-SourceOnlyTests.ps1`：

- base/schema/media：`110 passed, 1 deselected`，0 failed，exit 0；
- ASR experiments：`56 passed, 2 deselected, 1 warning`，0 failed，exit 0；
- warning 为既有 `audioop` Python 3.13弃用提示；
- `pip check`：`No broken requirements found.`，exit 0；
- 最终 `SOURCE_ONLY_RESULT.status = passed`，三个阶段退出码均为0。

未运行模型、真实媒体集成或 FFmpeg 集成。

## 10. 本地真实生成结果

- 窗口：20；
- WAV片段：20，均可由 `wave` 重新读取；
- 片段时长：最短20.7996875秒，最长21.600125秒；
- 20个输出均为 PCM、16 kHz、单声道、16-bit；
- `review.html`、`review-data.json`、`review-template.csv`、`review-manifest.json`、`README_LOCAL.md` 和 `exports/` 均生成；
- HTML包含20个相对音频引用，引用文件全部存在；
- review-data、模板CSV与manifest均为20个相同窗口；
- manifest SHA-256：`25e7d0a7c116b00b895eea0d5b67aa0ad62ff562c9d8c640685909867a9abf7b`；
- 第二次真实生成复用20/20片段，稳定文件哈希不变。

## 11. 输出目录占位符

```text
<LOCAL_REVIEW_OUTPUT>\
├─ review.html
├─ review-data.json
├─ review-template.csv
├─ review-manifest.json
├─ README_LOCAL.md
├─ clips\
│  ├─ window-001.wav
│  └─ ...
└─ exports\
```

公开报告不记录真实本机绝对路径。

## 12. Git忽略验证

- `.gitignore` 明确新增 `local-data/`。
- `git check-ignore` 已确认 `review.html` 和真实WAV片段命中该规则。
- `git status` 不显示任何 `local-data/` 内容。
- 真实音频、运行时review-data、用户结果、备注和导出JSON/CSV均不进入Git。

## 13. 修改文件

- `.gitignore`
- `experiments/asr/human_review/__init__.py`
- `experiments/asr/human_review/input_parser.py`
- `experiments/asr/human_review/wav_clipper.py`
- `experiments/asr/human_review/review_schema.py`
- `experiments/asr/human_review/build_review_package.py`
- `experiments/asr/human_review/templates/review.html`
- `experiments/asr/tests/test_human_review_input.py`
- `experiments/asr/tests/test_human_review_wav.py`
- `experiments/asr/tests/test_human_review_package.py`
- `docs/ASR_HUMAN_REVIEW_GUIDE.md`
- `docs/CURRENT_STATUS.md`
- `docs/DECISIONS.md`
- `tasks/TASK-002-HUMAN-001.md`
- `tasks/reports/TASK-002-HUMAN-001_RESULT.md`

未修改正式 `src/liveclip`。

## 14. 安全边界

- 原私有归档、源WAV、CSV和已有模型结果未修改；
- 未上传真实音频、模型文本运行副本或用户填写结果；
- 未调用云端、收费API或OpenAI API；
- 未运行任何ASR模型；
- 未下载模型或安装大型依赖；
- 未修改用户/系统PATH、永久环境变量或电源设置；
- 未执行人工准确率判断，未宣布准确率冠军或生产模型；
- 未执行TASK-003；
- 未启用auto-merge，未执行merge；
- 公开代码、测试和报告未发现真实绝对路径或个人信息。

## 15. 用户如何打开页面

使用 Chrome 或 Edge 直接打开：

```text
<LOCAL_REVIEW_OUTPUT>\review.html
```

不需要启动服务器。首次打开后从窗口1开始试听，填写最佳结果和三项严重度，再勾选“本窗口已完成”。

## 16. 用户完成后保留的文件

完成20/20后，保留并交给 Codex：

```text
asr-human-review-completed.json
```

不要附带或上传 `clips/` 音频目录。完成版CSV可作为个人查看副本，但结构化复核以完成版JSON为主。

## 17. 未完成项

- 用户人工听音进度仍为0/20；
- 尚未产生 `asr-human-review-completed.json`；
- 尚未形成最终人工准确率结论；
- 尚未计算CER/WER；
- 尚未确定生产ASR模型；
- 尚未执行独立代码审核；
- TASK-003尚未开始。

## 18. 下一步建议

先对本Draft PR执行独立审核。代码审核通过且由用户手动合并后，用户在本地打开审核页面完成20窗口听音，并交回 `asr-human-review-completed.json`。之后再建立单独任务分析人工结果；本任务不自动进入该阶段。

## 19. 回滚方法

- PR合并前：关闭本Draft PR，并仅删除精确任务分支 `task/TASK-002-HUMAN-001-review-package`。
- PR合并后：通过新的修复/回滚PR执行 `git revert`，不重写公开历史。
- 本地审核包如需重新生成，可再次运行生成器；哈希一致片段会复用。
- 只有用户明确要求时才可删除 `<LOCAL_REVIEW_OUTPUT>` 中的生成副本；绝不删除或修改 `<PRIVATE_ARCHIVE>` 中的源CSV、源WAV、模型或原始视频。
