"""REDISUS Detection Module"""
from .realtime_detector import (
    Detection,
    YOLODetector,
    RealtimeWoundDetector,
    BaseDetector,
)

__all__ = [
    "Detection",
    "YOLODetector",
    "RealtimeWoundDetector",
    "BaseDetector",
]
