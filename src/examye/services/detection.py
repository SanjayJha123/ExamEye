"""YOLOv8 detection + suspicion scoring for ExamEye frames.

We use ultralytics' COCO-pretrained YOLOv8n. The model auto-downloads on first
use. Suspicion heuristics combine person count, presence of phones/books, and
spatial crowding into a score in [0, 1].
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..config import get_settings

logger = logging.getLogger(__name__)


# COCO class names we treat specially.
_PERSON = "person"
_PHONE = "cell phone"
_BOOK = "book"
_LAPTOP = "laptop"


@dataclass
class Detection:
    label: str
    confidence: float
    bbox: tuple[float, float, float, float]  # xyxy


@dataclass
class FrameAnalysis:
    detections: list[Detection] = field(default_factory=list)
    person_count: int = 0
    phone_count: int = 0
    book_count: int = 0
    laptop_count: int = 0
    suspicion_score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def to_json_detections(self) -> list[dict[str, Any]]:
        return [
            {
                "label": d.label,
                "confidence": round(d.confidence, 4),
                "bbox": [round(v, 2) for v in d.bbox],
            }
            for d in d_list_or(self.detections)
        ]


def d_list_or(value: list[Detection]) -> list[Detection]:
    return value or []


# YOLO model loading is expensive and not thread-safe to redo; cache it.
_model_lock = threading.Lock()
_model: Optional[Any] = None
_model_load_failed = False


def _load_model() -> Optional[Any]:
    global _model, _model_load_failed
    if _model is not None or _model_load_failed:
        return _model
    with _model_lock:
        if _model is not None or _model_load_failed:
            return _model
        settings = get_settings()
        try:
            from ultralytics import YOLO  # type: ignore[import-untyped]

            logger.info("loading YOLOv8 model: %s", settings.yolo_model)
            _model = YOLO(settings.yolo_model)
            return _model
        except Exception as exc:
            logger.exception("failed to load YOLO model: %s", exc)
            _model_load_failed = True
            return None


def _bbox_center(b: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = b
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _normalized_distance(a: Detection, b: Detection, w: int, h: int) -> float:
    ax, ay = _bbox_center(a.bbox)
    bx, by = _bbox_center(b.bbox)
    diag = (w * w + h * h) ** 0.5 or 1.0
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 / diag


def _score(analysis: FrameAnalysis, width: int, height: int) -> None:
    """Compute suspicion score + human-readable reasons."""
    score = 0.0
    reasons: list[str] = []

    if analysis.phone_count > 0:
        score += 0.55 + 0.1 * (analysis.phone_count - 1)
        reasons.append(
            f"{analysis.phone_count} phone-like object{'s' if analysis.phone_count > 1 else ''} visible"
        )
    if analysis.book_count > 0 and analysis.person_count > 0:
        score += 0.15
        reasons.append("open book / paper near person")
    if analysis.laptop_count > 1:
        score += 0.1
        reasons.append("multiple laptops in frame")

    persons = [d for d in analysis.detections if d.label == _PERSON]
    if len(persons) >= 2:
        min_dist = min(
            (
                _normalized_distance(a, b, width, height)
                for i, a in enumerate(persons)
                for b in persons[i + 1 :]
            ),
            default=1.0,
        )
        if min_dist < 0.10:
            score += 0.35
            reasons.append(f"two people unusually close (d={min_dist:.2f})")
        elif min_dist < 0.18:
            score += 0.15
            reasons.append(f"persons in close proximity (d={min_dist:.2f})")

    if analysis.person_count == 0:
        score += 0.05
        reasons.append("no candidate visible (empty seat?)")

    analysis.suspicion_score = max(0.0, min(1.0, score))
    analysis.reasons = reasons


def score_from_detections(
    detections: list[Detection], width: int, height: int
) -> FrameAnalysis:
    """Public entrypoint used both by the inference path and by tests."""
    analysis = FrameAnalysis(detections=list(detections))
    for d in detections:
        if d.label == _PERSON:
            analysis.person_count += 1
        elif d.label == _PHONE:
            analysis.phone_count += 1
        elif d.label == _BOOK:
            analysis.book_count += 1
        elif d.label == _LAPTOP:
            analysis.laptop_count += 1
    _score(analysis, width, height)
    return analysis


def analyze_frame(image_path: Path, width: int, height: int) -> FrameAnalysis:
    model = _load_model()
    analysis = FrameAnalysis()
    if model is None:
        return analysis

    settings = get_settings()
    try:
        results = model.predict(
            source=str(image_path),
            conf=settings.yolo_conf,
            verbose=False,
        )
    except Exception as exc:
        logger.exception("YOLO inference failed for %s: %s", image_path, exc)
        return analysis

    if not results:
        return analysis

    res = results[0]
    names = res.names if hasattr(res, "names") else getattr(model, "names", {})
    boxes = getattr(res, "boxes", None)
    if boxes is None or len(boxes) == 0:
        _score(analysis, width, height)
        return analysis

    xyxy = boxes.xyxy.cpu().numpy().tolist()
    confs = boxes.conf.cpu().numpy().tolist()
    cls_ids = boxes.cls.cpu().numpy().astype(int).tolist()

    for (x1, y1, x2, y2), conf, cid in zip(xyxy, confs, cls_ids):
        label = str(names.get(cid, str(cid))) if isinstance(names, dict) else str(names[cid])
        det = Detection(label=label, confidence=float(conf), bbox=(float(x1), float(y1), float(x2), float(y2)))
        analysis.detections.append(det)
        if label == _PERSON:
            analysis.person_count += 1
        elif label == _PHONE:
            analysis.phone_count += 1
        elif label == _BOOK:
            analysis.book_count += 1
        elif label == _LAPTOP:
            analysis.laptop_count += 1

    _score(analysis, width, height)
    return analysis
