from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Sequence

import cv2


HEALTHY_TISSUE_KEYWORDS = ("granula", "epitel")
DEVITALIZED_TISSUE_KEYWORDS = ("necrose", "esfacelo", "fibrina")


@dataclass(slots=True)
class WoundPhotoSnapshot:
    sequence_index: int
    image_path: str
    filename: str
    is_valid_wound: bool
    rejection_reason: str = ""
    wound_area_px: int = 0
    health_score: float = 0.0
    primary_tissue: str = ""
    tissue_percentages: dict[str, float] = field(default_factory=dict)
    processing_time_ms: float = 0.0

    @property
    def healthy_tissue_pct(self) -> float:
        return _sum_tissue_group(self.tissue_percentages, HEALTHY_TISSUE_KEYWORDS)

    @property
    def devitalized_tissue_pct(self) -> float:
        return _sum_tissue_group(self.tissue_percentages, DEVITALIZED_TISSUE_KEYWORDS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence_index": self.sequence_index,
            "image_path": self.image_path,
            "filename": self.filename,
            "is_valid_wound": self.is_valid_wound,
            "rejection_reason": self.rejection_reason,
            "wound_area_px": self.wound_area_px,
            "health_score": round(self.health_score, 2),
            "primary_tissue": self.primary_tissue,
            "tissue_percentages": {
                name: round(value, 2)
                for name, value in self.tissue_percentages.items()
            },
            "healthy_tissue_pct": round(self.healthy_tissue_pct, 2),
            "devitalized_tissue_pct": round(self.devitalized_tissue_pct, 2),
            "processing_time_ms": round(self.processing_time_ms, 2),
        }


@dataclass(slots=True)
class TissueEvolutionDelta:
    tissue_name: str
    first_pct: float
    last_pct: float
    delta_pct: float
    trend: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tissue_name": self.tissue_name,
            "first_pct": round(self.first_pct, 2),
            "last_pct": round(self.last_pct, 2),
            "delta_pct": round(self.delta_pct, 2),
            "trend": self.trend,
        }


@dataclass(slots=True)
class HealingEstimate:
    trajectory: str
    confidence: str
    estimated_days_to_closure_min: int | None
    estimated_days_to_closure_max: int | None
    estimated_weeks_to_closure: float | None
    rationale: str
    assumptions: list[str] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trajectory": self.trajectory,
            "confidence": self.confidence,
            "estimated_days_to_closure_min": self.estimated_days_to_closure_min,
            "estimated_days_to_closure_max": self.estimated_days_to_closure_max,
            "estimated_weeks_to_closure": self.estimated_weeks_to_closure,
            "rationale": self.rationale,
            "assumptions": list(self.assumptions),
            "alerts": list(self.alerts),
        }


@dataclass(slots=True)
class WoundProgressionResult:
    snapshots: list[WoundPhotoSnapshot]
    tissue_deltas: list[TissueEvolutionDelta]
    valid_photo_count: int
    invalid_photo_count: int
    area_change_pct: float | None
    health_score_delta: float | None
    healthy_tissue_delta_pct: float | None
    devitalized_tissue_delta_pct: float | None
    closure_estimate: HealingEstimate
    summary: str
    recommendations: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "valid_photo_count": self.valid_photo_count,
            "invalid_photo_count": self.invalid_photo_count,
            "area_change_pct": _round_optional(self.area_change_pct),
            "health_score_delta": _round_optional(self.health_score_delta),
            "healthy_tissue_delta_pct": _round_optional(self.healthy_tissue_delta_pct),
            "devitalized_tissue_delta_pct": _round_optional(self.devitalized_tissue_delta_pct),
            "summary": self.summary,
            "recommendations": list(self.recommendations),
            "closure_estimate": self.closure_estimate.to_dict(),
            "tissue_deltas": [delta.to_dict() for delta in self.tissue_deltas],
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
        }


def snapshot_from_report(sequence_index: int, image_path: str, report: Any) -> WoundPhotoSnapshot:
    tissue_percentages: dict[str, float] = {}
    for tissue in getattr(report, "tissues", []) or []:
        name = _repair_text(str(getattr(tissue, "name", "") or "Nao classificado"))
        tissue_percentages[name] = float(getattr(tissue, "percentage", 0.0) or 0.0)

    return WoundPhotoSnapshot(
        sequence_index=sequence_index,
        image_path=image_path,
        filename=Path(image_path).name,
        is_valid_wound=bool(getattr(report, "is_valid_wound", False)),
        rejection_reason=_repair_text(str(getattr(report, "rejection_reason", "") or "")),
        wound_area_px=int(getattr(report, "wound_area_px", 0) or 0),
        health_score=float(getattr(report, "health_score", 0.0) or 0.0),
        primary_tissue=_repair_text(str(getattr(report, "primary_tissue", "") or "")),
        tissue_percentages=tissue_percentages,
        processing_time_ms=float(getattr(report, "processing_time_ms", 0.0) or 0.0),
    )


