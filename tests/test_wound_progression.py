from types import SimpleNamespace

from src.monitoring.wound_progression import build_progression_from_reports


def _tissue(name: str, percentage: float):
    return SimpleNamespace(name=name, percentage=percentage)


def _report(area: int, score: float, tissues: list[tuple[str, float]]):
    return SimpleNamespace(
        is_valid_wound=True,
        rejection_reason="",
        wound_area_px=area,
        health_score=score,
        primary_tissue=tissues[0][0],
        tissues=[_tissue(name, pct) for name, pct in tissues],
        processing_time_ms=100.0,
    )


def test_progression_estimates_closure_when_area_and_tissue_improve():
    result = build_progression_from_reports(
        ["first.jpg", "last.jpg"],
        [
            _report(1000, 35, [("Esfacelo (Fibrina)", 45), ("Tecido de Granulacao", 25)]),
            _report(700, 58, [("Esfacelo (Fibrina)", 15), ("Tecido de Granulacao", 55)]),
        ],
        days_between_photos=7,
    )

    assert result.closure_estimate.trajectory == "improving"
    assert result.closure_estimate.estimated_days_to_closure_min is not None
    assert result.area_change_pct == -30
    assert result.healthy_tissue_delta_pct == 30
    assert result.devitalized_tissue_delta_pct == -30


def test_progression_flags_worsening_without_closure_estimate():
    result = build_progression_from_reports(
        ["first.jpg", "last.jpg"],
        [
            _report(800, 60, [("Tecido de Granulacao", 60), ("Necrose de Coagulacao", 5)]),
            _report(980, 42, [("Tecido de Granulacao", 35), ("Necrose de Coagulacao", 24)]),
        ],
        days_between_photos=7,
    )

    assert result.closure_estimate.trajectory == "worsening"
    assert result.closure_estimate.estimated_days_to_closure_min is None
    assert result.recommendations
