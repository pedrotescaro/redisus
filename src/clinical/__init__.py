# -*- coding: utf-8 -*-
"""
HEAL+ / REDISUS — Módulo de Escalas Clínicas
============================================

Escalas validadas para avaliação de feridas e prevenção de lesões.
"""

from src.clinical.scales import (
    # PUSH
    PushScore,
    PushAreaScore,
    PushExudateScore,
    PushTissueScore,
    PUSH_AREA_RANGES,
    
    # BWAT
    BWATScore,
    BWATItem,
    BWAT_ITEMS,
    
    # Braden
    BradenScore,
    BradenCategory,
    BRADEN_CATEGORIES,
    
    # Helper
    ScaleCalculator,
)

__all__ = [
    "PushScore",
    "PushAreaScore",
    "PushExudateScore",
    "PushTissueScore",
    "PUSH_AREA_RANGES",
    "BWATScore",
    "BWATItem",
    "BWAT_ITEMS",
    "BradenScore",
    "BradenCategory",
    "BRADEN_CATEGORIES",
    "ScaleCalculator",
]
