"""
Testes unitários — WoundHealingSimulator & PatientDigitalTwin
"""
import math
from datetime import datetime, timedelta

import pytest

from src.digital_twin.twin_model import (
    EnvironmentRisk,
    HealingPhase,
    HomeEnvironment,
    PatientDigitalTwin,
    PatientProfile,
    RiskTrajectory,
    WoundHealingSimulator,
    WoundState,
)


# ===================================================================
# Enums
# ===================================================================

class TestEnums:
    def test_healing_phases(self):
        expected = {"hemostasia", "inflamatoria", "proliferativa", "remodelacao", "cronica", "estagnada"}
        assert {p.value for p in HealingPhase} == expected

    def test_risk_trajectory(self):
        assert len(RiskTrajectory) == 4

    def test_environment_risk(self):
        assert len(EnvironmentRisk) >= 5


# ===================================================================
# WoundState
# ===================================================================

class TestWoundState:
    def test_default_values(self):
        ws = WoundState()
        assert ws.area_cm2 == 0.0
        assert ws.infection_signs is False
        assert ws.healing_phase == HealingPhase.INFLAMMATORY

    def test_tissue_health_score_perfect(self):
        ws = WoundState(granulation_pct=100, epithelialization_pct=100,
                        necrosis_pct=0, slough_pct=0)
        score = ws.tissue_health_score()
        assert score == 100.0

    def test_tissue_health_score_infection_penalty(self):
        ws = WoundState(granulation_pct=80, epithelialization_pct=80,
                        necrosis_pct=0, slough_pct=0, infection_signs=True)
        score = ws.tissue_health_score()
        assert score < 100  # infecção reduz em 50%

    def test_tissue_health_score_range(self):
        ws = WoundState(granulation_pct=50, necrosis_pct=30, slough_pct=20)
        score = ws.tissue_health_score()
        assert 0 <= score <= 100


# ===================================================================
# PatientProfile
# ===================================================================

class TestPatientProfile:
    def test_bmi_calculation(self):
        p = PatientProfile(weight_kg=80, height_cm=175)
        bmi = p.bmi()
        assert abs(bmi - 26.12) < 0.1

    def test_bmi_zero_height(self):
        p = PatientProfile(weight_kg=80, height_cm=0)
        assert p.bmi() == 0.0

    def test_default_values(self):
        p = PatientProfile()
        assert p.mobility_level == "independent"
        assert p.diabetes is False
        assert p.caregiver_present is True


# ===================================================================
# HomeEnvironment
# ===================================================================

class TestHomeEnvironment:
    def test_defaults(self):
        env = HomeEnvironment()
        assert env.has_bathroom_adaptation is False
        assert env.room_temperature_c == 25.0
        assert env.accessibility_score == 0.0


# ===================================================================
# WoundHealingSimulator
# ===================================================================

