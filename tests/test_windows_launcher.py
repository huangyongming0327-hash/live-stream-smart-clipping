from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "tools" / "windows" / "Start-LiveClip.ps1"


def _quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_powershell(statement: str) -> subprocess.CompletedProcess[str]:
    command = (
        "$ErrorActionPreference='Stop'; "
        f". {_quote(LAUNCHER)}; "
        + statement
    )
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _touch_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"test-python")
    return path.resolve()


def _resolve_python(repo: Path, assets: Path, candidates: list[Path]) -> subprocess.CompletedProcess[str]:
    candidate_array = "@(" + ",".join(_quote(path) for path in candidates) + ")"
    return _run_powershell(
        "Resolve-LiveClipPython "
        f"-RepositoryRoot {_quote(repo)} "
        f"-AssetsRoot {_quote(assets)} "
        f"-CommandCandidates {candidate_array}"
    )


def test_repository_venv_is_first_python_choice(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    assets = tmp_path / "assets"
    repository_python = _touch_executable(repository / ".venv" / "Scripts" / "python.exe")
    assets_python = _touch_executable(assets / ".venv" / "Scripts" / "python.exe")
    real_python = _touch_executable(tmp_path / "Python312" / "python.exe")
    result = _resolve_python(repository, assets, [real_python])
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == repository_python
    assert repository_python != assets_python


def test_assets_venv_is_second_python_choice(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    assets = tmp_path / "assets"
    assets_python = _touch_executable(assets / ".venv" / "Scripts" / "python.exe")
    real_python = _touch_executable(tmp_path / "Python312" / "python.exe")
    result = _resolve_python(repository, assets, [real_python])
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == assets_python


def test_windowsapps_alias_is_excluded_and_only_one_real_python_is_selected(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    assets = tmp_path / "assets"
    alias = _touch_executable(tmp_path / "WindowsApps" / "python.exe")
    real_python = _touch_executable(tmp_path / "Python312" / "python.exe")
    second_real = _touch_executable(tmp_path / "Python311" / "python.exe")
    result = _resolve_python(repository, assets, [alias, real_python, second_real])
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == real_python
    assert "\n" not in result.stdout.strip()


def test_missing_python_error_is_clear_and_does_not_require_alias_changes(tmp_path: Path) -> None:
    result = _resolve_python(tmp_path / "repo", tmp_path / "assets", [])
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "Python was not found" in combined
    assert "WindowsApps aliases are ignored automatically" in combined
    assert "disable" not in combined.lower()


def test_missing_assets_message_lists_items_and_copyable_user_setting(tmp_path: Path) -> None:
    result = _run_powershell(
        "Resolve-LiveClipAssetsRoot "
        f"-RepositoryRoot {_quote(tmp_path / 'repo')} "
        "-AsrModel sensevoice -ConfiguredRoot ''"
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "FFmpeg/ffprobe" in combined
    assert "SenseVoice model" in combined
    assert "[Environment]::SetEnvironmentVariable" in combined
    assert '"LIVECLIP_ASSETS_ROOT"' in combined
    launcher_source = LAUNCHER.read_text(encoding="utf-8")
    assert (
        '[Environment]::SetEnvironmentVariable("LIVECLIP_ASSETS_ROOT", '
        '"<包含模型、FFmpeg和ASR环境的目录>", "User")'
    ) in launcher_source
    assert "API_KEY" not in combined
