from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from solutiongraph.integrations.ollama import OllamaAdapter, OllamaConfig, OllamaError
from solutiongraph.proposal_space import PROPOSAL_RESPONSE_SCHEMA
from solutiongraph.proposal_swarm import LLMRequest, ModelEndpoint


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Mapping[str, Any] | None, float]] = []

    def request(
        self, method: str, url: str, payload: Mapping[str, Any] | None,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        self.calls.append((method, url, payload, timeout_seconds))
        if url.endswith("/api/tags"):
            return {
                "models": [{
                    "name": "qwen-test:latest",
                    "size": 123,
                    "digest": "abc",
                    "details": {
                        "family": "qwen",
                        "parameter_size": "7B",
                        "quantization_level": "Q4_K_M",
                    },
                }]
            }
        return {
            "model": "qwen-test:latest",
            "message": {"role": "assistant", "content": '{"kind":"proposal.stop"}'},
            "done": True,
            "done_reason": "stop",
            "total_duration": 2_000_000_000,
            "prompt_eval_count": 21,
            "eval_count": 7,
        }


class ErrorTransport:
    def request(
        self, method: str, url: str, payload: Mapping[str, Any] | None,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        raise OllamaError("daemon unavailable")


def _request() -> LLMRequest:
    endpoint = ModelEndpoint(
        "model-endpoint.ollama", "adapter.ollama", "qwen-test:latest",
        temperature=0.0, seed=42, max_tokens=777,
    )
    return LLMRequest(
        "llm.request.ollama-fixture",
        endpoint,
        "system prompt",
        "user prompt",
        PROPOSAL_RESPONSE_SCHEMA,
    )


def test_ollama_chat_uses_structured_schema_and_bounded_options() -> None:
    transport = FakeTransport()
    adapter = OllamaAdapter(
        OllamaConfig(base_url="http://127.0.0.1:11434", keep_alive="10m"),
        transport,
    )
    response = adapter.complete(_request())
    assert response.successful
    assert response.raw_text == '{"kind":"proposal.stop"}'
    assert response.duration_seconds == 2.0
    assert response.prompt_tokens == 21
    assert response.completion_tokens == 7
    method, url, payload, timeout = transport.calls[0]
    assert method == "POST"
    assert url == "http://127.0.0.1:11434/api/chat"
    assert payload is not None
    assert payload["stream"] is False
    assert payload["format"] == PROPOSAL_RESPONSE_SCHEMA
    assert payload["options"] == {
        "temperature": 0.0,
        "num_predict": 777,
        "seed": 42,
    }
    assert payload["keep_alive"] == "10m"
    assert timeout == 300.0


def test_ollama_model_discovery_is_typed() -> None:
    transport = FakeTransport()
    models = OllamaAdapter(OllamaConfig(), transport).list_models()
    assert len(models) == 1
    assert models[0].name == "qwen-test:latest"
    assert models[0].family == "qwen"
    assert models[0].parameter_size == "7B"


def test_ollama_transport_failure_becomes_a_response_not_graph_authority() -> None:
    response = OllamaAdapter(OllamaConfig(), ErrorTransport()).complete(_request())
    assert not response.successful
    assert "daemon unavailable" in response.error
