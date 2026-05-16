# ExamEye

AI-powered exam surveillance and investigation platform. Turns passive CCTV footage into intelligent investigation assistants using YOLOv8 for detection and Gemma 4 (via vLLM) for natural-language reasoning.

## Stack

- Python 3.11+, FastAPI, SQLAlchemy 2.x (SQLite)
- OpenCV for frame extraction
- Ultralytics YOLOv8 for person/object detection
- Gemma 4 via vLLM OpenAI-compatible endpoint (with deterministic fallback)
- Jinja2 templates + a tiny vanilla JS frontend
- WebSockets for real-time alerts

## Quick start

```bash
uv sync
uv run examye serve
```

Open http://localhost:8000.

### Optional: real Gemma summaries

Run a vLLM server somewhere reachable (default `http://localhost:8001/v1`):

```bash
vllm serve google/gemma-2-9b-it --port 8001
```

Then set `EXAMYE_VLLM_BASE_URL` if it lives elsewhere. If vLLM isn't reachable, ExamEye falls back to a deterministic templated summary so the rest of the pipeline keeps working.

## End-to-end flow

1. Admin uploads CCTV footage (`/`).
2. Background pipeline extracts frames (OpenCV), runs YOLOv8 detection, scores suspicion per frame.
3. High-severity frames push live alerts over WebSocket.
4. Per-video summary is generated with Gemma 4 (or stub).
5. Admin asks natural-language questions; relevant events are retrieved as evidence and answered with Gemma.

## Layout

```
src/examye/
  main.py          FastAPI app wiring
  config.py        Pydantic settings
  database.py      SQLAlchemy session/engine
  models.py        ORM models (Video, Frame, Event, Summary, Query)
  schemas.py       Pydantic IO schemas
  pipeline.py      Per-video processing orchestrator
  routes/          HTTP + WebSocket endpoints
  services/        Frame extraction, detection, summarization, query, alerts
  templates/       Jinja2 HTML
  static/          CSS + JS
tests/             Pytest suite
```

## Testing

```bash
uv run pytest
```
