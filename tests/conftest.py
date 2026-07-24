from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def timeline_data() -> dict:
    return {
        "schema_version": "1.0",
        "project_id": "项目-中文路径",
        "video": {
            "path": "<PROJECT_ROOT>\\项目\\测试直播.mp4",
            "duration": 120.0,
            "file_name": "测试直播.mp4",
            "width": 1920,
            "height": 1080,
        },
        "model_info": {
            "provider": "本地",
            "model": "测试转写器",
            "version": "0.0-test",
            "local": True,
        },
        "segments": [
            {
                "id": "seg-001",
                "start": 1.0,
                "end": 4.0,
                "speaker": "主播",
                "raw_text": "大家 好",
                "clean_text": "大家好",
                "risk_level": "none",
                "risk_reasons": [],
                "words": [
                    {
                        "start": 1.0,
                        "end": 1.8,
                        "text": "大家",
                        "confidence": 0.98,
                    },
                    {
                        "start": 1.8,
                        "end": 2.2,
                        "text": "好",
                        "confidence": 0.97,
                    },
                ],
            },
            {
                "id": "seg-002",
                "start": 5.0,
                "end": 8.0,
                "speaker": "嘉宾",
                "raw_text": "这是 第二段",
                "clean_text": "这是第二段",
                "risk_level": "yellow",
                "risk_reasons": ["需要人工确认专有名词"],
                "words": [],
            },
        ],
    }


@pytest.fixture
def analysis_data() -> dict:
    return {
        "schema_version": "1.0",
        "project_id": "项目-中文路径",
        "analysis_version": "analysis-001",
        "video_duration": 120.0,
        "model_usage": [
            {
                "provider": "本地测试",
                "model": "规则引擎",
                "purpose": "离线契约验证",
                "local": True,
            }
        ],
        "topics": [
            {"topic_id": "topic-001", "name": "开场", "summary": "直播开场主题"}
        ],
        "candidates": [
            {
                "candidate_id": "candidate-001",
                "topic_id": "topic-001",
                "content_type": "viewpoint",
                "grade": "S",
                "score": 86.5,
                "ranges": {
                    "core": {"start": 10.0, "end": 20.0},
                    "recommended": {"start": 8.0, "end": 22.0},
                    "extended": {"start": 5.0, "end": 25.0},
                },
                "transcript": "这是一段值得审核的中文候选内容。",
                "titles": ["中文标题候选"],
                "quotes": ["值得保留的原话"],
                "recommendation_reason": "主题完整，开头明确。",
                "subtitle_reliability": "high",
                "visual_dependency": False,
                "risks": [],
                "status": "pending_review",
            }
        ],
    }


@pytest.fixture
def review_data() -> dict:
    return {
        "schema_version": "1.0",
        "project_id": "项目-中文路径",
        "source_analysis_version": "analysis-001",
        "candidates": [
            {
                "candidate_id": "candidate-001",
                "review_status": "selected",
                "final_start": 8.5,
                "final_end": 21.5,
                "final_title": "人工确认后的中文标题",
                "subtitle_edits": [
                    {
                        "segment_id": "seg-001",
                        "original_text": "原字幕",
                        "edited_text": "修订字幕",
                    }
                ],
                "needs_reanalysis": False,
                "user_notes": "中文备注：保留上下文。",
                "updated_at": datetime(
                    2026,
                    7,
                    18,
                    16,
                    0,
                    tzinfo=timezone(timedelta(hours=8)),
                ),
            }
        ],
    }
