from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

from liveclip.media.process_runner import decode_process_output


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = PROJECT_ROOT / "tools" / "Install-FFmpeg.ps1"
REAL_INSTALL_MARKER = PROJECT_ROOT / "tools" / "ffmpeg" / ".liveclip-ffmpeg-install.json"
REAL_INSTALL_ROOT = PROJECT_ROOT / "tools" / "ffmpeg"
REAL_FFMPEG = REAL_INSTALL_ROOT / "bin" / "ffmpeg.exe"
REAL_FFPROBE = REAL_INSTALL_ROOT / "bin" / "ffprobe.exe"
PINNED_SHA256 = "0fff188997a499b5382e0f66e845d4556c48c54f0113ebed4853d556dbdd7059"
DIRECT_URL = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-full_build.7z"
CHECKSUM_URL = DIRECT_URL + ".sha256"
ARCHIVE_NAME = "ffmpeg-8.1.2-full_build.7z"
TEST_SENTINEL = ".liveclip-ffmpeg-test-root"


def run_installer(
    project_root: str | Path,
    *arguments: str,
    test_mode: bool = False,
    isolation_root: str | Path | None = None,
    prepare_isolation: bool = True,
) -> tuple[subprocess.CompletedProcess[bytes], str]:
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(INSTALL_SCRIPT),
        "-ProjectRoot",
        str(project_root),
    ]
    if test_mode:
        isolation = isolation_root or Path(project_root).parent
        if prepare_isolation:
            isolation_path = Path(isolation)
            isolation_path.mkdir(parents=True, exist_ok=True)
            (isolation_path / TEST_SENTINEL).write_text(
                "isolated test root", encoding="utf-8"
            )
        command.extend(["-TestMode", "-TestIsolationRoot", str(isolation)])
    command.extend(arguments)
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
        timeout=30,
    )
    stdout = decode_process_output(completed.stdout).text
    stderr = decode_process_output(completed.stderr).text
    return completed, stdout + "\n" + stderr


def summaries(output: str) -> list[dict]:
    prefix = "LIVECLIP_FFMPEG_SUMMARY="
    return [
        json.loads(line[len(prefix) :])
        for line in output.splitlines()
        if line.startswith(prefix)
    ]


def make_test_resources(
    isolation_root: Path,
    content: bytes = b"isolated local archive fixture",
    checksum_text: str | None = None,
) -> tuple[Path, Path, str]:
    isolation_root.mkdir(parents=True, exist_ok=True)
    archive = isolation_root / "fixture.7z"
    checksum = isolation_root / "fixture.7z.sha256"
    archive.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    checksum.write_text(checksum_text if checksum_text is not None else digest, encoding="ascii")
    return archive, checksum, digest


def installer_test_mode_arguments(
    archive: str | Path, checksum: str | Path, digest: str
) -> list[str]:
    return [
        "-TestArchivePath",
        str(archive),
        "-TestPublisherChecksumPath",
        str(checksum),
        "-TestExpectedSha256",
        digest,
        "-TestExpectedVersion",
        "8.1.2",
    ]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def real_install_hashes() -> dict[str, str]:
    return {
        "marker": file_sha256(REAL_INSTALL_MARKER),
        "ffmpeg": file_sha256(REAL_FFMPEG),
        "ffprobe": file_sha256(REAL_FFPROBE),
    }


@contextmanager
def directory_junction(link: Path, target: Path) -> Iterator[None]:
    link.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        check=False,
        timeout=10,
    )
    output = decode_process_output(completed.stdout + completed.stderr).text
    assert completed.returncode == 0, output
    try:
        yield
    finally:
        if link.exists() or link.is_symlink():
            os.rmdir(link)


