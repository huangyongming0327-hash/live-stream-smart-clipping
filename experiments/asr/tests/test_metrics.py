from __future__ import annotations

import pytest

from experiments.asr.metrics import (
    ReferenceRequiredError,
    character_error_rate,
    compute_accuracy,
    mixed_word_error_rate,
)
from experiments.asr.normalize import cer_units, mixed_tokens, parse_srt


def test_chinese_mixed_normalization_preserves_numbers_and_english_words():
    assert cer_units("ＡＩ，版本 2.0！") == list("ai版本20")
    assert mixed_tokens("你好 OpenAI-4.1，版本2") == ["你", "好", "openai-4", "1", "版", "本", "2"]


def test_cer_and_mixed_wer_counts():
    cer = character_error_rate("你好世界", "你好世")
    assert (cer.errors, cer.deletions, cer.rate) == (1, 1, 0.25)
    wer = mixed_word_error_rate("你好 OpenAI", "你好 GPT")
    assert wer.substitutions == 1
    assert wer.errors == 1


def test_accuracy_requires_human_reference():
    with pytest.raises(ReferenceRequiredError):
        compute_accuracy(None, "不能计算")


def test_srt_parser_handles_utf8_bom_and_multiline_text():
    cues = parse_srt(
        "\ufeff1\r\n00:00:00,100 --> 00:00:01,250\r\n第一行\r\n第二行\r\n"
    )
    assert len(cues) == 1
    assert cues[0].start == 0.1
    assert cues[0].end == 1.25
    assert cues[0].text == "第一行\n第二行"
