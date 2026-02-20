"""
HEAL/REDISUS - Framework de Validação Clínica e Maturidade Tecnológica (TRL)
Protocolos de validação, rastreamento de TRL e framework de pilotos multicêntricos.

Implementa:
- TRL Tracker (Technology Readiness Level) — atualmente TRL 4-5
- Protocolo de validação clínica
- Framework para pilotos multicêntricos SUS
- Métricas de desempenho do sistema
- Conformidade regulatória (ANVISA, LGPD, CFM)
- Rastreamento de indicadores de impacto
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TRLevel(Enum):
    """Technology Readiness Levels (NASA/EU adaptado para saúde)"""
    TRL1 = 1   # Pesquisa básica
    TRL2 = 2   # Conceito formulado
    TRL3 = 3   # Prova de conceito experimental
    TRL4 = 4   # Validação em laboratório
    TRL5 = 5   # Validação em ambiente relevante
    TRL6 = 6   # Demonstração em ambiente relevante
    TRL7 = 7   # Demonstração em ambiente operacional
    TRL8 = 8   # Sistema completo e qualificado
    TRL9 = 9   # Sistema operacional em produção


class ValidationStatus(Enum):
    PLANNED = "planejado"
    IN_PROGRESS = "em_andamento"
    COMPLETED = "concluido"
    FAILED = "falhou"
    PAUSED = "pausado"


class RegulatoryBody(Enum):
    ANVISA = "ANVISA"
    CFM = "CFM"
    COFEN = "COFEN"
    LGPD = "LGPD"
    CEP_CONEP = "CEP/CONEP"
    MS = "Ministerio_da_Saude"


@dataclass
class TRLMilestone:
    """Marco de maturidade tecnológica"""
    trl: TRLevel
    description: str
    criteria: List[str]
    status: ValidationStatus = ValidationStatus.PLANNED
    achieved_date: str = ""
    evidence: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class ValidationMetric:
    """Métrica de validação"""
    name: str
    value: float
    target: float
    unit: str = ""
    category: str = ""
    achieved: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class PilotSite:
    """Local de piloto"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    city: str = ""
    state: str = ""
    institution_type: str = ""  # UBS, Hospital, NASF
    cnes_code: str = ""
    team_size: int = 0
    patients_enrolled: int = 0
    start_date: str = ""
    status: ValidationStatus = ValidationStatus.PLANNED
    contact_name: str = ""
    contact_email: str = ""


