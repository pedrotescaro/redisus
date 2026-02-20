"""
HEAL/REDISUS - Módulo de Telemedicina e Teleconsulta
Teleconsulta estruturada para feridas e leitura de testes rápidos via smartphone.

Implementa:
- Sessões de teleconsulta estruturadas
- Captura remota de imagens de feridas
- Leitura de testes rápidos via câmera do smartphone (ex: esporotricose)
- Integração com RUTE/RNP (Rede Universitária de Telemedicina)
- Protocolos de encaminhamento por severidade
- Histórico e laudos de teleconsulta
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class SessionStatus(Enum):
    SCHEDULED = "agendada"
    WAITING = "aguardando"
    IN_PROGRESS = "em_andamento"
    COMPLETED = "concluida"
    CANCELLED = "cancelada"
    NO_SHOW = "nao_compareceu"


class SessionType(Enum):
    WOUND_ASSESSMENT = "avaliacao_ferida"
    FOLLOW_UP = "retorno"
    RAPID_TEST = "teste_rapido"
    URGENT_CONSULT = "consulta_urgente"
    SECOND_OPINION = "segunda_opiniao"
    EDUCATION = "orientacao_educativa"


class UrgencyLevel(Enum):
    ROUTINE = "rotina"
    PRIORITY = "prioritaria"
    URGENT = "urgente"
    EMERGENCY = "emergencia"


class RapidTestType(Enum):
    SPOROTRICHOSIS = "esporotricose"
    LEISHMANIASIS = "leishmaniose"
    DIABETES_FOOT_SCREEN = "rastreio_pe_diabetico"
    WOUND_CULTURE = "cultura_ferida"


@dataclass
class TeleconsultImage:
    """Imagem capturada durante teleconsulta"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    filename: str = ""
    capture_type: str = "wound"  # wound, rapid_test, document, environment
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    quality_score: float = 0.0  # 0-1
    metadata: Dict = field(default_factory=dict)
    ai_analysis: Optional[Dict] = None


