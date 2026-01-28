"""
REDISUS - Sistema de Diagnóstico de Feridas
Módulo de Recomendação de Tratamento

Este módulo sugere protocolos de tratamento baseados na etiologia
e composição tecidual da ferida.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from ..core.config import EtiologyType, TissueType, ETIOLOGY_NAMES, TISSUE_NAMES


@dataclass
class TreatmentStep:
    """Etapa de tratamento"""
    order: int
    action: str
    description: str
    products: List[str]
    frequency: str
    notes: Optional[str] = None


@dataclass
class TreatmentProtocol:
    """Protocolo de tratamento completo"""
    name: str
    etiology: str
    objective: str
    steps: List[TreatmentStep]
    contraindications: List[str]
    monitoring: List[str]
    expected_outcome: str
    evidence_level: str  # A, B, C, D
    references: List[str]
    
    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        return {
            "name": self.name,
            "etiology": self.etiology,
            "objective": self.objective,
            "steps": [
                {
                    "order": s.order,
                    "action": s.action,
                    "description": s.description,
                    "products": s.products,
                    "frequency": s.frequency,
                    "notes": s.notes,
                }
                for s in self.steps
            ],
            "contraindications": self.contraindications,
            "monitoring": self.monitoring,
            "expected_outcome": self.expected_outcome,
            "evidence_level": self.evidence_level,
            "references": self.references,
        }
    
    def get_summary(self) -> str:
        """Retorna resumo textual do protocolo"""
        lines = [
            f"📋 PROTOCOLO: {self.name}",
            f"🎯 Objetivo: {self.objective}",
            "",
            "📝 ETAPAS DE TRATAMENTO:",
        ]
        
        for step in self.steps:
            lines.append(f"\n  {step.order}. {step.action}")
            lines.append(f"     {step.description}")
            lines.append(f"     Produtos: {', '.join(step.products)}")
            lines.append(f"     Frequência: {step.frequency}")
            if step.notes:
                lines.append(f"     ⚠️ {step.notes}")
        
        lines.extend([
            "",
            "⚠️ CONTRAINDICAÇÕES:",
            *[f"   • {c}" for c in self.contraindications],
            "",
            "📊 MONITORAMENTO:",
            *[f"   • {m}" for m in self.monitoring],
            "",
            f"📈 Resultado esperado: {self.expected_outcome}",
            f"📚 Nível de evidência: {self.evidence_level}",
        ])
        
        return "\n".join(lines)


@dataclass
class TreatmentRecommendation:
    """Recomendação completa de tratamento"""
    primary_protocol: TreatmentProtocol
    tissue_specific_actions: Dict[str, str]
    priority_level: str  # "urgent", "high", "moderate", "low"
    follow_up_days: int
    additional_notes: List[str]


class TreatmentKnowledgeBase:
    """
    Base de conhecimento com protocolos de tratamento.
    
    Carrega protocolos de arquivos JSON ou usa protocolos embutidos.
    """
    
    def __init__(self, protocols_dir: Optional[Path] = None):
        self.protocols_dir = protocols_dir
        self._protocols: Dict[EtiologyType, TreatmentProtocol] = {}
        self._tissue_actions: Dict[TissueType, str] = {}
        
        self._load_default_protocols()
        
    def _load_default_protocols(self):
        """Carrega protocolos padrão embutidos"""
        
        # Protocolo para Úlcera Venosa
        self._protocols[EtiologyType.VENOUS_ULCER] = TreatmentProtocol(
            name="Protocolo de Úlcera Venosa",
            etiology="Úlcera Venosa",
            objective="Promover cicatrização através de controle do edema e ambiente úmido",
            steps=[
                TreatmentStep(
                    order=1,
                    action="Limpeza da ferida",
                    description="Irrigar com solução fisiológica morna",
                    products=["Solução Fisiológica 0.9%", "Seringa 20ml"],
                    frequency="A cada troca de curativo"
                ),
                TreatmentStep(
                    order=2,
                    action="Desbridamento (se necessário)",
                    description="Remover tecido desvitalizado",
                    products=["Colagenase", "Hidrogel", "Curativo secundário"],
                    frequency="Conforme avaliação",
                    notes="Evitar desbridamento agressivo em pacientes anticoagulados"
                ),
                TreatmentStep(
                    order=3,
                    action="Cobertura primária",
                    description="Aplicar cobertura que mantenha meio úmido",
                    products=["Espuma de poliuretano", "Alginato de cálcio", "Hidrofibra"],
                    frequency="A cada 3-7 dias conforme exsudato"
                ),
                TreatmentStep(
                    order=4,
                    action="Terapia compressiva",
                    description="Aplicar bandagem compressiva multicamadas",
                    products=["Sistema de compressão multicamadas", "Atadura"],
                    frequency="Semanal ou conforme protocolo",
                    notes="ESSENCIAL para cicatrização. Verificar ITB antes"
                ),
            ],
            contraindications=[
                "ITB < 0.8 (doença arterial associada)",
                "Insuficiência cardíaca descompensada",
                "Infecção ativa não tratada",
            ],
            monitoring=[
                "Redução de área da ferida (>30% em 4 semanas)",
                "Controle do edema",
                "Sinais de infecção",
                "Aderência ao tratamento compressivo",
            ],
            expected_outcome="Cicatrização em 12-24 semanas com terapia compressiva adequada",
            evidence_level="A",
            references=[
                "SOBEST - Consenso de Úlcera Venosa",
                "EWMA Guidelines 2023",
            ]
        )
        
        # Protocolo para Úlcera Arterial
        self._protocols[EtiologyType.ARTERIAL_ULCER] = TreatmentProtocol(
            name="Protocolo de Úlcera Arterial",
            etiology="Úlcera Arterial",
            objective="Manter ferida limpa e seca enquanto trata causa base (revascularização)",
            steps=[
                TreatmentStep(
                    order=1,
                    action="Avaliação vascular",
                    description="Encaminhar para avaliação de cirurgia vascular",
                    products=[],
                    frequency="Imediato",
                    notes="Prioridade: revascularização"
                ),
                TreatmentStep(
                    order=2,
                    action="Limpeza suave",
                    description="Lavar com SF 0.9% sem esfregar",
                    products=["Solução Fisiológica 0.9%"],
                    frequency="A cada troca"
                ),
                TreatmentStep(
                    order=3,
                    action="Proteção da ferida",
                    description="Manter ferida seca e protegida",
                    products=["Gaze não aderente", "Filme transparente"],
                    frequency="Diária ou conforme necessidade"
                ),
                TreatmentStep(
                    order=4,
                    action="Controle da dor",
                    description="Analgesia adequada conforme prescrição",
                    products=["Conforme prescrição médica"],
                    frequency="Contínuo"
                ),
            ],
            contraindications=[
                "NÃO usar terapia compressiva",
                "Evitar desbridamento agressivo até revascularização",
                "Não usar produtos que aumentem perfusão local",
            ],
            monitoring=[
                "ITB seriado",
                "Sinais de isquemia crítica",
                "Dor em repouso",
                "Evolução após revascularização",
            ],
            expected_outcome="Cicatrização dependente do sucesso da revascularização",
            evidence_level="B",
            references=[
                "TASC II Guidelines",
                "SBC - Diretrizes de Doença Arterial Periférica",
            ]
        )
        
        # Protocolo para Pé Diabético
        self._protocols[EtiologyType.DIABETIC_FOOT] = TreatmentProtocol(
            name="Protocolo de Pé Diabético",
            etiology="Úlcera Neuropática - Pé Diabético",
            objective="Cicatrização através de offloading, controle glicêmico e prevenção de infecção",
            steps=[
                TreatmentStep(
                    order=1,
                    action="Avaliação multidisciplinar",
                    description="Envolver endocrinologista, vascular, infectologista",
                    products=[],
                    frequency="Inicial e conforme necessidade"
                ),
                TreatmentStep(
                    order=2,
                    action="Desbridamento",
                    description="Remover calosidades e tecido necrótico",
                    products=["Bisturi", "Curetas"],
                    frequency="Semanal",
                    notes="Essencial para remoção de carga bacteriana"
                ),
                TreatmentStep(
                    order=3,
                    action="Cobertura adequada",
                    description="Curativo conforme características da ferida",
                    products=["Espuma", "Alginato", "Prata (se infectado)"],
                    frequency="1-3x por semana"
                ),
                TreatmentStep(
                    order=4,
                    action="Offloading",
                    description="Reduzir pressão na área afetada",
                    products=["Gesso de contato total", "Bota removível", "Palmilhas"],
                    frequency="Contínuo",
                    notes="Fator mais importante para cicatrização"
                ),
                TreatmentStep(
                    order=5,
                    action="Controle glicêmico",
                    description="Otimizar controle do diabetes",
                    products=["Conforme prescrição"],
                    frequency="Contínuo",
                    notes="Meta: HbA1c < 7%"
                ),
            ],
            contraindications=[
                "Não usar agentes tópicos citotóxicos",
                "Evitar imersão em água quente (risco de queimadura)",
            ],
            monitoring=[
                "Classificação Wagner/Texas",
                "Sinais de infecção (IDSA/IWGDF)",
                "Controle glicêmico (HbA1c)",
                "Avaliação sensitiva com monofilamento",
            ],
            expected_outcome="Cicatrização em 8-12 semanas com offloading adequado",
            evidence_level="A",
            references=[
                "IWGDF Guidelines 2023",
                "SBD - Diretrizes Pé Diabético",
            ]
        )
        
        # Protocolo para Lesão por Pressão
        self._protocols[EtiologyType.PRESSURE_INJURY] = TreatmentProtocol(
            name="Protocolo de Lesão por Pressão",
            etiology="Lesão por Pressão",
            objective="Reduzir pressão, tratar infecção e promover ambiente de cicatrização",
            steps=[
                TreatmentStep(
                    order=1,
                    action="Alívio da pressão",
                    description="Superfície de suporte adequada e reposicionamento",
                    products=["Colchão pneumático", "Coxins de posicionamento"],
                    frequency="Reposicionar a cada 2h",
                    notes="Fundamental para qualquer estágio"
                ),
                TreatmentStep(
                    order=2,
                    action="Limpeza",
                    description="Irrigar com SF 0.9%",
                    products=["Solução Fisiológica 0.9%"],
                    frequency="A cada troca"
                ),
                TreatmentStep(
                    order=3,
                    action="Desbridamento",
                    description="Remover tecido necrótico (exceto calcanhar estável)",
                    products=["Colagenase", "Hidrogel", "Papaína"],
                    frequency="Conforme avaliação"
                ),
                TreatmentStep(
                    order=4,
                    action="Cobertura",
                    description="Manter meio úmido ideal",
                    products=["Hidrocolóide", "Espuma", "Alginato"],
                    frequency="Conforme exsudato"
                ),
                TreatmentStep(
                    order=5,
                    action="Suporte nutricional",
                    description="Avaliar e suplementar nutrição",
                    products=["Suplemento proteico", "Vitaminas A, C, Zinco"],
                    frequency="Diário"
                ),
            ],
            contraindications=[
                "Não desbridar escara seca e estável em calcanhar",
                "Evitar massagem em áreas de hiperemia",
            ],
            monitoring=[
                "Estadiamento NPUAP/EPUAP",
                "Escala de Braden",
                "Estado nutricional",
                "Sinais de infecção",
            ],
            expected_outcome="Melhora progressiva com alívio adequado da pressão",
            evidence_level="A",
            references=[
                "NPUAP/EPUAP/PPPIA Guidelines 2019",
                "SOBEST - Consenso Lesão por Pressão",
            ]
        )
        
        # Protocolo para Ferida Cirúrgica
        self._protocols[EtiologyType.SURGICAL_WOUND] = TreatmentProtocol(
            name="Protocolo de Ferida Cirúrgica",
            etiology="Ferida Cirúrgica",
            objective="Promover cicatrização por segunda intenção de forma limpa e ordenada",
            steps=[
                TreatmentStep(
                    order=1,
                    action="Avaliação",
                    description="Identificar causa da deiscência e tratar fatores",
                    products=[],
                    frequency="Inicial"
                ),
                TreatmentStep(
                    order=2,
                    action="Limpeza",
                    description="Irrigar com SF 0.9%",
                    products=["Solução Fisiológica 0.9%"],
                    frequency="A cada troca"
                ),
                TreatmentStep(
                    order=3,
                    action="Terapia Pressão Negativa",
                    description="Considerar VAC se ferida profunda",
                    products=["Sistema VAC", "Espumas específicas"],
                    frequency="Trocas a cada 48-72h",
                    notes="Excelente para feridas com grande perda de substância"
                ),
                TreatmentStep(
                    order=4,
                    action="Cobertura convencional",
                    description="Se VAC não disponível, usar coberturas absorventes",
                    products=["Alginato", "Espuma", "Hidrofibra"],
                    frequency="Conforme exsudato"
                ),
            ],
            contraindications=[
                "VAC contraindicado em feridas com exposição vascular",
                "Investigar fístula antes de fechar",
            ],
            monitoring=[
                "Redução de profundidade",
                "Qualidade do tecido de granulação",
                "Sinais de infecção de sítio cirúrgico",
            ],
            expected_outcome="Cicatrização progressiva com tecido de granulação saudável",
            evidence_level="B",
            references=[
                "CDC Guidelines SSI Prevention",
                "WUWHS Consensus 2020",
            ]
        )
        
        # Ações por tipo de tecido
        self._tissue_actions = {
            TissueType.GRANULATION: "Proteger o tecido de granulação. Manter meio úmido. Evitar trauma nas trocas.",
            TissueType.SLOUGH: "Realizar desbridamento autolítico (hidrogel) ou enzimático (colagenase). Considerar desbridamento instrumental se extenso.",
            TissueType.NECROSIS: "Desbridamento prioritário. Avaliar viabilidade para desbridamento cirúrgico. Exceção: necrose seca em calcanhar.",
            TissueType.PERIWOUND: "Proteger pele perilesional com barreira cutânea. Tratar dermatite se presente.",
        }
    
    def get_protocol(self, etiology: EtiologyType) -> Optional[TreatmentProtocol]:
        """Retorna protocolo para determinada etiologia"""
        return self._protocols.get(etiology)
    
    def get_tissue_action(self, tissue: TissueType) -> str:
        """Retorna ação recomendada para tipo de tecido"""
        return self._tissue_actions.get(tissue, "Avaliar individualmente")
    
    def load_custom_protocols(self, json_path: Path):
        """Carrega protocolos customizados de arquivo JSON"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for protocol_data in data.get("protocols", []):
                # Parse e adiciona ao dicionário
                etiology_key = protocol_data.get("etiology_key")
                if etiology_key and hasattr(EtiologyType, etiology_key):
                    etiology = EtiologyType[etiology_key]
                    protocol = self._parse_protocol(protocol_data)
                    self._protocols[etiology] = protocol
                    
            logger.info(f"Protocolos customizados carregados de {json_path}")
            
        except Exception as e:
            logger.error(f"Erro ao carregar protocolos: {e}")
    
    def _parse_protocol(self, data: Dict) -> TreatmentProtocol:
        """Parse de dados JSON para TreatmentProtocol"""
        steps = [
            TreatmentStep(
                order=s["order"],
                action=s["action"],
                description=s["description"],
                products=s.get("products", []),
                frequency=s.get("frequency", ""),
                notes=s.get("notes")
            )
            for s in data.get("steps", [])
        ]
        
        return TreatmentProtocol(
            name=data["name"],
            etiology=data["etiology"],
            objective=data["objective"],
            steps=steps,
            contraindications=data.get("contraindications", []),
            monitoring=data.get("monitoring", []),
            expected_outcome=data.get("expected_outcome", ""),
            evidence_level=data.get("evidence_level", "C"),
            references=data.get("references", [])
        )


