"""
Testes unitários — ClinicalKnowledgeBase & ClinicalDecisionSupport (RAG)
"""
import pytest

from src.rag.clinical_rag import (
    ClinicalDecisionSupport,
    ClinicalKnowledgeBase,
    EvidenceLevel,
    KnowledgeCategory,
    KnowledgeEntry,
)


# ===================================================================
# Enums
# ===================================================================

class TestRAGEnums:
    def test_evidence_levels(self):
        assert len(EvidenceLevel) >= 8

    def test_knowledge_categories(self):
        assert len(KnowledgeCategory) >= 10
        assert KnowledgeCategory.WOUND_TREATMENT.value == "tratamento_feridas"


# ===================================================================
# KnowledgeEntry
# ===================================================================

class TestKnowledgeEntry:
    def test_default_entry(self):
        e = KnowledgeEntry(title="Test", content="Content")
        assert e.year == 2024
        assert isinstance(e.id, str)
        assert len(e.keywords) == 0

    def test_relevance_score_matching_keywords(self):
        e = KnowledgeEntry(
            title="Curativo Venosa",
            content="terapia compressiva para úlcera venosa",
            keywords=["venosa", "compressao", "terapia"],
        )
        score = e.relevance_score(["venosa", "compressao"])
        assert score > 0

    def test_relevance_score_no_match(self):
        e = KnowledgeEntry(
            title="Test", content="xyz",
            keywords=["abc", "def"],
        )
        score = e.relevance_score(["zzz", "yyy"])
        assert score == 0 or score < 0.1  # minimal

    def test_relevance_score_empty_query(self):
        e = KnowledgeEntry(title="Test", content="Content", keywords=["a"])
        assert e.relevance_score([]) == 0.0

    def test_relevance_score_empty_keywords(self):
        e = KnowledgeEntry(title="Test", content="Content")
        assert e.relevance_score(["query"]) == 0.0

    def test_evidence_bonus(self):
        """Nível de evidência 1a deve dar bonus."""
        e1 = KnowledgeEntry(
            title="Estudo", content="bla compressao venosa",
            keywords=["venosa"],
            evidence_level=EvidenceLevel.LEVEL_1A,
        )
        e5 = KnowledgeEntry(
            title="Estudo", content="bla compressao venosa",
            keywords=["venosa"],
            evidence_level=EvidenceLevel.LEVEL_5,
        )
        s1 = e1.relevance_score(["venosa"])
        s5 = e5.relevance_score(["venosa"])
        assert s1 > s5


# ===================================================================
# ClinicalKnowledgeBase
# ===================================================================

class TestClinicalKnowledgeBase:
    @pytest.fixture
    def kb(self):
        return ClinicalKnowledgeBase()

    def test_has_entries(self, kb):
        assert len(kb.entries) > 0

    def test_search_venosa(self, kb):
        results = kb.search("úlcera venosa compressão")
        assert len(results) > 0
        # Primeiro resultado deve ter alguma relevância
        entry, score = results[0]
        assert score > 0
        assert isinstance(entry, KnowledgeEntry)

    def test_search_diabetico(self, kb):
        results = kb.search("pé diabético neuropatia offloading")
        assert len(results) > 0

    def test_search_pressao(self, kb):
        results = kb.search("lesão pressão braden reposicionamento")
        assert len(results) > 0

    def test_search_esporotricose(self, kb):
        results = kb.search("esporotricose itraconazol")
        assert len(results) > 0

    def test_search_infeccao(self, kb):
        results = kb.search("infecção antimicrobiano prata")
        assert len(results) > 0

    def test_search_top_k(self, kb):
        results = kb.search("ferida tratamento", top_k=3)
        assert len(results) <= 3

    def test_search_no_results(self, kb):
        results = kb.search("xyznonexistentkeyword")
        # Pode retornar vazio ou com scores muito baixos
        assert isinstance(results, list)

    def test_search_by_category(self, kb):
        results = kb.search("venosa", category=KnowledgeCategory.VENOUS_ULCER)
        for entry, _ in results:
            assert entry.category == KnowledgeCategory.VENOUS_ULCER

    def test_get_by_icd10(self, kb):
        results = kb.get_by_icd10("L89")
        assert len(results) > 0
        for entry in results:
            assert any("L89" in code for code in entry.icd10_codes)

    def test_add_entry(self, kb):
        initial = len(kb.entries)
        kb.add_entry(KnowledgeEntry(title="Custom", content="Custom entry"))
        assert len(kb.entries) == initial + 1


# ===================================================================
# ClinicalDecisionSupport
# ===================================================================

class TestClinicalDecisionSupport:
    @pytest.fixture
    def cds(self):
        return ClinicalDecisionSupport()

    def test_init_has_knowledge_base(self, cds):
        assert isinstance(cds.knowledge_base, ClinicalKnowledgeBase)

    def test_get_wound_guidance_venosa(self, cds):
        result = cds.get_wound_guidance(
            "venosa",
            {"necrosis_pct": 5, "exudate_level": "moderate"},
        )
        assert "guidance" in result
        assert "references" in result
        assert "disclaimer" in result
        assert "specific_recommendations" in result
        assert len(result["guidance"]) > 0

    def test_get_wound_guidance_diabetica(self, cds):
        result = cds.get_wound_guidance(
            "diabetica",
            {"necrosis_pct": 25, "infection": True},
            patient_data={"diabetes": True},
        )
        assert len(result["specific_recommendations"]) > 0

    def test_specific_recs_for_infection(self, cds):
        result = cds.get_wound_guidance(
            "venosa",
            {"infection": True},
        )
        recs = result["specific_recommendations"]
        types = {r["type"] for r in recs}
        assert "infection" in types

    def test_specific_recs_for_necrosis(self, cds):
        result = cds.get_wound_guidance(
            "venosa",
            {"necrosis_pct": 30},
        )
        recs = result["specific_recommendations"]
        types = {r["type"] for r in recs}
        assert "tissue" in types

    def test_answer_clinical_question(self, cds):
        result = cds.answer_clinical_question("Como tratar úlcera venosa?")
        assert "answer" in result
        assert "confidence" in result
        assert result["confidence"] > 0

    def test_answer_question_no_results(self, cds):
        result = cds.answer_clinical_question("xyznonexistent12345")
        assert "answer" in result
        # Pode ter confiança zero
        assert isinstance(result["confidence"], float)

    def test_guidance_has_generated_at(self, cds):
        result = cds.get_wound_guidance("venosa", {})
        assert "generated_at" in result
