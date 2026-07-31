"""One user-configured OpenAI-compatible Chat Completions client."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlsplit

from .prompt import build_messages
from .schema import AnalysisError


ENV_ENDPOINT = "LIVECLIP_LLM_ENDPOINT"
ENV_API_KEY = "LIVECLIP_LLM_API_KEY"
ENV_MODEL = "LIVECLIP_LLM_MODEL"
MAX_RESPONSE_BYTES = 1_000_000


class AnalysisClientError(AnalysisError):
    """Raised for a safe, user-facing model API failure."""


@dataclass(frozen=True)
class LLMConfig:
    endpoint: str
    api_key: str
    model: str
    endpoint_host: str


def load_config(environ: Mapping[str, str] | None = None) -> LLMConfig:
    values = os.environ if environ is None else environ
    missing = [
        name
        for name in (ENV_ENDPOINT, ENV_API_KEY, ENV_MODEL)
        if not str(values.get(name, "")).strip()
    ]
    if missing:
        raise AnalysisClientError("缺少环境变量: " + ", ".join(missing))

    endpoint = str(values[ENV_ENDPOINT]).strip()
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.netloc
        or not parsed.path
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise AnalysisClientError(
            f"{ENV_ENDPOINT} 必须是完整的 HTTPS Chat Completions 地址"
        )
    return LLMConfig(
        endpoint=endpoint,
        api_key=str(values[ENV_API_KEY]),
        model=str(values[ENV_MODEL]).strip(),
        endpoint_host=parsed.netloc.lower(),
    )


class OpenAICompatibleClient:
    """Minimal non-streaming client without a vendor SDK."""

    def __init__(self, config: LLMConfig, *, timeout_seconds: float = 60.0) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.request_count = 0

    def analyze_window(
        self,
        segments: list[dict[str, Any]],
        *,
        repair_error: str | None = None,
        previous_response: str | None = None,
    ) -> str:
        messages = build_messages(
            segments,
            repair_error=repair_error,
            previous_response=previous_response,
        )
        payload = json.dumps(
            {
                "model": self.config.model,
                "messages": messages,
                "stream": False,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            self.config.endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        response_bytes = self._send_with_retry(request)
        try:
            response = json.loads(response_bytes.decode("utf-8"))
            content = response["choices"][0]["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError):
            raise AnalysisClientError("模型 API 返回了无效的 Chat Completions 响应") from None
        if not isinstance(content, str) or not content.strip():
            raise AnalysisClientError("模型 API 返回了空内容")
        return content

    def _send_with_retry(self, request: urllib.request.Request) -> bytes:
        last_error: BaseException | None = None
        for attempt in range(2):
            self.request_count += 1
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout_seconds,
                ) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise AnalysisClientError("模型 API 响应过大")
                    return body
            except urllib.error.HTTPError as exc:
                last_error = exc
                retryable = exc.code == 429 or 500 <= exc.code <= 599
                if retryable and attempt == 0:
                    continue
                if exc.code in {401, 403}:
                    raise AnalysisClientError(f"模型 API 鉴权失败 (HTTP {exc.code})") from None
                raise AnalysisClientError(f"模型 API 请求失败 (HTTP {exc.code})") from None
            except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
                last_error = exc
                if attempt == 0:
                    continue
                raise AnalysisClientError("模型 API 请求超时或网络不可用") from None
        raise AnalysisClientError(f"模型 API 请求失败: {type(last_error).__name__}")