def link_project_binaries(binary_dir: Path) -> None:
    binary_dir.mkdir(parents=True)
    os.link(PROJECT_ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe", binary_dir / "ffmpeg.exe")
    os.link(PROJECT_ROOT / "tools" / "ffmpeg" / "bin" / "ffprobe.exe", binary_dir / "ffprobe.exe")


def write_known_marker(
    install: Path,
    *,
    provider: str,
    source: str,
    checksum_source: str,
    archive_name: str,
    archive_hash: str,
    legacy: bool,
) -> None:
    common = {
        "provider": provider,
        "actual_url": source,
        "published_checksum_url": checksum_source,
        "archive_file_name": archive_name,
        "archive_size_bytes": 166721853,
        "sha256": archive_hash,
        "sha256_verified_against_publisher": True,
        "expected_version": "8.1.2",
        "download_time": "2026-07-18T23:53:17.497+08:00",
        "installed_time": "2026-07-18T23:55:35.872+08:00",
        "version_line": "ffmpeg version 8.1.2-full_build-www.gyan.dev",
        "system_path_modified": False,
    }
    if provider == "gyan.dev":
        common.update(
            {
                "source_page": "https://ffmpeg.org/download.html",
                "provider_page": "https://www.gyan.dev/ffmpeg/builds/",
            }
        )
    if not legacy:
        common.update(
            {
                "mode": "test",
                "source_type": "local_test_resource",
                "installed_from_url": source,
                "installed_archive_size": 166721853,
                "installed_archive_sha256": archive_hash,
                "publisher_sha256": archive_hash,
                "publisher_hash_verified_at_install": True,
                "version": "8.1.2",
                "installed_at": "2026-07-18T23:55:35.872+08:00",
            }
        )
    (install / ".liveclip-ffmpeg-install.json").write_text(
        json.dumps(common), encoding="utf-8"
    )


def test_production_source_constants_and_new_fields_are_auditable() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8-sig")
    assert "https://ffmpeg.org/download.html" in script
    assert '@("gyan.dev", "BtbN")' in script
    assert "https://www.gyan.dev/ffmpeg/builds/" in script
    assert DIRECT_URL in script
    assert CHECKSUM_URL in script
    assert ARCHIVE_NAME in script
    assert re.fullmatch(r"[0-9a-f]{64}", PINNED_SHA256)
    assert PINNED_SHA256 in script
    for removed_parameter in (
        "DownloadUri",
        "PublisherChecksumUri",
        "ExpectedSha256",
        "ExpectedVersion",
        "ArchiveFileName",
    ):
        assert not re.search(rf"\[string\]\s*\${removed_parameter}\b", script)
    assert "publisher_hash_compared" not in script
    assert "publisher_hash_match =" not in script
    for field in (
        "publisher_hash_verified_at_install",
        "publisher_hash_checked_this_run",
        "publisher_hash_match_this_run",
        "archive_hash_recomputed_this_run",
        "archive_downloaded_this_run",
    ):
        assert field in script


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("DownloadUri", "https://example.com/not-gyan.7z"),
        ("PublisherChecksumUri", "https://example.com/not-gyan.sha256"),
        ("ExpectedSha256", "1" * 64),
        ("ExpectedVersion", "9.9.9"),
        ("ArchiveFileName", "caller-controlled.7z"),
    ],
)
def test_production_call_cannot_override_audited_source_fields(
    tmp_path: Path, parameter: str, value: str
) -> None:
    project = tmp_path / parameter
    unknown_install = project / "tools" / "ffmpeg"
    unknown_install.mkdir(parents=True)
    (unknown_install / "do-not-touch.txt").write_text("preserve", encoding="utf-8")
    completed, output = run_installer(project, f"-{parameter}", value)
    assert completed.returncode != 0
    assert "parameter cannot be found" in output.lower()
    assert (unknown_install / "do-not-touch.txt").read_text(encoding="utf-8") == "preserve"


def test_local_archive_cannot_be_injected_into_production_mode(tmp_path: Path) -> None:
    archive, _, _ = make_test_resources(tmp_path)
    completed, output = run_installer(tmp_path / "project", "-DownloadUri", str(archive))
    assert completed.returncode != 0
    assert "parameter cannot be found" in output.lower()
    assert not (tmp_path / "project" / "tools" / "ffmpeg").exists()


def test_preexisting_local_archive_is_not_used_or_deleted_in_production(tmp_path: Path) -> None:
    project = tmp_path / "project"
    archive = project / "runtime" / "temp" / "ffmpeg-download" / ARCHIVE_NAME
    archive.parent.mkdir(parents=True)
    content = b"caller-prepositioned local archive"
    archive.write_bytes(content)
    completed, output = run_installer(project)
    assert completed.returncode != 0
    assert "Refusing to use a pre-existing local archive" in output
    assert archive.read_bytes() == content
    summary = summaries(output)[-1]
    assert summary["status"] == "failed"
    assert summary["mode"] == "production"
    assert summary["archive_downloaded_this_run"] is False
    assert summary["archive_hash_recomputed_this_run"] is False
    assert not (project / "tools" / "ffmpeg").exists()


