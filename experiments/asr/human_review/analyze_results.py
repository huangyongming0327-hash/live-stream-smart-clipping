"""Command-line entry point for TASK-002-HUMAN-002 result analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.asr.common import atomic_write_text

from .result_analysis import ManifestMismatchError, run_analysis


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = (
    PROJECT_ROOT / "local-data" / "asr-human-review" / "review-manifest.json"
)
DEFAULT_LOCAL_OUTPUT = (
    PROJECT_ROOT / "local-data" / "asr-human-review" / "analysis"
)
DEFAULT_PUBLIC_RESULT = PROJECT_ROOT / "docs" / "ASR_HUMAN_REVIEW_RESULT.md"
DEFAULT_PUBLIC_BASELINE = PROJECT_ROOT / "docs" / "ASR_PRODUCTION_BASELINE.md"
DEFAULT_MISMATCH_REPORT = (
    PROJECT_ROOT
    / "tasks"
    / "reports"
    / "TASK-002-HUMAN-002_MANIFEST_MISMATCH.md"
)


def _write_manifest_mismatch(
    path: Path,
    error: ManifestMismatchError,
) -> None:
    atomic_write_text(
        path,
        "\n".join(
            (
                "# TASK-002-HUMAN-002｜manifest SHA 不匹配",
                "",
                "- 状态：已阻断，未执行任何统计、模型排名或生产基线决策。",
                f"- 完成版 JSON 声明 SHA-256：`{error.declared_sha256}`",
                f"- 真实 review-manifest.json SHA-256：`{error.actual_sha256}`",
                "- 下一步：确认完成版 JSON 是否来自当前本地审核包；不得自动改写用户 JSON。",
                "",
            )
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Strictly validate and analyze a completed ASR listening review."
    )
    parser.add_argument("--review-json", required=True)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--local-output-dir", default=str(DEFAULT_LOCAL_OUTPUT))
    parser.add_argument("--public-result", default=str(DEFAULT_PUBLIC_RESULT))
    parser.add_argument("--public-baseline", default=str(DEFAULT_PUBLIC_BASELINE))
    parser.add_argument(
        "--manifest-mismatch-report",
        default=str(DEFAULT_MISMATCH_REPORT),
    )
    args = parser.parse_args()

    try:
        analysis = run_analysis(
            args.review_json,
            args.manifest,
            args.local_output_dir,
            public_result_path=args.public_result,
            public_baseline_path=args.public_baseline,
        )
    except ManifestMismatchError as exc:
        _write_manifest_mismatch(Path(args.manifest_mismatch_report), exc)
        raise SystemExit("analysis blocked: manifest SHA-256 mismatch") from exc

    decision = analysis["decision"]
    summary = {
        "status": "passed",
        "completed": "20/20",
        "manifest_sha_match": True,
        "input_sha256_unchanged": analysis["source_integrity"]["unchanged"],
        "primary_model": decision["primary_model"],
        "fallback_model": decision["fallback_model"],
        "decision_confidence": decision["decision_confidence"],
        "decision_status": decision["decision_status"],
    }
    print("RESULT_ANALYSIS=" + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
