"""
Testes unitários — TreatmentRecommender & TreatmentKnowledgeBase
"""
import pytest

from src.core.config import EtiologyType, TissueType, TISSUE_NAMES, ETIOLOGY_NAMES
from src.treatment.recommender import (
    TreatmentKnowledgeBase,
    TreatmentProtocol,
    TreatmentRecommendation,
    TreatmentRecommender,
    TreatmentStep,
)


# ===================================================================
# TreatmentStep
# ===================================================================

class TestTreatmentStep:
    def test_basic_creation(self):
        step = TreatmentStep(
            order=1, action="Limpeza",
            description="Irrigar com SF 0.9%",
            products=["SF 0.9%"], frequency="A cada troca",
        )
        assert step.order == 1
        assert step.notes is None


# ===================================================================
# TreatmentProtocol
# ===================================================================

class TestTreatmentProtocol:
    @pytest.fixture
    def sample_protocol(self):
        return TreatmentProtocol(
            name="Protocolo Teste",
            etiology="Teste",
            objective="Testar",
            steps=[
                TreatmentStep(order=1, action="A1", description="D1",
                              products=["P1"], frequency="F1"),
            ],
            contraindications=["C1"],
            monitoring=["M1"],
            expected_outcome="OK",
            evidence_level="B",
            references=["Ref1"],
        )

    def test_to_dict(self, sample_protocol):
        d = sample_protocol.to_dict()
        assert d["name"] == "Protocolo Teste"
        assert len(d["steps"]) == 1
        assert d["steps"][0]["order"] == 1
        assert d["evidence_level"] == "B"

    def test_get_summary_contains_name(self, sample_protocol):
        s = sample_protocol.get_summary()
        assert "Protocolo Teste" in s
        assert "Testar" in s


# ===================================================================
# TreatmentKnowledgeBase
# ===================================================================

class TestTreatmentKnowledgeBase:
    @pytest.fixture
    def kb(self):
        return TreatmentKnowledgeBase()

    def test_all_etiologies_have_protocol(self, kb):
        for et in EtiologyType:
            protocol = kb.get_protocol(et)
            assert protocol is not None, f"Sem protocolo para {et}"
            assert isinstance(protocol, TreatmentProtocol)

    def test_venous_protocol_details(self, kb):
        p = kb.get_protocol(EtiologyType.VENOUS_ULCER)
        assert "Venosa" in p.name
        assert p.evidence_level == "A"
        assert len(p.steps) >= 3

    def test_arterial_protocol_details(self, kb):
        p = kb.get_protocol(EtiologyType.ARTERIAL_ULCER)
        assert "Arterial" in p.name
        assert any("compressiva" in c.lower() for c in p.contraindications)

    def test_diabetic_protocol_details(self, kb):
        p = kb.get_protocol(EtiologyType.DIABETIC_FOOT)
        assert "Diabético" in p.name
        assert p.evidence_level == "A"

    def test_pressure_protocol_details(self, kb):
        p = kb.get_protocol(EtiologyType.PRESSURE_INJURY)
        assert "Pressão" in p.name

    def test_surgical_protocol_details(self, kb):
        p = kb.get_protocol(EtiologyType.SURGICAL_WOUND)
        assert "Cirúrgica" in p.name

    def test_tissue_actions_exist(self, kb):
        for tt in [TissueType.GRANULATION, TissueType.SLOUGH, TissueType.NECROSIS, TissueType.PERIWOUND]:
            action = kb.get_tissue_action(tt)
            assert isinstance(action, str)
            assert len(action) > 0

    def test_unknown_tissue_returns_generic(self, kb):
        action = kb.get_tissue_action(TissueType.BACKGROUND)
        assert isinstance(action, str)

    def test_invalid_etiology_returns_none(self, kb):
        result = kb.get_protocol("nonexistent")
        assert result is None


# ===================================================================
# TreatmentRecommender
# ===================================================================

