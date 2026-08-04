"""Token-protected localhost review service using only the Python standard library."""

from __future__ import annotations

import hmac
import json
import re
import secrets
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, quote, unquote, urlsplit

from liveclip.media import FFmpegPaths

from .exporter import ExportResult, export_review_clip
from .schema import (
    ReviewConflictError,
    ReviewError,
    ReviewInputs,
    bind_review_inputs,
    build_session_payload,
)


STATIC_ROOT = Path(__file__).with_name("static")
STATIC_FILES = {
    "/static/review.css": ("review.css", "text/css; charset=utf-8"),
    "/static/review.js": ("review.js", "text/javascript; charset=utf-8"),
}
RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)")
MAX_REQUEST_BYTES = 16_384


Exporter = Callable[..., ExportResult]


class ReviewApplication:
    def __init__(
        self,
        inputs: ReviewInputs,
        token: str,
        *,
        exporter: Exporter,
        paths: FFmpegPaths | None,
        heartbeat_timeout_seconds: float,
    ) -> None:
        self.inputs = inputs
        self.token = token
        self.exporter = exporter
        self.paths = paths
        self.export_lock = threading.Lock()
        self.exported_candidate_id: str | None = None
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self._heartbeat_lock = threading.Lock()
        self._last_heartbeat = time.monotonic()

    def touch_heartbeat(self) -> None:
        with self._heartbeat_lock:
            self._last_heartbeat = time.monotonic()

    def heartbeat_age(self) -> float:
        with self._heartbeat_lock:
            return time.monotonic() - self._last_heartbeat


class LocalReviewServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True

    def __init__(self, app: ReviewApplication, *, heartbeat_check_seconds: float) -> None:
        self.app = app
        self.heartbeat_check_seconds = heartbeat_check_seconds
        self._monitor_stop = threading.Event()
        super().__init__(("127.0.0.1", 0), ReviewRequestHandler)

    def serve_forever(self, poll_interval: float = 0.5) -> None:
        self.app.touch_heartbeat()
        monitor = threading.Thread(target=self._monitor_heartbeat, daemon=True)
        monitor.start()
        try:
            super().serve_forever(poll_interval=poll_interval)
        finally:
            self._monitor_stop.set()
            monitor.join(timeout=max(1.0, self.heartbeat_check_seconds * 2))

    def _monitor_heartbeat(self) -> None:
        while not self._monitor_stop.wait(self.heartbeat_check_seconds):
            if self.app.heartbeat_age() >= self.app.heartbeat_timeout_seconds:
                self.shutdown()
                return

    def handle_error(self, request: Any, client_address: Any) -> None:
        # Browser disconnects are expected during seeks and hard tab closes.
        # Do not leak local paths or tracebacks through the standard server logger.
        return


class ReviewRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    @property
    def app(self) -> ReviewApplication:
        return self.server.app  # type: ignore[attr-defined,no-any-return]

    def log_message(self, format: str, *args: object) -> None:
        # Default logging includes the request URL and therefore the access token.
        return

    def _parts(self) -> tuple[str, dict[str, list[str]]] | None:
        parsed = urlsplit(self.path)
        decoded_path = unquote(parsed.path)
        normalized = decoded_path.replace("\\", "/")
        if any(part == ".." for part in normalized.split("/")):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "拒绝路径穿越请求。"})
            return None
        try:
            query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=False)
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "请求参数无效。"})
            return None
        return decoded_path, query

    def _authorized(self, query: dict[str, list[str]]) -> bool:
        if set(query) != {"token"} or len(query.get("token", [])) != 1:
            return False
        supplied = query["token"][0]
        return hmac.compare_digest(
            supplied.encode("utf-8"),
            self.app.token.encode("utf-8"),
        )

    def _require_token(self, query: dict[str, list[str]]) -> bool:
        if self.client_address[0] != "127.0.0.1" or not self._authorized(query):
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "访问被拒绝。"})
            return False
        return True

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "media-src 'self'; connect-src 'self'; img-src 'self' data:; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        ))
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")

    def _send_bytes(
        self,
        status: HTTPStatus,
        payload: bytes,
        content_type: str,
        *,
        extra_headers: dict[str, str] | None = None,
        head_only: bool = False,
    ) -> None:
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if not head_only:
            self.wfile.write(payload)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self._send_bytes(status, data, "application/json; charset=utf-8")

    def _send_static(self, path: str, *, head_only: bool) -> None:
        file_name, content_type = STATIC_FILES[path]
        try:
            payload = (STATIC_ROOT / file_name).read_bytes()
        except OSError:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "页面资源不可用。"})
            return
        self._send_bytes(
            HTTPStatus.OK,
            payload,
            content_type,
            head_only=head_only,
        )

    def _send_page(self, *, head_only: bool) -> None:
        try:
            payload = (STATIC_ROOT / "review.html").read_bytes()
        except OSError:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "审核页面不可用。"})
            return
        self._send_bytes(
            HTTPStatus.OK,
            payload,
            "text/html; charset=utf-8",
            head_only=head_only,
        )

    def _range(self, size: int) -> tuple[int, int] | None | bool:
        value = self.headers.get("Range")
        if value is None:
            return None
        match = RANGE_PATTERN.fullmatch(value.strip())
        if match is None or size <= 0:
            return False
        start_text, end_text = match.groups()
        if not start_text and not end_text:
            return False
        try:
            if not start_text:
                suffix = int(end_text)
                if suffix <= 0:
                    return False
                start = max(0, size - suffix)
                end = size - 1
            else:
                start = int(start_text)
                end = int(end_text) if end_text else size - 1
                if start >= size or end < start:
                    return False
                end = min(end, size - 1)
        except ValueError:
            return False
        return start, end

    def _send_media(self, *, head_only: bool) -> None:
        media = self.app.inputs.video_path
        try:
            size = media.stat().st_size
        except OSError:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "原视频暂时不可读。"})
            return
        requested_range = self._range(size)
        if requested_range is False:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self._security_headers()
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if requested_range is None:
            start, end = 0, size - 1
            status = HTTPStatus.OK
            extra = {"Accept-Ranges": "bytes"}
        else:
            start, end = requested_range
            status = HTTPStatus.PARTIAL_CONTENT
            extra = {
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {start}-{end}/{size}",
            }
        length = max(0, end - start + 1)
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(length))
        for name, value in extra.items():
            self.send_header(name, value)
        self.end_headers()
        if head_only:
            return
        try:
            with media.open("rb") as handle:
                handle.seek(start)
                remaining = length
                while remaining:
                    block = handle.read(min(1024 * 1024, remaining))
                    if not block:
                        break
                    self.wfile.write(block)
                    remaining -= len(block)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _read_json(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "请求正文大小无效。"})
            return None
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "请求正文不是合法 JSON。"})
            return None
        if not isinstance(payload, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "请求正文必须是 JSON 对象。"})
            return None
        return payload

    def do_HEAD(self) -> None:
        self._handle_get(head_only=True)

    def do_GET(self) -> None:
        self._handle_get(head_only=False)

    def _handle_get(self, *, head_only: bool) -> None:
        parts = self._parts()
        if parts is None:
            return
        path, query = parts
        if path in STATIC_FILES:
            if query:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "页面资源参数无效。"})
                return
            self._send_static(path, head_only=head_only)
            return
        if not self._require_token(query):
            return
        if path == "/":
            self._send_page(head_only=head_only)
        elif path == "/api/session":
            self._send_json(
                HTTPStatus.OK,
                build_session_payload(
                    self.app.inputs,
                    exported_candidate_id=self.app.exported_candidate_id,
                ),
            )
        elif path == "/media":
            self._send_media(head_only=head_only)
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "接口不存在。"})

    def do_POST(self) -> None:
        parts = self._parts()
        if parts is None:
            return
        path, query = parts
        if not self._require_token(query):
            return
        if path == "/api/shutdown":
            self._send_json(HTTPStatus.ACCEPTED, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if path == "/api/heartbeat":
            self.app.touch_heartbeat()
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        if path != "/api/export":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "接口不存在。"})
            return
        payload = self._read_json()
        if payload is None:
            return
        if set(payload) != {
            "candidate_id",
            "start_ms",
            "end_ms",
            "confirmed",
        }:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "导出请求字段无效。"})
            return
        if self.app.exported_candidate_id is not None:
            self._send_json(HTTPStatus.CONFLICT, {"error": "本次审核已经完成一次导出。"})
            return
        if not self.app.export_lock.acquire(blocking=False):
            self._send_json(HTTPStatus.CONFLICT, {"error": "导出正在进行，请勿重复点击。"})
            return
        try:
            result = self.app.exporter(
                self.app.inputs,
                candidate_id=payload["candidate_id"],
                start_ms=payload["start_ms"],
                end_ms=payload["end_ms"],
                confirmed=payload["confirmed"],
                paths=self.app.paths,
            )
            self.app.exported_candidate_id = str(payload["candidate_id"])
            message = "导出完成。"
            if result.subtitle_count == 0:
                message += "该片段范围内没有字幕。"
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "message": message,
                    "candidate_id": self.app.exported_candidate_id,
                    "video_file_name": result.video_path.name,
                    "subtitle_file_name": result.subtitle_path.name,
                    "subtitle_count": result.subtitle_count,
                    "duration_ms": result.duration_ms,
                },
            )
        except ReviewConflictError as exc:
            self._send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
        except ReviewError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "导出发生未预期错误，未写入完成审核结果。"},
            )
        finally:
            self.app.export_lock.release()