@dataclass
class RapidTestResult:
    """Resultado de leitura de teste rápido via smartphone"""
    test_type: RapidTestType = RapidTestType.SPOROTRICHOSIS
    image_id: str = ""
    result: str = ""  # positive, negative, inconclusive
    confidence: float = 0.0
    control_line_detected: bool = False
    test_line_detected: bool = False
    reading_quality: str = "good"
    notes: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TeleconsultSession:
    """Sessão de teleconsulta"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    patient_id: str = ""
    professional_id: str = ""
    professional_name: str = ""
    professional_specialty: str = ""
    session_type: SessionType = SessionType.WOUND_ASSESSMENT
    status: SessionStatus = SessionStatus.SCHEDULED
    urgency: UrgencyLevel = UrgencyLevel.ROUTINE

    scheduled_at: str = ""
    started_at: str = ""
    ended_at: str = ""

    # Conteúdo clínico
    chief_complaint: str = ""
    clinical_history: str = ""
    exam_findings: str = ""
    ai_wound_analysis: Optional[Dict] = None
    images: List[TeleconsultImage] = field(default_factory=list)
    rapid_tests: List[RapidTestResult] = field(default_factory=list)

    # Conduta
    diagnosis_icd10: str = ""
    diagnosis_text: str = ""
    treatment_plan: str = ""
    prescriptions: List[str] = field(default_factory=list)
    referrals: List[str] = field(default_factory=list)
    follow_up_days: int = 0
    notes: str = ""

    # RUTE integration
    rute_session_id: str = ""


@dataclass
class RUTEConfig:
    """Configuração de integração com RUTE/RNP"""
    institution_id: str = ""
    institution_name: str = ""
    rute_endpoint: str = "https://rute.rnp.br/api/v1"
    video_endpoint: str = ""
    auth_token: str = ""


class TeleconsultManager:
    """
    Gerenciador de teleconsultas.
    Coordena sessões, imagens, testes rápidos e integração RUTE.
    """

    # Protocolos de encaminhamento por tipo de ferida
    REFERRAL_PROTOCOLS = {
        "venosa": {
            "primary": "Enfermeiro estomaterapeuta",
            "secondary": "Angiologista / Cirurgião vascular",
            "urgency_triggers": ["infeccao", "area_grande", "dor_intensa"],
        },
        "arterial": {
            "primary": "Angiologista / Cirurgião vascular",
            "secondary": "Cirurgião geral",
            "urgency_triggers": ["isquemia_critica", "necrose_extensa", "dor_repouso"],
        },
        "diabetica": {
            "primary": "Enfermeiro estomaterapeuta",
            "secondary": "Endocrinologista / Ortopedista",
            "urgency_triggers": ["osteomielite", "gangrena", "infeccao_profunda"],
        },
        "pressao": {
            "primary": "Enfermeiro estomaterapeuta",
            "secondary": "Cirurgião plástico",
            "urgency_triggers": ["necrose_profunda", "exposicao_ossea", "sepse"],
        },
        "esporotricose": {
            "primary": "Dermatologista / Infectologista",
            "secondary": "Cirurgião geral",
            "urgency_triggers": ["forma_disseminada", "imunocomprometimento", "falha_terapeutica"],
        },
    }

    def __init__(self, rute_config: Optional[RUTEConfig] = None):
        self.sessions: Dict[str, TeleconsultSession] = {}
        self.rute_config = rute_config or RUTEConfig()
        self._scheduled: List[str] = []  # session IDs ordenados por data

    def schedule_session(
        self,
        patient_id: str,
        professional_id: str,
        session_type: SessionType,
        urgency: UrgencyLevel = UrgencyLevel.ROUTINE,
        scheduled_at: Optional[str] = None,
        chief_complaint: str = "",
    ) -> TeleconsultSession:
        """Agenda teleconsulta"""
        if not scheduled_at:
            # Tempo de espera baseado na urgência
            if urgency == UrgencyLevel.EMERGENCY:
                delta = timedelta(minutes=15)
            elif urgency == UrgencyLevel.URGENT:
                delta = timedelta(hours=2)
            elif urgency == UrgencyLevel.PRIORITY:
                delta = timedelta(days=1)
            else:
                delta = timedelta(days=7)
            scheduled_at = (datetime.now() + delta).isoformat()

        session = TeleconsultSession(
            patient_id=patient_id,
            professional_id=professional_id,
            session_type=session_type,
            urgency=urgency,
            scheduled_at=scheduled_at,
            chief_complaint=chief_complaint,
        )
        self.sessions[session.id] = session
        self._scheduled.append(session.id)

        return session

    def start_session(self, session_id: str) -> Optional[TeleconsultSession]:
        """Inicia teleconsulta"""
        session = self.sessions.get(session_id)
        if not session:
            return None

        session.status = SessionStatus.IN_PROGRESS
        session.started_at = datetime.now().isoformat()
        return session

    def add_image(
        self,
        session_id: str,
        filename: str,
        capture_type: str = "wound",
        quality_score: float = 0.8,
        metadata: Optional[Dict] = None,
    ) -> Optional[TeleconsultImage]:
        """Adiciona imagem capturada à sessão"""
        session = self.sessions.get(session_id)
        if not session:
            return None

        image = TeleconsultImage(
            filename=filename,
            capture_type=capture_type,
            quality_score=quality_score,
            metadata=metadata or {},
        )
        session.images.append(image)
        return image

    def request_ai_analysis(self, session_id: str, image_id: str) -> Optional[Dict]:
        """
        Solicita análise de IA para imagem da teleconsulta.
        Integra com os módulos de detecção/diagnóstico existentes do REDISUS.
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        image = next((img for img in session.images if img.id == image_id), None)
        if not image:
            return None

        # Placeholder — em produção, integra com os módulos de visão computacional
        analysis = {
            "image_id": image_id,
            "wound_detected": True,
            "analysis_type": "teleconsult_remote",
            "message": (
                "Para análise completa de IA, a imagem deve ser processada "
                "pelo pipeline REDISUS (YOLO → U-Net → EfficientNet). "
                "Em modo teleconsulta, o profissional realiza avaliação visual assistida."
            ),
            "timestamp": datetime.now().isoformat(),
        }
        image.ai_analysis = analysis
        session.ai_wound_analysis = analysis

        return analysis

    def read_rapid_test(
        self,
        session_id: str,
        image_id: str,
        test_type: RapidTestType,
    ) -> Optional[RapidTestResult]:
        """
        Leitura de teste rápido via imagem capturada pelo smartphone.
        Particularmente útil para esporotricose em campo.

        Em produção, usa modelo de visão computacional para detectar
        linhas de controle e teste no cassete do teste rápido.
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        # Algoritmo de leitura (simplificado — em produção usa CNN)
        result = RapidTestResult(
            test_type=test_type,
            image_id=image_id,
            result="inconclusive",
            confidence=0.0,
            control_line_detected=True,
            test_line_detected=False,
            reading_quality="acceptable",
            notes=(
                "Leitura automatizada requer modelo treinado. "
                "Resultado deve ser confirmado pelo profissional de saúde."
            ),
        )

        session.rapid_tests.append(result)
        return result

    def complete_session(
        self,
        session_id: str,
        diagnosis_icd10: str = "",
        diagnosis_text: str = "",
        treatment_plan: str = "",
        prescriptions: Optional[List[str]] = None,
        referrals: Optional[List[str]] = None,
        follow_up_days: int = 0,
        notes: str = "",
    ) -> Optional[TeleconsultSession]:
        """Finaliza teleconsulta com conduta"""
        session = self.sessions.get(session_id)
        if not session:
            return None

        session.status = SessionStatus.COMPLETED
        session.ended_at = datetime.now().isoformat()
        session.diagnosis_icd10 = diagnosis_icd10
        session.diagnosis_text = diagnosis_text
        session.treatment_plan = treatment_plan
        session.prescriptions = prescriptions or []
        session.referrals = referrals or []
        session.follow_up_days = follow_up_days
        session.notes = notes

        return session

    def get_referral_recommendation(self, wound_etiology: str, triggers: List[str]) -> Dict:
        """
        Recomendação de encaminhamento baseada no protocolo por etiologia.
        """
        protocol = self.REFERRAL_PROTOCOLS.get(wound_etiology, {})
        if not protocol:
            return {
                "recommendation": "Encaminhamento para especialista estomaterapeuta",
                "urgency": "routine",
            }

        # Verificar triggers de urgência
        urgency_triggered = any(t in protocol.get("urgency_triggers", []) for t in triggers)

        return {
            "wound_etiology": wound_etiology,
            "primary_referral": protocol.get("primary", ""),
            "secondary_referral": protocol.get("secondary", ""),
            "urgency": "urgent" if urgency_triggered else "routine",
            "urgency_triggers_detected": [
                t for t in triggers if t in protocol.get("urgency_triggers", [])
            ],
            "recommendation": (
                f"Encaminhamento URGENTE para {protocol.get('secondary', 'especialista')}"
                if urgency_triggered
                else f"Acompanhamento com {protocol.get('primary', 'especialista')}"
            ),
        }

    def get_patient_sessions(
        self,
        patient_id: str,
        status: Optional[SessionStatus] = None,
    ) -> List[Dict]:
        """Lista teleconsultas do paciente"""
        results = []
        for s in self.sessions.values():
            if s.patient_id != patient_id:
                continue
            if status and s.status != status:
                continue
            results.append({
                "id": s.id,
                "type": s.session_type.value,
                "status": s.status.value,
                "urgency": s.urgency.value,
                "scheduled_at": s.scheduled_at,
                "professional": s.professional_name,
                "specialty": s.professional_specialty,
                "diagnosis": s.diagnosis_text,
                "images_count": len(s.images),
            })
        return results

    def generate_session_report(self, session_id: str) -> Optional[Dict]:
        """Gera relatório/laudo de teleconsulta"""
        s = self.sessions.get(session_id)
        if not s:
            return None

        duration_min = 0
        if s.started_at and s.ended_at:
            try:
                start = datetime.fromisoformat(s.started_at)
                end = datetime.fromisoformat(s.ended_at)
                duration_min = int((end - start).total_seconds() / 60)
            except (ValueError, TypeError):
                pass

        return {
            "session_id": s.id,
            "type": s.session_type.value,
            "status": s.status.value,
            "patient_id": s.patient_id,
            "professional": {
                "id": s.professional_id,
                "name": s.professional_name,
                "specialty": s.professional_specialty,
            },
            "schedule": {
                "scheduled_at": s.scheduled_at,
                "started_at": s.started_at,
                "ended_at": s.ended_at,
                "duration_minutes": duration_min,
            },
            "clinical_content": {
                "chief_complaint": s.chief_complaint,
                "clinical_history": s.clinical_history,
                "exam_findings": s.exam_findings,
                "diagnosis_icd10": s.diagnosis_icd10,
                "diagnosis_text": s.diagnosis_text,
            },
            "conduct": {
                "treatment_plan": s.treatment_plan,
                "prescriptions": s.prescriptions,
                "referrals": s.referrals,
                "follow_up_days": s.follow_up_days,
            },
            "images": [
                {
                    "id": img.id,
                    "type": img.capture_type,
                    "quality": img.quality_score,
                    "ai_analysis": img.ai_analysis is not None,
                }
                for img in s.images
            ],
            "rapid_tests": [
                {
                    "type": rt.test_type.value,
                    "result": rt.result,
                    "confidence": rt.confidence,
                }
                for rt in s.rapid_tests
            ],
            "notes": s.notes,
            "rute_session_id": s.rute_session_id,
            "generated_at": datetime.now().isoformat(),
        }

    def get_queue_summary(self) -> Dict:
        """Resumo da fila de teleconsultas"""
        by_status = {}
        by_urgency = {}

        for s in self.sessions.values():
            st = s.status.value
            by_status[st] = by_status.get(st, 0) + 1
            if s.status in (SessionStatus.SCHEDULED, SessionStatus.WAITING):
                urg = s.urgency.value
                by_urgency[urg] = by_urgency.get(urg, 0) + 1

        return {
            "total_sessions": len(self.sessions),
            "by_status": by_status,
            "waiting_by_urgency": by_urgency,
            "timestamp": datetime.now().isoformat(),
        }


class SporotrichosisScreening:
    """
    Módulo específico para triagem de esporotricose via telemedicina.
    A esporotricose é endêmica no Brasil com aumento de casos.
    O diagnóstico precoce via telemedicina permite acesso em áreas remotas.
    """

    # Critérios clínicos para suspeita de esporotricose
    CLINICAL_CRITERIA = {
        "major": [
            "Lesão nodular ou úlcera que não cicatriza após 2 semanas",
            "Lesões em padrão linfocutâneo (linha ascendente no membro)",
            "Contato com gato doente ou com lesões",
            "Contato com material vegetal (palha, feno, espinhos)",
        ],
        "minor": [
            "Área endêmica",
            "Profissão de risco (jardineiro, agricultor, veterinário)",
            "Lesão em membro superior ou face",
            "Febre ou sintomas sistêmicos associados",
        ],
    }

    # Formas clínicas
    CLINICAL_FORMS = {
        "cutanea_fixa": {
            "description": "Lesão única no local de inoculação",
            "severity": "leve",
            "treatment": "Itraconazol 100mg/dia por 3-6 meses",
        },
        "linfocutanea": {
            "description": "Lesão primária + nódulos ao longo do trajeto linfático",
            "severity": "moderada",
            "treatment": "Itraconazol 100mg/dia por 3-6 meses",
        },
        "cutanea_disseminada": {
            "description": "Lesões múltiplas sem padrão linfocutâneo",
            "severity": "grave",
            "treatment": "Itraconazol 200mg/dia ou Anfotericina B",
        },
        "extracutanea": {
            "description": "Comprometimento osteoarticular, pulmonar ou sistêmico",
            "severity": "grave",
            "treatment": "Anfotericina B + Itraconazol prolongado",
        },
    }

    def evaluate_screening(self, criteria_met: Dict[str, List[int]]) -> Dict:
        """
        Avalia critérios de triagem para esporotricose.

        Args:
            criteria_met: {"major": [indices], "minor": [indices]}

        Returns:
            Avaliação de suspeita e conduta recomendada
        """
        major_count = len(criteria_met.get("major", []))
        minor_count = len(criteria_met.get("minor", []))

        if major_count >= 2:
            suspicion = "alta"
            action = "Encaminhar para biópsia e cultura fúngica. Iniciar tratamento empírico."
        elif major_count == 1 and minor_count >= 2:
            suspicion = "moderada"
            action = "Encaminhar para avaliação dermatológica presencial. Solicitar exames."
        elif major_count == 1 or minor_count >= 3:
            suspicion = "baixa"
            action = "Monitorar evolução. Retorno em 7 dias se não houver melhora."
        else:
            suspicion = "improvavel"
            action = "Diagnóstico diferencial. Investigar outras etiologias."

        criteria_detail = {
            "major_met": [
                self.CLINICAL_CRITERIA["major"][i]
                for i in criteria_met.get("major", [])
                if i < len(self.CLINICAL_CRITERIA["major"])
            ],
            "minor_met": [
                self.CLINICAL_CRITERIA["minor"][i]
                for i in criteria_met.get("minor", [])
                if i < len(self.CLINICAL_CRITERIA["minor"])
            ],
        }

        return {
            "suspicion_level": suspicion,
            "major_criteria_met": major_count,
            "minor_criteria_met": minor_count,
            "criteria_detail": criteria_detail,
            "recommended_action": action,
            "clinical_forms": self.CLINICAL_FORMS,
            "note": (
                "Diagnóstico definitivo requer cultura fúngica (padrão-ouro) "
                "ou histopatologia com coloração especial."
            ),
        }

    def classify_clinical_form(
        self,
        single_lesion: bool,
        lymphocutaneous_pattern: bool,
        disseminated: bool,
        extracutaneous: bool,
    ) -> Dict:
        """Classifica a forma clínica da esporotricose"""
        if extracutaneous:
            form_key = "extracutanea"
        elif disseminated:
            form_key = "cutanea_disseminada"
        elif lymphocutaneous_pattern:
            form_key = "linfocutanea"
        else:
            form_key = "cutanea_fixa"

        form = self.CLINICAL_FORMS[form_key]
        return {
            "form": form_key,
            **form,
            "referral_needed": form["severity"] in ("grave",),
        }
