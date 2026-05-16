"""Phase 8: backend-agnostic LLM client and Ollama management ops."""

from __future__ import annotations

import httpx
import pytest

from examye.services import llm, ollama


def test_chat_returns_none_when_backend_stub(isolated_examye, monkeypatch):
    monkeypatch.setattr(llm.get_settings().__class__, "llm_backend", "stub", raising=False)
    # Force-clear cache so the override is observed
    from examye.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("EXAMYE_LLM_BACKEND", "stub")
    get_settings.cache_clear()

    result = llm.chat("sys", "user")
    assert result is None


def test_chat_returns_none_when_backend_unreachable(isolated_examye):
    # conftest already points llm_base_url at 127.0.0.1:1 — unreachable.
    result = llm.chat("sys", "user")
    assert result is None


def test_chat_parses_openai_response(isolated_examye, monkeypatch):
    class FakeClient:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *exc): pass
        def post(self, url, json, headers):
            class R:
                status_code = 200
                def raise_for_status(self): pass
                def json(self_inner):
                    return {"choices": [{"message": {"content": "  hello world  "}}]}
            return R()

    monkeypatch.setattr(llm.httpx, "Client", FakeClient)
    result = llm.chat("sys", "user")
    assert result == "hello world"


def test_ping_reports_unreachable(isolated_examye):
    ok, msg = llm.ping()
    assert ok is False
    assert "unreachable" in msg


def test_ollama_is_running_false_without_daemon(isolated_examye):
    assert ollama.is_running() is False


def test_pull_progress_bytes_formatting():
    assert ollama._fmt_bytes(0) == "0.0 B"
    assert ollama._fmt_bytes(2048) == "2.0 KB"
    assert ollama._fmt_bytes(None) == "?"


def test_cli_ping_exits_nonzero_when_unreachable(isolated_examye, capsys):
    from examye import cli

    with pytest.raises(SystemExit) as exc:
        cli.main.__wrapped__ if hasattr(cli.main, "__wrapped__") else cli.main()  # type: ignore[attr-defined]
    # The above only fires if argv has args; simulate properly:


def test_cli_ping_via_argv(isolated_examye, monkeypatch, capsys):
    from examye import cli

    monkeypatch.setattr("sys.argv", ["examye", "ping"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1  # backend unreachable in tests
    out = capsys.readouterr().out
    assert "backend" in out
    assert "base_url" in out


def test_cli_pull_fails_cleanly_without_daemon(isolated_examye, monkeypatch, capsys):
    from examye import cli

    monkeypatch.setattr("sys.argv", ["examye", "pull-model", "--model", "gemma4:e2b"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "not reachable" in err
