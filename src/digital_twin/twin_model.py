"""
HEAL/REDISUS - Digital Twin do Paciente (Twin@Home)
Modelo digital do paciente para simulação, predição e monitoramento domiciliar.

Conceito Twin@Home:
- Gêmeo digital do paciente em ambiente domiciliar
- Reconstrução 3D do ambiente para acessibilidade
- Simulação de cicatrização de feridas
- Predição de desfechos baseada em dados temporais
- Integração com sensores ambientais e vestíveis

Implementa:
- PatientDigitalTwin: modelo completo do paciente
- WoundHealingSimulator: simulação de cicatrização
- HomeEnvironmentModel: modelo do ambiente domiciliar
- PredictiveEngine: predição de desfechos
"""
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class HealingPhase(Enum):
    """Fases da cicatrização"""
    HEMOSTASIS = "hemostasia"
    INFLAMMATORY = "inflamatoria"
    PROLIFERATIVE = "proliferativa"
    REMODELING = "remodelacao"
    CHRONIC = "cronica"
    STALLED = "estagnada"


class RiskTrajectory(Enum):
    """Trajetória de risco do paciente"""
    IMPROVING = "melhorando"
    STABLE = "estavel"
    WORSENING = "piorando"
    CRITICAL = "critico"


class EnvironmentRisk(Enum):
    """Riscos ambientais para o paciente"""
    FALL_RISK = "risco_queda"
    ACCESSIBILITY = "acessibilidade"
    HUMIDITY = "umidade"
    TEMPERATURE = "temperatura"
    HYGIENE = "higiene"
    CAREGIVER_ABSENT = "ausencia_cuidador"


