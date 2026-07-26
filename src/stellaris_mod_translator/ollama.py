"""Strict loopback-only Ollama client using only the Python standard library."""

from __future__ import annotations

import json
from typing import Any
import urllib.error
import urllib.request


ENDPOINT = "http://127.0.0.1:11434"


class OllamaError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise OllamaError("redirect rejected")


class OllamaClient:
    def __init__(self, *, timeout: float = 60.0) -> None:
        self.timeout = timeout
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()
        )

    def exact_model(self, tag: str) -> dict[str, str]:
        if not tag or tag.endswith("-cloud"):
            raise OllamaError("an explicit non-cloud model tag is required")
        payload = self._request("GET", "/api/tags")
        models = payload.get("models")
        if not isinstance(models, list):
            raise OllamaError("invalid model inventory")
        matches = [
            model
            for model in models
            if isinstance(model, dict) and model.get("name") == tag
        ]
        if len(matches) != 1:
            raise OllamaError(f"exact model tag not installed exactly once: {tag}")
        digest = matches[0].get("digest")
        if not isinstance(digest, str) or not digest:
            raise OllamaError("exact model digest is missing")
        return {"tag": tag, "digest": digest}

    def translate(self, *, tag: str, text: str) -> str:
        prompt = (
            "Translate the following Stellaris human-facing text into literary, "
            "natural Russian. Preserve exact meaning, names, numbers, negation, "
            "modality, and Stellaris tone. Every __SMT_TOKEN_NNNN__ identifier "
            "must remain byte-for-byte unchanged and in the same order. Return "
            "no explanations. Respond only with JSON matching "
            '{"translation":"string"}.\n\nTEXT:\n' + text
        )
        payload = self._request(
            "POST",
            "/api/generate",
            {
                "model": tag,
                "prompt": prompt,
                "stream": False,
                "format": {
                    "type": "object",
                    "properties": {"translation": {"type": "string"}},
                    "required": ["translation"],
                    "additionalProperties": False,
                },
            },
        )
        if payload.get("model") != tag:
            raise OllamaError("Ollama response model does not match requested tag")
        if payload.get("done") is not True:
            raise OllamaError("Ollama response is not a complete terminal result")
        response = payload.get("response")
        if not isinstance(response, str):
            raise OllamaError("Ollama response is not a string")
        try:
            structured = json.loads(response)
        except json.JSONDecodeError as exc:
            raise OllamaError("Ollama response is not JSON") from exc
        if (
            not isinstance(structured, dict)
            or set(structured) != {"translation"}
            or not isinstance(structured["translation"], str)
        ):
            raise OllamaError("invalid structured translation")
        return structured["translation"]

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = ENDPOINT + path
        encoded = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=encoded,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                if response.geturl() != url:
                    raise OllamaError("endpoint changed")
                raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise OllamaError("response too large")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise OllamaError(f"local Ollama request failed: {exc}") from exc
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaError("invalid Ollama JSON") from exc
        if not isinstance(payload, dict):
            raise OllamaError("invalid Ollama payload")
        return payload
