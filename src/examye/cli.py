"""CLI entrypoint for ExamEye."""

from __future__ import annotations

import argparse
import sys

from .config import get_settings


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "examye.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def _cmd_pull(args: argparse.Namespace) -> int:
    from .services.ollama import pull_with_progress

    model = args.model or get_settings().llm_model
    return pull_with_progress(model)


def _cmd_models(_: argparse.Namespace) -> int:
    from .services.ollama import is_running, list_models

    if not is_running():
        print(f"Ollama not reachable at {get_settings().ollama_host}", file=sys.stderr)
        return 1
    rows = list_models()
    if not rows:
        print("(no models pulled yet)")
        return 0
    for m in rows:
        size = m.get("size", 0)
        gb = size / (1024**3) if size else 0
        print(f"{m.get('name', '?'):<30} {gb:>6.2f} GB   {m.get('modified_at', '')}")
    return 0


def _cmd_ping(_: argparse.Namespace) -> int:
    from .services.llm import ping

    ok, msg = ping()
    settings = get_settings()
    print(f"backend  : {settings.llm_backend}")
    print(f"base_url : {settings.llm_base_url}")
    print(f"model    : {settings.llm_model}")
    print(f"status   : {'OK ' if ok else 'FAIL'} {msg}")
    return 0 if ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="examye")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="Run the ExamEye web server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=_cmd_serve)

    pull = sub.add_parser("pull-model", help="Download the configured LLM model via Ollama")
    pull.add_argument(
        "--model",
        default=None,
        help="Model tag to pull (defaults to EXAMYE_LLM_MODEL, e.g. gemma4:e2b)",
    )
    pull.set_defaults(func=_cmd_pull)

    models = sub.add_parser("models", help="List models available in the local Ollama daemon")
    models.set_defaults(func=_cmd_models)

    ping = sub.add_parser("ping", help="Check whether the configured LLM backend is reachable")
    ping.set_defaults(func=_cmd_ping)

    args = parser.parse_args()
    rc = args.func(args)
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
