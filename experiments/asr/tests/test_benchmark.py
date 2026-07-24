from __future__ import annotations

from experiments.asr.benchmark import run_selected


def test_candidate_failure_is_isolated():
    calls = []

    def runner(candidate):
        calls.append(candidate)
        if candidate == "bad":
            raise RuntimeError("expected failure")
        return {"candidate": candidate, "success": True}

    statuses = run_selected(["first", "bad", "last"], runner=runner)
    assert calls == ["first", "bad", "last"]
    assert [item["success"] for item in statuses] == [True, False, True]
