# TASK-004-FIX RESULT｜爆点候选容错与分析稳定性

## 1. 结果

已完成 repair 后的 candidate 逐项容错，同时保持所有既有硬规则。首次响应仍按原逻辑整包严格
校验；只有首次失败并完成唯一一次 repair 后，才允许丢弃 repair 响应中的单个坏 candidate。
合格项保留，全部不合格时以空 `candidates` 完成窗口。没有第 3 次模型请求。

本任务从包含 TASK-007 的最新 `master` 创建
`task/TASK-004-FIX-candidate-tolerance`，未直接修改 master。

## 2. 校验边界

repair 响应仍先严格校验以下整体条件，任一失败都会停止：

- JSON 可解析，且顶层必须且只能有 `topics` 和 `candidates`；
- topics 和 candidates 都是数组，每窗口 candidates 不超过 3 个；
- topics 字段完整、范围引用真实连续 segment、按顺序且不重叠。

只有整体条件全部有效后，才逐个复用既有 candidate 校验。时长不是 15—180 秒、跨 topic、
quote 越界、segment ID 不真实或不连续、字段错误、score/risk 越界等项目会被丢弃。实现不延长、
缩短、重定位或补写 candidate，不改 topic，不猜 ID，也不把 candidate 强塞进 topic。

清洗后的结果沿用既有 state 写入、恢复、merge、总分计算、60 分发布门槛、重叠去重与全局上限。
state 恢复再次执行原有严格 `validate_model_payload`，最终文件在 staging 和发布前继续执行严格
`validate_analysis`。

## 3. 自动测试

TASK-004 专项：42 passed、0 failed。新增用例覆盖：

- 1 个合法、1 个时长错误、1 个跨 topic 时只保留合法项；
- quote 越界、score 越界、candidate 字段错误时只丢对应项；
- 全部 candidate 无效时发布空 candidates；
- repair 后 JSON 损坏、topics 重叠、topic 引用未知 segment、candidates 非数组时继续失败；
- 首次响应仍严格触发 repair，repair 超过 3 个 candidates 继续失败；
- 失败在第 2 次请求后停止，不发生第 3 次请求；
- candidate 过滤后的窗口 state 成功保存，再运行从下一窗口恢复；
- 既有最近 3 个完整 analysis 版本测试保持通过。

完整 source-only：

- base-schema-media：245 passed、1 deselected、0 failed；
- asr-experiments：91 passed、2 deselected、0 failed，只有 1 个既有 `audioop` deprecation warning；
- `pip check`：`No broken requirements found.`；
- 三阶段退出码均为 0，`SOURCE_ONLY_RESULT.status=passed`。

## 4. 真实 API 验证

复用 Git 忽略目录中既有 completed timeline：827.766 秒、169 segments。直接运行 analyze，未调用
ASR、未读取或上传视频/音频，也没有扫描工作区以外的用户磁盘。两个窗口均完成，最终结果为
15 topics、5 candidates、5 recommended；候选时长范围为 17.472—27.424 秒。

发布后的 `current_analysis.json` 已再次通过严格 `validate_analysis`；analysis 内 timeline SHA 与
输入逐字节 SHA 相同，输入 timeline 验证前后 SHA 不变，完成后 `.analysis_work` 已清理。真实运行
未在 CLI 输出中暴露底层请求计数，因此不据此推断调用次数；每窗口两次上限及无第 3 次请求由
可观察 `FakeClient.request_count` 的自动测试验证。

真实 timeline、analysis、字幕正文、候选标题/理由/quote、本地绝对路径和 API Key 均未写入本
报告或 Git。API Key 只来自既有进程环境，不进入请求正文、state、日志或提交内容。

## 5. 范围与后续

未更换模型，未修改 ASR、字幕烧录、review/export、Windows 启动器或 TASK-007 行为；没有实现
批量、多片段拼接、自动发布或 TASK-008。交付只创建 Draft PR，不 Ready、不 merge、不启用
auto-merge、不 force push。GitHub latest-head Actions 与独立审核不在本地结果中预先宣称。