def invalid_snapshot(sequence_index: int, image_path: str, reason: str) -> WoundPhotoSnapshot:
    return WoundPhotoSnapshot(
        sequence_index=sequence_index,
        image_path=image_path,
        filename=Path(image_path).name,
        is_valid_wound=False,
        rejection_reason=reason,
    )


def build_progression_from_snapshots(
    snapshots: Sequence[WoundPhotoSnapshot],
    *,
    days_between_photos: float = 7.0,
) -> WoundProgressionResult:
    ordered_snapshots = sorted(snapshots, key=lambda item: item.sequence_index)
    valid_snapshots = [snapshot for snapshot in ordered_snapshots if snapshot.is_valid_wound]
    invalid_count = len(ordered_snapshots) - len(valid_snapshots)

    if len(valid_snapshots) < 2:
        estimate = HealingEstimate(
            trajectory="insufficient_data",
            confidence="low",
            estimated_days_to_closure_min=None,
            estimated_days_to_closure_max=None,
            estimated_weeks_to_closure=None,
            rationale="Sao necessarias pelo menos duas fotos validas para estimar evolucao.",
            assumptions=_default_assumptions(days_between_photos),
            alerts=["Inclua duas ou mais fotos cronologicas da mesma ferida."],
        )
        return WoundProgressionResult(
            snapshots=list(ordered_snapshots),
            tissue_deltas=[],
            valid_photo_count=len(valid_snapshots),
            invalid_photo_count=invalid_count,
            area_change_pct=None,
            health_score_delta=None,
            healthy_tissue_delta_pct=None,
            devitalized_tissue_delta_pct=None,
            closure_estimate=estimate,
            summary="Evolucao insuficiente: menos de duas fotos validas.",
            recommendations=["Padronizar distancia, angulo e iluminacao antes de comparar novas fotos."],
        )

    first = valid_snapshots[0]
    last = valid_snapshots[-1]
    area_change_pct = _percent_change(first.wound_area_px, last.wound_area_px)
    health_score_delta = last.health_score - first.health_score
    healthy_delta = last.healthy_tissue_pct - first.healthy_tissue_pct
    devitalized_delta = last.devitalized_tissue_pct - first.devitalized_tissue_pct
    tissue_deltas = _build_tissue_deltas(first, last)
    estimate = _estimate_healing(
        first,
        last,
        valid_photo_count=len(valid_snapshots),
        days_between_photos=days_between_photos,
        area_change_pct=area_change_pct,
        health_score_delta=health_score_delta,
        healthy_delta=healthy_delta,
        devitalized_delta=devitalized_delta,
    )
    recommendations = _build_recommendations(
        estimate,
        area_change_pct=area_change_pct,
        health_score_delta=health_score_delta,
        healthy_delta=healthy_delta,
        devitalized_delta=devitalized_delta,
        invalid_count=invalid_count,
    )
    summary = _build_summary(
        estimate,
        area_change_pct=area_change_pct,
        health_score_delta=health_score_delta,
        healthy_delta=healthy_delta,
        devitalized_delta=devitalized_delta,
    )
    return WoundProgressionResult(
        snapshots=list(ordered_snapshots),
        tissue_deltas=tissue_deltas,
        valid_photo_count=len(valid_snapshots),
        invalid_photo_count=invalid_count,
        area_change_pct=area_change_pct,
        health_score_delta=health_score_delta,
        healthy_tissue_delta_pct=healthy_delta,
        devitalized_tissue_delta_pct=devitalized_delta,
        closure_estimate=estimate,
        summary=summary,
        recommendations=recommendations,
    )


def build_progression_from_reports(
    image_paths: Sequence[str],
    reports: Sequence[Any],
    *,
    days_between_photos: float = 7.0,
) -> WoundProgressionResult:
    snapshots = [
        snapshot_from_report(index + 1, image_path, report)
        for index, (image_path, report) in enumerate(zip(image_paths, reports))
    ]
    return build_progression_from_snapshots(snapshots, days_between_photos=days_between_photos)