class TestTreatmentRecommender:
    @pytest.fixture
    def recommender(self):
        return TreatmentRecommender()

    def test_recommend_returns_recommendation(self, recommender, sample_tissue_percentages):
        rec = recommender.recommend(
            EtiologyType.VENOUS_ULCER,
            sample_tissue_percentages,
            confidence=0.85,
        )
        assert isinstance(rec, TreatmentRecommendation)
        assert isinstance(rec.primary_protocol, TreatmentProtocol)
        assert rec.priority_level in {"urgent", "high", "moderate", "low"}
        assert rec.follow_up_days > 0

    def test_recommend_all_etiologies(self, recommender, sample_tissue_percentages):
        for et in EtiologyType:
            rec = recommender.recommend(et, sample_tissue_percentages, 0.9)
            assert isinstance(rec, TreatmentRecommendation)

    def test_tissue_specific_actions_populated(self, recommender, sample_tissue_percentages):
        rec = recommender.recommend(
            EtiologyType.VENOUS_ULCER,
            sample_tissue_percentages,
        )
        # Ações para tecidos com > 5%
        assert isinstance(rec.tissue_specific_actions, dict)


# ===================================================================
# Priority determination
# ===================================================================

class TestPriorityDetermination:
    @pytest.fixture
    def recommender(self):
        return TreatmentRecommender()

    def test_high_necrosis_is_urgent(self, recommender):
        tissue = {TISSUE_NAMES[TissueType.NECROSIS.value]: 50.0}
        rec = recommender.recommend(EtiologyType.VENOUS_ULCER, tissue, 0.9)
        assert rec.priority_level == "urgent"

    def test_arterial_is_high(self, recommender, sample_tissue_percentages):
        rec = recommender.recommend(EtiologyType.ARTERIAL_ULCER, sample_tissue_percentages, 0.9)
        assert rec.priority_level == "high"

    def test_diabetic_with_necrosis_is_high(self, recommender):
        tissue = {
            TISSUE_NAMES[TissueType.NECROSIS.value]: 15.0,
            TISSUE_NAMES[TissueType.GRANULATION.value]: 50.0,
        }
        rec = recommender.recommend(EtiologyType.DIABETIC_FOOT, tissue, 0.9)
        assert rec.priority_level == "high"

    def test_good_granulation_is_moderate(self, recommender):
        tissue = {
            TISSUE_NAMES[TissueType.GRANULATION.value]: 70.0,
            TISSUE_NAMES[TissueType.NECROSIS.value]: 2.0,
            TISSUE_NAMES[TissueType.SLOUGH.value]: 5.0,
        }
        rec = recommender.recommend(EtiologyType.VENOUS_ULCER, tissue, 0.9)
        assert rec.priority_level == "moderate"


# ===================================================================
# Follow-up days
# ===================================================================

class TestFollowUp:
    @pytest.fixture
    def recommender(self):
        return TreatmentRecommender()

    def test_urgent_follow_up_1_day(self, recommender):
        tissue = {TISSUE_NAMES[TissueType.NECROSIS.value]: 50.0}
        rec = recommender.recommend(EtiologyType.VENOUS_ULCER, tissue, 0.9)
        assert rec.follow_up_days == 1

    def test_moderate_follow_up_7_days(self, recommender):
        tissue = {
            TISSUE_NAMES[TissueType.GRANULATION.value]: 70.0,
            TISSUE_NAMES[TissueType.NECROSIS.value]: 2.0,
            TISSUE_NAMES[TissueType.SLOUGH.value]: 5.0,
        }
        rec = recommender.recommend(EtiologyType.VENOUS_ULCER, tissue, 0.9)
        assert rec.follow_up_days == 7


# ===================================================================
# Additional notes
# ===================================================================

class TestAdditionalNotes:
    @pytest.fixture
    def recommender(self):
        return TreatmentRecommender()

    def test_low_confidence_generates_note(self, recommender, sample_tissue_percentages):
        rec = recommender.recommend(EtiologyType.VENOUS_ULCER, sample_tissue_percentages, 0.5)
        assert any("baixa confiança" in n.lower() or "avaliação" in n.lower() for n in rec.additional_notes)

    def test_high_necrosis_generates_note(self, recommender):
        tissue = {TISSUE_NAMES[TissueType.NECROSIS.value]: 40.0}
        rec = recommender.recommend(EtiologyType.VENOUS_ULCER, tissue, 0.9)
        assert any("necrótico" in n.lower() or "desbridamento" in n.lower() for n in rec.additional_notes)

    def test_high_granulation_generates_positive_note(self, recommender):
        tissue = {TISSUE_NAMES[TissueType.GRANULATION.value]: 80.0}
        rec = recommender.recommend(EtiologyType.VENOUS_ULCER, tissue, 0.9)
        assert any("granulação" in n.lower() or "evolução" in n.lower() for n in rec.additional_notes)
