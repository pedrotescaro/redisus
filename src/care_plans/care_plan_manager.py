"""
HEAL/REDISUS - Gestão de Planos de Cuidado e mHealth Personalizado
Planos de cuidado em linguagem natural convertidos em apps mHealth.

Implementa:
- Criação de planos de cuidado estruturados
- Templates por etiologia e perfil do paciente
- Conversão de plano de cuidado → configuração de app mHealth (conceito Takere)
- Acompanhamento de adesão ao plano
- Alertas e lembretes de medicação/curativos
- Histórico de evolução do plano
"""
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger


class ActivityType(Enum):
    """Tipos de atividade no plano de cuidado"""
    WOUND_CARE = "cuidado_ferida"
    MEDICATION = "medicacao"
    DRESSING_CHANGE = "troca_curativo"
    VITAL_SIGNS = "sinais_vitais"
    NUTRITION = "nutricao"
    EXERCISE = "exercicio"
    EDUCATION = "educacao"
    FOLLOW_UP = "retorno"
    LAB_TEST = "exame_laboratorial"
    SPECIALIST_REFERRAL = "encaminhamento"
    TELECONSULTATION = "teleconsulta"
    SELF_ASSESSMENT = "autoavaliacao"


class FrequencyType(Enum):
    """Frequência de atividades"""
    ONCE = "unica"
    DAILY = "diario"
    TWICE_DAILY = "2x_dia"
    THREE_DAILY = "3x_dia"
    WEEKLY = "semanal"
    BIWEEKLY = "quinzenal"
    MONTHLY = "mensal"
    AS_NEEDED = "quando_necessario"


@dataclass
class CareActivity:
    """Atividade individual do plano de cuidado"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: ActivityType = ActivityType.WOUND_CARE
    title: str = ""
    description: str = ""
    instructions: str = ""
    frequency: FrequencyType = FrequencyType.DAILY
    duration_days: int = 30
    materials: List[str] = field(default_factory=list)
    precautions: List[str] = field(default_factory=list)
    educational_content: str = ""
    requires_photo: bool = False
    requires_professional: bool = False
    priority: int = 1  # 1=alta, 2=média, 3=baixa

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "instructions": self.instructions,
            "frequency": self.frequency.value,
            "duration_days": self.duration_days,
            "materials": self.materials,
            "precautions": self.precautions,
            "educational_content": self.educational_content,
            "requires_photo": self.requires_photo,
            "requires_professional": self.requires_professional,
            "priority": self.priority,
        }


@dataclass
class CarePlan:
    """Plano de cuidado completo"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    patient_id: str = ""
    title: str = ""
    etiology: str = ""
    risk_level: str = "moderado"
    activities: List[CareActivity] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    created_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    valid_until: str = ""
    status: str = "active"  # active, completed, suspended, cancelled
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "title": self.title,
            "etiology": self.etiology,
            "risk_level": self.risk_level,
            "activities": [a.to_dict() for a in self.activities],
            "goals": self.goals,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "valid_until": self.valid_until,
            "status": self.status,
            "notes": self.notes,
        }


