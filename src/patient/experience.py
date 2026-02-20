"""
HEAL/REDISUS - Experiência do Paciente
Educação em saúde, adesão ao tratamento, comunicação bidirecional.

Implementa:
- Biblioteca de conteúdo educativo sobre feridas e autocuidado
- Sistema de acompanhamento de adesão terapêutica
- Comunicação bidirecional paciente-profissional
- Lembretes inteligentes e motivacionais
- Suporte à desospitalização e cuidado domiciliar
"""
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger


class ContentCategory(Enum):
    """Categorias de conteúdo educativo"""
    WOUND_CARE = "cuidado_ferida"
    NUTRITION = "nutricao"
    EXERCISE = "atividade_fisica"
    MEDICATION = "medicacao"
    PREVENTION = "prevencao"
    SELF_ASSESSMENT = "autoavaliacao"
    MENTAL_HEALTH = "saude_mental"
    RIGHTS = "direitos_sus"
    EMERGENCY = "emergencia"


class MessageType(Enum):
    """Tipos de mensagem"""
    TEXT = "texto"
    PHOTO = "foto"
    AUDIO = "audio"
    ALERT = "alerta"
    REMINDER = "lembrete"
    EDUCATIONAL = "educativo"
    TELECONSULT_REQUEST = "solicitacao_teleconsulta"


@dataclass
class EducationalContent:
    """Conteúdo educativo para pacientes"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    category: ContentCategory = ContentCategory.WOUND_CARE
    content: str = ""
    summary: str = ""
    target_conditions: List[str] = field(default_factory=list)
    reading_time_min: int = 3
    language: str = "pt-BR"
    accessibility: Dict = field(default_factory=lambda: {
        "font_size": "large",
        "high_contrast": True,
        "audio_available": False,
    })

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category.value,
            "content": self.content,
            "summary": self.summary,
            "target_conditions": self.target_conditions,
            "reading_time_min": self.reading_time_min,
        }


@dataclass
class PatientMessage:
    """Mensagem no sistema de comunicação"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    sender_type: str = "patient"  # patient, professional, system
    recipient_id: str = ""
    message_type: MessageType = MessageType.TEXT
    content: str = ""
    attachment_path: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    read: bool = False
    urgent: bool = False


