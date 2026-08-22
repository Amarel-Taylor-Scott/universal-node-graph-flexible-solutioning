"""Dependency-free Ollama adapter for proposal swarms.

The adapter uses Ollama's local JSON API and accepts an injectable transport so
unit tests and deterministic replays do not require a running daemon.  It is a
model invocation adapter only; it has no graph, compiler, execution, or promotion
authority.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Protocol
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from solutiongraph.model import ID_RE
from solutiongraph.proposal_swarm import LLMRequest, LLMResponse, LanguageModelAdapter

OLLAMA_ADAPTER_MODEL_VERSION = "0.1"


class OllamaError(RuntimeError):
    pass


class JsonTransport(Protocol):
    def request(
        self, method: str, url: str, payload: Mapping[str, Any] | None,
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class UrlLibJsonTransport:
    """Small standard-library JSON transport with bounded reads."""

    maximum_response_bytes: int = 64 * 1024 * 1024

    def request(
        self, method: str, url: str, payload: Mapping[str, Any] | None,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310
                data = response.read(self.maximum_response_bytes + 1)
        except HTTPError as exc:
            detail = exc.read(8192).decode("utf-8", errors="replace")
            raise OllamaError(f"Ollama HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise OllamaError(f"Ollama connection failed: {exc.reason}") from exc
        if len(data) > self.maximum_response_bytes:
            raise OllamaError("Ollama response exceeded maximum_response_bytes")
        try:
            value = json.loads(data)
        except json.JSONDecodeError as exc:
            raise OllamaError(f"Ollama returned invalid JSON: {exc}") from exc
        if not isinstance(value, Mapping):
            raise OllamaError("Ollama response must be a JSON object")
        return value


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 300.0
    keep_alive: str = "5m"
    adapter_id: str = "adapter.ollama"

    def validate(self) -> list[str]:
        problems: list[str] = []
        parsed = urlparse(self.base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            problems.append("Ollama base_url must be an absolute HTTP(S) URL")
        if self.timeout_seconds <= 0:
            problems.append("Ollama timeout_seconds must be positive")
        if not ID_RE.fullmatch(self.adapter_id):
            problems.append("Ollama adapter_id must be namespaced")
        return problems


@dataclass(frozen=True)
class OllamaModelInfo:
    name: str
    modified_at: str = ""
    size: int = 0
    digest: str = ""
    family: str = ""
    parameter_size: str = ""
    quantization_level: str = ""

    @classmethod
    def from_api(cls, value: Mapping[str, Any]) -> OllamaModelInfo:
        details = value.get("details", {})
        if not isinstance(details, Mapping):
            details = {}
        return cls(
            name=str(value.get("name", value.get("model", ""))),
            modified_at=str(value.get("modified_at", "")),
            size=int(value.get("size", 0) or 0),
            digest=str(value.get("digest", "")),
            family=str(details.get("family", "")),
            parameter_size=str(details.get("parameter_size", "")),
            quantization_level=str(details.get("quantization_level", "")),
        )


@dataclass
class OllamaAdapter(LanguageModelAdapter):
    config: OllamaConfig = field(default_factory=OllamaConfig)
    transport: JsonTransport = field(default_factory=UrlLibJsonTransport)

    def __post_init__(self) -> None:
        problems = self.config.validate()
        if problems:
            raise ValueError("invalid Ollama config: " + "; ".join(problems))

    @property
    def adapter_id(self) -> str:
        return self.config.adapter_id

    def _url(self, path: str) -> str:
        return urljoin(self.config.base_url.rstrip("/") + "/", path.lstrip("/"))

    def complete(self, request: LLMRequest) -> LLMResponse:
        options: dict[str, Any] = {
            "temperature": request.endpoint.temperature,
            "num_predict": request.endpoint.max_tokens,
        }
        seed = request.endpoint.seed
        if seed is not None:
            options["seed"] = seed
        messages = []
        if request.system_prompt.strip():
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_prompt})
        payload: dict[str, Any] = {
            "model": request.endpoint.model,
            "messages": messages,
            "stream": False,
            "format": dict(request.response_schema),
            "options": options,
        }
        if self.config.keep_alive:
            payload["keep_alive"] = self.config.keep_alive
        try:
            response = self.transport.request(
                "POST", self._url("api/chat"), payload, self.config.timeout_seconds
            )
        except OllamaError as exc:
            return LLMResponse(
                request.id, self.adapter_id, request.endpoint.model, "", error=str(exc)
            )
        message = response.get("message", {})
        if not isinstance(message, Mapping):
            return LLMResponse(
                request.id, self.adapter_id, request.endpoint.model, "",
                error="Ollama response.message must be an object",
            )
        content = message.get("content", "")
        if not isinstance(content, str):
            return LLMResponse(
                request.id, self.adapter_id, request.endpoint.model, "",
                error="Ollama response.message.content must be text",
            )
        total_duration = response.get("total_duration", 0)
        duration_seconds = (
            float(total_duration) / 1_000_000_000
            if isinstance(total_duration, (int, float)) and total_duration >= 0
            else 0.0
        )
        metadata = tuple(
            (key, response[key])
            for key in ("done", "done_reason", "load_duration", "eval_duration")
            if key in response
        )
        return LLMResponse(
            request_id=request.id,
            adapter_id=self.adapter_id,
            model=str(response.get("model", request.endpoint.model)),
            raw_text=content,
            duration_seconds=duration_seconds,
            prompt_tokens=_optional_int(response.get("prompt_eval_count")),
            completion_tokens=_optional_int(response.get("eval_count")),
            provider_metadata=metadata,
        )

    def list_models(self) -> tuple[OllamaModelInfo, ...]:
        response = self.transport.request(
            "GET", self._url("api/tags"), None, self.config.timeout_seconds
        )
        models = response.get("models", ())
        if not isinstance(models, list):
            raise OllamaError("Ollama tags response.models must be a list")
        result = tuple(OllamaModelInfo.from_api(item) for item in models if isinstance(item, Mapping))
        if any(not item.name for item in result):
            raise OllamaError("Ollama model records must include a name")
        return result


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if value >= 0 else None


__all__ = [
    "OLLAMA_ADAPTER_MODEL_VERSION", "JsonTransport", "OllamaAdapter", "OllamaConfig",
    "OllamaError", "OllamaModelInfo", "UrlLibJsonTransport",
]
