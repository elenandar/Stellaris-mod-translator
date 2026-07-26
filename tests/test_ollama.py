from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

import stellaris_mod_translator.ollama as ollama
from stellaris_mod_translator.engine import translate_mod
from stellaris_mod_translator.ollama import OllamaClient, OllamaError


class Handler(BaseHTTPRequestHandler):
    generate_response = {"translation": "Привет __SMT_TOKEN_0000__"}
    generate_calls = 0

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        assert self.path == "/api/tags"
        self._send(
            {
                "models": [
                    {"name": "synthetic:1", "digest": "sha256:synthetic"},
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
        assert request["model"] == "synthetic:1"
        assert request["format"]["additionalProperties"] is False
        self._send({"response": json.dumps(type(self).generate_response)})

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


def test_structured_non_streaming_happy_path(fake_ollama) -> None:
    client = OllamaClient()
    result = client.translate(
        tag="synthetic:1", text="Hello __SMT_TOKEN_0000__"
    )
    assert result == "Привет __SMT_TOKEN_0000__"
    assert Handler.generate_calls == 1


def test_nested_or_non_string_response_is_rejected(fake_ollama) -> None:
    Handler.generate_response = {"translation": {"text": "x"}}
    with pytest.raises(OllamaError, match="structured"):
        OllamaClient().translate(tag="synthetic:1", text="x")
    Handler.generate_response = {"translation": "x"}


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
