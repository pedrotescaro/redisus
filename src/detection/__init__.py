"""REDISUS Detection Module"""
from .realtime_detector import (
    Detection,
    YOLODetector,
    RealtimeWoundDetector,
    BaseDetector,
)
from .body_part_detector import (
    BodyPartDetector,
    BodyPartPrediction,
    BodyRegion,
    create_body_part_detector,
)

try:
    from .mediapipe_body_detector import MediaPipeBodyDetector
except ImportError:
    MediaPipeBodyDetector = None  # type: ignore[assignment,misc]

__all__ = [
    "Detection",
    "YOLODetector",
    "RealtimeWoundDetector",
    "BaseDetector",
    "BodyPartDetector",
    "BodyPartPrediction",
    "BodyRegion",
    "create_body_part_detector",
]