class CarePlanTemplates:
    """
    Templates de planos de cuidado baseados em evidências clínicas.
    Profissionais podem personalizar sem necessidade de programação.
    """

    @staticmethod
    def get_venous_ulcer_plan(patient_id: str, risk_level: str = "moderado") -> CarePlan:
        """Plano para úlcera venosa"""
        plan = CarePlan(
            patient_id=patient_id,
            title="Plano de Cuidado — Úlcera Venosa",
            etiology="VENOUS_ULCER",
            risk_level=risk_level,
            goals=[
                "Promover cicatrização da úlcera venosa",
                "Controlar edema do membro inferior",
                "Prevenir recidiva",
                "Orientar autocuidado e uso de compressão",
            ],
            valid_until=(datetime.now() + timedelta(days=90)).isoformat()[:10],
        )

        plan.activities = [
            CareActivity(
                type=ActivityType.DRESSING_CHANGE,
                title="Troca de curativo",
                description="Realizar troca de curativo conforme protocolo institucional",
                instructions=(
                    "1. Lavar as mãos e calçar luvas\n"
                    "2. Remover curativo anterior com soro fisiológico morno\n"
                    "3. Limpar ferida com SF 0,9% em jato\n"
                    "4. Avaliar leito da ferida e bordas\n"
                    "5. Aplicar cobertura primária conforme aspecto do leito\n"
                    "6. Aplicar cobertura secundária\n"
                    "7. Registrar evolução"
                ),
                frequency=FrequencyType.DAILY if risk_level in ("alto", "critico") else FrequencyType.BIWEEKLY,
                materials=["Soro fisiológico 0,9%", "Luvas de procedimento", "Cobertura primária", "Cobertura secundária", "Fita adesiva"],
                precautions=["Observar sinais de infecção", "Avaliar dor durante o procedimento"],
                educational_content="O curativo deve ser trocado regularmente para manter o leito da ferida limpo e favorecer a cicatrização.",
                requires_photo=True,
                requires_professional=True,
                priority=1,
            ),
            CareActivity(
                type=ActivityType.WOUND_CARE,
                title="Terapia compressiva",
                description="Aplicar/manter bandagem compressiva ou meia elástica",
                instructions=(
                    "1. Aplicar bandagem compressiva multicamadas OU\n"
                    "2. Orientar uso de meia elástica de compressão graduada (30-40 mmHg)\n"
                    "3. Verificar perfusão distal após aplicação\n"
                    "4. Paciente deve elevar membros inferiores quando em repouso"
                ),
                frequency=FrequencyType.DAILY,
                materials=["Bandagem compressiva multicamadas", "Ou meia elástica graduada"],
                precautions=["Verificar ITB > 0.8 antes de iniciar", "Não aplicar se doença arterial significativa"],
                priority=1,
            ),
            CareActivity(
                type=ActivityType.EXERCISE,
                title="Exercícios para bomba muscular",
                description="Exercícios de dorsiflexão para ativar bomba muscular da panturrilha",
                instructions=(
                    "1. Sentar com pernas estendidas\n"
                    "2. Flexionar o pé para cima e para baixo (10 repetições)\n"
                    "3. Fazer círculos com os pés (10 para cada lado)\n"
                    "4. Repetir 3x ao dia"
                ),
                frequency=FrequencyType.THREE_DAILY,
                educational_content="Os exercícios ajudam a melhorar a circulação venosa e reduzir o edema.",
                priority=2,
            ),
            CareActivity(
                type=ActivityType.SELF_ASSESSMENT,
                title="Autoavaliação diária",
                description="Paciente avalia sinais de alerta",
                instructions=(
                    "Verificar diariamente:\n"
                    "- Aumento de dor\n"
                    "- Vermelhidão ao redor da ferida\n"
                    "- Secreção com odor\n"
                    "- Febre\n"
                    "- Aumento do edema\n\n"
                    "Se algum sinal presente → contatar equipe de saúde"
                ),
                frequency=FrequencyType.DAILY,
                requires_photo=True,
                priority=1,
            ),
            CareActivity(
                type=ActivityType.FOLLOW_UP,
                title="Retorno para avaliação",
                description="Consulta de enfermagem para reavaliação da ferida",
                frequency=FrequencyType.WEEKLY if risk_level in ("alto", "critico") else FrequencyType.BIWEEKLY,
                requires_professional=True,
                priority=1,
            ),
            CareActivity(
                type=ActivityType.EDUCATION,
                title="Educação em saúde",
                description="Orientações sobre cuidados com a ferida e prevenção de recidiva",
                instructions=(
                    "Temas a abordar:\n"
                    "1. Importância da compressão\n"
                    "2. Elevação dos membros\n"
                    "3. Cuidados com a pele perilesional\n"
                    "4. Nutrição e hidratação\n"
                    "5. Sinais de alerta\n"
                    "6. Quando procurar serviço de saúde"
                ),
                frequency=FrequencyType.WEEKLY,
                educational_content="A educação em saúde é fundamental para a adesão ao tratamento e prevenção de complicações.",
                priority=2,
            ),
        ]

        return plan

    @staticmethod
    def get_diabetic_foot_plan(patient_id: str, risk_level: str = "alto") -> CarePlan:
        """Plano para pé diabético"""
        plan = CarePlan(
            patient_id=patient_id,
            title="Plano de Cuidado — Pé Diabético",
            etiology="DIABETIC_FOOT",
            risk_level=risk_level,
            goals=[
                "Cicatrização da úlcera neuropática",
                "Controle glicêmico adequado",
                "Prevenção de amputação",
                "Descarregamento de pressão no local da ferida",
                "Acompanhamento multiprofissional",
            ],
            valid_until=(datetime.now() + timedelta(days=60)).isoformat()[:10],
        )

        plan.activities = [
            CareActivity(
                type=ActivityType.DRESSING_CHANGE,
                title="Curativo da ferida",
                description="Troca de curativo especializado para pé diabético",
                instructions=(
                    "1. Higiene rigorosa das mãos\n"
                    "2. Remover curativo anterior com cuidado\n"
                    "3. Limpar com SF 0,9%\n"
                    "4. Avaliar sinais de infecção profunda\n"
                    "5. Aplicar cobertura apropriada ao leito\n"
                    "6. Não aplicar pressão no local da ferida"
                ),
                frequency=FrequencyType.DAILY,
                materials=["SF 0,9%", "Cobertura primária", "Espuma de proteção"],
                precautions=[
                    "Avaliar neuropatia sensitiva",
                    "Observar sinais de osteomielite",
                    "Verificar perfusão distal",
                ],
                requires_photo=True,
                requires_professional=True,
                priority=1,
            ),
            CareActivity(
                type=ActivityType.WOUND_CARE,
                title="Descarregamento de pressão",
                description="Uso de dispositivo de alívio de pressão plantar",
                instructions=(
                    "1. Utilizar sapato/sandália de descarregamento\n"
                    "2. Evitar caminhar descalço\n"
                    "3. Limitar deambulação ao mínimo necessário\n"
                    "4. Usar muletas se indicado"
                ),
                frequency=FrequencyType.DAILY,
                materials=["Sandália de descarregamento", "Palmilha especial"],
                priority=1,
            ),
            CareActivity(
                type=ActivityType.VITAL_SIGNS,
                title="Monitoramento glicêmico",
                description="Controle da glicemia capilar",
                instructions=(
                    "1. Verificar glicemia em jejum (meta: 80-130 mg/dL)\n"
                    "2. Verificar glicemia pós-prandial 2h (meta: < 180 mg/dL)\n"
                    "3. Registrar valores no diário\n"
                    "4. Se glicemia > 300 ou < 70: contatar equipe"
                ),
                frequency=FrequencyType.TWICE_DAILY,
                materials=["Glicosímetro", "Tiras reagentes", "Lancetas"],
                priority=1,
            ),
            CareActivity(
                type=ActivityType.SPECIALIST_REFERRAL,
                title="Avaliação vascular",
                description="Encaminhamento ao angiologista para avaliação de doença vascular",
                frequency=FrequencyType.ONCE,
                requires_professional=True,
                priority=1,
            ),
            CareActivity(
                type=ActivityType.NUTRITION,
                title="Orientação nutricional",
                description="Acompanhamento nutricional para controle glicêmico e cicatrização",
                instructions=(
                    "1. Dieta para diabetes (contagem de carboidratos)\n"
                    "2. Aumentar aporte proteico (1.25-1.5g/kg/dia)\n"
                    "3. Suplementar vitamina C e zinco se deficiente\n"
                    "4. Hidratação adequada (> 2L/dia)"
                ),
                frequency=FrequencyType.MONTHLY,
                priority=2,
            ),
            CareActivity(
                type=ActivityType.SELF_ASSESSMENT,
                title="Inspeção diária dos pés",
                description="Autoexame diário dos pés",
                instructions=(
                    "Examinar diariamente:\n"
                    "- Cor da pele (palidez, vermelhidão, cianose)\n"
                    "- Temperatura (comparar ambos pés)\n"
                    "- Presença de novas feridas ou bolhas\n"
                    "- Alteração de sensibilidade\n"
                    "- Unhas (encravamento, micose)\n"
                    "- Se não conseguir ver: usar espelho"
                ),
                frequency=FrequencyType.DAILY,
                educational_content="A inspeção diária dos pés é a principal forma de prevenção de complicações no pé diabético.",
                priority=1,
            ),
        ]

        return plan

    @staticmethod
    def get_pressure_injury_plan(patient_id: str, risk_level: str = "alto") -> CarePlan:
        """Plano para lesão por pressão"""
        plan = CarePlan(
            patient_id=patient_id,
            title="Plano de Cuidado — Lesão por Pressão",
            etiology="PRESSURE_INJURY",
            risk_level=risk_level,
            goals=[
                "Cicatrização da lesão por pressão",
                "Alívio de pressão na área afetada",
                "Prevenção de novas lesões",
                "Manutenção da integridade da pele",
            ],
            valid_until=(datetime.now() + timedelta(days=60)).isoformat()[:10],
        )

        plan.activities = [
            CareActivity(
                type=ActivityType.DRESSING_CHANGE,
                title="Curativo da lesão",
                description="Troca de curativo especializado para lesão por pressão",
                frequency=FrequencyType.DAILY,
                requires_photo=True,
                requires_professional=True,
                priority=1,
            ),
            CareActivity(
                type=ActivityType.WOUND_CARE,
                title="Mudança de decúbito",
                description="Reposicionamento a cada 2 horas para alívio de pressão",
                instructions=(
                    "1. Reposicionar paciente a cada 2 horas\n"
                    "2. Usar travesseiros para descarregamento\n"
                    "3. Manter cabeceira a no máximo 30°\n"
                    "4. Evitar pressão direta sobre a lesão\n"
                    "5. Usar superfície de suporte redistribuinte"
                ),
                frequency=FrequencyType.DAILY,
                materials=["Travesseiros", "Colchão redistribuinte de pressão"],
                priority=1,
            ),
            CareActivity(
                type=ActivityType.NUTRITION,
                title="Suporte nutricional",
                description="Dieta hiperproteica e hipercalórica para cicatrização",
                instructions=(
                    "1. Aporte proteico > 1.5g/kg/dia\n"
                    "2. Suplemento nutricional oral se ingestão < 75%\n"
                    "3. Zinco, vitamina C, vitamina A\n"
                    "4. Hidratação adequada"
                ),
                frequency=FrequencyType.DAILY,
                priority=1,
            ),
        ]

        return plan

    @staticmethod
    def get_template_for_etiology(etiology: str, patient_id: str, risk_level: str = "moderado") -> CarePlan:
        """Retorna template apropriado para a etiologia"""
        templates = {
            "VENOUS_ULCER": CarePlanTemplates.get_venous_ulcer_plan,
            "DIABETIC_FOOT": CarePlanTemplates.get_diabetic_foot_plan,
            "PRESSURE_INJURY": CarePlanTemplates.get_pressure_injury_plan,
        }

        factory = templates.get(etiology)
        if factory:
            return factory(patient_id, risk_level)

        # Plano genérico para outras etiologias
        return CarePlan(
            patient_id=patient_id,
            title=f"Plano de Cuidado — {etiology}",
            etiology=etiology,
            risk_level=risk_level,
            goals=["Promover cicatrização", "Prevenir complicações", "Orientar autocuidado"],
            valid_until=(datetime.now() + timedelta(days=60)).isoformat()[:10],
            activities=[
                CareActivity(
                    type=ActivityType.DRESSING_CHANGE,
                    title="Troca de curativo",
                    description="Curativo conforme protocolo",
                    frequency=FrequencyType.DAILY,
                    requires_professional=True,
                    requires_photo=True,
                    priority=1,
                ),
                CareActivity(
                    type=ActivityType.SELF_ASSESSMENT,
                    title="Autoavaliação",
                    description="Observar sinais de alerta",
                    frequency=FrequencyType.DAILY,
                    priority=1,
                ),
                CareActivity(
                    type=ActivityType.FOLLOW_UP,
                    title="Retorno",
                    description="Consulta de reavaliação",
                    frequency=FrequencyType.WEEKLY,
                    requires_professional=True,
                    priority=1,
                ),
            ],
        )