@dataclass
class AdherenceRecord:
    """Registro de adesão ao tratamento"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    patient_id: str = ""
    plan_id: str = ""
    activity_id: str = ""
    activity_name: str = ""
    scheduled_date: str = ""
    completed: bool = False
    completed_at: Optional[str] = None
    photo_path: Optional[str] = None
    pain_level: Optional[int] = None  # 0-10
    notes: str = ""
    alert_signs: List[str] = field(default_factory=list)


class HealthEducationLibrary:
    """
    Biblioteca de conteúdo educativo sobre saúde.
    Conteúdos em linguagem acessível para pacientes do SUS.
    """

    def __init__(self):
        self.contents: List[EducationalContent] = self._load_default_contents()
        logger.info(f"HealthEducationLibrary: {len(self.contents)} conteúdos carregados")

    def _load_default_contents(self) -> List[EducationalContent]:
        """Carrega biblioteca padrão de conteúdo educativo"""
        return [
            EducationalContent(
                title="O que são feridas crônicas?",
                category=ContentCategory.WOUND_CARE,
                target_conditions=["VENOUS_ULCER", "ARTERIAL_ULCER", "DIABETIC_FOOT", "PRESSURE_INJURY"],
                summary="Entenda o que é uma ferida crônica e por que ela precisa de cuidado especial.",
                content=(
                    "Uma ferida é considerada crônica quando não cicatriza no tempo esperado, "
                    "geralmente mais de 4 a 6 semanas. Isso pode acontecer por vários motivos:\n\n"
                    "• Problemas de circulação (veias ou artérias)\n"
                    "• Diabetes\n"
                    "• Ficar muito tempo na mesma posição\n"
                    "• Infecção\n"
                    "• Má nutrição\n\n"
                    "O tratamento adequado é fundamental. Siga sempre as orientações da "
                    "equipe de saúde e não aplique produtos caseiros sem orientação."
                ),
            ),
            EducationalContent(
                title="Como cuidar da sua ferida em casa",
                category=ContentCategory.WOUND_CARE,
                target_conditions=["VENOUS_ULCER", "ARTERIAL_ULCER", "DIABETIC_FOOT", "PRESSURE_INJURY"],
                summary="Dicas práticas para cuidar da ferida entre as consultas.",
                content=(
                    "Cuidados básicos com sua ferida:\n\n"
                    "1. MANTENHA O CURATIVO LIMPO E SECO\n"
                    "   - Não molhe o curativo no banho\n"
                    "   - Troque se ficar sujo ou molhado\n\n"
                    "2. NÃO MEXA NA FERIDA\n"
                    "   - Não tente descolar crostas\n"
                    "   - Não aplique produtos caseiros\n"
                    "   - Não coloque pomadas sem orientação\n\n"
                    "3. OBSERVE SINAIS DE PROBLEMA\n"
                    "   - Dor que piora\n"
                    "   - Secreção com cheiro ruim\n"
                    "   - Vermelhidão que aumenta\n"
                    "   - Febre\n\n"
                    "4. VÁ AOS RETORNOS MARCADOS\n"
                    "   - Não falte às consultas\n"
                    "   - Leve suas dúvidas anotadas"
                ),
            ),
            EducationalContent(
                title="Alimentação que ajuda na cicatrização",
                category=ContentCategory.NUTRITION,
                target_conditions=["VENOUS_ULCER", "ARTERIAL_ULCER", "DIABETIC_FOOT", "PRESSURE_INJURY"],
                summary="Alimentos que ajudam sua ferida a cicatrizar melhor.",
                content=(
                    "A alimentação é muito importante para a cicatrização:\n\n"
                    "PROTEÍNAS (comer todo dia):\n"
                    "• Feijão, lentilha, grão-de-bico\n"
                    "• Ovo (pode ser cozido ou mexido)\n"
                    "• Carne magra, frango, peixe\n"
                    "• Leite e derivados\n\n"
                    "VITAMINA C (fortalece a cicatrização):\n"
                    "• Laranja, limão, acerola, goiaba\n"
                    "• Couve, brócolis, pimentão\n\n"
                    "FERRO (evita anemia):\n"
                    "• Feijão, carne vermelha, folhas verdes escuras\n\n"
                    "ÁGUA (beba bastante):\n"
                    "• Pelo menos 2 litros por dia\n"
                    "• Água, chá, suco natural\n\n"
                    "EVITE:\n"
                    "• Refrigerante, salgadinhos, doces em excesso\n"
                    "• Álcool\n"
                    "• Alimentos ultraprocessados"
                ),
            ),
            EducationalContent(
                title="Cuidados com o pé diabético",
                category=ContentCategory.PREVENTION,
                target_conditions=["DIABETIC_FOOT"],
                summary="Prevenção e cuidados essenciais para quem tem diabetes.",
                content=(
                    "Se você tem diabetes, seus pés precisam de atenção especial:\n\n"
                    "TODO DIA:\n"
                    "• Examine seus pés (use um espelho se necessário)\n"
                    "• Lave com água morna (nunca quente)\n"
                    "• Seque bem, especialmente entre os dedos\n"
                    "• Use creme hidratante (não entre os dedos)\n\n"
                    "SAPATOS:\n"
                    "• Use sapatos fechados e confortáveis\n"
                    "• NUNCA ande descalço\n"
                    "• Verifique dentro do sapato antes de calçar\n"
                    "• Use meias de algodão sem costura\n\n"
                    "UNHAS:\n"
                    "• Corte reto, sem arredondar os cantos\n"
                    "• Não corte cutículas\n"
                    "• Se tiver dificuldade, peça a um profissional\n\n"
                    "GLICEMIA:\n"
                    "• Mantenha a glicemia controlada\n"
                    "• Tome os remédios conforme prescrição\n"
                    "• Faça os exames de acompanhamento"
                ),
            ),
            EducationalContent(
                title="Prevenção de lesão por pressão",
                category=ContentCategory.PREVENTION,
                target_conditions=["PRESSURE_INJURY"],
                summary="Como prevenir escaras em pessoas acamadas.",
                content=(
                    "Para quem fica muito tempo deitado ou sentado:\n\n"
                    "MUDANÇA DE POSIÇÃO:\n"
                    "• Mudar de posição a cada 2 horas\n"
                    "• Não arrastar — levantar o corpo\n"
                    "• Usar travesseiros para apoio\n\n"
                    "CUIDADOS COM A PELE:\n"
                    "• Manter a pele limpa e seca\n"
                    "• Usar creme hidratante\n"
                    "• Observar vermelhidão em proeminências ósseas\n"
                    "• Manter a cama limpa e sem rugas no lençol\n\n"
                    "ALIMENTAÇÃO E HIDRATAÇÃO:\n"
                    "• Comer alimentos ricos em proteínas\n"
                    "• Beber bastante líquido\n\n"
                    "EXERCÍCIOS (com orientação):\n"
                    "• Fazer movimentos nos braços e pernas\n"
                    "• Sentir-se livre para pedir ajuda"
                ),
            ),
            EducationalContent(
                title="Quando ir ao posto de saúde por urgência",
                category=ContentCategory.EMERGENCY,
                target_conditions=["VENOUS_ULCER", "ARTERIAL_ULCER", "DIABETIC_FOOT", "PRESSURE_INJURY"],
                summary="Sinais de que você precisa de atendimento urgente.",
                content=(
                    "PROCURE ATENDIMENTO URGENTE SE:\n\n"
                    "🔴 A ferida está sangrando muito e não para\n"
                    "🔴 Saiu pus (secreção amarela/verde com cheiro forte)\n"
                    "🔴 A dor ficou insuportável\n"
                    "🔴 A pele ao redor ficou muito vermelha e quente\n"
                    "🔴 Você está com febre alta (> 38°C)\n"
                    "🔴 O pé ou perna ficou escuro ou frio\n"
                    "🔴 Você não consegue mexer a parte afetada\n\n"
                    "LIGUE PARA:\n"
                    "• UBS mais próxima\n"
                    "• SAMU: 192\n"
                    "• Telessaúde do seu município\n\n"
                    "NÃO ESPERE PIORAR!"
                ),
            ),
            EducationalContent(
                title="Seus direitos no SUS",
                category=ContentCategory.RIGHTS,
                target_conditions=["VENOUS_ULCER", "ARTERIAL_ULCER", "DIABETIC_FOOT", "PRESSURE_INJURY"],
                summary="Conheça seus direitos como paciente do SUS.",
                content=(
                    "VOCÊ TEM DIREITO A:\n\n"
                    "• Atendimento gratuito e de qualidade\n"
                    "• Receber curativos e materiais necessários\n"
                    "• Ser atendido com respeito e dignidade\n"
                    "• Receber informações sobre seu tratamento\n"
                    "• Ter acompanhamento regular\n"
                    "• Ser encaminhado para especialista quando necessário\n"
                    "• Receber medicamentos da farmácia básica\n"
                    "• Ter acesso a atendimento domiciliar se acamado\n"
                    "  (Programa Melhor em Casa)\n\n"
                    "PROGRAMA MELHOR EM CASA:\n"
                    "Se você tem dificuldade para ir ao posto,\n"
                    "pode solicitar atendimento em casa.\n"
                    "Peça informações na sua UBS."
                ),
            ),
        ]

    def get_content_for_patient(
        self,
        conditions: List[str],
        categories: Optional[List[ContentCategory]] = None,
    ) -> List[EducationalContent]:
        """
        Retorna conteúdos relevantes para o perfil do paciente.

        Args:
            conditions: Lista de condições do paciente
            categories: Filtrar por categorias (None = todas)
        """
        results = []
        for content in self.contents:
            # Verifica se alguma condição do paciente está nos targets
            if any(c in content.target_conditions for c in conditions):
                if categories is None or content.category in categories:
                    results.append(content)
        return results

    def add_content(self, content: EducationalContent):
        """Adiciona novo conteúdo à biblioteca"""
        self.contents.append(content)

    def search_content(self, query: str) -> List[EducationalContent]:
        """Busca conteúdo por texto"""
        q = query.lower()
        return [c for c in self.contents if q in c.title.lower() or q in c.content.lower()]


class PatientCommunication:
    """
    Sistema de comunicação bidirecional paciente-profissional.
    """

    def __init__(self):
        self.messages: Dict[str, List[PatientMessage]] = {}
        logger.info("PatientCommunication inicializado")

    def send_message(
        self,
        sender_id: str,
        sender_type: str,
        recipient_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        urgent: bool = False,
        attachment_path: Optional[str] = None,
    ) -> str:
        """Envia mensagem"""
        msg = PatientMessage(
            sender_id=sender_id,
            sender_type=sender_type,
            recipient_id=recipient_id,
            message_type=message_type,
            content=content,
            urgent=urgent,
            attachment_path=attachment_path,
        )

        # Armazenar na conversa de ambos
        for uid in (sender_id, recipient_id):
            if uid not in self.messages:
                self.messages[uid] = []
            self.messages[uid].append(msg)

        if urgent:
            logger.warning(f"Mensagem URGENTE de {sender_id} para {recipient_id}: {content[:50]}")
        else:
            logger.info(f"Mensagem enviada de {sender_id} para {recipient_id}")

        return msg.id

    def send_system_alert(
        self,
        recipient_id: str,
        content: str,
    ) -> str:
        """Envia alerta do sistema"""
        return self.send_message(
            sender_id="system",
            sender_type="system",
            recipient_id=recipient_id,
            content=content,
            message_type=MessageType.ALERT,
            urgent=True,
        )

    def send_educational_content(
        self,
        recipient_id: str,
        content: EducationalContent,
    ) -> str:
        """Envia conteúdo educativo"""
        return self.send_message(
            sender_id="system",
            sender_type="system",
            recipient_id=recipient_id,
            content=f"📚 {content.title}\n\n{content.content}",
            message_type=MessageType.EDUCATIONAL,
        )

    def get_conversation(self, user_id: str, unread_only: bool = False) -> List[Dict]:
        """Obtém mensagens de um usuário"""
        msgs = self.messages.get(user_id, [])
        if unread_only:
            msgs = [m for m in msgs if not m.read and m.recipient_id == user_id]
        return [
            {
                "id": m.id,
                "sender": m.sender_id,
                "sender_type": m.sender_type,
                "type": m.message_type.value,
                "content": m.content,
                "timestamp": m.timestamp,
                "read": m.read,
                "urgent": m.urgent,
            }
            for m in msgs
        ]

    def mark_as_read(self, user_id: str, message_id: str):
        """Marca mensagem como lida"""
        for msg in self.messages.get(user_id, []):
            if msg.id == message_id:
                msg.read = True
                break

    def get_unread_count(self, user_id: str) -> int:
        """Conta mensagens não lidas"""
        return sum(
            1 for m in self.messages.get(user_id, [])
            if not m.read and m.recipient_id == user_id
        )


class AdherenceTracker:
    """
    Rastreador de adesão ao tratamento.
    Monitora se o paciente está seguindo o plano de cuidado.
    """

    def __init__(self):
        self.records: Dict[str, List[AdherenceRecord]] = {}
        logger.info("AdherenceTracker inicializado")

    def record_activity(
        self,
        patient_id: str,
        plan_id: str,
        activity_id: str,
        activity_name: str,
        completed: bool,
        pain_level: Optional[int] = None,
        photo_path: Optional[str] = None,
        notes: str = "",
        alert_signs: Optional[List[str]] = None,
    ) -> str:
        """Registra execução (ou não) de uma atividade do plano"""
        record = AdherenceRecord(
            patient_id=patient_id,
            plan_id=plan_id,
            activity_id=activity_id,
            activity_name=activity_name,
            scheduled_date=datetime.now().isoformat()[:10],
            completed=completed,
            completed_at=datetime.now().isoformat() if completed else None,
            pain_level=pain_level,
            photo_path=photo_path,
            notes=notes,
            alert_signs=alert_signs or [],
        )

        if patient_id not in self.records:
            self.records[patient_id] = []
        self.records[patient_id].append(record)

        logger.info(
            f"Adesão registrada: {activity_name} — "
            f"{'completado' if completed else 'não completado'} — paciente {patient_id}"
        )
        return record.id

    def get_adherence_rate(self, patient_id: str, days: int = 30) -> float:
        """Calcula taxa de adesão do paciente (0.0 - 1.0)"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        records = [
            r for r in self.records.get(patient_id, [])
            if r.scheduled_date >= cutoff[:10]
        ]
        if not records:
            return 0.0
        return sum(1 for r in records if r.completed) / len(records)

    def get_adherence_report(self, patient_id: str) -> Dict:
        """Relatório de adesão do paciente"""
        all_records = self.records.get(patient_id, [])
        if not all_records:
            return {"patient_id": patient_id, "total_records": 0, "adherence_rate": 0.0}

        total = len(all_records)
        completed = sum(1 for r in all_records if r.completed)
        rate = completed / total

        # Dor média
        pain_scores = [r.pain_level for r in all_records if r.pain_level is not None]
        avg_pain = sum(pain_scores) / len(pain_scores) if pain_scores else None

        # Sinais de alerta reportados
        all_alerts = []
        for r in all_records:
            all_alerts.extend(r.alert_signs)

        return {
            "patient_id": patient_id,
            "total_records": total,
            "completed": completed,
            "missed": total - completed,
            "adherence_rate": round(rate, 3),
            "adherence_level": "boa" if rate > 0.8 else "parcial" if rate > 0.5 else "baixa",
            "average_pain": round(avg_pain, 1) if avg_pain else None,
            "alert_signs_reported": list(set(all_alerts)),
            "photos_submitted": sum(1 for r in all_records if r.photo_path),
        }

    def identify_non_adherent_patients(
        self,
        patient_ids: List[str],
        threshold: float = 0.5,
    ) -> List[Dict]:
        """Identifica pacientes com baixa adesão para busca ativa"""
        non_adherent = []
        for pid in patient_ids:
            rate = self.get_adherence_rate(pid)
            if rate < threshold:
                non_adherent.append({
                    "patient_id": pid,
                    "adherence_rate": rate,
                    "action": "busca_ativa",
                    "message": f"Adesão de {rate*100:.0f}% — necessita busca ativa e suporte",
                })
        return non_adherent