def test_test_only_parameters_require_explicit_test_mode(tmp_path: Path) -> None:
    archive, checksum, digest = make_test_resources(tmp_path)
    completed, output = run_installer(
        tmp_path / "project", *installer_test_mode_arguments(archive, checksum, digest)
    )
    assert completed.returncode != 0
    assert "require explicit -TestMode" in output
    assert not (tmp_path / "project" / "tools" / "ffmpeg").exists()


@pytest.mark.parametrize("remote_field", ["archive", "checksum"])
def test_test_mode_rejects_remote_resources(tmp_path: Path, remote_field: str) -> None:
    archive, checksum, digest = make_test_resources(tmp_path)
    archive_value = "https://example.com/fixture.7z" if remote_field == "archive" else str(archive)
    checksum_value = "https://example.com/fixture.sha256" if remote_field == "checksum" else str(checksum)
    completed, output = run_installer(
        tmp_path / "project",
        *installer_test_mode_arguments(archive_value, checksum_value, digest),
        test_mode=True,
        isolation_root=tmp_path,
    )
    assert completed.returncode != 0
    assert "remote URLs are forbidden" in output
    assert not (tmp_path / "project" / "tools" / "ffmpeg").exists()


def test_test_mode_rejects_unc_isolation_root_without_accessing_it(
    tmp_path: Path,
) -> None:
    archive, checksum, digest = make_test_resources(tmp_path)
    real_before = real_install_hashes()
    project = tmp_path / "project"
    completed, output = run_installer(
        project,
        *installer_test_mode_arguments(archive, checksum, digest),
        test_mode=True,
        isolation_root=r"\\server\share\liveclip-isolation",
        prepare_isolation=False,
    )
    assert completed.returncode != 0
    assert "TestIsolationRoot failed validation" in output
    assert "TestMode only allows local fixed-disk paths" in output
    assert "UNC" in output and "forbidden" in output
    assert not project.exists()
    assert real_install_hashes() == real_before


@pytest.mark.parametrize("remote_field", ["archive", "checksum"])
def test_test_mode_rejects_unc_resources_before_file_access(
    tmp_path: Path, remote_field: str
) -> None:
    archive, checksum, digest = make_test_resources(tmp_path)
    archive_value = (
        r"\\server\share\fixture.7z" if remote_field == "archive" else str(archive)
    )
    checksum_value = (
        r"\\localhost\share\fixture.7z.sha256"
        if remote_field == "checksum"
        else str(checksum)
    )
    real_before = real_install_hashes()
    project = tmp_path / "project"
    completed, output = run_installer(
        project,
        *installer_test_mode_arguments(archive_value, checksum_value, digest),
        test_mode=True,
        isolation_root=tmp_path,
    )
    assert completed.returncode != 0
    assert f"Test{'ArchivePath' if remote_field == 'archive' else 'PublisherChecksumPath'} failed validation" in output
    assert "TestMode only allows local fixed-disk paths" in output
    assert "UNC" in output and "forbidden" in output
    assert not (project / "runtime" / "temp" / "ffmpeg-download").exists()
    assert not (project / "tools" / "ffmpeg").exists()
    assert real_install_hashes() == real_before


@pytest.mark.parametrize("host", ["server", "localhost"])
def test_test_mode_rejects_remote_file_uri_before_file_access(
    tmp_path: Path, host: str
) -> None:
    _, checksum, digest = make_test_resources(tmp_path)
    remote_archive = f"file://{host}/share/fixture.7z"
    real_before = real_install_hashes()
    project = tmp_path / "project"
    completed, output = run_installer(
        project,
        *installer_test_mode_arguments(remote_archive, checksum, digest),
        test_mode=True,
        isolation_root=tmp_path,
    )
    assert completed.returncode != 0
    assert "TestArchivePath failed validation" in output
    assert "remote file URI hosts are forbidden" in output
    assert not (project / "runtime" / "temp" / "ffmpeg-download").exists()
    assert not (project / "tools" / "ffmpeg").exists()
    assert real_install_hashes() == real_before