class MHealthAppGenerator:
    """
    Gerador de configurações mHealth a partir de planos de cuidado.
    Conceito inspirado no mHealth Takere: profissionais criam apps
    personalizados sem necessidade de programação.

    Converte CarePlan → configuração de app mHealth (JSON) que pode
    ser renderizado por uma aplicação móvel genérica.
    """

    def __init__(self):
        logger.info("MHealthAppGenerator inicializado")

    def generate_app_config(self, care_plan: CarePlan, patient_name: str = "") -> Dict:
        """
        Converte um plano de cuidado em configuração de app mHealth.

        Args:
            care_plan: Plano de cuidado estruturado
            patient_name: Nome do paciente (para personalização)

        Returns:
            Dict com configuração completa do app mHealth
        """
        app_config = {
            "app_id": f"heal-mhealth-{care_plan.id[:8]}",
            "app_name": f"HEAL — {care_plan.title}",
            "version": "1.0",
            "platform": "HEAL/REDISUS mHealth",
            "generated_at": datetime.now().isoformat(),

            # Dados do plano
            "care_plan_id": care_plan.id,
            "patient_name": patient_name,
            "etiology": care_plan.etiology,
            "risk_level": care_plan.risk_level,
            "valid_until": care_plan.valid_until,

            # Telas do app
            "screens": self._generate_screens(care_plan),

            # Notificações/Lembretes
            "notifications": self._generate_notifications(care_plan),

            # Formulários de coleta de dados
            "data_forms": self._generate_data_forms(care_plan),

            # Conteúdo educativo
            "educational_content": self._generate_educational_content(care_plan),

            # Configurações de comunicação
            "communication": {
                "enable_messaging": True,
                "enable_photo_upload": True,
                "enable_teleconsultation": True,
                "emergency_contact": True,
            },

            # Integração
            "integration": {
                "fhir_enabled": True,
                "esus_sync": True,
                "heal_platform_sync": True,
            },
        }

        logger.info(f"App mHealth gerado: {app_config['app_name']}")
        return app_config

    def _generate_screens(self, plan: CarePlan) -> List[Dict]:
        """Gera definição de telas do app"""
        screens = [
            {
                "id": "home",
                "title": "Meu Cuidado",
                "type": "dashboard",
                "components": [
                    {"type": "greeting", "text": f"Olá! Seu plano: {plan.title}"},
                    {"type": "progress_bar", "label": "Objetivos do plano", "goals": plan.goals},
                    {"type": "today_tasks", "label": "Atividades de hoje"},
                    {"type": "alerts", "label": "Alertas"},
                ],
            },
            {
                "id": "activities",
                "title": "Atividades",
                "type": "task_list",
                "items": [
                    {
                        "id": a.id,
                        "title": a.title,
                        "description": a.description,
                        "frequency": a.frequency.value,
                        "priority": a.priority,
                        "requires_photo": a.requires_photo,
                        "instructions": a.instructions,
                    }
                    for a in plan.activities
                ],
            },
            {
                "id": "photo_capture",
                "title": "Registro Fotográfico",
                "type": "camera",
                "instructions": "Tire uma foto da ferida para acompanhamento",
                "guidelines": [
                    "Posicione a câmera a 30cm da ferida",
                    "Use iluminação clara e natural",
                    "Inclua uma régua de referência se possível",
                    "Evite sombras sobre a ferida",
                ],
            },
            {
                "id": "education",
                "title": "Saúde e Orientações",
                "type": "content_list",
                "items": [
                    {
                        "title": a.title,
                        "content": a.educational_content,
                        "type": a.type.value,
                    }
                    for a in plan.activities if a.educational_content
                ],
            },
            {
                "id": "communication",
                "title": "Contato com a Equipe",
                "type": "messaging",
                "features": ["text_message", "photo_share", "voice_note", "teleconsultation_request"],
            },
            {
                "id": "history",
                "title": "Meu Progresso",
                "type": "timeline",
                "data_sources": ["photos", "assessments", "vital_signs"],
            },
        ]

        return screens

    def _generate_notifications(self, plan: CarePlan) -> List[Dict]:
        """Gera configuração de notificações/lembretes"""
        notifications = []

        frequency_schedules = {
            FrequencyType.DAILY: [{"hour": 8, "minute": 0}],
            FrequencyType.TWICE_DAILY: [{"hour": 8, "minute": 0}, {"hour": 20, "minute": 0}],
            FrequencyType.THREE_DAILY: [
                {"hour": 8, "minute": 0},
                {"hour": 14, "minute": 0},
                {"hour": 20, "minute": 0},
            ],
            FrequencyType.WEEKLY: [{"hour": 9, "minute": 0, "day_of_week": 1}],  # Segunda
            FrequencyType.BIWEEKLY: [{"hour": 9, "minute": 0, "day_of_week": 1, "interval_weeks": 2}],
        }

        for activity in plan.activities:
            schedule = frequency_schedules.get(activity.frequency, [])
            for s in schedule:
                notifications.append({
                    "activity_id": activity.id,
                    "title": f"Lembrete: {activity.title}",
                    "body": activity.description[:100],
                    "schedule": s,
                    "priority": "high" if activity.priority == 1 else "normal",
                    "sound": True,
                })

        return notifications

    def _generate_data_forms(self, plan: CarePlan) -> List[Dict]:
        """Gera formulários de coleta de dados"""
        forms = []

        # Formulário de auto-avaliação
        forms.append({
            "id": "daily_assessment",
            "title": "Avaliação Diária",
            "fields": [
                {"type": "scale", "label": "Nível de dor (0-10)", "min": 0, "max": 10, "required": True},
                {"type": "checkbox_group", "label": "Sinais observados", "options": [
                    "Vermelhidão ao redor da ferida",
                    "Secreção com odor",
                    "Aumento de dor",
                    "Febre",
                    "Inchaço/edema",
                    "Sangramento",
                ]},
                {"type": "photo", "label": "Foto da ferida", "required": False},
                {"type": "text", "label": "Observações", "multiline": True, "required": False},
            ],
        })

        # Formulário de sinais vitais (se aplicável)
        if any(a.type == ActivityType.VITAL_SIGNS for a in plan.activities):
            forms.append({
                "id": "vital_signs",
                "title": "Sinais Vitais",
                "fields": [
                    {"type": "number", "label": "Pressão sistólica (mmHg)", "min": 60, "max": 250},
                    {"type": "number", "label": "Pressão diastólica (mmHg)", "min": 30, "max": 150},
                    {"type": "number", "label": "Frequência cardíaca (bpm)", "min": 30, "max": 200},
                    {"type": "number", "label": "Temperatura (°C)", "min": 35, "max": 42, "step": 0.1},
                    {"type": "number", "label": "Glicemia capilar (mg/dL)", "min": 20, "max": 600},
                ],
            })

        return forms

    def _generate_educational_content(self, plan: CarePlan) -> List[Dict]:
        """Gera conteúdo educativo para o app"""
        content = [
            {
                "id": "about_wound",
                "title": "Sobre sua ferida",
                "category": "educacao",
                "content": (
                    f"Você está em tratamento por {plan.etiology}. "
                    "É importante seguir todas as orientações da equipe de saúde "
                    "para uma recuperação adequada."
                ),
            },
            {
                "id": "when_to_seek_help",
                "title": "Quando procurar ajuda",
                "category": "alerta",
                "content": (
                    "Procure a equipe de saúde imediatamente se:\n\n"
                    "• A dor piorar muito\n"
                    "• Aparecer secreção com mau cheiro\n"
                    "• A área ao redor ficar muito vermelha/quente\n"
                    "• Você tiver febre acima de 37,8°C\n"
                    "• A ferida aumentar de tamanho\n"
                    "• Houver sangramento que não para"
                ),
            },
            {
                "id": "nutrition_tips",
                "title": "Alimentação e cicatrização",
                "category": "nutricao",
                "content": (
                    "Uma boa alimentação ajuda na cicatrização:\n\n"
                    "• Aumente o consumo de proteínas (carnes, ovos, leite)\n"
                    "• Coma frutas ricas em vitamina C (laranja, limão, acerola)\n"
                    "• Beba bastante água (pelo menos 2 litros/dia)\n"
                    "• Evite alimentos ultraprocessados\n"
                    "• Não fique em jejum prolongado"
                ),
            },
        ]

        return content

    def export_app_config(self, config: Dict, output_path: str) -> str:
        """Exporta configuração do app para arquivo JSON"""
        from pathlib import Path
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"Configuração mHealth exportada para {path}")
        return str(path)


