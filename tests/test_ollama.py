from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

import stellaris_mod_translator.ollama as ollama
from stellaris_mod_translator.engine import SafetyError, translate_mod
from stellaris_mod_translator.ollama import (
    OllamaClient,
    OllamaError,
    OllamaSystemError,
)


_ABSENT = object()


class Handler(BaseHTTPRequestHandler):
    generate_response = {"translation": "Привет __SMT_TOKEN_0000__"}
    generate_raw_response: object = _ABSENT
    generate_thinking: object = _ABSENT
    generate_calls = 0
    generate_model = "synthetic:1"
    generate_done: object = True
    generate_done_reason: object = _ABSENT
    inventory_calls = 0
    inventory_digests = ["sha256:synthetic"]

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        assert self.path == "/api/tags"
        index = min(
            type(self).inventory_calls, len(type(self).inventory_digests) - 1
        )
        digest = type(self).inventory_digests[index]
        type(self).inventory_calls += 1
        self._send(
            {
                "models": [
                    {"name": "synthetic:1", "digest": digest},
                    {"name": "other:1", "digest": "sha256:other"},
                ]
            }
        )

    def do_POST(self) -> None:
        assert self.path == "/api/generate"
        type(self).generate_calls += 1
        length = int(self.headers["Content-Length"])
        request = json.loads(self.rfile.read(length))
        assert request["stream"] is False
        assert request["think"] is False
        assert request["model"] == "synthetic:1"
        assert request["format"]["additionalProperties"] is False
        raw_response = type(self).generate_raw_response
        if raw_response is _ABSENT:
            raw_response = json.dumps(type(self).generate_response)
        response = {
            "model": type(self).generate_model,
            "done": type(self).generate_done,
            "response": raw_response,
        }
        if type(self).generate_thinking is not _ABSENT:
            response["thinking"] = type(self).generate_thinking
        if type(self).generate_done_reason is not _ABSENT:
            response["done_reason"] = type(self).generate_done_reason
        self._send(response)

    def _send(self, payload: object) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def fake_ollama(monkeypatch: pytest.MonkeyPatch):
    Handler.generate_calls = 0
    Handler.generate_model = "synthetic:1"
    Handler.generate_done = True
    Handler.generate_done_reason = _ABSENT
    Handler.generate_raw_response = _ABSENT
    Handler.generate_thinking = _ABSENT
    Handler.inventory_calls = 0
    Handler.inventory_digests = ["sha256:synthetic"]
    Handler.generate_response = {
        "translation": "Привет __SMT_TOKEN_0000__"
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    host, port = server.server_address
    monkeypatch.setattr(ollama, "ENDPOINT", f"http://{host}:{port}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_inventory_requires_exact_tag_and_digest(fake_ollama) -> None:
    client = OllamaClient()
    assert client.exact_model("synthetic:1") == {
        "tag": "synthetic:1",
        "digest": "sha256:synthetic",
    }
    with pytest.raises(OllamaError, match="not installed"):
        client.exact_model("synthetic")
    with pytest.raises(OllamaError, match="non-cloud"):
        client.exact_model("synthetic-cloud")


def test_inventory_rejects_duplicate_exact_tag(fake_ollama) -> None:
    original_send = Handler.do_GET

    def duplicate(self: Handler) -> None:
        assert self.path == "/api/tags"
        self._send(
            {
                "models": [
                    {"name": "synthetic:1", "digest": "sha256:first"},
                    {"name": "synthetic:1", "digest": "sha256:second"},
                ]
            }
        )

    Handler.do_GET = duplicate
    try:
        with pytest.raises(OllamaError, match="exactly once"):
            OllamaClient().exact_model("synthetic:1")
    finally:
        Handler.do_GET = original_send


def test_absent_done_reason_is_accepted(fake_ollama) -> None:
    client = OllamaClient()
    result = client.translate(
        tag="synthetic:1", text="Hello __SMT_TOKEN_0000__"
    )
    assert result == "Привет __SMT_TOKEN_0000__"
    assert Handler.generate_calls == 1


def test_stop_terminal_reason_is_accepted(fake_ollama) -> None:
    Handler.generate_done_reason = "stop"
    result = OllamaClient().translate(
        tag="synthetic:1", text="Hello __SMT_TOKEN_0000__"
    )
    assert result == "Привет __SMT_TOKEN_0000__"


@pytest.mark.parametrize(
    "done_reason",
    ["length", "unload", "future_reason", None],
)
def test_non_stop_terminal_reason_is_rejected(
    fake_ollama, done_reason: object
) -> None:
    Handler.generate_done_reason = done_reason
    with pytest.raises(OllamaError, match="terminal reason"):
        OllamaClient().translate(tag="synthetic:1", text="x")


def test_nested_or_non_string_response_is_rejected(fake_ollama) -> None:
    Handler.generate_response = {"translation": {"text": "x"}}
    with pytest.raises(OllamaError, match="structured"):
        OllamaClient().translate(tag="synthetic:1", text="x")
    Handler.generate_response = {"translation": "x"}


def test_empty_response_with_nonempty_thinking_is_english_fallback(
    fake_ollama, tmp_path
) -> None:
    Handler.generate_raw_response = ""
    Handler.generate_thinking = json.dumps(
        {"translation": "Нельзя использовать как перевод"}
    )
    source_file = (
        tmp_path / "source/localisation/english/demo_l_english.yml"
    )
    source_file.parent.mkdir(parents=True)
    source_bytes = b'l_english:\n key:0 "Original English"\n'
    source_file.write_bytes(source_bytes)
    output = tmp_path / "candidate"

    report = translate_mod(tmp_path / "source", output, "synthetic:1")

    candidate = output / "localisation/russian/demo_l_russian.yml"
    assert candidate.read_bytes() == (
        b'l_russian:\n key:0 "Original English"\n'
    )
    assert report["counts"]["translated_occurrences"] == 0
    assert report["counts"]["fallback_occurrences"] == 1
    assert source_file.read_bytes() == source_bytes


@pytest.mark.parametrize(
    ("outer_model", "done", "reason"),
    [
        ("other:1", True, "model"),
        ("synthetic:1", False, "terminal"),
        ("synthetic:1", None, "terminal"),
    ],
)
def test_wrong_model_or_incomplete_terminal_result_is_rejected(
    fake_ollama, outer_model: str, done: object, reason: str
) -> None:
    Handler.generate_model = outer_model
    Handler.generate_done = done
    with pytest.raises(OllamaError, match=reason):
        OllamaClient().translate(tag="synthetic:1", text="x")


@pytest.mark.parametrize(
    ("outer_model", "done"),
    [
        ("other:1", True),
        ("synthetic:1", False),
        ("synthetic:1", None),
    ],
)
def test_terminal_provenance_error_stops_run_without_candidate(
    fake_ollama, tmp_path, outer_model: str, done: object
) -> None:
    Handler.generate_model = outer_model
    Handler.generate_done = done
    source_file = (
        tmp_path / "source/localisation/english/demo_l_english.yml"
    )
    source_file.parent.mkdir(parents=True)
    source_bytes = b'l_english:\n key:0 "Hello $NAME$"\n'
    source_file.write_bytes(source_bytes)
    output = tmp_path / "candidate"

    with pytest.raises(OllamaSystemError):
        translate_mod(tmp_path / "source", output, "synthetic:1")

    assert not output.exists()
    assert list(tmp_path.glob(".candidate.tmp-*")) == []
    assert source_file.read_bytes() == source_bytes


@pytest.mark.parametrize("done_reason", ["length", "future_reason"])
def test_terminal_reason_error_stops_run_without_candidate(
    fake_ollama, tmp_path, done_reason: str
) -> None:
    Handler.generate_done_reason = done_reason
    source_file = (
        tmp_path / "source/localisation/english/demo_l_english.yml"
    )
    source_file.parent.mkdir(parents=True)
    source_bytes = b'l_english:\n key:0 "Hello $NAME$"\n'
    source_file.write_bytes(source_bytes)
    output = tmp_path / "candidate"

    with pytest.raises(OllamaSystemError):
        translate_mod(tmp_path / "source", output, "synthetic:1")

    assert not output.exists()
    assert list(tmp_path.glob(".candidate.tmp-*")) == []
    assert source_file.read_bytes() == source_bytes


def test_model_digest_drift_removes_temp_and_publishes_nothing(
    fake_ollama, tmp_path
) -> None:
    Handler.inventory_digests = [
        "sha256:synthetic",
        "sha256:synthetic-drift",
    ]
    source_file = (
        tmp_path / "source/localisation/english/demo_l_english.yml"
    )
    source_file.parent.mkdir(parents=True)
    source_bytes = b'l_english:\n key:0 "Hello $NAME$"\n'
    source_file.write_bytes(source_bytes)
    output = tmp_path / "candidate"

    with pytest.raises(SafetyError, match="model_identity_changed"):
        translate_mod(tmp_path / "source", output, "synthetic:1")

    assert not output.exists()
    assert list(tmp_path.glob(".candidate.tmp-*")) == []
    assert source_file.read_bytes() == source_bytes


def test_fake_loopback_happy_path_creates_candidate(
    fake_ollama, tmp_path
) -> None:
    source_file = (
        tmp_path / "source/localisation/english/demo_l_english.yml"
    )
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b'l_english:\n key:0 "Hello $NAME$"\n')
    output = tmp_path / "candidate"
    report = translate_mod(
        tmp_path / "source", output, "synthetic:1"
    )
    candidate = output / "localisation/russian/demo_l_russian.yml"
    assert candidate.read_bytes() == (
        'l_russian:\n key:0 "Привет $NAME$"\n'.encode()
    )
    assert report["counts"]["translated_occurrences"] == 1