def analyze_wound_photo_progression(
    image_paths: Sequence[str],
    *,
    analyzer_factory: Callable[[], Any],
    days_between_photos: float = 7.0,
    progress_callback: Callable[[str], None] | None = None,
) -> WoundProgressionResult:
    analyzer = analyzer_factory()
    snapshots: list[WoundPhotoSnapshot] = []
    total = len(image_paths)

    for index, image_path in enumerate(image_paths, start=1):
        if progress_callback:
            progress_callback(f"Analisando foto {index}/{total}: {Path(image_path).name}")

        image = cv2.imread(str(image_path))
        if image is None:
            snapshots.append(invalid_snapshot(index, image_path, "Nao foi possivel carregar a imagem."))
            continue

        try:
            report = analyzer.analyze(image)
        except Exception as exc:  # defensive boundary for UI/API calls
            snapshots.append(invalid_snapshot(index, image_path, f"Falha na analise: {exc}"))
            continue

        snapshots.append(snapshot_from_report(index, image_path, report))

    return build_progression_from_snapshots(snapshots, days_between_photos=days_between_photos)


def _sum_tissue_group(tissue_percentages: dict[str, float], keywords: tuple[str, ...]) -> float:
    total = 0.0
    for name, percentage in tissue_percentages.items():
        normalized = name.lower()
        if any(keyword in normalized for keyword in keywords):
            total += float(percentage)
    return total


def _repair_text(value: str) -> str:
    repaired = value
    for _ in range(2):
        if not any(marker in repaired for marker in ("Ã", "Â", "â")):
            break
        try:
            candidate = repaired.encode("latin1").decode("utf-8")
        except UnicodeError:
            break
        if candidate == repaired:
            break
        repaired = candidate
    return repaired


def _build_tissue_deltas(first: WoundPhotoSnapshot, last: WoundPhotoSnapshot) -> list[TissueEvolutionDelta]:
    tissue_names = sorted(set(first.tissue_percentages) | set(last.tissue_percentages))
    deltas: list[TissueEvolutionDelta] = []
    for tissue_name in tissue_names:
        first_pct = float(first.tissue_percentages.get(tissue_name, 0.0))
        last_pct = float(last.tissue_percentages.get(tissue_name, 0.0))
        delta_pct = last_pct - first_pct
        if delta_pct >= 3:
            trend = "aumentou"
        elif delta_pct <= -3:
            trend = "reduziu"
        else:
            trend = "estavel"
        deltas.append(TissueEvolutionDelta(tissue_name, first_pct, last_pct, delta_pct, trend))
    return sorted(deltas, key=lambda item: abs(item.delta_pct), reverse=True)


def _estimate_healing(
    first: WoundPhotoSnapshot,
    last: WoundPhotoSnapshot,
    *,
    valid_photo_count: int,
    days_between_photos: float,
    area_change_pct: float | None,
    health_score_delta: float,
    healthy_delta: float,
    devitalized_delta: float,
) -> HealingEstimate:
    assumptions = _default_assumptions(days_between_photos)
    alerts: list[str] = []
    elapsed_days = max(days_between_photos * max(valid_photo_count - 1, 1), 1.0)
    area_delta_px = float(first.wound_area_px - last.wound_area_px)
    daily_area_reduction = area_delta_px / elapsed_days if area_delta_px > 0 else 0.0

    improving = (
        (area_change_pct is not None and area_change_pct <= -10.0)
        or health_score_delta >= 8.0
        or (healthy_delta >= 8.0 and devitalized_delta <= 0.0)
    )
    worsening = (
        (area_change_pct is not None and area_change_pct >= 10.0)
        or health_score_delta <= -8.0
        or devitalized_delta >= 8.0
    )

    if worsening:
        trajectory = "worsening"
        confidence = "moderate"
        rationale = "A tendencia sugere piora ou estagnacao clinicamente relevante."
        alerts.append("Area, tecido desvitalizado ou score pioraram; reavaliacao presencial e indicada.")
        return HealingEstimate(
            trajectory=trajectory,
            confidence=confidence,
            estimated_days_to_closure_min=None,
            estimated_days_to_closure_max=None,
            estimated_weeks_to_closure=None,
            rationale=rationale,
            assumptions=assumptions,
            alerts=alerts,
        )

    if not improving or daily_area_reduction <= 0:
        trajectory = "stable"
        confidence = "low"
        rationale = "Nao ha reducao de area suficiente para projetar fechamento com seguranca."
        alerts.append("Estimativa de fechamento indisponivel ate haver reducao consistente da area.")
        return HealingEstimate(
            trajectory=trajectory,
            confidence=confidence,
            estimated_days_to_closure_min=None,
            estimated_days_to_closure_max=None,
            estimated_weeks_to_closure=None,
            rationale=rationale,
            assumptions=assumptions,
            alerts=alerts,
        )

    raw_days = max(float(last.wound_area_px) / daily_area_reduction, 1.0)
    modifier = 1.0
    if healthy_delta >= 10:
        modifier *= 0.88
    if devitalized_delta > 0:
        modifier *= 1.25
        alerts.append("Tecido desvitalizado aumentou; a estimativa pode estar otimista.")
    if health_score_delta < 4:
        modifier *= 1.15

    estimated_days = raw_days * modifier
    min_days = max(1, int(round(estimated_days * 0.75)))
    max_days = max(min_days + 1, int(round(estimated_days * 1.5)))
    confidence = "moderate" if area_change_pct is not None and area_change_pct <= -20 and healthy_delta >= 0 else "low"
    rationale = "A estimativa usa reducao relativa de area em pixels e mudanca de composicao tecidual."
    return HealingEstimate(
        trajectory="improving",
        confidence=confidence,
        estimated_days_to_closure_min=min_days,
        estimated_days_to_closure_max=max_days,
        estimated_weeks_to_closure=round(estimated_days / 7.0, 1),
        rationale=rationale,
        assumptions=assumptions,
        alerts=alerts,
    )