@pytest.mark.parametrize(
    "unsafe_path",
    [r"\\?\D:\fixture.7z", r"\\.\pipe\liveclip-fixture"],
)
def test_test_mode_rejects_device_and_named_pipe_paths_without_access(
    tmp_path: Path, unsafe_path: str
) -> None:
    _, checksum, digest = make_test_resources(tmp_path)
    project = tmp_path / "project"
    completed, output = run_installer(
        project,
        *installer_test_mode_arguments(unsafe_path, checksum, digest),
        test_mode=True,
        isolation_root=tmp_path,
    )
    assert completed.returncode != 0
    assert "TestMode only allows local fixed-disk paths" in output
    assert "UNC" in output and "forbidden" in output
    assert not (project / "runtime" / "temp" / "ffmpeg-download").exists()


def test_test_mode_requires_driveinfo_fixed_disk_semantics() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8-sig")
    assert "System.IO.DriveInfo" in script
    assert "$driveType -ne [System.IO.DriveType]::Fixed" in script
    assert "unable to determine a local fixed-disk volume" in script
    assert "drive type '$driveType' is forbidden" in script


def test_test_mode_rejects_resource_outside_isolation_root(tmp_path: Path) -> None:
    isolation = tmp_path / "isolation"
    outside = tmp_path / "outside"
    archive, checksum, digest = make_test_resources(outside)
    completed, output = run_installer(
        isolation / "project",
        *installer_test_mode_arguments(archive, checksum, digest),
        test_mode=True,
        isolation_root=isolation,
    )
    assert completed.returncode != 0
    assert "path must remain inside" in output


def test_test_mode_rejects_reparse_point_isolation_root(tmp_path: Path) -> None:
    actual_isolation = tmp_path / "actual-isolation"
    actual_isolation.mkdir()
    (actual_isolation / TEST_SENTINEL).write_text("sentinel", encoding="utf-8")
    archive, checksum, digest = make_test_resources(actual_isolation)
    isolation_link = tmp_path / "isolation-junction"
    real_before = real_install_hashes()
    with directory_junction(isolation_link, actual_isolation):
        completed, output = run_installer(
            isolation_link / "project",
            *installer_test_mode_arguments(archive, checksum, digest),
            test_mode=True,
            isolation_root=isolation_link,
            prepare_isolation=False,
        )
        assert completed.returncode != 0
        assert "TestIsolationRoot failed validation" in output
        assert "reparse point" in output.lower()
        assert not (actual_isolation / "project").exists()
    assert real_install_hashes() == real_before


def test_test_mode_rejects_project_root_junction_to_real_project(
    tmp_path: Path,
) -> None:
    isolation = tmp_path / "isolation"
    archive, checksum, digest = make_test_resources(isolation)
    project_link = isolation / "project"
    real_before = real_install_hashes()
    with directory_junction(project_link, PROJECT_ROOT):
        completed, output = run_installer(
            project_link,
            *installer_test_mode_arguments(archive, checksum, digest),
            test_mode=True,
            isolation_root=isolation,
        )
        assert completed.returncode != 0
        assert "ProjectRoot failed validation" in output
        assert "reparse point" in output.lower()
    assert real_install_hashes() == real_before


def test_test_mode_rejects_resource_junction_to_outside(tmp_path: Path) -> None:
    isolation = tmp_path / "isolation"
    isolation.mkdir()
    outside = tmp_path / "outside-resources"
    archive, checksum, digest = make_test_resources(outside)
    resource_link = isolation / "resources"
    real_before = real_install_hashes()
    with directory_junction(resource_link, outside):
        completed, output = run_installer(
            isolation / "project",
            *installer_test_mode_arguments(
                resource_link / archive.name, resource_link / checksum.name, digest
            ),
            test_mode=True,
            isolation_root=isolation,
        )
        assert completed.returncode != 0
        assert "TestArchivePath failed validation" in output
        assert "reparse point" in output.lower()
        assert not (isolation / "project" / "runtime").exists()
    assert real_install_hashes() == real_before


def test_test_mode_rejects_target_junction_to_real_install(tmp_path: Path) -> None:
    isolation = tmp_path / "isolation"
    archive, checksum, digest = make_test_resources(isolation)
    project = isolation / "project"
    target_link = project / "tools" / "ffmpeg"
    real_before = real_install_hashes()
    with directory_junction(target_link, REAL_INSTALL_ROOT):
        completed, output = run_installer(
            project,
            *installer_test_mode_arguments(archive, checksum, digest),
            test_mode=True,
            isolation_root=isolation,
        )
        assert completed.returncode != 0
        assert "test install target failed validation" in output
        assert "reparse point" in output.lower()
        assert not (project / "runtime" / "temp" / "ffmpeg-download").exists()
    assert real_install_hashes() == real_before