def create_review_server(
    inputs: ReviewInputs,
    *,
    token: str | None = None,
    exporter: Exporter = export_review_clip,
    paths: FFmpegPaths | None = None,
    heartbeat_timeout_seconds: float = 10.0,
    heartbeat_check_seconds: float = 1.0,
) -> LocalReviewServer:
    runtime_token = token or secrets.token_urlsafe(32)
    if len(runtime_token) < 16:
        raise ReviewError("运行时访问 token 长度不足。")
    if heartbeat_timeout_seconds <= 0 or heartbeat_check_seconds <= 0:
        raise ReviewError("页面心跳超时参数必须大于 0。")
    return LocalReviewServer(
        ReviewApplication(
            inputs,
            runtime_token,
            exporter=exporter,
            paths=paths,
            heartbeat_timeout_seconds=heartbeat_timeout_seconds,
        ),
        heartbeat_check_seconds=heartbeat_check_seconds,
    )


def launch_review(
    video: str | Path,
    timeline: str | Path,
    analysis: str | Path,
    *,
    output_dir: str | Path | None = None,
) -> None:
    inputs = bind_review_inputs(
        video,
        timeline,
        analysis,
        output_dir=output_dir,
    )
    server = create_review_server(inputs)
    host, port = server.server_address
    url = f"http://{host}:{port}/?token={quote(server.app.token)}"
    serve_thread = threading.Thread(target=server.serve_forever, daemon=False)
    serve_thread.start()
    try:
        try:
            opened = webbrowser.open(url, new=1)
        except Exception:
            opened = False
        print("审核页面已启动，仅监听 127.0.0.1。关闭页面或按 Ctrl+C 停止。")
        if not opened:
            print(f"浏览器未自动打开，请在本机访问：{url}")
        while serve_thread.is_alive():
            serve_thread.join(timeout=0.5)
    finally:
        if serve_thread.is_alive():
            server.shutdown()
            serve_thread.join(timeout=5)
        server.server_close()