@dataclass
class WoundState:
    """Estado da ferida em um ponto no tempo"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    area_cm2: float = 0.0
    depth_cm: float = 0.0
    perimeter_cm: float = 0.0
    granulation_pct: float = 0.0
    necrosis_pct: float = 0.0
    slough_pct: float = 0.0
    epithelialization_pct: float = 0.0
    exudate_level: str = "moderate"  # none, light, moderate, heavy
    infection_signs: bool = False
    pain_level: int = 0  # 0-10
    healing_phase: HealingPhase = HealingPhase.INFLAMMATORY

    def tissue_health_score(self) -> float:
        """Score 0-100 de saúde tecidual"""
        score = (
            self.granulation_pct * 0.4 +
            self.epithelialization_pct * 0.4 +
            (100 - self.necrosis_pct) * 0.1 +
            (100 - self.slough_pct) * 0.1
        )
        if self.infection_signs:
            score *= 0.5
        return min(max(score, 0), 100)


@dataclass
class PatientProfile:
    """Perfil digital completo do paciente"""
    id: str = ""
    age: int = 0
    sex: str = ""
    weight_kg: float = 0.0
    height_cm: float = 0.0
    comorbidities: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)
    mobility_level: str = "independent"  # independent, assisted, bedridden
    nutrition_status: str = "adequate"  # adequate, moderate_risk, malnourished
    smoking: bool = False
    diabetes: bool = False
    vascular_disease: bool = False
    immunocompromised: bool = False
    caregiver_present: bool = True

    def bmi(self) -> float:
        if self.height_cm > 0 and self.weight_kg > 0:
            h_m = self.height_cm / 100
            return self.weight_kg / (h_m * h_m)
        return 0.0


@dataclass
class HomeEnvironment:
    """Modelo do ambiente domiciliar"""
    has_bathroom_adaptation: bool = False
    has_grab_bars: bool = False
    has_ramp: bool = False
    floor_type: str = "ceramic"  # ceramic, wood, carpet
    bed_type: str = "standard"  # standard, hospital, air_mattress
    ventilation: str = "adequate"  # adequate, poor
    lighting: str = "adequate"  # adequate, poor
    cleanliness: str = "adequate"  # adequate, poor
    room_temperature_c: float = 25.0
    room_humidity_pct: float = 60.0
    accessibility_score: float = 0.0  # 0-100
    risk_factors: List[EnvironmentRisk] = field(default_factory=list)


class WoundHealingSimulator:
    """
    Simulador de cicatrização de feridas baseado em modelo matemático.
    Usa equações diferenciais simplificadas para projetar evolução da ferida.
    """

    # Fatores que afetam a taxa de cicatrização
    HEALING_MODIFIERS = {
        "diabetes": -0.30,
        "vascular_disease": -0.25,
        "smoking": -0.20,
        "immunocompromised": -0.35,
        "malnourished": -0.25,
        "bedridden": -0.15,
        "infection": -0.50,
        "good_compliance": 0.15,
        "adequate_nutrition": 0.10,
        "compression_therapy": 0.20,
        "negative_pressure": 0.25,
    }

    def estimate_healing_rate(
        self,
        patient: PatientProfile,
        wound: WoundState,
        treatments: List[str] = None,
    ) -> float:
        """
        Estima taxa de cicatrização (% redução de área por semana).
        Taxa base: ~10-15% por semana para ferida sem complicações.
        """
        base_rate = 0.12  # 12% por semana

        # Ajustar por idade
        if patient.age > 65:
            base_rate *= 0.85
        if patient.age > 80:
            base_rate *= 0.75

        # Ajustar por comorbidades
        modifier = 0.0
        if patient.diabetes:
            modifier += self.HEALING_MODIFIERS["diabetes"]
        if patient.vascular_disease:
            modifier += self.HEALING_MODIFIERS["vascular_disease"]
        if patient.smoking:
            modifier += self.HEALING_MODIFIERS["smoking"]
        if patient.immunocompromised:
            modifier += self.HEALING_MODIFIERS["immunocompromised"]
        if patient.nutrition_status == "malnourished":
            modifier += self.HEALING_MODIFIERS["malnourished"]
        if patient.mobility_level == "bedridden":
            modifier += self.HEALING_MODIFIERS["bedridden"]
        if wound.infection_signs:
            modifier += self.HEALING_MODIFIERS["infection"]

        # Ajustar por tratamentos
        for t in (treatments or []):
            if t in self.HEALING_MODIFIERS:
                modifier += self.HEALING_MODIFIERS[t]

        rate = base_rate * (1 + modifier)
        return max(rate, 0.01)  # mínimo 1% por semana

    def simulate_healing(
        self,
        patient: PatientProfile,
        current_wound: WoundState,
        weeks: int = 12,
        treatments: List[str] = None,
    ) -> List[Dict]:
        """
        Simula evolução da ferida ao longo do tempo.

        Returns:
            Lista de estados projetados semana a semana
        """
        rate = self.estimate_healing_rate(patient, current_wound, treatments)
        trajectory = []

        area = current_wound.area_cm2
        gran = current_wound.granulation_pct
        epit = current_wound.epithelialization_pct
        necr = current_wound.necrosis_pct

        for week in range(weeks + 1):
            # Modelo exponencial decrescente para área
            projected_area = area * math.exp(-rate * week)

            # Tecido de granulação cresce
            projected_gran = min(100, gran + (100 - gran) * (1 - math.exp(-0.15 * week)))

            # Epitelização cresce mais lentamente
            projected_epit = min(100, epit + (100 - epit) * (1 - math.exp(-0.08 * week)))

            # Necrose diminui com debridamento
            projected_necr = max(0, necr * math.exp(-0.2 * week))

            # Determinar fase
            if projected_epit > 50:
                phase = HealingPhase.REMODELING
            elif projected_gran > 50:
                phase = HealingPhase.PROLIFERATIVE
            elif week < 2:
                phase = HealingPhase.INFLAMMATORY
            else:
                phase = HealingPhase.PROLIFERATIVE

            trajectory.append({
                "week": week,
                "area_cm2": round(projected_area, 2),
                "area_reduction_pct": round((1 - projected_area / area) * 100, 1) if area > 0 else 0,
                "granulation_pct": round(projected_gran, 1),
                "epithelialization_pct": round(projected_epit, 1),
                "necrosis_pct": round(projected_necr, 1),
                "healing_phase": phase.value,
                "estimated_closure": projected_area < 0.5,
            })

        # Estimar semanas para fechamento
        weeks_to_closure = None
        if area > 0:
            # A = A0 * e^(-rt) => t = -ln(0.5/A0) / r
            target = 0.5  # cm²
            if rate > 0 and area > target:
                weeks_to_closure = int(math.ceil(-math.log(target / area) / rate))

        return {
            "healing_rate_per_week": round(rate * 100, 1),
            "estimated_weeks_to_closure": weeks_to_closure,
            "trajectory": trajectory,
            "modifiers_applied": {
                k: v for k, v in self.HEALING_MODIFIERS.items()
                if any([
                    k == "diabetes" and patient.diabetes,
                    k == "vascular_disease" and patient.vascular_disease,
                    k == "smoking" and patient.smoking,
                    k == "infection" and current_wound.infection_signs,
                ])
            },
        }

    def detect_stall(
        self,
        wound_history: List[WoundState],
        stall_threshold_weeks: int = 4,
    ) -> Dict:
        """
        Detecta estagnação na cicatrização.
        Ferida é considerada estagnada se <10% de redução de área em 4 semanas.
        """
        if len(wound_history) < 2:
            return {"stalled": False, "message": "Dados insuficientes"}

        first = wound_history[0]
        last = wound_history[-1]

        try:
            t0 = datetime.fromisoformat(first.timestamp)
            tn = datetime.fromisoformat(last.timestamp)
            weeks_elapsed = (tn - t0).days / 7
        except (ValueError, TypeError):
            weeks_elapsed = len(wound_history)

        if weeks_elapsed < stall_threshold_weeks:
            return {"stalled": False, "message": "Período insuficiente para avaliação"}

        if first.area_cm2 <= 0:
            return {"stalled": False, "message": "Área inicial inválida"}

        reduction = (first.area_cm2 - last.area_cm2) / first.area_cm2

        stalled = reduction < 0.10  # menos de 10%

        return {
            "stalled": stalled,
            "area_reduction_pct": round(reduction * 100, 1),
            "weeks_evaluated": round(weeks_elapsed, 1),
            "initial_area": first.area_cm2,
            "current_area": last.area_cm2,
            "message": (
                "Ferida ESTAGNADA — considerar reavaliação de tratamento, "
                "debridamento, terapia por pressão negativa ou encaminhamento."
                if stalled
                else "Cicatrização progredindo adequadamente."
            ),
        }


class PatientDigitalTwin:
    """
    Gêmeo Digital do Paciente.
    Integra todos os dados para criar modelo preditivo completo.
    """

    def __init__(self, patient: PatientProfile):
        self.patient = patient
        self.wound_history: List[WoundState] = []
        self.vital_signs_summary: Dict = {}
        self.environment: Optional[HomeEnvironment] = None
        self.adherence_rate: float = 1.0
        self.active_treatments: List[str] = []
        self.simulator = WoundHealingSimulator()
        self._risk_factors: List[str] = []

    def update_wound_state(self, state: WoundState):
        """Atualiza estado da ferida no gêmeo digital"""
        self.wound_history.append(state)

    def set_environment(self, env: HomeEnvironment):
        """Define modelo do ambiente domiciliar"""
        self.environment = env
        self._assess_environment_risks()

    def _assess_environment_risks(self):
        """Avalia riscos ambientais"""
        if not self.environment:
            return

        env = self.environment
        env.risk_factors = []

        # Risco de queda
        if (not env.has_grab_bars and self.patient.mobility_level != "independent"):
            env.risk_factors.append(EnvironmentRisk.FALL_RISK)

        # Acessibilidade
        if (not env.has_ramp and self.patient.mobility_level == "bedridden"):
            env.risk_factors.append(EnvironmentRisk.ACCESSIBILITY)

        # Temperatura
        if env.room_temperature_c < 20 or env.room_temperature_c > 30:
            env.risk_factors.append(EnvironmentRisk.TEMPERATURE)

        # Umidade
        if env.room_humidity_pct > 80 or env.room_humidity_pct < 30:
            env.risk_factors.append(EnvironmentRisk.HUMIDITY)

        # Higiene
        if env.cleanliness == "poor":
            env.risk_factors.append(EnvironmentRisk.HYGIENE)

        # Cuidador
        if not self.patient.caregiver_present and self.patient.mobility_level != "independent":
            env.risk_factors.append(EnvironmentRisk.CAREGIVER_ABSENT)

        # Score de acessibilidade
        score = 100
        if not env.has_bathroom_adaptation:
            score -= 20
        if not env.has_grab_bars:
            score -= 15
        if not env.has_ramp:
            score -= 15
        if env.lighting == "poor":
            score -= 10
        if env.floor_type == "ceramic" and self.patient.mobility_level != "independent":
            score -= 10  # piso escorregadio
        if env.bed_type == "standard" and self.patient.mobility_level == "bedridden":
            score -= 20
        env.accessibility_score = max(0, score)

    def get_risk_trajectory(self) -> Dict:
        """
        Calcula trajetória de risco baseada em dados temporais.
        """
        if len(self.wound_history) < 2:
            return {
                "trajectory": RiskTrajectory.STABLE.value,
                "confidence": 0.3,
                "message": "Dados insuficientes para determinar trajetória",
            }

        # Comparar últimos 2 estados
        prev = self.wound_history[-2]
        curr = self.wound_history[-1]

        # Calcular scores
        prev_score = prev.tissue_health_score()
        curr_score = curr.tissue_health_score()

        delta = curr_score - prev_score

        if delta > 10:
            trajectory = RiskTrajectory.IMPROVING
        elif delta > -5:
            trajectory = RiskTrajectory.STABLE
        elif delta > -20:
            trajectory = RiskTrajectory.WORSENING
        else:
            trajectory = RiskTrajectory.CRITICAL

        # Fatores agravantes
        aggravators = []
        if curr.infection_signs and not prev.infection_signs:
            aggravators.append("Nova infecção detectada")
            trajectory = RiskTrajectory.WORSENING
        if curr.area_cm2 > prev.area_cm2 * 1.1:
            aggravators.append("Aumento da área da ferida")
        if curr.necrosis_pct > prev.necrosis_pct + 10:
            aggravators.append("Aumento de necrose")

        return {
            "trajectory": trajectory.value,
            "health_score_current": round(curr_score, 1),
            "health_score_previous": round(prev_score, 1),
            "score_change": round(delta, 1),
            "aggravators": aggravators,
            "confidence": min(0.5 + len(self.wound_history) * 0.05, 0.95),
        }

    def predict_outcomes(self, weeks: int = 12) -> Dict:
        """
        Predição de desfechos usando simulação.
        """
        if not self.wound_history:
            return {"error": "Sem histórico de ferida"}

        current = self.wound_history[-1]
        simulation = self.simulator.simulate_healing(
            self.patient,
            current,
            weeks=weeks,
            treatments=self.active_treatments,
        )

        stall_check = self.simulator.detect_stall(self.wound_history)

        # Risco de complicações
        complication_risk = self._calculate_complication_risk(current)

        return {
            "current_state": {
                "area_cm2": current.area_cm2,
                "tissue_health": round(current.tissue_health_score(), 1),
                "healing_phase": current.healing_phase.value,
            },
            "simulation": simulation,
            "stall_detection": stall_check,
            "complication_risk": complication_risk,
            "trajectory": self.get_risk_trajectory(),
            "environment_risks": (
                [r.value for r in self.environment.risk_factors]
                if self.environment else []
            ),
            "recommendations": self._generate_recommendations(current, simulation, stall_check),
        }

    def _calculate_complication_risk(self, wound: WoundState) -> Dict:
        """Calcula risco de complicações"""
        risk_score = 0.0

        # Fatores do paciente
        if self.patient.diabetes:
            risk_score += 15
        if self.patient.vascular_disease:
            risk_score += 15
        if self.patient.immunocompromised:
            risk_score += 20
        if self.patient.smoking:
            risk_score += 10
        if self.patient.nutrition_status == "malnourished":
            risk_score += 15
        if self.patient.age > 75:
            risk_score += 10

        # Fatores da ferida
        if wound.infection_signs:
            risk_score += 25
        if wound.necrosis_pct > 30:
            risk_score += 15
        if wound.area_cm2 > 20:
            risk_score += 10

        # Aderência
        if self.adherence_rate < 0.5:
            risk_score += 15
        elif self.adherence_rate < 0.7:
            risk_score += 10

        risk_score = min(risk_score, 100)

        if risk_score >= 70:
            level = "alto"
        elif risk_score >= 40:
            level = "moderado"
        else:
            level = "baixo"

        return {
            "score": round(risk_score, 1),
            "level": level,
            "factors": self._list_risk_factors(wound),
        }

    def _list_risk_factors(self, wound: WoundState) -> List[str]:
        """Lista fatores de risco ativos"""
        factors = []
        if self.patient.diabetes:
            factors.append("Diabetes mellitus")
        if self.patient.vascular_disease:
            factors.append("Doença vascular")
        if self.patient.immunocompromised:
            factors.append("Imunocomprometimento")
        if self.patient.smoking:
            factors.append("Tabagismo")
        if self.patient.nutrition_status == "malnourished":
            factors.append("Desnutrição")
        if wound.infection_signs:
            factors.append("Sinais de infecção")
        if wound.necrosis_pct > 30:
            factors.append("Necrose extensa")
        if self.adherence_rate < 0.7:
            factors.append("Baixa aderência ao tratamento")
        if self.environment and EnvironmentRisk.HYGIENE in self.environment.risk_factors:
            factors.append("Condições higiênicas inadequadas")
        return factors

    def _generate_recommendations(
        self,
        wound: WoundState,
        simulation: Dict,
        stall: Dict,
    ) -> List[Dict]:
        """Recomendações baseadas no gêmeo digital"""
        recs = []

        # Se estagnada
        if stall.get("stalled"):
            recs.append({
                "priority": "alta",
                "category": "tratamento",
                "recommendation": (
                    "Ferida estagnada — reavaliar plano terapêutico. "
                    "Considerar debridamento, terapia por pressão negativa "
                    "ou encaminhamento para cirurgião."
                ),
            })

        # Infecção
        if wound.infection_signs:
            recs.append({
                "priority": "alta",
                "category": "infeccao",
                "recommendation": (
                    "Sinais de infecção presentes — solicitar cultura e "
                    "iniciar antibioticoterapia conforme protocolo."
                ),
            })

        # Necrose
        if wound.necrosis_pct > 20:
            recs.append({
                "priority": "moderada",
                "category": "tratamento",
                "recommendation": "Necrose significativa — considerar debridamento.",
            })

        # Nutrição
        if self.patient.nutrition_status == "malnourished":
            recs.append({
                "priority": "moderada",
                "category": "nutricao",
                "recommendation": (
                    "Desnutrição prejudica cicatrização. "
                    "Encaminhar para avaliação nutricional. "
                    "Suplementar proteínas e micronutrientes."
                ),
            })

        # Ambiente
        if self.environment:
            for risk in self.environment.risk_factors:
                if risk == EnvironmentRisk.FALL_RISK:
                    recs.append({
                        "priority": "moderada",
                        "category": "ambiente",
                        "recommendation": "Risco de queda — instalar barras de apoio.",
                    })
                elif risk == EnvironmentRisk.HYGIENE:
                    recs.append({
                        "priority": "alta",
                        "category": "ambiente",
                        "recommendation": (
                            "Condições higiênicas inadequadas — risco de infecção. "
                            "Orientar limpeza adequada do ambiente."
                        ),
                    })

        # Aderência
        if self.adherence_rate < 0.7:
            recs.append({
                "priority": "moderada",
                "category": "aderencia",
                "recommendation": (
                    "Baixa aderência ao tratamento. "
                    "Ativar busca ativa e educação personalizada via mHealth."
                ),
            })

        return recs

    def get_digital_twin_summary(self) -> Dict:
        """Resumo completo do gêmeo digital"""
        current_wound = self.wound_history[-1] if self.wound_history else None

        return {
            "patient": {
                "id": self.patient.id,
                "age": self.patient.age,
                "bmi": round(self.patient.bmi(), 1),
                "comorbidities": self.patient.comorbidities,
                "mobility": self.patient.mobility_level,
                "nutrition": self.patient.nutrition_status,
            },
            "wound": {
                "history_entries": len(self.wound_history),
                "current_area_cm2": current_wound.area_cm2 if current_wound else None,
                "tissue_health": round(current_wound.tissue_health_score(), 1) if current_wound else None,
                "healing_phase": current_wound.healing_phase.value if current_wound else None,
            },
            "environment": {
                "accessibility_score": self.environment.accessibility_score if self.environment else None,
                "risks": [r.value for r in self.environment.risk_factors] if self.environment else [],
            },
            "adherence_rate": round(self.adherence_rate * 100, 1),
            "active_treatments": self.active_treatments,
            "trajectory": self.get_risk_trajectory() if len(self.wound_history) >= 2 else None,
            "generated_at": datetime.now().isoformat(),
        }