def test_test_mode_rejects_temporary_directory_junction(tmp_path: Path) -> None:
    isolation = tmp_path / "isolation"
    archive, checksum, digest = make_test_resources(isolation)
    project = isolation / "project"
    outside_temp = tmp_path / "outside-temp"
    outside_temp.mkdir()
    temp_link = project / "runtime" / "temp" / "ffmpeg-download"
    real_before = real_install_hashes()
    with directory_junction(temp_link, outside_temp):
        completed, output = run_installer(
            project,
            *installer_test_mode_arguments(archive, checksum, digest),
            test_mode=True,
            isolation_root=isolation,
        )
        assert completed.returncode != 0
        assert "test temporary download directory failed validation" in output
        assert "reparse point" in output.lower()
        assert list(outside_temp.iterdir()) == []
    assert real_install_hashes() == real_before


def test_test_mode_rejects_archive_and_checksum_file_symlinks(
    tmp_path: Path,
) -> None:
    isolation = tmp_path / "isolation"
    isolation.mkdir()
    outside = tmp_path / "outside-files"
    archive, checksum, digest = make_test_resources(outside)
    archive_link = isolation / "archive-link.7z"
    checksum_link = isolation / "checksum-link.sha256"
    created_links: list[Path] = []
    real_before = real_install_hashes()
    try:
        try:
            archive_link.symlink_to(archive)
            created_links.append(archive_link)
            checksum_link.symlink_to(checksum)
            created_links.append(checksum_link)
        except OSError as error:
            pytest.skip(f"Windows file symlink creation is not permitted: {error}")

        completed, output = run_installer(
            isolation / "archive-link-project",
            *installer_test_mode_arguments(archive_link, checksum_link, digest),
            test_mode=True,
            isolation_root=isolation,
        )
        assert completed.returncode != 0
        assert "TestArchivePath failed validation" in output
        assert "reparse point" in output.lower()

        local_archive = isolation / "local-archive.7z"
        local_archive.write_bytes(archive.read_bytes())
        completed, output = run_installer(
            isolation / "checksum-link-project",
            *installer_test_mode_arguments(local_archive, checksum_link, digest),
            test_mode=True,
            isolation_root=isolation,
        )
        assert completed.returncode != 0
        assert "TestPublisherChecksumPath failed validation" in output
        assert "reparse point" in output.lower()
    finally:
        for link in reversed(created_links):
            if link.is_symlink():
                link.unlink()
    assert real_install_hashes() == real_before


def test_test_mode_cannot_target_real_installation(tmp_path: Path) -> None:
    archive, checksum, digest = make_test_resources(tmp_path)
    marker_before = hashlib.sha256(REAL_INSTALL_MARKER.read_bytes()).hexdigest()
    completed, output = run_installer(
        PROJECT_ROOT,
        *installer_test_mode_arguments(archive, checksum, digest),
        test_mode=True,
        isolation_root=tmp_path,
    )
    assert completed.returncode != 0
    assert "ProjectRoot failed validation" in output
    assert "path must remain inside" in output
    assert hashlib.sha256(REAL_INSTALL_MARKER.read_bytes()).hexdigest() == marker_before


def test_test_mode_summary_truthfully_identifies_local_fixture(tmp_path: Path) -> None:
    assert tmp_path.drive.upper() == "D:"
    archive, checksum, digest = make_test_resources(tmp_path)
    project = tmp_path / "project"
    install = project / "tools" / "ffmpeg"
    link_project_binaries(install / "bin")
    write_known_marker(
        install,
        provider="test_fixture",
        source=str(archive.resolve()),
        checksum_source=str(checksum.resolve()),
        archive_name=archive.name,
        archive_hash=digest,
        legacy=False,
    )
    real_marker_before = hashlib.sha256(REAL_INSTALL_MARKER.read_bytes()).hexdigest()
    completed, output = run_installer(
        project,
        *installer_test_mode_arguments(archive.as_uri(), checksum.as_uri(), digest),
        test_mode=True,
        isolation_root=tmp_path,
    )
    assert completed.returncode == 0, output
    summary = summaries(output)[-1]
    assert summary["status"] == "already_installed"
    assert summary["mode"] == "test"
    assert summary["selected_provider"] == "test_fixture"
    assert summary["source_type"] == "local_test_resource"
    assert summary["selected_provider"] != "gyan.dev"
    assert summary["direct_download_url"] == str(archive.resolve())
    assert summary["publisher_checksum_url"] == str(checksum.resolve())
    assert summary["archive_downloaded_this_run"] is False
    assert summary["archive_hash_recomputed_this_run"] is False
    assert hashlib.sha256(REAL_INSTALL_MARKER.read_bytes()).hexdigest() == real_marker_before


