"""
Testes unitários — WoundRiskScoring (Risk Stratification)
"""
import pytest

from src.risk.stratification import (
    AlertSeverity,
    AlertType,
    ClinicalAlert,
    PopulationIndicator,
    RiskFactor,
    RiskLevel,
    RiskScore,
    WoundRiskScoring,
)


# ===================================================================
# Enums
# ===================================================================

class TestRiskEnums:
    def test_risk_levels(self):
        assert {r.value for r in RiskLevel} == {"baixo", "moderado", "alto", "critico"}

    def test_alert_types(self):
        assert len(AlertType) >= 5

    def test_alert_severities(self):
        assert {s.value for s in AlertSeverity} == {"informativo", "atenção", "urgente", "critico"}


# ===================================================================
# Dataclasses
# ===================================================================

class TestRiskDataclasses:
    def test_risk_factor(self):
        f = RiskFactor(
            name="Teste", category="clinico",
            weight=0.5, value=0.8, description="desc",
        )
        assert f.weight == 0.5

    def test_risk_score_to_dict(self):
        rs = RiskScore(
            total_score=45.0, level=RiskLevel.MODERATE,
            factors=[], alerts=[], recommendations=["R1"],
            next_evaluation="2025-01-01",
        )
        d = rs.to_dict()
        assert d["total_score"] == 45.0
        assert d["level"] == "moderado"
        assert "timestamp" in d

    def test_clinical_alert_to_dict(self):
        a = ClinicalAlert(
            alert_type=AlertType.INFECTION_RISK,
            severity=AlertSeverity.URGENT,
            patient_id="P001",
            message="Risco de infecção elevado",
        )
        d = a.to_dict()
        assert d["type"] == "risco_infeccao"
        assert d["severity"] == "urgente"

    def test_population_indicator(self):
        ind = PopulationIndicator(
            name="Prevalência LP", value=12.5,
            unit="%", category="prevalencia",
        )
        assert ind.name == "Prevalência LP"


# ===================================================================
# WoundRiskScoring — init
# ===================================================================

class TestWoundRiskScoring:
    @pytest.fixture
    def scorer(self):
        return WoundRiskScoring()

    def test_init(self, scorer):
        assert isinstance(scorer.FACTOR_WEIGHTS, dict)
        assert len(scorer.FACTOR_WEIGHTS) > 0

    def test_thresholds_cover_full_range(self, scorer):
        """Os limiares devem cobrir 0-100 sem lacunas."""
        ranges = list(scorer.RISK_THRESHOLDS.values())
        assert ranges[0][0] == 0
        assert ranges[-1][1] == 100


# ===================================================================
# calculate_risk_score
# ===================================================================

class TestCalculateRiskScore:
    @pytest.fixture
    def scorer(self):
        return WoundRiskScoring()

    def test_returns_risk_score(self, scorer, sample_wound_data, sample_patient_data):
        rs = scorer.calculate_risk_score(sample_wound_data, sample_patient_data)
        assert isinstance(rs, RiskScore)
        assert 0 <= rs.total_score <= 100
        assert isinstance(rs.level, RiskLevel)

    def test_empty_data_returns_low_score(self, scorer):
        rs = scorer.calculate_risk_score({}, {})
        assert isinstance(rs, RiskScore)
        assert rs.total_score >= 0

    def test_high_necrosis_raises_score(self, scorer, sample_patient_data):
        wound = {
            "area_cm2": 80,
            "tissue_percentages": {"Necrose": 70, "Esfacelo": 15},
            "wound_age_days": 120,
            "infection_signs": True,
        }
        rs = scorer.calculate_risk_score(wound, sample_patient_data)
        assert rs.total_score > 40  # deve ser alto

    def test_healthy_wound_lower_score(self, scorer, sample_patient_data):
        wound = {
            "area_cm2": 5,
            "tissue_percentages": {"Granulação": 80, "Necrose": 0},
            "wound_age_days": 10,
            "infection_signs": False,
        }
        rs = scorer.calculate_risk_score(wound, sample_patient_data)
        # Score deve ser relativamente baixo
        assert rs.total_score < 80

    def test_factors_list_populated(self, scorer, sample_wound_data, sample_patient_data):
        rs = scorer.calculate_risk_score(sample_wound_data, sample_patient_data)
        assert len(rs.factors) > 0
        assert all(isinstance(f, RiskFactor) for f in rs.factors)

    def test_recommendations_exist(self, scorer, sample_wound_data, sample_patient_data):
        rs = scorer.calculate_risk_score(sample_wound_data, sample_patient_data)
        assert isinstance(rs.recommendations, list)

    def test_next_evaluation_varies_by_risk(self, scorer, sample_patient_data):
        """Pacientes com risco maior devem ter reavaliação mais cedo."""
        wound_high = {
            "area_cm2": 80,
            "tissue_percentages": {"Necrose": 60},
            "infection_signs": True,
            "wound_age_days": 120,
        }
        wound_low = {
            "area_cm2": 5,
            "tissue_percentages": {"Granulação": 80, "Necrose": 0},
            "infection_signs": False,
            "wound_age_days": 10,
        }
        rs_high = scorer.calculate_risk_score(wound_high, sample_patient_data)
        rs_low = scorer.calculate_risk_score(wound_low, sample_patient_data)

        assert isinstance(rs_high.next_evaluation, str)
        assert isinstance(rs_low.next_evaluation, str)


# ===================================================================
# Risk classification
# ===================================================================

class TestRiskClassification:
    @pytest.fixture
    def scorer(self):
        return WoundRiskScoring()

    def test_classify_low(self, scorer):
        assert scorer._classify_risk(10) == RiskLevel.LOW

    def test_classify_moderate(self, scorer):
        assert scorer._classify_risk(35) == RiskLevel.MODERATE

    def test_classify_high(self, scorer):
        assert scorer._classify_risk(60) == RiskLevel.HIGH

    def test_classify_critical(self, scorer):
        assert scorer._classify_risk(85) == RiskLevel.CRITICAL

    def test_boundary_low_moderate(self, scorer):
        assert scorer._classify_risk(25) == RiskLevel.MODERATE

    def test_boundary_high_critical(self, scorer):
        assert scorer._classify_risk(75) == RiskLevel.CRITICAL
