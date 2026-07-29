# TASK-002-HUMAN-001｜生成20窗口本地人工听音审核包

## 目标

从既有20窗口 ASR 对比 CSV 和同一份本地基准 PCM WAV 生成完全离线、可直接在 Chrome/Edge 打开的人工听音审核包，让用户逐窗口比较 SenseVoice、Paraformer 与 Faster-Whisper。

## 公开交付

- `experiments/asr/human_review/`：严格输入解析、PCM WAV裁切、审核schema、生成器与离线HTML模板；
- `experiments/asr/tests/test_human_review_*.py`：合成数据测试；
- `docs/ASR_HUMAN_REVIEW_GUIDE.md`：用户指南；
- 本任务记录与脱敏结果报告。

## 本地交付

```text
<LOCAL_REVIEW_OUTPUT>\
├─ review.html
├─ review-data.json
├─ review-template.csv
├─ review-manifest.json
├─ README_LOCAL.md
├─ clips\
└─ exports\
```

`<LOCAL_REVIEW_OUTPUT>` 对应本地被 Git 忽略的 `local-data/asr-human-review/`。真实音频、模型文本运行副本、用户审核内容、备注和导出结果均不得提交或上传。

## 输入与边界

- CSV 必须严格匹配既有8列格式并恰好含20个唯一窗口；
- 时间必须有限、非负且结束晚于开始；
- 三位小数的末端表示只允许不超过0.0005秒的明确舍入差，实际裁切永不越过 WAV 最后一帧；
- WAV 必须为 PCM、16 kHz、单声道、16-bit；
- 源 CSV、WAV 和已有模型结果只读，不修改；
- 不运行 ASR 模型、不调用云端或收费 API、不安装大型依赖；
- 不修改 `src/liveclip`，不执行 TASK-003，不自动合并 PR。

## 完成条件

- 生成20个稳定命名的 padded WAV 和含 SHA-256 的manifest；
- 离线页面支持三候选、严重度、错误标签、参考文本、备注、难辨认和完成状态；
- 支持 localStorage、手动保存、二次确认清空、JSON导入导出、CSV导出及草稿/完成文件名；
- 真实本地生成、专项测试、source-only回归、安全扫描和 Git 忽略验证通过；
- 通过项目发布器创建新的 Draft PR，等待三项 Actions；不标记Ready、不合并。