def test_legacy_known_production_install_is_safely_skipped_offline(tmp_path: Path) -> None:
    project = tmp_path / "project"
    install = project / "tools" / "ffmpeg"
    link_project_binaries(install / "bin")
    write_known_marker(
        install,
        provider="gyan.dev",
        source=DIRECT_URL,
        checksum_source=CHECKSUM_URL,
        archive_name=ARCHIVE_NAME,
        archive_hash=PINNED_SHA256,
        legacy=True,
    )
    completed, output = run_installer(project)
    assert completed.returncode == 0, output
    summary = summaries(output)[-1]
    assert summary["status"] == "already_installed"
    assert summary["mode"] == "production"
    assert summary["source_type"] == "remote_https"
    assert summary["selected_provider"] == "gyan.dev"
    assert summary["direct_download_url"] == DIRECT_URL
    assert summary["publisher_checksum_url"] == CHECKSUM_URL
    assert summary["archive_file_name"] == ARCHIVE_NAME
    assert summary["fixed_audited_sha256"] == PINNED_SHA256
    assert summary["publisher_hash_verified_at_install"] is True
    assert summary["publisher_hash_checked_this_run"] is False
    assert summary["publisher_hash_match_this_run"] is None
    assert summary["archive_hash_recomputed_this_run"] is False
    assert summary["archive_downloaded_this_run"] is False
    assert summary["publisher_sha256"] is None
    assert summary["installed_archive_sha256"] == PINNED_SHA256
    assert not (project / "runtime" / "temp" / "ffmpeg-download").exists()


def test_invalid_publisher_hash_fails_without_installing(tmp_path: Path) -> None:
    archive, checksum, digest = make_test_resources(tmp_path, checksum_text="not-a-sha256")
    completed, output = run_installer(
        tmp_path / "project",
        *installer_test_mode_arguments(archive, checksum, digest),
        test_mode=True,
        isolation_root=tmp_path,
    )
    assert completed.returncode != 0
    assert "does not contain a SHA-256" in output
    summary = summaries(output)[-1]
    assert summary["publisher_hash_checked_this_run"] is True
    assert summary["publisher_hash_match_this_run"] is None
    assert not (tmp_path / "project" / "tools" / "ffmpeg").exists()


def test_pinned_hash_mismatch_with_publisher_fails_before_archive_copy(tmp_path: Path) -> None:
    archive, checksum, _ = make_test_resources(tmp_path, checksum_text="1" * 64)
    completed, output = run_installer(
        tmp_path / "project",
        *installer_test_mode_arguments(archive, checksum, "2" * 64),
        test_mode=True,
        isolation_root=tmp_path,
    )
    assert completed.returncode != 0
    assert "Pinned SHA-256 does not match" in output
    summary = summaries(output)[-1]
    assert summary["publisher_hash_checked_this_run"] is True
    assert summary["publisher_hash_match_this_run"] is False
    assert summary["archive_downloaded_this_run"] is False
    assert summary["archive_hash_recomputed_this_run"] is False
    assert not (tmp_path / "project" / "tools" / "ffmpeg").exists()


def test_empty_archive_never_forms_stable_install(tmp_path: Path) -> None:
    archive, checksum, digest = make_test_resources(tmp_path, content=b"")
    project = tmp_path / "project"
    completed, output = run_installer(
        project,
        *installer_test_mode_arguments(archive, checksum, digest),
        test_mode=True,
        isolation_root=tmp_path,
    )
    assert completed.returncode != 0
    assert "archive is empty" in output
    assert not (project / "tools" / "ffmpeg").exists()
    assert not (project / "runtime" / "temp" / "ffmpeg-download" / archive.name).exists()