def _build_recommendations(
    estimate: HealingEstimate,
    *,
    area_change_pct: float | None,
    health_score_delta: float,
    healthy_delta: float,
    devitalized_delta: float,
    invalid_count: int,
) -> list[str]:
    recommendations: list[str] = []
    if estimate.trajectory == "improving":
        recommendations.append("Manter protocolo se a avaliacao clinica confirmar melhora e ausencia de infeccao.")
        recommendations.append("Repetir foto padronizada no mesmo intervalo para confirmar tendencia.")
    elif estimate.trajectory == "worsening":
        recommendations.append("Priorizar revisao por estomaterapia/enfermagem antes de esperar fechamento espontaneo.")
        recommendations.append("Verificar pressao, infeccao, perfusao, dor, exsudato e necessidade de desbridamento.")
    else:
        recommendations.append("Padronizar proxima foto e reavaliar medidas; tendencia ainda nao e robusta.")

    if area_change_pct is not None and area_change_pct > 0:
        recommendations.append("Area aparente aumentou; confirmar se a escala/distancia da foto foi a mesma.")
    if healthy_delta < -5:
        recommendations.append("Tecido de reparo reduziu; investigar trauma, umidade excessiva ou pressao persistente.")
    if devitalized_delta > 5:
        recommendations.append("Tecido desvitalizado aumentou; considerar avaliacao de limpeza/desbridamento conforme protocolo.")
    if health_score_delta < -5:
        recommendations.append("Score de saude caiu; tratar como alerta de piora ate prova em contrario.")
    if invalid_count:
        recommendations.append(f"{invalid_count} foto(s) foram rejeitadas; refazer com melhor foco, luz e enquadramento.")
    return recommendations


def _build_summary(
    estimate: HealingEstimate,
    *,
    area_change_pct: float | None,
    health_score_delta: float,
    healthy_delta: float,
    devitalized_delta: float,
) -> str:
    area_text = "area sem base comparavel" if area_change_pct is None else f"area {area_change_pct:+.1f}%"
    return (
        f"Trajetoria: {estimate.trajectory}. "
        f"{area_text}; score {health_score_delta:+.1f}; "
        f"tecido de reparo {healthy_delta:+.1f} pp; "
        f"tecido desvitalizado {devitalized_delta:+.1f} pp."
    )


def _percent_change(first_value: int | float, last_value: int | float) -> float | None:
    first_float = float(first_value or 0.0)
    if first_float <= 0:
        return None
    return ((float(last_value) - first_float) / first_float) * 100.0


def _default_assumptions(days_between_photos: float) -> list[str]:
    return [
        f"Fotos tratadas como cronologicas, com intervalo medio de {days_between_photos:g} dia(s).",
        "Area em pixels depende de distancia, angulo e zoom; sem escala fisica, a estimativa e aproximada.",
        "Estimativa nao substitui avaliacao presencial, mensuracao com regua/escala e julgamento clinico.",
    ]


def _round_optional(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None
