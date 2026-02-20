"""
HEAL/REDISUS - Cliente HL7 FHIR R4
Integração com padrões internacionais de interoperabilidade em saúde.

Implementa recursos FHIR R4:
- Patient (Paciente)
- Observation (Observação clínica)
- Condition (Condição/Diagnóstico)
- DiagnosticReport (Relatório diagnóstico)
- DocumentReference (Referência de documento)
- Media (Imagens clínicas)
- CarePlan (Plano de cuidado)
- Encounter (Encontro/Atendimento)
"""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger


class FHIRResourceBuilder:
    """
    Construtor de recursos FHIR R4 para o HEAL/REDISUS.
    Gera recursos JSON válidos no padrão HL7 FHIR R4.
    """

    FHIR_VERSION = "4.0.1"
    SYSTEM_URL = "https://heal.redisus.org.br"
    SNOMED_SYSTEM = "http://snomed.info/sct"
    LOINC_SYSTEM = "http://loinc.org"
    ICD10_SYSTEM = "http://hl7.org/fhir/sid/icd-10"

    # Mapeamento de etiologias para códigos SNOMED CT
    WOUND_SNOMED_CODES = {
        "VENOUS_ULCER": {"code": "404684003", "display": "Venous leg ulcer"},
        "ARTERIAL_ULCER": {"code": "238792006", "display": "Arterial ulcer"},
        "DIABETIC_FOOT": {"code": "280137006", "display": "Diabetic foot ulcer"},
        "PRESSURE_INJURY": {"code": "399912005", "display": "Pressure ulcer"},
        "SURGICAL_WOUND": {"code": "225552003", "display": "Surgical wound"},
    }

    # Mapeamento para ICD-10
    WOUND_ICD10_CODES = {
        "VENOUS_ULCER": {"code": "I83.0", "display": "Úlcera varicosa de membro inferior com úlcera"},
        "ARTERIAL_ULCER": {"code": "I70.2", "display": "Aterosclerose das artérias das extremidades"},
        "DIABETIC_FOOT": {"code": "E11.621", "display": "DM tipo 2 com úlcera de pé"},
        "PRESSURE_INJURY": {"code": "L89", "display": "Úlcera de decúbito"},
        "SURGICAL_WOUND": {"code": "T81.4", "display": "Infecção pós-procedimento"},
    }

    # Tecidos → LOINC codes
    TISSUE_LOINC_CODES = {
        "GRANULATION": {"code": "72514-3", "display": "Wound bed granulation tissue percentage"},
        "SLOUGH": {"code": "72287-6", "display": "Wound bed slough percentage"},
        "NECROSIS": {"code": "72288-4", "display": "Wound bed necrotic tissue percentage"},
    }

    def __init__(self, server_url: str = "https://hapi.fhir.org/baseR4"):
        """
        Args:
            server_url: URL do servidor FHIR (padrão: servidor público HAPI)
        """
        self.server_url = server_url
        logger.info(f"FHIRResourceBuilder inicializado — servidor: {server_url}")

    def _generate_id(self) -> str:
        """Gera um UUID para identificar o recurso"""
        return str(uuid.uuid4())

    def _now_fhir(self) -> str:
        """Data/hora no formato FHIR"""
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")

    # -------------------------------------------------------------------------
    # Patient
    # -------------------------------------------------------------------------
    def build_patient(
        self,
        patient_id: str,
        name: str,
        birth_date: Optional[str] = None,
        gender: str = "unknown",
        cpf: Optional[str] = None,
        cns: Optional[str] = None,
        address: Optional[Dict] = None,
        phone: Optional[str] = None,
    ) -> Dict:
        """
        Constrói recurso FHIR Patient.

        Args:
            patient_id: ID interno do paciente
            name: Nome completo
            birth_date: Data de nascimento (YYYY-MM-DD)
            gender: male|female|other|unknown
            cpf: CPF do paciente
            cns: Cartão Nacional de Saúde (CNS)
            address: Dict com line, city, state, postalCode
            phone: Telefone de contato
        """
        parts = name.split()
        family = parts[-1] if len(parts) > 1 else name
        given = parts[:-1] if len(parts) > 1 else [name]

        resource = {
            "resourceType": "Patient",
            "id": patient_id,
            "meta": {
                "profile": ["http://www.saude.gov.br/fhir/r4/StructureDefinition/BRIndividuo-1.0"],
                "lastUpdated": self._now_fhir(),
            },
            "identifier": [],
            "active": True,
            "name": [{
                "use": "official",
                "family": family,
                "given": given,
                "text": name,
            }],
            "gender": gender,
        }

        # CPF
        if cpf:
            resource["identifier"].append({
                "system": "https://saude.gov.br/fhir/r4/NamingSystem/cpf",
                "value": cpf,
            })

        # CNS (Cartão Nacional de Saúde)
        if cns:
            resource["identifier"].append({
                "system": "https://saude.gov.br/fhir/r4/NamingSystem/cns",
                "value": cns,
            })

        # ID HEAL
        resource["identifier"].append({
            "system": f"{self.SYSTEM_URL}/patient-id",
            "value": patient_id,
        })

        if birth_date:
            resource["birthDate"] = birth_date

        if phone:
            resource["telecom"] = [{
                "system": "phone",
                "value": phone,
                "use": "mobile",
            }]

        if address:
            resource["address"] = [{
                "use": "home",
                "type": "physical",
                "line": [address.get("line", "")],
                "city": address.get("city", ""),
                "state": address.get("state", ""),
                "postalCode": address.get("postalCode", ""),
                "country": "BR",
            }]

        return resource

    # -------------------------------------------------------------------------
    # Observation — Wound Analysis
    # -------------------------------------------------------------------------
    def build_wound_observation(
        self,
        patient_id: str,
        wound_data: Dict[str, Any],
        practitioner_id: Optional[str] = None,
    ) -> Dict:
        """
        Constrói recurso FHIR Observation para análise de ferida.

        Args:
            patient_id: ID do paciente
            wound_data: Dados da análise (tissue_percentages, area_cm2, etc.)
            practitioner_id: ID do profissional responsável
        """
        observation_id = self._generate_id()

        resource = {
            "resourceType": "Observation",
            "id": observation_id,
            "meta": {"lastUpdated": self._now_fhir()},
            "status": "final",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "exam",
                    "display": "Exam",
                }],
            }],
            "code": {
                "coding": [{
                    "system": self.LOINC_SYSTEM,
                    "code": "72170-4",
                    "display": "Wound assessment panel",
                }],
                "text": "Avaliação de ferida — HEAL/REDISUS",
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": self._now_fhir(),
            "issued": self._now_fhir(),
            "component": [],
        }

        if practitioner_id:
            resource["performer"] = [{"reference": f"Practitioner/{practitioner_id}"}]

        # Componentes: tecidos
        tissue_pcts = wound_data.get("tissue_percentages", {})
        for tissue_key, loinc in self.TISSUE_LOINC_CODES.items():
            pct = tissue_pcts.get(tissue_key, 0)
            resource["component"].append({
                "code": {
                    "coding": [{"system": self.LOINC_SYSTEM, **loinc}],
                },
                "valueQuantity": {
                    "value": round(pct, 1),
                    "unit": "%",
                    "system": "http://unitsofmeasure.org",
                    "code": "%",
                },
            })

        # Área da ferida
        area = wound_data.get("area_cm2")
        if area is not None:
            resource["component"].append({
                "code": {
                    "coding": [{
                        "system": self.LOINC_SYSTEM,
                        "code": "89260-9",
                        "display": "Wound area",
                    }],
                },
                "valueQuantity": {
                    "value": round(area, 2),
                    "unit": "cm2",
                    "system": "http://unitsofmeasure.org",
                    "code": "cm2",
                },
            })

        # Health score
        health_score = wound_data.get("health_score")
        if health_score is not None:
            resource["component"].append({
                "code": {
                    "coding": [{
                        "system": f"{self.SYSTEM_URL}/CodeSystem/wound-health-score",
                        "code": "wound-health-score",
                        "display": "Wound health score (HEAL)",
                    }],
                },
                "valueQuantity": {
                    "value": round(health_score, 1),
                    "unit": "score",
                },
            })

        # Confiança da IA
        confidence = wound_data.get("confidence")
        if confidence is not None:
            resource["component"].append({
                "code": {
                    "coding": [{
                        "system": f"{self.SYSTEM_URL}/CodeSystem/ai-confidence",
                        "code": "ai-confidence",
                        "display": "AI classification confidence",
                    }],
                },
                "valueQuantity": {
                    "value": round(confidence * 100, 1),
                    "unit": "%",
                },
            })

        return resource

    # -------------------------------------------------------------------------
    # Condition — Wound Diagnosis
    # -------------------------------------------------------------------------
    def build_wound_condition(
        self,
        patient_id: str,
        etiology: str,
        confidence: float,
        body_site: Optional[str] = None,
        onset_date: Optional[str] = None,
        risk_level: Optional[str] = None,
    ) -> Dict:
        """
        Constrói recurso FHIR Condition para diagnóstico de ferida.

        Args:
            patient_id: ID do paciente
            etiology: Tipo de etiologia (VENOUS_ULCER, etc.)
            confidence: Confiança da classificação (0-1)
            body_site: Local anatômico da ferida
            onset_date: Data de início da ferida (YYYY-MM-DD)
            risk_level: Nível de risco (baixo/moderado/alto/critico)
        """
        condition_id = self._generate_id()
        snomed = self.WOUND_SNOMED_CODES.get(etiology, {})
        icd10 = self.WOUND_ICD10_CODES.get(etiology, {})

        resource = {
            "resourceType": "Condition",
            "id": condition_id,
            "meta": {"lastUpdated": self._now_fhir()},
            "clinicalStatus": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active",
                }],
            },
            "verificationStatus": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    "code": "provisional" if confidence < 0.7 else "confirmed",
                }],
            },
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                    "code": "encounter-diagnosis",
                    "display": "Encounter Diagnosis",
                }],
            }],
            "severity": self._risk_to_severity(risk_level),
            "code": {
                "coding": [],
                "text": f"Ferida crônica — {etiology}",
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "recordedDate": self._now_fhir(),
        }

        # SNOMED CT
        if snomed:
            resource["code"]["coding"].append({
                "system": self.SNOMED_SYSTEM,
                **snomed,
            })

        # ICD-10
        if icd10:
            resource["code"]["coding"].append({
                "system": self.ICD10_SYSTEM,
                **icd10,
            })

        if body_site:
            resource["bodySite"] = [{
                "text": body_site,
            }]

        if onset_date:
            resource["onsetDateTime"] = onset_date

        # Extensão: confiança da IA
        resource["extension"] = [{
            "url": f"{self.SYSTEM_URL}/StructureDefinition/ai-confidence",
            "valueDecimal": round(confidence, 3),
        }]

        return resource

    def _risk_to_severity(self, risk_level: Optional[str]) -> Dict:
        """Converte nível de risco HEAL para severity FHIR"""
        mapping = {
            "baixo": {"code": "24484000", "display": "Severe"},
            "moderado": {"code": "6736007", "display": "Moderate"},
            "alto": {"code": "24484000", "display": "Severe"},
            "critico": {"code": "442452003", "display": "Life threatening severity"},
        }
        if not risk_level or risk_level not in mapping:
            return {"coding": [{"system": self.SNOMED_SYSTEM, "code": "6736007", "display": "Moderate"}]}

        sev = mapping[risk_level]
        return {"coding": [{"system": self.SNOMED_SYSTEM, **sev}]}

    # -------------------------------------------------------------------------
    # DiagnosticReport
    # -------------------------------------------------------------------------
    def build_diagnostic_report(
        self,
        patient_id: str,
        observation_ids: List[str],
        condition_id: Optional[str] = None,
        conclusion: str = "",
        practitioner_id: Optional[str] = None,
    ) -> Dict:
        """
        Constrói recurso FHIR DiagnosticReport para relatório completo.
        """
        report_id = self._generate_id()

        resource = {
            "resourceType": "DiagnosticReport",
            "id": report_id,
            "meta": {"lastUpdated": self._now_fhir()},
            "status": "final",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                    "code": "IMG",
                    "display": "Diagnostic Imaging",
                }],
            }],
            "code": {
                "coding": [{
                    "system": self.LOINC_SYSTEM,
                    "code": "72170-4",
                    "display": "Wound assessment panel",
                }],
                "text": "Relatório de avaliação de ferida — HEAL/REDISUS",
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": self._now_fhir(),
            "issued": self._now_fhir(),
            "result": [{"reference": f"Observation/{oid}"} for oid in observation_ids],
            "conclusion": conclusion,
        }

        if practitioner_id:
            resource["performer"] = [{"reference": f"Practitioner/{practitioner_id}"}]

        if condition_id:
            resource["conclusionCode"] = [{
                "coding": [{
                    "system": f"{self.SYSTEM_URL}/CodeSystem/wound-diagnosis",
                    "code": condition_id,
                }],
            }]

        return resource

    # -------------------------------------------------------------------------
    # CarePlan
    # -------------------------------------------------------------------------
    def build_care_plan(
        self,
        patient_id: str,
        title: str,
        activities: List[Dict[str, str]],
        condition_id: Optional[str] = None,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
    ) -> Dict:
        """
        Constrói recurso FHIR CarePlan para plano de cuidado.

        Args:
            patient_id: ID do paciente
            title: Título do plano
            activities: Lista de atividades [{"description": str, "frequency": str}]
            condition_id: ID da condição associada
            period_start: Início do plano (YYYY-MM-DD)
            period_end: Fim do plano (YYYY-MM-DD)
        """
        plan_id = self._generate_id()

        resource = {
            "resourceType": "CarePlan",
            "id": plan_id,
            "meta": {"lastUpdated": self._now_fhir()},
            "status": "active",
            "intent": "plan",
            "title": title,
            "description": f"Plano de cuidado gerado pelo HEAL/REDISUS — {title}",
            "subject": {"reference": f"Patient/{patient_id}"},
            "created": self._now_fhir(),
            "activity": [],
        }

        if condition_id:
            resource["addresses"] = [{"reference": f"Condition/{condition_id}"}]

        if period_start:
            resource["period"] = {"start": period_start}
            if period_end:
                resource["period"]["end"] = period_end

        for act in activities:
            resource["activity"].append({
                "detail": {
                    "status": "not-started",
                    "description": act.get("description", ""),
                    "scheduledString": act.get("frequency", "Conforme prescrição"),
                },
            })

        return resource

    # -------------------------------------------------------------------------
    # Media — Clinical Image
    # -------------------------------------------------------------------------
    def build_media_resource(
        self,
        patient_id: str,
        image_path: str,
        content_type: str = "image/jpeg",
        body_site: Optional[str] = None,
        note: str = "",
    ) -> Dict:
        """
        Constrói recurso FHIR Media para imagem clínica.
        """
        media_id = self._generate_id()
        import base64
        from pathlib import Path

        # Codifica imagem em base64
        data_b64 = ""
        img_path = Path(image_path)
        if img_path.exists():
            with open(img_path, "rb") as f:
                data_b64 = base64.b64encode(f.read()).decode("utf-8")

        resource = {
            "resourceType": "Media",
            "id": media_id,
            "meta": {"lastUpdated": self._now_fhir()},
            "status": "completed",
            "type": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/media-type",
                    "code": "photo",
                    "display": "Photo",
                }],
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "createdDateTime": self._now_fhir(),
            "content": {
                "contentType": content_type,
                "data": data_b64[:100] + "..." if len(data_b64) > 100 else data_b64,
                "title": f"Imagem clínica — {img_path.name}",
            },
        }

        if body_site:
            resource["bodySite"] = {"text": body_site}

        if note:
            resource["note"] = [{"text": note}]

        return resource

    # -------------------------------------------------------------------------
    # Bundle — FHIR Transaction
    # -------------------------------------------------------------------------
    def build_transaction_bundle(
        self,
        resources: List[Dict],
    ) -> Dict:
        """
        Agrupa múltiplos recursos em um FHIR Bundle do tipo transaction.
        """
        return {
            "resourceType": "Bundle",
            "type": "transaction",
            "timestamp": self._now_fhir(),
            "entry": [
                {
                    "resource": res,
                    "request": {
                        "method": "PUT",
                        "url": f"{res['resourceType']}/{res['id']}",
                    },
                }
                for res in resources
            ],
        }

    # -------------------------------------------------------------------------
    # Exportação completa de análise
    # -------------------------------------------------------------------------
    def export_analysis_as_fhir(
        self,
        patient_data: Dict,
        wound_data: Dict,
        treatment_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Exporta uma análise completa de ferida como Bundle FHIR.

        Args:
            patient_data: Dados do paciente (id, name, birth_date, etc.)
            wound_data: Dados da análise (etiology, tissue_percentages, etc.)
            treatment_data: Dados do tratamento/plano de cuidado

        Returns:
            Bundle FHIR contendo todos os recursos
        """
        resources = []

        # Patient
        patient = self.build_patient(
            patient_id=patient_data.get("id", self._generate_id()),
            name=patient_data.get("name", "Paciente"),
            birth_date=patient_data.get("birth_date"),
            cpf=patient_data.get("cpf"),
            cns=patient_data.get("cns"),
        )
        resources.append(patient)

        # Observation
        observation = self.build_wound_observation(
            patient_id=patient["id"],
            wound_data=wound_data,
        )
        resources.append(observation)

        # Condition
        etiology = wound_data.get("etiology", "VENOUS_ULCER")
        confidence = wound_data.get("confidence", 0.5)
        condition = self.build_wound_condition(
            patient_id=patient["id"],
            etiology=etiology,
            confidence=confidence,
            risk_level=wound_data.get("risk_level"),
        )
        resources.append(condition)

        # DiagnosticReport
        report = self.build_diagnostic_report(
            patient_id=patient["id"],
            observation_ids=[observation["id"]],
            condition_id=condition["id"],
            conclusion=wound_data.get("conclusion", ""),
        )
        resources.append(report)

        # CarePlan (se houver tratamento)
        if treatment_data:
            activities = [
                {"description": step, "frequency": "Conforme prescrição"}
                for step in treatment_data.get("steps", [])
            ]
            care_plan = self.build_care_plan(
                patient_id=patient["id"],
                title=treatment_data.get("title", "Plano de Cuidado da Ferida"),
                activities=activities,
                condition_id=condition["id"],
            )
            resources.append(care_plan)

        bundle = self.build_transaction_bundle(resources)
        logger.info(
            f"Exportação FHIR gerada: {len(resources)} recursos em bundle "
            f"para paciente {patient['id']}"
        )
        return bundle


class FHIRClient:
    """
    Cliente HTTP para comunicação com servidores FHIR R4.
    Suporta operações CRUD e busca de recursos.
    """

    def __init__(self, server_url: str = "https://hapi.fhir.org/baseR4"):
        self.server_url = server_url.rstrip("/")
        self.builder = FHIRResourceBuilder(server_url)
        self._headers = {
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json",
        }
        logger.info(f"FHIRClient inicializado — servidor: {server_url}")

    def send_bundle(self, bundle: Dict) -> Dict:
        """
        Envia um Bundle FHIR para o servidor.
        Retorna resposta do servidor ou erro.
        """
        try:
            import requests
            response = requests.post(
                self.server_url,
                json=bundle,
                headers=self._headers,
                timeout=30,
            )
            response.raise_for_status()
            logger.info(f"Bundle FHIR enviado com sucesso — status {response.status_code}")
            return response.json()
        except ImportError:
            logger.warning("Módulo 'requests' não disponível — exportação apenas local")
            return {"status": "local_only", "bundle": bundle}
        except Exception as e:
            logger.error(f"Erro ao enviar Bundle FHIR: {e}")
            return {"status": "error", "message": str(e)}

    def get_patient(self, patient_id: str) -> Optional[Dict]:
        """Busca paciente por ID no servidor FHIR"""
        try:
            import requests
            r = requests.get(
                f"{self.server_url}/Patient/{patient_id}",
                headers=self._headers,
                timeout=15,
            )
            if r.status_code == 200:
                return r.json()
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar Patient/{patient_id}: {e}")
            return None

    def search_patients(self, name: Optional[str] = None, identifier: Optional[str] = None) -> List[Dict]:
        """Busca pacientes no servidor FHIR"""
        try:
            import requests
            params = {}
            if name:
                params["name"] = name
            if identifier:
                params["identifier"] = identifier

            r = requests.get(
                f"{self.server_url}/Patient",
                params=params,
                headers=self._headers,
                timeout=15,
            )
            if r.status_code == 200:
                bundle = r.json()
                return [e["resource"] for e in bundle.get("entry", [])]
            return []
        except Exception as e:
            logger.error(f"Erro na busca de pacientes: {e}")
            return []

    def export_to_file(self, bundle: Dict, output_path: str) -> str:
        """Exporta Bundle FHIR para arquivo JSON"""
        from pathlib import Path
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2, ensure_ascii=False)
        logger.info(f"Bundle FHIR exportado para {path}")
        return str(path)