def test_incomplete_archive_never_forms_stable_install(tmp_path: Path) -> None:
    full_content = b"complete archive bytes expected by checksum fixture"
    expected = hashlib.sha256(full_content).hexdigest()
    archive, checksum, _ = make_test_resources(
        tmp_path, content=full_content[:12], checksum_text=expected
    )
    project = tmp_path / "project"
    completed, output = run_installer(
        project,
        *installer_test_mode_arguments(archive, checksum, expected),
        test_mode=True,
        isolation_root=tmp_path,
    )
    assert completed.returncode != 0
    assert "SHA-256 mismatch" in output
    summary = summaries(output)[-1]
    assert summary["archive_downloaded_this_run"] is False
    assert summary["archive_hash_recomputed_this_run"] is True
    assert not (project / "tools" / "ffmpeg").exists()
    download_root = project / "runtime" / "temp" / "ffmpeg-download"
    assert not list(download_root.glob("*.partial"))
    assert not (download_root / archive.name).exists()


def test_matching_hash_corrupt_archive_fails_extraction_without_publication(
    tmp_path: Path,
) -> None:
    corrupt_content = (
        b"LiveClip FIX3 deliberately corrupt 7z fixture; hash is valid for these bytes."
    )
    archive, checksum, digest = make_test_resources(
        tmp_path, content=corrupt_content
    )
    assert file_sha256(archive) == digest
    assert checksum.read_text(encoding="ascii") == digest

    project = tmp_path / "project"
    user_file = project / "用户资料" / "必须保留.txt"
    user_file.parent.mkdir(parents=True)
    user_file.write_text("不要删除", encoding="utf-8")
    real_before = real_install_hashes()

    completed, output = run_installer(
        project,
        *installer_test_mode_arguments(archive, checksum, digest),
        test_mode=True,
        isolation_root=tmp_path,
    )

    assert completed.returncode != 0
    assert "Archive extraction failed with exit code" in output
    summary = summaries(output)[-1]
    assert summary["status"] == "failed"
    assert summary["mode"] == "test"
    assert summary["publisher_hash_checked_this_run"] is True
    assert summary["publisher_hash_match_this_run"] is True
    assert summary["archive_hash_recomputed_this_run"] is True
    assert summary["installed_archive_sha256"] == digest
    assert summary["publisher_sha256"] == digest
    assert summary["archive_downloaded_this_run"] is False

    install_root = project / "tools" / "ffmpeg"
    download_root = project / "runtime" / "temp" / "ffmpeg-download"
    assert not install_root.exists()
    assert not list(project.rglob(".liveclip-ffmpeg-install.json"))
    assert user_file.read_text(encoding="utf-8") == "不要删除"
    assert archive.read_bytes() == corrupt_content
    assert not list(download_root.glob("*.partial"))
    assert not (download_root / archive.name).exists()
    assert not list(download_root.glob("extract-*"))
    assert real_install_hashes() == real_before


def test_unknown_existing_install_directory_is_not_overwritten(tmp_path: Path) -> None:
    archive, checksum, digest = make_test_resources(tmp_path)
    project = tmp_path / "project"
    install = project / "tools" / "ffmpeg"
    install.mkdir(parents=True)
    user_file = install / "用户文件.txt"
    user_file.write_text("必须保留", encoding="utf-8")
    completed, output = run_installer(
        project,
        *installer_test_mode_arguments(archive, checksum, digest),
        test_mode=True,
        isolation_root=tmp_path,
    )
    assert completed.returncode != 0
    assert "Refusing to overwrite" in output
    assert user_file.read_text(encoding="utf-8") == "必须保留"
    summary = summaries(output)[-1]
    assert summary["status"] == "failed"
    assert summary["mode"] == "test"
    assert summary["selected_provider"] == "test_fixture"
    assert summary["publisher_hash_checked_this_run"] is False


def test_installer_never_modifies_path(tmp_path: Path) -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8-sig")
    assert "SetEnvironmentVariable" not in script
    assert "$ENV:PATH" not in script.upper()
    path_before = os.environ.get("PATH")
    project = tmp_path / "project"
    install = project / "tools" / "ffmpeg"
    link_project_binaries(install / "bin")
    write_known_marker(
        install,
        provider="gyan.dev",
        source=DIRECT_URL,
        checksum_source=CHECKSUM_URL,
        archive_name=ARCHIVE_NAME,
        archive_hash=PINNED_SHA256,
        legacy=True,
    )
    completed, output = run_installer(project)
    assert completed.returncode == 0, output
    assert os.environ.get("PATH") == path_before
    assert summaries(output)[-1]["system_path_modified"] is False
