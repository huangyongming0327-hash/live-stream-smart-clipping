"""Public commands for transcription, analysis, and local review."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from .analysis import AnalysisError, run_analysis
from .asr.pipeline import ASRPipelineError, StateFileError, run_transcription
from .media import MediaError
from .pipeline import PipelineRunError, run_pipeline
from .review.schema import ReviewError
from .review.server import launch_review


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m liveclip")
    commands = parser.add_subparsers(dest="command", required=True)
    transcribe = commands.add_parser(
        "transcribe", help="Generate a local timeline, SRT, and transcript from one MP4."
    )
    transcribe.add_argument("--input", required=True, help="One input .mp4 file.")
    transcribe.add_argument(
        "--engine",
        choices=("paraformer", "sensevoice"),
        default="paraformer",
        help="Local ASR engine (default: paraformer).",
    )
    transcribe.add_argument(
        "--output",
        help="Output directory (default: <video_stem>_liveclip beside the MP4).",
    )
    transcribe.add_argument(
        "--chunk-seconds",
        type=float,
        default=60.0,
        help="Sequential audio chunk length from 1 to 600 seconds (default: 60).",
    )
    transcribe.add_argument(
        "--assets-root",
        help=(
            "Root containing tools/ffmpeg, runtime/asr-envs, and 模型/asr. "
            "Defaults to LIVECLIP_ASSETS_ROOT or this project."
        ),
    )
    transcribe.add_argument(
        "--model-root",
        help="Optional direct override for the local ASR model root.",
    )
    transcribe.add_argument(
        "--asr-python",
        help="Optional engine-specific Python interpreter override.",
    )
    analyze = commands.add_parser(
        "analyze",
        help="Generate topics and highlight candidates from one completed timeline.",
    )
    analyze.add_argument("--timeline", required=True, help="One completed timeline.json.")
    analyze.add_argument(
        "--output",
        help="Output directory (default: beside timeline.json).",
    )
    review = commands.add_parser(
        "review",
        help="Review candidates locally and export one confirmed MP4 and SRT.",
    )
    review.add_argument("--video", required=True, help="One source .mp4 file.")
    review.add_argument("--timeline", required=True, help="Its completed timeline.json.")
    review.add_argument(
        "--analysis",
        required=True,
        help="Its completed current_analysis.json.",
    )
    review.add_argument(
        "--output",
        help="Export directory (default: <video_stem>_exports beside the MP4).",
    )
    run = commands.add_parser(
        "run",
        help="Run local transcription, analysis, review, and one confirmed export.",
    )
    run.add_argument("--video", required=True, help="One source .mp4 file.")
    run.add_argument(
        "--workdir",
        help="Working directory (default: <video_stem>_liveclip beside the MP4).",
    )
    run.add_argument(
        "--asr-model",
        choices=("paraformer", "sensevoice"),
        default="paraformer",
        help="Local ASR model (default: paraformer).",
    )
    run.add_argument(
        "--output",
        help="Export directory (default: <workdir>/exports).",
    )
    run.add_argument(
        "--no-open-browser",
        action="store_true",
        help="Start the local review service without opening the default browser.",
    )
    return parser


def _assets_root(value: str | None) -> Path:
    configured = value or os.environ.get("LIVECLIP_ASSETS_ROOT")
    return Path(configured).resolve() if configured else project_root()


def _engine_python(
    engine: str,
    assets_root: Path,
    override: str | None,
) -> Path | None:
    if override:
        return Path(override).resolve()
    environment_name = (
        "LIVECLIP_PARAFORMER_PYTHON"
        if engine == "paraformer"
        else "LIVECLIP_SENSEVOICE_PYTHON"
    )
    configured = os.environ.get(environment_name)
    if configured:
        return Path(configured).resolve()
    environment = "funasr" if engine == "paraformer" else "sherpa-onnx"
    candidate = (
        assets_root / "runtime" / "asr-envs" / environment / "Scripts" / "python.exe"
    )
    return candidate.resolve() if candidate.is_file() else None


def _offline_environment(assets_root: Path) -> dict[str, str]:
    environment = dict(os.environ)
    cache_root = assets_root / "runtime" / "cache" / "asr"
    temp_root = assets_root / "runtime" / "temp" / "asr-production"
    paths = {
        "PIP_CACHE_DIR": cache_root / "pip",
        "HF_HOME": cache_root / "hf",
        "HUGGINGFACE_HUB_CACHE": cache_root / "hf" / "hub",
        "MODELSCOPE_CACHE": cache_root / "modelscope",
        "TORCH_HOME": cache_root / "torch",
        "XDG_CACHE_HOME": cache_root / "xdg",
        "TEMP": temp_root,
        "TMP": temp_root,
    }
    for name, path in paths.items():
        path.mkdir(parents=True, exist_ok=True)
        environment[name] = str(path.resolve())
    environment.update(
        OMP_NUM_THREADS="4",
        MKL_NUM_THREADS="4",
        OPENBLAS_NUM_THREADS="4",
        CUDA_VISIBLE_DEVICES="-1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        MODELSCOPE_OFFLINE="1",
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
        TOKENIZERS_PARALLELISM="false",
    )
    source_root = str(Path(__file__).resolve().parents[1])
    current_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source_root
        if not current_pythonpath
        else source_root + os.pathsep + current_pythonpath
    )
    for secret_name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "HF_TOKEN",
        "HUGGING_FACE_HUB_TOKEN",
        "MODELSCOPE_API_TOKEN",
    ):
        environment.pop(secret_name, None)
    return environment


def _same_executable(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))


def _maybe_reexec(
    argv: Sequence[str],
    *,
    engine: str,
    assets_root: Path,
    asr_python: str | None,
) -> int | None:
    selected = _engine_python(engine, assets_root, asr_python)
    if selected is None:
        return None
    if not selected.is_file():
        raise ASRPipelineError(f"Configured ASR Python does not exist: {selected}")
    if _same_executable(Path(sys.executable), selected):
        return None
    completed = subprocess.run(
        [str(selected), "-m", "liveclip", *argv],
        cwd=project_root(),
        env=_offline_environment(assets_root),
        stdin=None,
        stdout=None,
        stderr=None,
        shell=False,
        check=False,
    )
    return completed.returncode


def main(argv: Sequence[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(effective_argv)
    if args.command == "run":
        assets_root = _assets_root(None)
        try:
            reexec_result = _maybe_reexec(
                effective_argv,
                engine=args.asr_model,
                assets_root=assets_root,
                asr_python=None,
            )
            if reexec_result is not None:
                return reexec_result
            run_pipeline(
                args.video,
                workdir=args.workdir,
                asr_model=args.asr_model,
                output_dir=args.output,
                open_browser=not args.no_open_browser,
                assets_root=assets_root,
            )
            return 0
        except KeyboardInterrupt:
            print(
                "当前阶段：已中断\n下一步：再次运行同一命令可继续。",
                file=sys.stderr,
            )
            return 130
        except PipelineRunError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except (ASRPipelineError, StateFileError, MediaError, OSError, ValueError) as exc:
            print(
                "启动检查：失败\n"
                f"原因：{' '.join(str(exc).splitlines())}\n"
                "下一步：修正直接原因后再次运行同一命令。\n"
                "再次运行同一命令：可以继续。",
                file=sys.stderr,
            )
            return 1
    if args.command == "analyze":
        try:
            run_analysis(args.timeline, output_dir=args.output)
            return 0
        except KeyboardInterrupt:
            print("失败: 分析已中断；下次运行将从最近完成窗口继续。", file=sys.stderr)
            return 130
        except (AnalysisError, OSError, ValueError) as exc:
            print(f"失败: {exc}", file=sys.stderr)
            return 1

    if args.command == "review":
        try:
            launch_review(
                args.video,
                args.timeline,
                args.analysis,
                output_dir=args.output,
            )
            print("审核服务已停止。")
            return 0
        except KeyboardInterrupt:
            print("审核服务已停止。", file=sys.stderr)
            return 130
        except (ReviewError, OSError, ValueError) as exc:
            print(f"失败: {exc}", file=sys.stderr)
            return 1

    if args.command != "transcribe":
        parser.error("Unsupported command.")
    assets_root = _assets_root(args.assets_root)
    try:
        reexec_result = _maybe_reexec(
            effective_argv,
            engine=args.engine,
            assets_root=assets_root,
            asr_python=args.asr_python,
        )
        if reexec_result is not None:
            return reexec_result
        run_transcription(
            args.input,
            engine=args.engine,
            output_dir=args.output,
            chunk_seconds=args.chunk_seconds,
            assets_root=assets_root,
            model_root=args.model_root,
        )
        return 0
    except KeyboardInterrupt:
        print("失败: 任务已中断；下次运行将从最近完成分块继续。", file=sys.stderr)
        return 130
    except (ASRPipelineError, StateFileError, MediaError, OSError, ValueError) as exc:
        print(f"失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