class TestWoundHealingSimulator:
    @pytest.fixture
    def simulator(self):
        return WoundHealingSimulator()

    @pytest.fixture
    def healthy_patient(self):
        return PatientProfile(age=45, weight_kg=70, height_cm=170)

    @pytest.fixture
    def complex_patient(self):
        return PatientProfile(
            age=75, weight_kg=90, height_cm=165,
            diabetes=True, vascular_disease=True, smoking=True,
        )

    @pytest.fixture
    def sample_wound(self):
        return WoundState(area_cm2=20.0, granulation_pct=40, necrosis_pct=10)

    # --- estimate_healing_rate ---

    def test_base_rate_healthy(self, simulator, healthy_patient, sample_wound):
        rate = simulator.estimate_healing_rate(healthy_patient, sample_wound)
        assert rate > 0
        assert rate <= 0.5  # razoável

    def test_comorbidities_reduce_rate(self, simulator, healthy_patient, complex_patient, sample_wound):
        rate_h = simulator.estimate_healing_rate(healthy_patient, sample_wound)
        rate_c = simulator.estimate_healing_rate(complex_patient, sample_wound)
        assert rate_c < rate_h

    def test_infection_reduces_rate(self, simulator, healthy_patient):
        wound_clean = WoundState(area_cm2=15)
        wound_infected = WoundState(area_cm2=15, infection_signs=True)
        rate_clean = simulator.estimate_healing_rate(healthy_patient, wound_clean)
        rate_infected = simulator.estimate_healing_rate(healthy_patient, wound_infected)
        assert rate_infected < rate_clean

    def test_minimum_rate(self, simulator, complex_patient):
        """Mesmo com muitas comorbidades, taxa mínima é 1%/semana."""
        wound = WoundState(area_cm2=30, infection_signs=True)
        rate = simulator.estimate_healing_rate(complex_patient, wound)
        assert rate >= 0.01

    def test_treatments_boost_rate(self, simulator, healthy_patient, sample_wound):
        rate_no_tx = simulator.estimate_healing_rate(healthy_patient, sample_wound)
        rate_tx = simulator.estimate_healing_rate(
            healthy_patient, sample_wound,
            treatments=["compression_therapy", "negative_pressure"],
        )
        assert rate_tx > rate_no_tx

    # --- simulate_healing ---

    def test_simulate_returns_dict(self, simulator, healthy_patient, sample_wound):
        result = simulator.simulate_healing(healthy_patient, sample_wound, weeks=8)
        assert isinstance(result, dict)
        assert "trajectory" in result
        assert "healing_rate_per_week" in result
        assert "estimated_weeks_to_closure" in result

    def test_trajectory_length(self, simulator, healthy_patient, sample_wound):
        result = simulator.simulate_healing(healthy_patient, sample_wound, weeks=12)
        assert len(result["trajectory"]) == 13  # weeks 0..12

    def test_area_decreases_over_time(self, simulator, healthy_patient, sample_wound):
        result = simulator.simulate_healing(healthy_patient, sample_wound, weeks=8)
        areas = [t["area_cm2"] for t in result["trajectory"]]
        assert areas[0] >= areas[-1]

    def test_granulation_increases(self, simulator, healthy_patient, sample_wound):
        result = simulator.simulate_healing(healthy_patient, sample_wound, weeks=8)
        granulations = [t["granulation_pct"] for t in result["trajectory"]]
        assert granulations[-1] >= granulations[0]

    def test_necrosis_decreases(self, simulator, healthy_patient, sample_wound):
        result = simulator.simulate_healing(healthy_patient, sample_wound, weeks=8)
        necrosis = [t["necrosis_pct"] for t in result["trajectory"]]
        assert necrosis[-1] <= necrosis[0]

    # --- detect_stall ---

    def test_detect_stall_insufficient_data(self, simulator):
        result = simulator.detect_stall([WoundState(area_cm2=20)])
        assert result["stalled"] is False

    def test_detect_stall_healing(self, simulator):
        t0 = datetime.now() - timedelta(weeks=6)
        states = [
            WoundState(area_cm2=20, timestamp=t0.isoformat()),
            WoundState(area_cm2=10, timestamp=datetime.now().isoformat()),
        ]
        result = simulator.detect_stall(states)
        assert result["stalled"] is False

    def test_detect_stall_stalled(self, simulator):
        t0 = datetime.now() - timedelta(weeks=6)
        states = [
            WoundState(area_cm2=20, timestamp=t0.isoformat()),
            WoundState(area_cm2=19.5, timestamp=datetime.now().isoformat()),
        ]
        result = simulator.detect_stall(states)
        assert result["stalled"] is True


# ===================================================================
# PatientDigitalTwin
# ===================================================================

class TestPatientDigitalTwin:
    @pytest.fixture
    def twin(self):
        patient = PatientProfile(
            id="P001", age=65, sex="F",
            weight_kg=70, height_cm=160,
            diabetes=True,
        )
        return PatientDigitalTwin(patient)

    def test_init(self, twin):
        assert twin.patient.id == "P001"
        assert len(twin.wound_history) == 0

    def test_update_wound_state(self, twin):
        ws = WoundState(area_cm2=15)
        twin.update_wound_state(ws)
        assert len(twin.wound_history) == 1

    def test_set_environment(self, twin):
        env = HomeEnvironment(has_grab_bars=False)
        twin.set_environment(env)
        assert twin.environment is not None

    def test_environment_risk_assessment(self, twin):
        twin.patient.mobility_level = "assisted"
        env = HomeEnvironment(has_grab_bars=False)
        twin.set_environment(env)
        assert EnvironmentRisk.FALL_RISK in twin.environment.risk_factors