@dataclass
class ClinicalTrialProtocol:
    """Protocolo de estudo clínico/validação"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    version: str = "1.0"
    study_type: str = ""  # observacional, quase-experimental, ECR
    primary_objective: str = ""
    secondary_objectives: List[str] = field(default_factory=list)
    inclusion_criteria: List[str] = field(default_factory=list)
    exclusion_criteria: List[str] = field(default_factory=list)
    sample_size: int = 0
    duration_months: int = 0
    primary_outcome: str = ""
    secondary_outcomes: List[str] = field(default_factory=list)
    ethical_approval: str = ""
    cep_number: str = ""
    status: ValidationStatus = ValidationStatus.PLANNED


class TRLTracker:
    """
    Rastreador de Maturidade Tecnológica (TRL) para o HEAL/REDISUS.
    Mapeia o estado atual e próximos passos para evolução tecnológica.
    """

    def __init__(self):
        self.milestones: List[TRLMilestone] = self._initialize_milestones()
        self.current_trl = TRLevel.TRL4

    def _initialize_milestones(self) -> List[TRLMilestone]:
        """Inicializa marcos TRL para o HEAL/REDISUS"""
        return [
            TRLMilestone(
                trl=TRLevel.TRL1,
                description="Pesquisa básica em visão computacional para feridas",
                criteria=[
                    "Revisão de literatura em detecção de feridas por IA",
                    "Identificação de técnicas aplicáveis (YOLO, U-Net, EfficientNet)",
                    "Definição de requisitos de saúde digital SUS",
                ],
                status=ValidationStatus.COMPLETED,
                achieved_date="2023-06-01",
                evidence=["Artigos publicados", "Revisão sistemática realizada"],
            ),
            TRLMilestone(
                trl=TRLevel.TRL2,
                description="Formulação do conceito HEAL integrado",
                criteria=[
                    "Arquitetura dos 5 eixos definida",
                    "Casos de uso mapeados",
                    "Interoperabilidade FHIR R4 planejada",
                ],
                status=ValidationStatus.COMPLETED,
                achieved_date="2023-09-01",
                evidence=["Canvas HEAL", "Pitch documentado", "Diagrama de arquitetura"],
            ),
            TRLMilestone(
                trl=TRLevel.TRL3,
                description="Prova de conceito: detecção e classificação de feridas",
                criteria=[
                    "Protótipo funcional de detecção de feridas via câmera",
                    "Classificação de etiologia com >40% acurácia",
                    "Pipeline YOLO →  U-Net → EfficientNet validado em lab",
                ],
                status=ValidationStatus.COMPLETED,
                achieved_date="2024-01-01",
                evidence=[
                    "Modelo YOLO treinado",
                    "U-Net de segmentação funcional",
                    "EfficientNet com 44.3% acurácia",
                ],
            ),
            TRLMilestone(
                trl=TRLevel.TRL4,
                description="Validação em laboratório: plataforma integrada",
                criteria=[
                    "App desktop funcional com detecção em tempo real",
                    "Módulos de diagnóstico, tratamento e exportação",
                    "Interoperabilidade HL7 FHIR implementada",
                    "Dashboard clínico operacional",
                    "Módulos HEAL (5 eixos) implementados",
                ],
                status=ValidationStatus.IN_PROGRESS,
                evidence=[
                    "realtime_app.py operacional",
                    "Módulos de vigilância, telemedicina, digital twin",
                    "Integração e-SUS/DATASUS",
                    "Dashboard Flask funcional",
                ],
            ),
            TRLMilestone(
                trl=TRLevel.TRL5,
                description="Validação em ambiente relevante (UBS piloto)",
                criteria=[
                    "Piloto em pelo menos 1 UBS",
                    "≥30 pacientes avaliados",
                    "Acurácia de classificação >70%",
                    "Usabilidade medida (SUS Score >68)",
                    "Feedback de profissionais de saúde",
                ],
                status=ValidationStatus.PLANNED,
            ),
            TRLMilestone(
                trl=TRLevel.TRL6,
                description="Demonstração em ambiente relevante",
                criteria=[
                    "Piloto multicêntrico (≥3 UBS)",
                    "≥100 pacientes",
                    "Integração funcional com e-SUS PEC",
                    "Redução mensurável no tempo de atendimento",
                    "Validação de planos de cuidado personalizados",
                ],
                status=ValidationStatus.PLANNED,
            ),
            TRLMilestone(
                trl=TRLevel.TRL7,
                description="Demonstração em ambiente operacional SUS",
                criteria=[
                    "Implantação em ≥10 unidades de saúde",
                    "≥500 pacientes",
                    "Interoperabilidade total com RNDS",
                    "Módulo mHealth Takere em uso por pacientes",
                    "Vigilância epidemiológica com dados reais",
                ],
                status=ValidationStatus.PLANNED,
            ),
            TRLMilestone(
                trl=TRLevel.TRL8,
                description="Sistema completo qualificado",
                criteria=[
                    "Registro ANVISA (software como dispositivo médico)",
                    "Conformidade LGPD auditada",
                    "Certificação HL7 FHIR BR",
                    "Treinamento completo de equipes",
                    "Documentação regulatória completa",
                ],
                status=ValidationStatus.PLANNED,
            ),
            TRLMilestone(
                trl=TRLevel.TRL9,
                description="Sistema operacional em produção nacional",
                criteria=[
                    "Implantação em múltiplos estados",
                    "Milhares de pacientes atendidos",
                    "Impacto epidemiológico mensurável",
                    "Sustentabilidade financeira via SUS",
                    "Publicações científicas de impacto",
                ],
                status=ValidationStatus.PLANNED,
            ),
        ]

    def get_current_status(self) -> Dict:
        """Status atual de maturidade tecnológica"""
        completed = [m for m in self.milestones if m.status == ValidationStatus.COMPLETED]
        in_progress = [m for m in self.milestones if m.status == ValidationStatus.IN_PROGRESS]

        return {
            "current_trl": self.current_trl.value,
            "trl_description": next(
                (m.description for m in self.milestones if m.trl == self.current_trl), ""
            ),
            "completed_levels": [m.trl.value for m in completed],
            "in_progress": [
                {"trl": m.trl.value, "description": m.description}
                for m in in_progress
            ],
            "next_milestone": self._get_next_milestone(),
            "overall_progress": f"{len(completed)}/9 TRL levels completed",
        }

    def _get_next_milestone(self) -> Optional[Dict]:
        """Próximo marco a ser alcançado"""
        for m in self.milestones:
            if m.status in (ValidationStatus.PLANNED, ValidationStatus.IN_PROGRESS):
                return {
                    "trl": m.trl.value,
                    "description": m.description,
                    "criteria": m.criteria,
                    "status": m.status.value,
                }
        return None

    def update_milestone(self, trl: int, status: ValidationStatus, evidence: List[str] = None):
        """Atualiza status de um marco TRL"""
        for m in self.milestones:
            if m.trl.value == trl:
                m.status = status
                if evidence:
                    m.evidence.extend(evidence)
                if status == ValidationStatus.COMPLETED:
                    m.achieved_date = datetime.now().isoformat()
                    # Atualizar TRL atual
                    self.current_trl = TRLevel(trl)
                break

    def get_roadmap(self) -> List[Dict]:
        """Roadmap completo de TRL"""
        return [
            {
                "trl": m.trl.value,
                "description": m.description,
                "criteria": m.criteria,
                "status": m.status.value,
                "achieved_date": m.achieved_date,
                "evidence": m.evidence,
            }
            for m in self.milestones
        ]


class ValidationFramework:
    """
    Framework de validação clínica para o HEAL/REDISUS.
    Gerencia protocolos de estudo, métricas e pilotos.
    """

    def __init__(self):
        self.trl_tracker = TRLTracker()
        self.metrics: List[ValidationMetric] = []
        self.pilot_sites: List[PilotSite] = []
        self.protocols: List[ClinicalTrialProtocol] = []
        self._initialize_default_protocol()

    def _initialize_default_protocol(self):
        """Inicializa protocolo padrão de validação"""
        self.protocols.append(ClinicalTrialProtocol(
            title="Validação da Plataforma HEAL/REDISUS na Atenção Primária do SUS",
            version="1.0",
            study_type="quase-experimental (antes-depois com grupo controle)",
            primary_objective=(
                "Avaliar a acurácia e impacto clínico da plataforma HEAL/REDISUS "
                "na detecção, classificação e monitoramento de feridas crônicas "
                "na atenção primária do SUS."
            ),
            secondary_objectives=[
                "Avaliar usabilidade da plataforma por profissionais de saúde",
                "Medir redução no tempo de avaliação de feridas",
                "Avaliar concordância entre IA e avaliação de especialista",
                "Medir impacto na aderência dos pacientes ao tratamento",
                "Avaliar viabilidade de integração com e-SUS PEC",
            ],
            inclusion_criteria=[
                "Pacientes ≥18 anos",
                "Ferida crônica (>4 semanas) em acompanhamento na UBS",
                "Consentimento informado assinado",
                "Etiologia: venosa, arterial, diabética, pressão ou esporotricose",
            ],
            exclusion_criteria=[
                "Feridas agudas (<4 semanas)",
                "Pacientes em cuidados paliativos exclusivos",
                "Feridas neoplásicas",
                "Recusa em participar",
            ],
            sample_size=100,
            duration_months=12,
            primary_outcome="Acurácia da classificação de etiologia por IA (vs. especialista)",
            secondary_outcomes=[
                "Tempo médio de avaliação (minutos)",
                "Score SUS de usabilidade",
                "Taxa de aderência ao plano de cuidado",
                "Taxa de cicatrização em 12 semanas",
                "Satisfação do paciente (escala Likert)",
            ],
        ))

    def add_pilot_site(self, site: PilotSite):
        """Adiciona local de piloto"""
        self.pilot_sites.append(site)

    def record_metric(
        self,
        name: str,
        value: float,
        target: float,
        unit: str = "",
        category: str = "",
    ) -> ValidationMetric:
        """Registra métrica de validação"""
        metric = ValidationMetric(
            name=name,
            value=value,
            target=target,
            unit=unit,
            category=category,
            achieved=value >= target,
        )
        self.metrics.append(metric)
        return metric

    def get_performance_metrics(self) -> Dict:
        """Métricas de desempenho do sistema"""
        # Métricas padrão para validação
        default_metrics = {
            "ai_model": {
                "detection_sensitivity": {"target": 0.85, "unit": "%", "description": "Sensibilidade de detecção de feridas"},
                "detection_specificity": {"target": 0.90, "unit": "%", "description": "Especificidade de detecção"},
                "classification_accuracy": {"target": 0.70, "unit": "%", "description": "Acurácia de classificação etiológica"},
                "segmentation_dice": {"target": 0.80, "unit": "", "description": "Coeficiente Dice de segmentação"},
            },
            "usability": {
                "sus_score": {"target": 68, "unit": "pontos", "description": "System Usability Scale"},
                "task_completion_rate": {"target": 0.90, "unit": "%", "description": "Taxa de conclusão de tarefas"},
                "avg_assessment_time": {"target": 10, "unit": "min", "description": "Tempo médio de avaliação"},
            },
            "clinical_impact": {
                "healing_rate_improvement": {"target": 0.15, "unit": "%", "description": "Melhora na taxa de cicatrização"},
                "adherence_rate": {"target": 0.70, "unit": "%", "description": "Aderência ao plano de cuidado"},
                "complication_reduction": {"target": 0.20, "unit": "%", "description": "Redução de complicações"},
            },
            "interoperability": {
                "fhir_compliance": {"target": 1.0, "unit": "", "description": "Conformidade FHIR R4"},
                "esus_integration": {"target": 1.0, "unit": "", "description": "Integração e-SUS funcional"},
            },
        }

        # Combinar com métricas registradas
        recorded = {}
        for m in self.metrics:
            key = m.name
            recorded[key] = {
                "value": m.value,
                "target": m.target,
                "achieved": m.achieved,
                "unit": m.unit,
                "timestamp": m.timestamp,
            }

        return {
            "target_metrics": default_metrics,
            "recorded_metrics": recorded,
            "summary": {
                "total_metrics": len(self.metrics),
                "achieved": sum(1 for m in self.metrics if m.achieved),
                "pending": sum(1 for m in self.metrics if not m.achieved),
            },
        }

    def get_regulatory_checklist(self) -> Dict:
        """Checklist regulatório brasileiro"""
        return {
            "ANVISA": {
                "description": "Agência Nacional de Vigilância Sanitária",
                "requirements": [
                    {"item": "Classificação como SaMD (Software as Medical Device)", "status": "pendente"},
                    {"item": "Classe de risco II (software de apoio à decisão)", "status": "pendente"},
                    {"item": "Dossiê técnico (IEC 62304, ISO 14971)", "status": "em_andamento"},
                    {"item": "Validação clínica documentada", "status": "em_andamento"},
                    {"item": "Registro/Notificação na ANVISA", "status": "pendente"},
                ],
            },
            "LGPD": {
                "description": "Lei Geral de Proteção de Dados Pessoais",
                "requirements": [
                    {"item": "RIPD (Relatório de Impacto à Proteção de Dados)", "status": "pendente"},
                    {"item": "Base legal: consentimento e tutela da saúde", "status": "implementado"},
                    {"item": "Anonimização de dados para pesquisa", "status": "implementado"},
                    {"item": "Criptografia de dados em trânsito e repouso", "status": "em_andamento"},
                    {"item": "Registro de operações de tratamento de dados", "status": "pendente"},
                    {"item": "DPO (Encarregado de dados) nomeado", "status": "pendente"},
                ],
            },
            "CEP_CONEP": {
                "description": "Comitê de Ética em Pesquisa / CONEP",
                "requirements": [
                    {"item": "Protocolo de pesquisa submetido ao CEP", "status": "pendente"},
                    {"item": "TCLE (Termo de Consentimento Livre e Esclarecido)", "status": "rascunho"},
                    {"item": "Aprovação ética para piloto multicêntrico", "status": "pendente"},
                ],
            },
            "CFM_COFEN": {
                "description": "Conselhos profissionais (Medicina e Enfermagem)",
                "requirements": [
                    {"item": "Conformidade com Resolução CFM 2.314/2022 (Telemedicina)", "status": "implementado"},
                    {"item": "Registro de teleconsultas conforme norma", "status": "implementado"},
                    {"item": "Laudo médico em conformidade", "status": "implementado"},
                ],
            },
            "MS_RNDS": {
                "description": "Ministério da Saúde / RNDS",
                "requirements": [
                    {"item": "Conformidade HL7 FHIR R4 (perfis brasileiros)", "status": "implementado"},
                    {"item": "Integração com RNDS (Rede Nacional de Dados em Saúde)", "status": "em_andamento"},
                    {"item": "Certificação e-SUS PEC compatível", "status": "em_andamento"},
                ],
            },
        }

    def get_pilot_summary(self) -> Dict:
        """Resumo dos pilotos"""
        total_patients = sum(s.patients_enrolled for s in self.pilot_sites)

        return {
            "total_sites": len(self.pilot_sites),
            "total_patients": total_patients,
            "sites": [
                {
                    "name": s.name,
                    "city": f"{s.city}/{s.state}",
                    "type": s.institution_type,
                    "patients": s.patients_enrolled,
                    "status": s.status.value,
                }
                for s in self.pilot_sites
            ],
            "protocol": {
                "title": self.protocols[0].title if self.protocols else "",
                "study_type": self.protocols[0].study_type if self.protocols else "",
                "sample_target": self.protocols[0].sample_size if self.protocols else 0,
                "enrolled": total_patients,
            },
        }

    def generate_validation_report(self) -> Dict:
        """Relatório completo de validação"""
        return {
            "trl_status": self.trl_tracker.get_current_status(),
            "performance_metrics": self.get_performance_metrics(),
            "regulatory": self.get_regulatory_checklist(),
            "pilots": self.get_pilot_summary(),
            "roadmap": self.trl_tracker.get_roadmap(),
            "generated_at": datetime.now().isoformat(),
        }