class CarePlanManager:
    """
    Gerenciador central de planos de cuidado.
    Integra templates, personalização e geração de mHealth.
    """

    def __init__(self):
        self.plans: Dict[str, CarePlan] = {}
        self.mhealth_generator = MHealthAppGenerator()
        self.adherence_records: Dict[str, List[Dict]] = {}
        logger.info("CarePlanManager inicializado")

    def create_plan_from_analysis(
        self,
        patient_id: str,
        wound_data: Dict,
        professional_id: str = "",
    ) -> CarePlan:
        """
        Cria plano de cuidado automaticamente a partir de uma análise HEAL.

        Args:
            patient_id: ID do paciente
            wound_data: Dados da análise (etiology, risk_level, etc.)
            professional_id: ID do profissional responsável

        Returns:
            CarePlan personalizado
        """
        etiology = wound_data.get("etiology", "VENOUS_ULCER")
        risk_level = wound_data.get("risk_level", "moderado")

        plan = CarePlanTemplates.get_template_for_etiology(etiology, patient_id, risk_level)
        plan.created_by = professional_id

        self.plans[plan.id] = plan
        logger.info(f"Plano de cuidado criado: {plan.id} — {plan.title}")
        return plan

    def get_plan(self, plan_id: str) -> Optional[CarePlan]:
        """Obtém plano de cuidado por ID"""
        return self.plans.get(plan_id)

    def get_patient_plans(self, patient_id: str) -> List[CarePlan]:
        """Obtém todos os planos de um paciente"""
        return [p for p in self.plans.values() if p.patient_id == patient_id]

    def generate_mhealth_app(
        self,
        plan_id: str,
        patient_name: str = "",
    ) -> Optional[Dict]:
        """
        Gera app mHealth a partir de um plano de cuidado.

        Args:
            plan_id: ID do plano de cuidado
            patient_name: Nome do paciente

        Returns:
            Configuração do app mHealth ou None
        """
        plan = self.plans.get(plan_id)
        if not plan:
            logger.error(f"Plano {plan_id} não encontrado")
            return None

        return self.mhealth_generator.generate_app_config(plan, patient_name)

    def record_adherence(
        self,
        plan_id: str,
        activity_id: str,
        completed: bool,
        notes: str = "",
    ):
        """Registra adesão a uma atividade do plano"""
        if plan_id not in self.adherence_records:
            self.adherence_records[plan_id] = []

        self.adherence_records[plan_id].append({
            "activity_id": activity_id,
            "completed": completed,
            "timestamp": datetime.now().isoformat(),
            "notes": notes,
        })

    def calculate_adherence(self, plan_id: str) -> float:
        """Calcula taxa de adesão ao plano (0.0 - 1.0)"""
        records = self.adherence_records.get(plan_id, [])
        if not records:
            return 0.0
        completed = sum(1 for r in records if r["completed"])
        return completed / len(records)
