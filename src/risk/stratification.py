"""
HEAL/REDISUS - Sistema de Estratificação de Risco
Estratificação automatizada baseada em dados clínicos, imagem e histórico do paciente.

Implementa:
- Scoring de risco para feridas crônicas
- Classificação em níveis (baixo/moderado/alto/crítico)
- Alertas preditivos baseados em evolução temporal
- Indicadores populacionais para gestão em saúde
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


class RiskLevel(Enum):
    """Níveis de risco clínico"""
    LOW = "baixo"
    MODERATE = "moderado"
    HIGH = "alto"
    CRITICAL = "critico"


class AlertType(Enum):
    """Tipos de alerta clínico"""
    WORSENING = "piora_clinica"
    INFECTION_RISK = "risco_infeccao"
    NON_HEALING = "nao_cicatrizacao"
    ADHERENCE = "baixa_adesao"
    COMORBIDITY = "comorbidade_risco"
    READMISSION = "risco_reinternacao"
    AMPUTATION = "risco_amputacao"
    SEPSIS = "risco_sepse"


class AlertSeverity(Enum):
    """Severidade do alerta"""
    INFO = "informativo"
    WARNING = "atenção"
    URGENT = "urgente"
    CRITICAL = "critico"


@dataclass
class RiskFactor:
    """Fator de risco individual"""
    name: str
    category: str  # clinico, social, ambiental, comportamental
    weight: float  # 0.0 - 1.0
    value: float   # valor atual do fator
    description: str = ""
    evidence_level: str = ""  # nivel de evidencia cientifica


@dataclass
class RiskScore:
    """Resultado da avaliação de risco"""
    total_score: float  # 0-100
    level: RiskLevel
    factors: List[RiskFactor]
    alerts: List[Dict[str, Any]]
    recommendations: List[str]
    next_evaluation: str  # data sugerida
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "total_score": self.total_score,
            "level": self.level.value,
            "factors": [
                {"name": f.name, "category": f.category, "weight": f.weight,
                 "value": f.value, "description": f.description}
                for f in self.factors
            ],
            "alerts": self.alerts,
            "recommendations": self.recommendations,
            "next_evaluation": self.next_evaluation,
            "timestamp": self.timestamp,
        }


@dataclass
class ClinicalAlert:
    """Alerta clínico gerado pelo sistema"""
    alert_type: AlertType
    severity: AlertSeverity
    patient_id: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    action_required: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    acknowledged: bool = False

    def to_dict(self) -> Dict:
        return {
            "type": self.alert_type.value,
            "severity": self.severity.value,
            "patient_id": self.patient_id,
            "message": self.message,
            "details": self.details,
            "action_required": self.action_required,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
        }


@dataclass
class PopulationIndicator:
    """Indicador populacional para gestão em saúde"""
    name: str
    value: float
    unit: str
    category: str  # prevalencia, incidencia, adesao, desfecho
    region: str = ""
    period: str = ""
    trend: str = ""  # subindo, estavel, descendo
    benchmark: Optional[float] = None


class WoundRiskScoring:
    """
    Sistema de scoring de risco para feridas crônicas.
    Baseado em escalas validadas: Braden, PUSH Tool, Bates-Jensen WAT.
    """

    # Pesos dos fatores de risco por categoria
    FACTOR_WEIGHTS = {
        # Fatores da ferida
        "wound_area": 0.15,
        "wound_depth": 0.10,
        "tissue_necrosis_pct": 0.20,
        "tissue_slough_pct": 0.10,
        "wound_age_days": 0.10,
        "infection_signs": 0.15,
        # Fatores do paciente
        "diabetes": 0.08,
        "venous_insufficiency": 0.05,
        "arterial_disease": 0.07,
        "immobility": 0.06,
        "malnutrition": 0.05,
        "age_over_65": 0.04,
        "smoking": 0.03,
        "immunosuppression": 0.05,
        # Fatores de adesão
        "treatment_adherence": 0.08,
        "follow_up_compliance": 0.05,
    }

    # Limiares para classificação de risco
    RISK_THRESHOLDS = {
        RiskLevel.LOW: (0, 25),
        RiskLevel.MODERATE: (25, 50),
        RiskLevel.HIGH: (50, 75),
        RiskLevel.CRITICAL: (75, 100),
    }

    def __init__(self):
        self.alert_history: List[ClinicalAlert] = []
        logger.info("WoundRiskScoring inicializado")

    def calculate_risk_score(
        self,
        wound_data: Dict[str, Any],
        patient_data: Dict[str, Any],
        history: Optional[List[Dict]] = None,
    ) -> RiskScore:
        """
        Calcula score de risco integrado para uma ferida.

        Args:
            wound_data: Dados da ferida (area_cm2, tissue_percentages, etc.)
            patient_data: Dados do paciente (comorbidades, idade, etc.)
            history: Histórico de avaliações anteriores

        Returns:
            RiskScore com score total, fatores e alertas
        """
        factors = []
        total_weighted = 0.0
        total_weight = 0.0

        # --- Fatores da ferida ---
        # Área da ferida (normaliza 0-100 cm² → 0-1)
        area = wound_data.get("area_cm2", 0)
        area_score = min(area / 100.0, 1.0)
        factors.append(RiskFactor(
            name="Área da ferida",
            category="ferida",
            weight=self.FACTOR_WEIGHTS["wound_area"],
            value=area_score,
            description=f"{area:.1f} cm² — {'extensa' if area > 50 else 'moderada' if area > 20 else 'pequena'}",
            evidence_level="Alta (PUSH Tool)",
        ))
        total_weighted += area_score * self.FACTOR_WEIGHTS["wound_area"]
        total_weight += self.FACTOR_WEIGHTS["wound_area"]

        # Percentual de necrose
        tissue_pcts = wound_data.get("tissue_percentages", {})
        necrosis_pct = tissue_pcts.get("Necrose", tissue_pcts.get("NECROSIS", 0)) / 100.0
        factors.append(RiskFactor(
            name="Tecido necrótico",
            category="ferida",
            weight=self.FACTOR_WEIGHTS["tissue_necrosis_pct"],
            value=necrosis_pct,
            description=f"{necrosis_pct*100:.1f}% de tecido necrótico",
            evidence_level="Alta (Bates-Jensen WAT)",
        ))
        total_weighted += necrosis_pct * self.FACTOR_WEIGHTS["tissue_necrosis_pct"]
        total_weight += self.FACTOR_WEIGHTS["tissue_necrosis_pct"]

        # Percentual de esfacelo
        slough_pct = tissue_pcts.get("Esfacelo", tissue_pcts.get("SLOUGH", 0)) / 100.0
        factors.append(RiskFactor(
            name="Tecido esfacelado",
            category="ferida",
            weight=self.FACTOR_WEIGHTS["tissue_slough_pct"],
            value=slough_pct,
            description=f"{slough_pct*100:.1f}% de esfacelo",
            evidence_level="Alta (Bates-Jensen WAT)",
        ))
        total_weighted += slough_pct * self.FACTOR_WEIGHTS["tissue_slough_pct"]
        total_weight += self.FACTOR_WEIGHTS["tissue_slough_pct"]

        # Idade da ferida em dias
        wound_age = wound_data.get("wound_age_days", 0)
        age_score = min(wound_age / 180.0, 1.0)  # Normaliza até 6 meses
        factors.append(RiskFactor(
            name="Tempo de evolução",
            category="ferida",
            weight=self.FACTOR_WEIGHTS["wound_age_days"],
            value=age_score,
            description=f"{wound_age} dias — {'crônica' if wound_age > 90 else 'subaguda' if wound_age > 30 else 'aguda'}",
            evidence_level="Moderada",
        ))
        total_weighted += age_score * self.FACTOR_WEIGHTS["wound_age_days"]
        total_weight += self.FACTOR_WEIGHTS["wound_age_days"]

        # Sinais de infecção
        infection = wound_data.get("infection_signs", False)
        infection_score = 1.0 if infection else 0.0
        factors.append(RiskFactor(
            name="Sinais de infecção",
            category="ferida",
            weight=self.FACTOR_WEIGHTS["infection_signs"],
            value=infection_score,
            description="Sinais clínicos de infecção presentes" if infection else "Sem sinais de infecção",
            evidence_level="Alta",
        ))
        total_weighted += infection_score * self.FACTOR_WEIGHTS["infection_signs"]
        total_weight += self.FACTOR_WEIGHTS["infection_signs"]

        # --- Fatores do paciente ---
        comorbidities = patient_data.get("comorbidities", {})
        patient_factors = [
            ("diabetes", "Diabetes mellitus", "Comprometimento da cicatrização e risco de pé diabético"),
            ("venous_insufficiency", "Insuficiência venosa", "Comprometimento do retorno venoso"),
            ("arterial_disease", "Doença arterial periférica", "Comprometimento do fluxo arterial"),
            ("immobility", "Imobilidade/Acamado", "Risco de lesão por pressão e trombose"),
            ("malnutrition", "Desnutrição", "Comprometimento da cicatrização por déficit nutricional"),
            ("immunosuppression", "Imunossupressão", "Risco aumentado de infecção"),
        ]

        for key, name, desc in patient_factors:
            present = comorbidities.get(key, False)
            score = 1.0 if present else 0.0
            w = self.FACTOR_WEIGHTS.get(key, 0.05)
            factors.append(RiskFactor(
                name=name, category="paciente", weight=w,
                value=score, description=desc if present else f"Sem {name.lower()}",
                evidence_level="Moderada",
            ))
            total_weighted += score * w
            total_weight += w

        # Idade
        age = patient_data.get("age", 0)
        age_factor = 1.0 if age >= 65 else (age / 65.0 if age > 0 else 0.0)
        factors.append(RiskFactor(
            name="Idade", category="paciente",
            weight=self.FACTOR_WEIGHTS["age_over_65"],
            value=age_factor,
            description=f"{age} anos — {'idoso' if age >= 65 else 'adulto'}",
            evidence_level="Alta",
        ))
        total_weighted += age_factor * self.FACTOR_WEIGHTS["age_over_65"]
        total_weight += self.FACTOR_WEIGHTS["age_over_65"]

        # Tabagismo
        smoking = patient_data.get("smoking", False)
        smoke_score = 1.0 if smoking else 0.0
        factors.append(RiskFactor(
            name="Tabagismo", category="comportamental",
            weight=self.FACTOR_WEIGHTS["smoking"],
            value=smoke_score,
            description="Tabagista — comprometimento da microcirculação" if smoking else "Não tabagista",
            evidence_level="Alta",
        ))
        total_weighted += smoke_score * self.FACTOR_WEIGHTS["smoking"]
        total_weight += self.FACTOR_WEIGHTS["smoking"]

        # --- Fatores de adesão ---
        adherence = patient_data.get("treatment_adherence", 1.0)
        adherence_risk = 1.0 - adherence  # Menor adesão = maior risco
        factors.append(RiskFactor(
            name="Adesão ao tratamento", category="adesao",
            weight=self.FACTOR_WEIGHTS["treatment_adherence"],
            value=adherence_risk,
            description=f"Adesão: {adherence*100:.0f}% — {'boa' if adherence > 0.8 else 'parcial' if adherence > 0.5 else 'baixa'}",
            evidence_level="Moderada",
        ))
        total_weighted += adherence_risk * self.FACTOR_WEIGHTS["treatment_adherence"]
        total_weight += self.FACTOR_WEIGHTS["treatment_adherence"]

        # Calcular score final (0-100)
        raw_score = (total_weighted / max(total_weight, 0.001)) * 100
        total_score = min(max(raw_score, 0), 100)

        # Classificar nível de risco
        level = self._classify_risk(total_score)

        # Gerar alertas
        alerts = self._generate_alerts(
            total_score, factors, wound_data, patient_data, history
        )

        # Gerar recomendações
        recommendations = self._generate_recommendations(level, factors, wound_data)

        # Calcular próxima avaliação
        next_eval = self._calculate_next_evaluation(level)

        return RiskScore(
            total_score=total_score,
            level=level,
            factors=factors,
            alerts=alerts,
            recommendations=recommendations,
            next_evaluation=next_eval,
        )

    def _classify_risk(self, score: float) -> RiskLevel:
        """Classifica o nível de risco pelo score"""
        for level, (low, high) in self.RISK_THRESHOLDS.items():
            if low <= score < high:
                return level
        return RiskLevel.CRITICAL

    def _generate_alerts(
        self,
        score: float,
        factors: List[RiskFactor],
        wound_data: Dict,
        patient_data: Dict,
        history: Optional[List[Dict]],
    ) -> List[Dict]:
        """Gera alertas clínicos baseados na análise de risco"""
        alerts = []

        # Alerta de infecção
        if wound_data.get("infection_signs", False):
            alerts.append({
                "type": AlertType.INFECTION_RISK.value,
                "severity": AlertSeverity.URGENT.value,
                "message": "Sinais de infecção identificados — avaliação médica urgente necessária",
                "action": "Solicitar cultura de ferida e avaliação médica em 24h",
            })

        # Alerta de necrose elevada
        tissue_pcts = wound_data.get("tissue_percentages", {})
        necrosis = tissue_pcts.get("Necrose", tissue_pcts.get("NECROSIS", 0))
        if necrosis > 30:
            alerts.append({
                "type": AlertType.WORSENING.value,
                "severity": AlertSeverity.URGENT.value,
                "message": f"Necrose elevada ({necrosis:.0f}%) — considerar desbridamento",
                "action": "Avaliar necessidade de desbridamento cirúrgico ou autolítico",
            })

        # Alerta de não cicatrização (baseado no histórico)
        if history and len(history) >= 3:
            recent = history[-3:]
            areas = [h.get("area_cm2", 0) for h in recent if "area_cm2" in h]
            if len(areas) >= 3 and all(a >= areas[0] for a in areas[1:]):
                alerts.append({
                    "type": AlertType.NON_HEALING.value,
                    "severity": AlertSeverity.WARNING.value,
                    "message": "Ferida sem evolução de melhora nas últimas 3 avaliações",
                    "action": "Reavaliar plano terapêutico e considerar encaminhamento especializado",
                })

        # Alerta de risco de amputação (pé diabético)
        if (patient_data.get("comorbidities", {}).get("diabetes") and
                wound_data.get("etiology") == "DIABETIC_FOOT" and score > 70):
            alerts.append({
                "type": AlertType.AMPUTATION.value,
                "severity": AlertSeverity.CRITICAL.value,
                "message": "Risco elevado de amputação — pé diabético com score crítico",
                "action": "Encaminhamento urgente para equipe vascular e endócrina",
            })

        # Alerta de baixa adesão
        adherence = patient_data.get("treatment_adherence", 1.0)
        if adherence < 0.5:
            alerts.append({
                "type": AlertType.ADHERENCE.value,
                "severity": AlertSeverity.WARNING.value,
                "message": f"Adesão ao tratamento muito baixa ({adherence*100:.0f}%)",
                "action": "Realizar entrevista motivacional e avaliar barreiras ao tratamento",
            })

        return alerts

    def _generate_recommendations(
        self,
        level: RiskLevel,
        factors: List[RiskFactor],
        wound_data: Dict,
    ) -> List[str]:
        """Gera recomendações baseadas no nível de risco"""
        recs = []

        if level == RiskLevel.CRITICAL:
            recs.extend([
                "Avaliação médica URGENTE necessária em até 24 horas",
                "Considerar internação para cuidados intensivos da ferida",
                "Solicitar exames complementares (cultura, hemograma, PCR)",
                "Avaliar necessidade de desbridamento cirúrgico",
            ])
        elif level == RiskLevel.HIGH:
            recs.extend([
                "Agendar avaliação médica em até 48 horas",
                "Intensificar frequência de curativos",
                "Reavaliar protocolo terapêutico atual",
                "Solicitar exames laboratoriais de acompanhamento",
            ])
        elif level == RiskLevel.MODERATE:
            recs.extend([
                "Manter protocolo terapêutico atual com monitoramento semanal",
                "Reforçar orientações de autocuidado ao paciente",
                "Reavaliar em 7-14 dias",
            ])
        else:  # LOW
            recs.extend([
                "Manter protocolo terapêutico atual",
                "Próxima avaliação em 14-30 dias",
                "Reforçar orientações de prevenção",
            ])

        # Recomendações específicas por fator
        for f in factors:
            if f.value > 0.7:
                if f.name == "Desnutrição":
                    recs.append("Encaminhar ao serviço de nutrição para suporte nutricional")
                elif f.name == "Tabagismo":
                    recs.append("Orientar cessação do tabagismo — programa de apoio")
                elif f.name == "Imobilidade/Acamado":
                    recs.append("Implementar protocolo de prevenção de lesão por pressão (mudança de decúbito)")

        return recs

    def _calculate_next_evaluation(self, level: RiskLevel) -> str:
        """Calcula data da próxima avaliação baseada no risco"""
        intervals = {
            RiskLevel.CRITICAL: 1,   # 1 dia
            RiskLevel.HIGH: 3,       # 3 dias
            RiskLevel.MODERATE: 7,   # 7 dias
            RiskLevel.LOW: 14,       # 14 dias
        }
        days = intervals.get(level, 7)
        return (datetime.now() + timedelta(days=days)).isoformat()


class PopulationRiskAnalyzer:
    """
    Analisador de risco populacional para gestão em saúde.
    Gera indicadores dinâmicos para equipes e gestores do SUS.
    """

    def __init__(self):
        logger.info("PopulationRiskAnalyzer inicializado")

    def calculate_population_indicators(
        self,
        patients_data: List[Dict[str, Any]],
        region: str = "",
    ) -> List[PopulationIndicator]:
        """
        Calcula indicadores populacionais a partir de dados agregados.

        Args:
            patients_data: Lista de dicionários com dados de pacientes
            region: Região/localidade para contextualização

        Returns:
            Lista de indicadores populacionais
        """
        if not patients_data:
            return []

        indicators = []
        total = len(patients_data)
        now = datetime.now().isoformat()[:10]

        # Prevalência por etiologia
        etiology_counts: Dict[str, int] = {}
        for p in patients_data:
            et = p.get("etiology", "desconhecida")
            etiology_counts[et] = etiology_counts.get(et, 0) + 1

        for et, count in etiology_counts.items():
            indicators.append(PopulationIndicator(
                name=f"Prevalência — {et}",
                value=count / total * 100,
                unit="%",
                category="prevalencia",
                region=region,
                period=now,
            ))

        # Distribuição por nível de risco
        risk_counts = {"baixo": 0, "moderado": 0, "alto": 0, "critico": 0}
        for p in patients_data:
            level = p.get("risk_level", "moderado")
            if level in risk_counts:
                risk_counts[level] += 1

        for level, count in risk_counts.items():
            indicators.append(PopulationIndicator(
                name=f"Pacientes risco {level}",
                value=count,
                unit="pacientes",
                category="risco",
                region=region,
                period=now,
            ))

        # Taxa de adesão média
        adherences = [p.get("treatment_adherence", 0.5) for p in patients_data]
        if adherences:
            avg_adherence = sum(adherences) / len(adherences)
            indicators.append(PopulationIndicator(
                name="Adesão média ao tratamento",
                value=avg_adherence * 100,
                unit="%",
                category="adesao",
                region=region,
                period=now,
                benchmark=80.0,  # Meta SUS
            ))

        # Health score médio
        scores = [p.get("health_score", 0) for p in patients_data]
        if scores:
            avg_score = sum(scores) / len(scores)
            indicators.append(PopulationIndicator(
                name="Score de saúde médio",
                value=avg_score,
                unit="pontos",
                category="desfecho",
                region=region,
                period=now,
            ))

        # Taxa de feridas crônicas (> 90 dias)
        chronic = sum(1 for p in patients_data if p.get("wound_age_days", 0) > 90)
        indicators.append(PopulationIndicator(
            name="Taxa de feridas crônicas",
            value=chronic / max(total, 1) * 100,
            unit="%",
            category="prevalencia",
            region=region,
            period=now,
        ))

        # Taxa de internações
        hospitalized = sum(1 for p in patients_data if p.get("hospitalized", False))
        indicators.append(PopulationIndicator(
            name="Taxa de internação",
            value=hospitalized / max(total, 1) * 100,
            unit="%",
            category="desfecho",
            region=region,
            period=now,
            benchmark=15.0,
        ))

        logger.info(f"Calculados {len(indicators)} indicadores populacionais para {total} pacientes")
        return indicators

    def detect_trends(
        self,
        historical_indicators: List[List[PopulationIndicator]],
    ) -> Dict[str, str]:
        """
        Detecta tendências temporais nos indicadores.

        Args:
            historical_indicators: Lista de snapshots de indicadores ao longo do tempo

        Returns:
            Dict com nome do indicador → tendência (subindo/estavel/descendo)
        """
        trends = {}
        if len(historical_indicators) < 2:
            return trends

        latest = {i.name: i.value for i in historical_indicators[-1]}
        previous = {i.name: i.value for i in historical_indicators[-2]}

        for name in latest:
            if name in previous:
                diff = latest[name] - previous[name]
                threshold = max(abs(previous[name]) * 0.05, 0.5)
                if diff > threshold:
                    trends[name] = "subindo"
                elif diff < -threshold:
                    trends[name] = "descendo"
                else:
                    trends[name] = "estavel"

        return trends

    def generate_risk_stratification_report(
        self,
        patients_data: List[Dict],
        region: str = "",
    ) -> Dict[str, Any]:
        """
        Gera relatório completo de estratificação de risco populacional.
        """
        indicators = self.calculate_population_indicators(patients_data, region)

        # Agrupar por categoria
        by_category: Dict[str, List] = {}
        for ind in indicators:
            cat = ind.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append({
                "name": ind.name,
                "value": ind.value,
                "unit": ind.unit,
                "benchmark": ind.benchmark,
            })

        # Resumo executivo
        total = len(patients_data)
        critical = sum(1 for p in patients_data if p.get("risk_level") == "critico")
        high = sum(1 for p in patients_data if p.get("risk_level") == "alto")

        return {
            "region": region,
            "total_patients": total,
            "report_date": datetime.now().isoformat(),
            "summary": {
                "critical_risk_count": critical,
                "high_risk_count": high,
                "attention_needed_pct": (critical + high) / max(total, 1) * 100,
            },
            "indicators_by_category": by_category,
            "recommendations": self._generate_population_recommendations(
                total, critical, high, indicators
            ),
        }

    def _generate_population_recommendations(
        self,
        total: int,
        critical: int,
        high: int,
        indicators: List[PopulationIndicator],
    ) -> List[str]:
        """Gera recomendações para gestão populacional"""
        recs = []

        attention_pct = (critical + high) / max(total, 1) * 100
        if attention_pct > 30:
            recs.append(
                f"ALERTA: {attention_pct:.0f}% dos pacientes em risco alto/crítico — "
                "considerar reforço de equipe e revisão de protocolos"
            )

        if critical > 5:
            recs.append(
                f"{critical} pacientes em risco CRÍTICO — priorizar atendimento imediato"
            )

        # Verificar adesão
        for ind in indicators:
            if "Adesão" in ind.name and ind.value < 60:
                recs.append(
                    f"Adesão média ao tratamento abaixo de 60% — "
                    "implementar estratégias de educação em saúde e busca ativa"
                )

            if "internação" in ind.name.lower() and ind.benchmark and ind.value > ind.benchmark:
                recs.append(
                    f"Taxa de internação ({ind.value:.1f}%) acima da meta ({ind.benchmark:.1f}%) — "
                    "fortalecer atenção primária e domiciliar"
                )

        return recs
