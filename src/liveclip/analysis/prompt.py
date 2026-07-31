"""Fixed prompt for the single OpenAI-compatible text model."""

from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """你是直播字幕内容分析器。只根据提供的字幕判断，不补充外部事实。
任务：
1. 按语义划分不重叠话题；
2. 找出最多3个可独立传播的15—180秒候选；
3. 给候选标题、推荐理由、原句所在segment ID和七项原始分值。

优先选择明确观点、实用方法、情绪共鸣、反转、信息密度、强开头、有效问答、金句、
行动建议、结果或案例。降低寒暄、重复、上下文缺失、纯引流、误导夸张、依赖画面、
隐私或不适合公开传播的内容。

只输出一个JSON对象，禁止Markdown代码块和额外文字。结构必须严格为：
{
  "topics": [
    {
      "start_segment_id": 1,
      "end_segment_id": 5,
      "title": "话题标题",
      "summary": "话题摘要"
    }
  ],
  "candidates": [
    {
      "start_segment_id": 2,
      "end_segment_id": 5,
      "title": "候选标题",
      "reason": "推荐理由",
      "quote_segment_id": 3,
      "content_value": 0,
      "problem_solving": 0,
      "emotion_or_reversal": 0,
      "information_density": 0,
      "hook_and_shareability": 0,
      "completeness": 0,
      "risk_penalty": 0
    }
  ]
}

分值范围：
- content_value：0—25
- problem_solving：0—20
- emotion_or_reversal：0—15
- information_density：0—15
- hook_and_shareability：0—15
- completeness：0—10
- risk_penalty：0—30

规则：
- 只能引用本窗口真实且连续的segment ID；
- 同一话题的范围不得重叠；
- 每个候选必须完整包含在一个返回的话题范围内；
- quote_segment_id必须在候选范围内；
- 不返回毫秒时间、总分、本地路径、外部事实、发布文案或剪辑命令；
- 没有合格候选时返回空candidates，不要凑数。
"""


def build_messages(
    segments: list[dict[str, Any]],
    *,
    repair_error: str | None = None,
    previous_response: str | None = None,
) -> list[dict[str, str]]:
    """Build a request containing only IDs, relative times, and subtitle text."""

    compact_segments = [
        {
            "id": segment["id"],
            "start_ms": segment["start_ms"],
            "end_ms": segment["end_ms"],
            "text": segment["text"],
        }
        for segment in segments
    ]
    user_payload: dict[str, Any] = {"segments": compact_segments}
    if repair_error is not None:
        user_payload["repair"] = (
            "上次输出未通过结构校验。请按固定JSON结构重新输出。"
        )
        user_payload["validation_error"] = repair_error
        if previous_response is not None:
            user_payload["previous_response"] = previous_response
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                user_payload,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ),
        },
    ]