class TreatmentRecommender:
    """
    Motor de recomendação de tratamento.
    
    Combina:
    - Etiologia classificada
    - Composição tecidual
    - Protocolos baseados em evidência
    """
    
    def __init__(self, knowledge_base: Optional[TreatmentKnowledgeBase] = None):
        self.kb = knowledge_base or TreatmentKnowledgeBase()
    
    def recommend(
        self,
        etiology: EtiologyType,
        tissue_percentages: Dict[str, float],
        confidence: float = 1.0
    ) -> TreatmentRecommendation:
        """
        Gera recomendação de tratamento.
        
        Args:
            etiology: Etiologia classificada
            tissue_percentages: Porcentagem de cada tecido
            confidence: Confiança na classificação
            
        Returns:
            TreatmentRecommendation
        """
        # Obtém protocolo base
        protocol = self.kb.get_protocol(etiology)
        
        if protocol is None:
            # Protocolo genérico se não encontrado
            protocol = self._get_generic_protocol()
        
        # Ações específicas por tecido
        tissue_actions = {}
        for tissue_type in TissueType:
            tissue_name = TISSUE_NAMES[tissue_type.value]
            percentage = tissue_percentages.get(tissue_name, 0)
            
            if percentage > 5:  # Só inclui se > 5%
                tissue_actions[tissue_name] = self.kb.get_tissue_action(tissue_type)
        
        # Determina prioridade
        priority = self._determine_priority(tissue_percentages, etiology)
        
        # Follow-up
        follow_up = self._determine_follow_up(tissue_percentages, priority)
        
        # Notas adicionais
        notes = self._generate_notes(tissue_percentages, confidence)
        
        return TreatmentRecommendation(
            primary_protocol=protocol,
            tissue_specific_actions=tissue_actions,
            priority_level=priority,
            follow_up_days=follow_up,
            additional_notes=notes
        )
    
    def _determine_priority(
        self,
        tissue_percentages: Dict[str, float],
        etiology: EtiologyType
    ) -> str:
        """Determina nível de prioridade"""
        necrosis_pct = tissue_percentages.get(TISSUE_NAMES[TissueType.NECROSIS.value], 0)
        
        # Alta prioridade se muita necrose
        if necrosis_pct > 30:
            return "urgent"
        
        # Úlcera arterial é sempre alta prioridade
        if etiology == EtiologyType.ARTERIAL_ULCER:
            return "high"
        
        # Pé diabético com necrose
        if etiology == EtiologyType.DIABETIC_FOOT and necrosis_pct > 10:
            return "high"
        
        # Se tem mais granulação que necrose/esfacelo
        granulation_pct = tissue_percentages.get(TISSUE_NAMES[TissueType.GRANULATION.value], 0)
        slough_pct = tissue_percentages.get(TISSUE_NAMES[TissueType.SLOUGH.value], 0)
        
        if granulation_pct > (necrosis_pct + slough_pct):
            return "moderate"
        
        return "high"
    
    def _determine_follow_up(
        self,
        tissue_percentages: Dict[str, float],
        priority: str
    ) -> int:
        """Determina dias até próxima avaliação"""
        follow_up_map = {
            "urgent": 1,
            "high": 3,
            "moderate": 7,
            "low": 14
        }
        return follow_up_map.get(priority, 7)
    
    def _generate_notes(
        self,
        tissue_percentages: Dict[str, float],
        confidence: float
    ) -> List[str]:
        """Gera notas adicionais"""
        notes = []
        
        if confidence < 0.7:
            notes.append(
                "⚠️ Classificação com baixa confiança. "
                "Recomenda-se avaliação presencial por especialista."
            )
        
        necrosis_pct = tissue_percentages.get(TISSUE_NAMES[TissueType.NECROSIS.value], 0)
        if necrosis_pct > 20:
            notes.append(
                "⚠️ Alta porcentagem de tecido necrótico. "
                "Considerar desbridamento cirúrgico urgente."
            )
        
        granulation_pct = tissue_percentages.get(TISSUE_NAMES[TissueType.GRANULATION.value], 0)
        if granulation_pct > 70:
            notes.append(
                "✅ Boa evolução com tecido de granulação predominante. "
                "Manter conduta e proteger o leito."
            )
        
        return notes
    
    def _get_generic_protocol(self) -> TreatmentProtocol:
        """Retorna protocolo genérico"""
        return TreatmentProtocol(
            name="Protocolo Genérico de Feridas",
            etiology="Não classificada",
            objective="Manter ambiente adequado para cicatrização",
            steps=[
                TreatmentStep(
                    order=1,
                    action="Limpeza",
                    description="Irrigar com SF 0.9%",
                    products=["Solução Fisiológica 0.9%"],
                    frequency="A cada troca"
                ),
                TreatmentStep(
                    order=2,
                    action="Avaliação",
                    description="Identificar etiologia para tratamento específico",
                    products=[],
                    frequency="Consultar especialista"
                ),
                TreatmentStep(
                    order=3,
                    action="Cobertura",
                    description="Manter meio úmido",
                    products=["Cobertura adequada ao exsudato"],
                    frequency="Conforme necessidade"
                ),
            ],
            contraindications=[],
            monitoring=["Evolução da ferida", "Sinais de infecção"],
            expected_outcome="Dependente da identificação da etiologia",
            evidence_level="C",
            references=[]
        )
