"""
Testes unitários — FHIRResourceBuilder (Interoperability)
"""
import pytest

from src.interoperability.fhir_client import FHIRResourceBuilder


class TestFHIRResourceBuilderInit:
    def test_default_init(self):
        b = FHIRResourceBuilder()
        assert "fhir" in b.server_url.lower()
        assert b.FHIR_VERSION == "4.0.1"

    def test_custom_server(self):
        b = FHIRResourceBuilder(server_url="http://localhost:8080/fhir")
        assert b.server_url == "http://localhost:8080/fhir"


class TestBuildPatient:
    @pytest.fixture
    def builder(self):
        return FHIRResourceBuilder()

    def test_basic_patient(self, builder):
        p = builder.build_patient("P001", "Maria Silva")
        assert p["resourceType"] == "Patient"
        assert p["id"] == "P001"
        assert p["active"] is True
        assert p["name"][0]["text"] == "Maria Silva"
        assert p["name"][0]["family"] == "Silva"
        assert p["name"][0]["given"] == ["Maria"]

    def test_patient_with_cpf(self, builder):
        p = builder.build_patient("P002", "João", cpf="12345678901")
        ids = {i["system"]: i["value"] for i in p["identifier"]}
        assert "12345678901" in ids.values()

    def test_patient_with_cns(self, builder):
        p = builder.build_patient("P003", "Ana", cns="700000000000001")
        ids = {i["system"]: i["value"] for i in p["identifier"]}
        assert "700000000000001" in ids.values()

    def test_patient_gender(self, builder):
        p = builder.build_patient("P004", "Carlos", gender="male")
        assert p["gender"] == "male"

    def test_patient_birthdate(self, builder):
        p = builder.build_patient("P005", "Luiza", birth_date="1990-05-15")
        assert p["birthDate"] == "1990-05-15"

    def test_patient_address(self, builder):
        addr = {"line": "Rua A 123", "city": "São Paulo", "state": "SP", "postalCode": "01000-000"}
        p = builder.build_patient("P006", "Pedro", address=addr)
        assert p["address"][0]["city"] == "São Paulo"
        assert p["address"][0]["country"] == "BR"

    def test_patient_phone(self, builder):
        p = builder.build_patient("P007", "Julia", phone="11999887766")
        assert p["telecom"][0]["value"] == "11999887766"


class TestBuildWoundObservation:
    @pytest.fixture
    def builder(self):
        return FHIRResourceBuilder()

    def test_basic_observation(self, builder):
        obs = builder.build_wound_observation("P001", {"tissue_percentages": {"GRANULATION": 60}})
        assert obs["resourceType"] == "Observation"
        assert obs["status"] == "final"
        assert obs["subject"]["reference"] == "Patient/P001"

    def test_observation_components(self, builder):
        wound_data = {
            "tissue_percentages": {"GRANULATION": 60, "NECROSIS": 10},
            "area_cm2": 15.5,
            "health_score": 72.0,
            "confidence": 0.85,
        }
        obs = builder.build_wound_observation("P001", wound_data)
        # Should have components for tissue, area, health_score, confidence
        assert len(obs["component"]) >= 4

    def test_observation_with_practitioner(self, builder):
        obs = builder.build_wound_observation("P001", {}, practitioner_id="PRACT01")
        assert obs["performer"][0]["reference"] == "Practitioner/PRACT01"

    def test_area_component_units(self, builder):
        obs = builder.build_wound_observation("P001", {"area_cm2": 25.0})
        area_components = [c for c in obs["component"]
                          if any(cod.get("code") == "89260-9"
                                for cod in c["code"]["coding"])]
        assert len(area_components) == 1
        assert area_components[0]["valueQuantity"]["unit"] == "cm2"
        assert area_components[0]["valueQuantity"]["value"] == 25.0


class TestBuildWoundCondition:
    @pytest.fixture
    def builder(self):
        return FHIRResourceBuilder()

    def test_basic_condition(self, builder):
        cond = builder.build_wound_condition("P001", "VENOUS_ULCER", 0.85)
        assert cond["resourceType"] == "Condition"
        assert cond["subject"]["reference"] == "Patient/P001"

    def test_condition_snomed_code(self, builder):
        cond = builder.build_wound_condition("P001", "VENOUS_ULCER", 0.9)
        codings = cond.get("code", {}).get("coding", [])
        snomed_codes = [c for c in codings if "snomed" in c.get("system", "").lower()]
        assert len(snomed_codes) > 0

    def test_unknown_etiology_no_crash(self, builder):
        """Uma etiologia desconhecida não deve gerar exceção."""
        cond = builder.build_wound_condition("P001", "NONEXISTENT", 0.5)
        assert cond["resourceType"] == "Condition"


class TestSNOMEDMappings:
    def test_all_etiologies_mapped(self):
        expected = {"VENOUS_ULCER", "ARTERIAL_ULCER", "DIABETIC_FOOT",
                    "PRESSURE_INJURY", "SURGICAL_WOUND"}
        assert set(FHIRResourceBuilder.WOUND_SNOMED_CODES.keys()) == expected

    def test_icd10_mapped(self):
        assert len(FHIRResourceBuilder.WOUND_ICD10_CODES) >= 5

    def test_loinc_tissue_codes(self):
        assert "GRANULATION" in FHIRResourceBuilder.TISSUE_LOINC_CODES
        assert "NECROSIS" in FHIRResourceBuilder.TISSUE_LOINC_CODES
