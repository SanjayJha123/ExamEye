"""Phase 3: suspicion-scoring heuristics on top of YOLO detections."""

from __future__ import annotations

from examye.services.detection import Detection, score_from_detections


def _det(label: str, bbox: tuple[float, float, float, float], conf: float = 0.9) -> Detection:
    return Detection(label=label, confidence=conf, bbox=bbox)


def test_empty_scene_flags_absent_candidate():
    analysis = score_from_detections([], 640, 480)
    assert analysis.person_count == 0
    assert analysis.suspicion_score > 0
    assert any("no candidate" in r for r in analysis.reasons)


def test_solo_person_is_low_suspicion():
    persons = [_det("person", (100, 100, 200, 400))]
    analysis = score_from_detections(persons, 640, 480)
    assert analysis.person_count == 1
    assert analysis.phone_count == 0
    assert analysis.suspicion_score < 0.55


def test_phone_visible_triggers_high_suspicion():
    detections = [
        _det("person", (100, 100, 200, 400)),
        _det("cell phone", (180, 250, 220, 290)),
    ]
    analysis = score_from_detections(detections, 640, 480)
    assert analysis.phone_count == 1
    assert analysis.suspicion_score >= 0.55
    assert any("phone" in r for r in analysis.reasons)


def test_two_people_close_together_flagged():
    detections = [
        _det("person", (100, 100, 200, 400)),
        _det("person", (205, 100, 305, 400)),  # right next to the first
    ]
    analysis = score_from_detections(detections, 640, 480)
    assert analysis.person_count == 2
    assert analysis.suspicion_score > 0
    assert any("close" in r or "proximity" in r for r in analysis.reasons)


def test_two_people_far_apart_not_flagged_for_proximity():
    detections = [
        _det("person", (10, 100, 110, 400)),
        _det("person", (520, 100, 620, 400)),
    ]
    analysis = score_from_detections(detections, 640, 480)
    assert analysis.suspicion_score < 0.55
    assert not any("close" in r or "proximity" in r for r in analysis.reasons)


def test_score_is_clamped_to_one():
    detections = [
        _det("cell phone", (10, 10, 50, 50)),
        _det("cell phone", (100, 10, 140, 50)),
        _det("cell phone", (200, 10, 240, 50)),
        _det("person", (100, 100, 200, 400)),
        _det("person", (205, 100, 305, 400)),
        _det("book", (100, 200, 200, 300)),
    ]
    analysis = score_from_detections(detections, 640, 480)
    assert analysis.suspicion_score == 1.0
