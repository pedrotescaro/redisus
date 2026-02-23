# -*- coding: utf-8 -*-
"""
HEAL+ / REDISUS — Escalas Clínicas Validadas
=============================================

Implementação das principais escalas de avaliação de feridas:
1. PUSH Tool (Pressure Ulcer Scale for Healing)
2. BWAT (Bates-Jensen Wound Assessment Tool)
3. Escala de Braden (Risco de Lesão por Pressão)

Referências:
- NPUAP PUSH Tool 3.0
- Bates-Jensen Wound Assessment Tool (BWAT)
- Braden Scale for Predicting Pressure Sore Risk
"""

from dataclasses import dataclass, field
from enum import IntEnum, Enum
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json


# ============================================================
# PUSH Tool (Pressure Ulcer Scale for Healing)
# ============================================================

class PushAreaScore(IntEnum):
    """Score de área da ferida (cm²) - PUSH Tool."""
    SCORE_0 = 0   # 0 cm²
    SCORE_1 = 1   # < 0.3 cm²
    SCORE_2 = 2   # 0.3 - 0.6 cm²
    SCORE_3 = 3   # 0.7 - 1.0 cm²
    SCORE_4 = 4   # 1.1 - 2.0 cm²
    SCORE_5 = 5   # 2.1 - 3.0 cm²
    SCORE_6 = 6   # 3.1 - 4.0 cm²
    SCORE_7 = 7   # 4.1 - 8.0 cm²
    SCORE_8 = 8   # 8.1 - 12.0 cm²
    SCORE_9 = 9   # 12.1 - 24.0 cm²
    SCORE_10 = 10 # > 24.0 cm²


class PushExudateScore(IntEnum):
    """Score de exsudato - PUSH Tool."""
    NONE = 0      # Nenhum
    LIGHT = 1     # Pequeno
    MODERATE = 2  # Moderado
    HEAVY = 3     # Grande


class PushTissueScore(IntEnum):
    """Score de tipo de tecido - PUSH Tool."""
    CLOSED = 0           # Ferida fechada
    EPITHELIAL = 1       # Tecido epitelial
    GRANULATION = 2      # Tecido de granulação
    SLOUGH = 3           # Esfacelo
    NECROTIC = 4         # Tecido necrótico


# Mapeamento de área (cm²) para score PUSH
PUSH_AREA_RANGES = [
    (0, 0, 0),           # Score 0: 0 cm²
    (0.01, 0.3, 1),      # Score 1: < 0.3 cm²
    (0.3, 0.6, 2),       # Score 2: 0.3 - 0.6 cm²
    (0.7, 1.0, 3),       # Score 3: 0.7 - 1.0 cm²
    (1.1, 2.0, 4),       # Score 4: 1.1 - 2.0 cm²
    (2.1, 3.0, 5),       # Score 5: 2.1 - 3.0 cm²
    (3.1, 4.0, 6),       # Score 6: 3.1 - 4.0 cm²
    (4.1, 8.0, 7),       # Score 7: 4.1 - 8.0 cm²
    (8.1, 12.0, 8),      # Score 8: 8.1 - 12.0 cm²
    (12.1, 24.0, 9),     # Score 9: 12.1 - 24.0 cm²
    (24.1, float('inf'), 10),  # Score 10: > 24.0 cm²
]


@dataclass
class PushScore:
    """
    PUSH Tool Score (Pressure Ulcer Scale for Healing).
    
    Range: 0-17 (0 = ferida cicatrizada, 17 = pior estado)
    
    Componentes:
    - Área: 0-10 pontos
    - Exsudato: 0-3 pontos
    - Tipo de Tecido: 0-4 pontos
    """
    # Dados de entrada
    area_cm2: float = 0.0
    exudate_level: PushExudateScore = PushExudateScore.NONE
    dominant_tissue: PushTissueScore = PushTissueScore.CLOSED
    
    # Scores calculados
    area_score: int = 0
    exudate_score: int = 0
    tissue_score: int = 0
    total_score: int = 0
    
    # Metadados
    date: str = ""
    notes: str = ""
    
    def calculate(self) -> int:
        """Calcula o score total PUSH."""
        # Score de área
        self.area_score = self._calculate_area_score(self.area_cm2)
        
        # Score de exsudato
        self.exudate_score = int(self.exudate_level)
        
        # Score de tecido
        self.tissue_score = int(self.dominant_tissue)
        
        # Total
        self.total_score = self.area_score + self.exudate_score + self.tissue_score
        return self.total_score
    
    @staticmethod
    def _calculate_area_score(area_cm2: float) -> int:
        """Converte área em cm² para score PUSH (0-10)."""
        if area_cm2 <= 0:
            return 0
        for min_val, max_val, score in PUSH_AREA_RANGES:
            if min_val <= area_cm2 <= max_val:
                return score
        return 10  # > 24 cm²
    
    def get_interpretation(self) -> str:
        """Retorna interpretação clínica do score."""
        if self.total_score == 0:
            return "Ferida cicatrizada"
        elif self.total_score <= 5:
            return "Ferida em boa evolução - cicatrização avançada"
        elif self.total_score <= 10:
            return "Ferida em cicatrização moderada - monitorar evolução"
        elif self.total_score <= 14:
            return "Ferida com cicatrização lenta - reavaliar tratamento"
        else:
            return "Ferida grave - intervenção urgente necessária"
    
    def get_trend_analysis(self, previous_scores: List[int]) -> str:
        """Analisa tendência comparando com scores anteriores."""
        if not previous_scores:
            return "Primeira avaliação - sem histórico para comparação"
        
        last_score = previous_scores[-1]
        diff = self.total_score - last_score
        
        if diff < -3:
            return "✓ Melhora significativa - tratamento eficaz"
        elif diff < 0:
            return "✓ Melhora gradual - manter conduta"
        elif diff == 0:
            return "→ Estável - avaliar necessidade de ajuste"
        elif diff <= 3:
            return "⚠ Piora leve - revisar protocolo"
        else:
            return "⚠ Piora significativa - intervenção necessária"
    
    def to_dict(self) -> Dict:
        """Serializa para dicionário."""
        return {
            "area_cm2": self.area_cm2,
            "exudate_level": self.exudate_level.name,
            "dominant_tissue": self.dominant_tissue.name,
            "area_score": self.area_score,
            "exudate_score": self.exudate_score,
            "tissue_score": self.tissue_score,
            "total_score": self.total_score,
            "date": self.date,
            "notes": self.notes,
            "interpretation": self.get_interpretation(),
        }


# ============================================================
# BWAT (Bates-Jensen Wound Assessment Tool)
# ============================================================

class BWATItem(Enum):
    """Itens de avaliação BWAT (13 itens)."""
    SIZE = "size"                           # 1. Tamanho
    DEPTH = "depth"                         # 2. Profundidade
    EDGES = "edges"                         # 3. Bordas
    UNDERMINING = "undermining"             # 4. Descolamento
    NECROTIC_TYPE = "necrotic_type"         # 5. Tipo de tecido necrótico
    NECROTIC_AMOUNT = "necrotic_amount"     # 6. Quantidade de tecido necrótico
    EXUDATE_TYPE = "exudate_type"           # 7. Tipo de exsudato
    EXUDATE_AMOUNT = "exudate_amount"       # 8. Quantidade de exsudato
    SKIN_COLOR = "skin_color"               # 9. Cor da pele perilesional
    PERIPHERAL_EDEMA = "peripheral_edema"   # 10. Edema periférico
    INDURATION = "induration"               # 11. Endurecimento
    GRANULATION = "granulation"             # 12. Tecido de granulação
    EPITHELIALIZATION = "epithelialization" # 13. Epitelização


# Descrições e scores para cada item BWAT
BWAT_ITEMS = {
    BWATItem.SIZE: {
        "name": "Tamanho",
        "description": "Comprimento x largura (cm²)",
        "auto_fillable": True,  # IA pode preencher
        "scores": {
            1: "0 cm² (cicatrizada)",
            2: "< 4 cm²",
            3: "4-16 cm²",
            4: "16.1-36 cm²",
            5: "> 36 cm²",
        }
    },
    BWATItem.DEPTH: {
        "name": "Profundidade",
        "description": "Profundidade da ferida",
        "auto_fillable": False,  # Precisa input manual
        "scores": {
            1: "Sem perda de tecido",
            2: "Perda parcial envolvendo epiderme/derme",
            3: "Perda total envolvendo subcutâneo",
            4: "Obscurecida por necrose",
            5: "Perda total com exposição óssea/muscular",
        }
    },
    BWATItem.EDGES: {
        "name": "Bordas",
        "description": "Características das bordas da ferida",
        "auto_fillable": True,  # IA pode detectar
        "scores": {
            1: "Indistintas, difusas, nenhuma claramente visível",
            2: "Distintas, contorno claramente visível",
            3: "Bem definidas, não aderidas ao leito",
            4: "Bem definidas, aderidas, enroladas",
            5: "Bem definidas, fibróticas, cicatriz/hiperqueratose",
        }
    },
    BWATItem.UNDERMINING: {
        "name": "Descolamento/Tunelização",
        "description": "Área de tecido destruído sob pele íntegra",
        "auto_fillable": False,  # Precisa sondagem manual
        "scores": {
            1: "Ausente",
            2: "< 2 cm em qualquer área",
            3: "2-4 cm em < 50% das bordas",
            4: "2-4 cm em ≥ 50% das bordas",
            5: "> 4 cm ou tunelização",
        }
    },
    BWATItem.NECROTIC_TYPE: {
        "name": "Tipo de Tecido Necrótico",
        "description": "Tipo de tecido desvitalizado presente",
        "auto_fillable": True,  # IA pode classificar
        "scores": {
            1: "Nenhum visível",
            2: "Branco/cinza não aderente (fibrina)",
            3: "Amarelo aderente solto (esfacelo)",
            4: "Amarelo aderente fortemente (esfacelo)",
            5: "Preto/marrom, endurecido (escara)",
        }
    },
    BWATItem.NECROTIC_AMOUNT: {
        "name": "Quantidade de Necrose",
        "description": "Percentual do leito com tecido necrótico",
        "auto_fillable": True,  # IA pode calcular %
        "scores": {
            1: "Nenhum",
            2: "< 25% do leito",
            3: "25-50% do leito",
            4: "50-75% do leito",
            5: "> 75% do leito",
        }
    },
    BWATItem.EXUDATE_TYPE: {
        "name": "Tipo de Exsudato",
        "description": "Característica do exsudato",
        "auto_fillable": False,  # Precisa observação clínica
        "scores": {
            1: "Nenhum",
            2: "Sanguinolento",
            3: "Serossanguinolento",
            4: "Seroso",
            5: "Purulento",
        }
    },
    BWATItem.EXUDATE_AMOUNT: {
        "name": "Quantidade de Exsudato",
        "description": "Volume de exsudato produzido",
        "auto_fillable": False,  # Precisa observação clínica
        "scores": {
            1: "Nenhum, ferida seca",
            2: "Escasso",
            3: "Pequeno",
            4: "Moderado",
            5: "Grande",
        }
    },
    BWATItem.SKIN_COLOR: {
        "name": "Cor da Pele Perilesional",
        "description": "Cor da pele ao redor da ferida (4cm)",
        "auto_fillable": True,  # IA pode detectar
        "scores": {
            1: "Rosa ou normal para etnia",
            2: "Vermelho brilhante e/ou esbranquiçado ao toque",
            3: "Vermelho-escuro ou púrpura",
            4: "Escuro (cinza, marrom, preto)",
            5: "Pele saudável",  # Invertido - menor score = pior
        }
    },
    BWATItem.PERIPHERAL_EDEMA: {
        "name": "Edema Periférico",
        "description": "Edema na área perilesional (4cm)",
        "auto_fillable": False,  # Precisa palpação
        "scores": {
            1: "Sem edema",
            2: "Edema não depressível, < 4cm",
            3: "Edema não depressível, ≥ 4cm",
            4: "Edema depressível, < 4cm",
            5: "Crepitação e/ou edema depressível ≥ 4cm",
        }
    },
    BWATItem.INDURATION: {
        "name": "Endurecimento",
        "description": "Endurecimento da pele perilesional",
        "auto_fillable": False,  # Precisa palpação
        "scores": {
            1: "Ausente",
            2: "Endurecimento < 2cm ao redor da ferida",
            3: "Endurecimento 2-4cm, < 50% bordas",
            4: "Endurecimento 2-4cm, ≥ 50% bordas",
            5: "Endurecimento > 4cm em qualquer área",
        }
    },
    BWATItem.GRANULATION: {
        "name": "Tecido de Granulação",
        "description": "Percentual do leito com tecido de granulação",
        "auto_fillable": True,  # IA pode calcular %
        "scores": {
            1: "Pele intacta ou perda parcial",
            2: "Granulação brilhante > 75%",
            3: "Granulação brilhante 50-75%",
            4: "Granulação brilhante 25-50%",
            5: "Granulação < 25%",
        }
    },
    BWATItem.EPITHELIALIZATION: {
        "name": "Epitelização",
        "description": "Extensão da epitelização nas bordas",
        "auto_fillable": True,  # IA pode detectar
        "scores": {
            1: "100% do leito coberto (cicatrizada)",
            2: "75-100% do leito coberto",
            3: "50-75% do leito coberto",
            4: "25-50% do leito coberto",
            5: "< 25% do leito coberto",
        }
    },
}


@dataclass
class BWATScore:
    """
    BWAT Score (Bates-Jensen Wound Assessment Tool).
    
    Range: 13-65 (13 = ferida cicatrizada, 65 = pior estado)
    
    13 itens, cada um pontuado de 1 a 5.
    """
    # Scores por item (1-5 cada)
    scores: Dict[str, int] = field(default_factory=dict)
    
    # Auto-preenchidos pela IA
    auto_filled: Dict[str, int] = field(default_factory=dict)
    
    # Preenchidos manualmente
    manual_filled: Dict[str, int] = field(default_factory=dict)
    
    # Metadados
    total_score: int = 0
    date: str = ""
    evaluator: str = ""
    notes: str = ""
    
    def __post_init__(self):
        # Inicializa todos os itens com score 1 (melhor)
        if not self.scores:
            self.scores = {item.value: 1 for item in BWATItem}
    
    def set_score(self, item: BWATItem, score: int, is_auto: bool = False):
        """Define score para um item (1-5)."""
        score = max(1, min(5, score))
        self.scores[item.value] = score
        if is_auto:
            self.auto_filled[item.value] = score
        else:
            self.manual_filled[item.value] = score
    
    def calculate(self) -> int:
        """Calcula score total BWAT."""
        self.total_score = sum(self.scores.values())
        return self.total_score
    
    def get_completion_status(self) -> Tuple[int, int, List[str]]:
        """Retorna status de preenchimento."""
        total_items = len(BWATItem)
        filled_items = len([v for v in self.scores.values() if v > 0])
        
        # Itens que precisam preenchimento manual
        pending_manual = []
        for item in BWATItem:
            info = BWAT_ITEMS[item]
            if not info["auto_fillable"] and item.value not in self.manual_filled:
                pending_manual.append(info["name"])
        
        return filled_items, total_items, pending_manual
    
    def get_interpretation(self) -> str:
        """Retorna interpretação clínica do score."""
        if self.total_score == 0:
            return "Avaliação incompleta"
        elif self.total_score <= 20:
            return "Ferida em excelente estado - cicatrização avançada"
        elif self.total_score <= 30:
            return "Ferida em bom estado - cicatrização progredindo"
        elif self.total_score <= 40:
            return "Ferida em estado moderado - acompanhamento necessário"
        elif self.total_score <= 50:
            return "Ferida em estado preocupante - intensificar tratamento"
        else:
            return "Ferida em estado grave - intervenção especializada urgente"
    
    def get_severity(self) -> str:
        """Retorna severidade da ferida."""
        if self.total_score <= 20:
            return "LEVE"
        elif self.total_score <= 35:
            return "MODERADA"
        elif self.total_score <= 50:
            return "GRAVE"
        else:
            return "CRÍTICA"
    
    def to_dict(self) -> Dict:
        """Serializa para dicionário."""
        return {
            "scores": self.scores,
            "auto_filled": self.auto_filled,
            "manual_filled": self.manual_filled,
            "total_score": self.total_score,
            "date": self.date,
            "evaluator": self.evaluator,
            "notes": self.notes,
            "interpretation": self.get_interpretation(),
            "severity": self.get_severity(),
        }


# ============================================================
# Escala de Braden (Risco de Lesão por Pressão)
# ============================================================

class BradenCategory(Enum):
    """Categorias da Escala de Braden."""
    SENSORY_PERCEPTION = "sensory_perception"  # Percepção sensorial
    MOISTURE = "moisture"                       # Umidade
    ACTIVITY = "activity"                       # Atividade
    MOBILITY = "mobility"                       # Mobilidade
    NUTRITION = "nutrition"                     # Nutrição
    FRICTION_SHEAR = "friction_shear"           # Fricção e cisalhamento


# Descrições e scores para cada categoria Braden
BRADEN_CATEGORIES = {
    BradenCategory.SENSORY_PERCEPTION: {
        "name": "Percepção Sensorial",
        "description": "Capacidade de responder à pressão",
        "scores": {
            1: "Totalmente limitado - Não reage a estímulos dolorosos",
            2: "Muito limitado - Reage apenas a estímulos dolorosos",
            3: "Levemente limitado - Responde a comandos verbais",
            4: "Sem limitação - Responde adequadamente",
        }
    },
    BradenCategory.MOISTURE: {
        "name": "Umidade",
        "description": "Grau de exposição da pele à umidade",
        "scores": {
            1: "Sempre úmida - Pele constantemente molhada",
            2: "Muito úmida - Frequentemente úmida",
            3: "Ocasionalmente úmida - Às vezes úmida",
            4: "Raramente úmida - Pele geralmente seca",
        }
    },
    BradenCategory.ACTIVITY: {
        "name": "Atividade",
        "description": "Grau de atividade física",
        "scores": {
            1: "Acamado - Confinado à cama",
            2: "Restrito à cadeira - Muito limitado",
            3: "Caminha ocasionalmente - Com/sem assistência",
            4: "Caminha frequentemente - Fora do quarto 2x/dia",
        }
    },
    BradenCategory.MOBILITY: {
        "name": "Mobilidade",
        "description": "Capacidade de mudar e controlar posição",
        "scores": {
            1: "Totalmente imóvel - Não faz mudanças",
            2: "Muito limitado - Mudanças ocasionais leves",
            3: "Levemente limitado - Mudanças frequentes leves",
            4: "Sem limitações - Mudanças frequentes significativas",
        }
    },
    BradenCategory.NUTRITION: {
        "name": "Nutrição",
        "description": "Padrão habitual de ingestão alimentar",
        "scores": {
            1: "Muito pobre - Nunca come refeição completa",
            2: "Provavelmente inadequada - Come < 50% das refeições",
            3: "Adequada - Come > 50% das refeições",
            4: "Excelente - Come maioria das refeições",
        }
    },
    BradenCategory.FRICTION_SHEAR: {
        "name": "Fricção e Cisalhamento",
        "description": "Risco de fricção e cisalhamento",
        "scores": {
            1: "Problema - Requer assistência máxima, escorrega",
            2: "Problema potencial - Move-se com dificuldade",
            3: "Sem problema aparente - Move-se independentemente",
        }
    },
}


@dataclass
class BradenScore:
    """
    Escala de Braden (Risco de Lesão por Pressão).
    
    Range: 6-23 (6 = risco máximo, 23 = sem risco)
    
    Classificação de risco:
    - ≤ 9: Risco muito alto
    - 10-12: Risco alto
    - 13-14: Risco moderado
    - 15-18: Risco baixo
    - ≥ 19: Sem risco
    """
    # Scores por categoria
    scores: Dict[str, int] = field(default_factory=dict)
    
    # Metadados
    total_score: int = 0
    date: str = ""
    evaluator: str = ""
    patient_id: str = ""
    notes: str = ""
    
    def __post_init__(self):
        # Inicializa categorias com score máximo (sem risco)
        if not self.scores:
            self.scores = {
                BradenCategory.SENSORY_PERCEPTION.value: 4,
                BradenCategory.MOISTURE.value: 4,
                BradenCategory.ACTIVITY.value: 4,
                BradenCategory.MOBILITY.value: 4,
                BradenCategory.NUTRITION.value: 4,
                BradenCategory.FRICTION_SHEAR.value: 3,
            }
    
    def set_score(self, category: BradenCategory, score: int):
        """Define score para uma categoria."""
        # Fricção/cisalhamento vai até 3, outros até 4
        max_score = 3 if category == BradenCategory.FRICTION_SHEAR else 4
        score = max(1, min(max_score, score))
        self.scores[category.value] = score
    
    def calculate(self) -> int:
        """Calcula score total Braden."""
        self.total_score = sum(self.scores.values())
        return self.total_score
    
    def get_risk_level(self) -> Tuple[str, str]:
        """Retorna nível de risco e cor associada."""
        if self.total_score <= 9:
            return "MUITO ALTO", "#dc2626"  # Vermelho
        elif self.total_score <= 12:
            return "ALTO", "#f97316"  # Laranja
        elif self.total_score <= 14:
            return "MODERADO", "#eab308"  # Amarelo
        elif self.total_score <= 18:
            return "BAIXO", "#22c55e"  # Verde
        else:
            return "SEM RISCO", "#3b82f6"  # Azul
    
    def get_recommendations(self) -> List[str]:
        """Retorna recomendações baseadas no score."""
        recommendations = []
        risk_level, _ = self.get_risk_level()
        
        # Recomendações gerais por nível de risco
        if risk_level in ["MUITO ALTO", "ALTO"]:
            recommendations.append("⏰ Mudança de decúbito a cada 2 horas")
            recommendations.append("🛏️ Uso de colchão de redistribuição de pressão")
            recommendations.append("🧴 Hidratação intensiva da pele")
            recommendations.append("📋 Avaliação nutricional urgente")
        elif risk_level == "MODERADO":
            recommendations.append("⏰ Mudança de decúbito a cada 3-4 horas")
            recommendations.append("🧴 Hidratação regular da pele")
            recommendations.append("👀 Inspeção diária da pele")
        else:
            recommendations.append("👀 Inspeção periódica da pele")
            recommendations.append("🧴 Manter pele hidratada")
        
        # Recomendações específicas por categoria com score baixo
        for cat_value, score in self.scores.items():
            cat = BradenCategory(cat_value)
            if score <= 2:
                if cat == BradenCategory.MOISTURE:
                    recommendations.append("💧 Troca frequente de fraldas/lençóis")
                    recommendations.append("🧴 Uso de cremes barreira")
                elif cat == BradenCategory.NUTRITION:
                    recommendations.append("🍽️ Suplementação nutricional")
                    recommendations.append("👨‍⚕️ Avaliação por nutricionista")
                elif cat == BradenCategory.MOBILITY:
                    recommendations.append("🏃 Fisioterapia para mobilização")
                elif cat == BradenCategory.FRICTION_SHEAR:
                    recommendations.append("📐 Manter cabeceira ≤ 30°")
                    recommendations.append("🧤 Usar elevador de paciente")
        
        return recommendations
    
    def get_interpretation(self) -> str:
        """Retorna interpretação clínica."""
        risk_level, _ = self.get_risk_level()
        
        interpretations = {
            "MUITO ALTO": (
                "Paciente com risco muito alto de desenvolver lesão por pressão. "
                "Requer vigilância intensiva e medidas preventivas imediatas."
            ),
            "ALTO": (
                "Paciente com risco alto de lesão por pressão. "
                "Implementar protocolo de prevenção completo."
            ),
            "MODERADO": (
                "Paciente com risco moderado. "
                "Monitorar fatores de risco e manter medidas preventivas."
            ),
            "BAIXO": (
                "Paciente com risco baixo. "
                "Manter cuidados básicos de prevenção."
            ),
            "SEM RISCO": (
                "Paciente atualmente sem risco identificado. "
                "Reavaliar se houver mudança no estado clínico."
            ),
        }
        
        return interpretations.get(risk_level, "")
    
    def to_dict(self) -> Dict:
        """Serializa para dicionário."""
        risk_level, risk_color = self.get_risk_level()
        return {
            "scores": self.scores,
            "total_score": self.total_score,
            "risk_level": risk_level,
            "risk_color": risk_color,
            "date": self.date,
            "evaluator": self.evaluator,
            "patient_id": self.patient_id,
            "notes": self.notes,
            "interpretation": self.get_interpretation(),
            "recommendations": self.get_recommendations(),
        }


# ============================================================
# Helper: Conversão de análise de IA para escalas
# ============================================================

class ScaleCalculator:
    """
    Calcula scores de escalas clínicas a partir de análise de IA.
    
    Integra resultados do ClinicalWoundAnalyzer com escalas validadas.
    """
    
    # Fator de conversão pixels para cm² (precisa calibração com marcador)
    PIXEL_TO_CM2_FACTOR = 0.01  # Default: 100 pixels² = 1 cm²
    
    @classmethod
    def calculate_push_from_analysis(
        cls,
        tissue_percentages: Dict[str, float],
        wound_area_px: int,
        exudate_level: Optional[PushExudateScore] = None,
        pixel_to_cm2: Optional[float] = None,
    ) -> PushScore:
        """
        Calcula PUSH Score a partir de análise de IA.
        
        Args:
            tissue_percentages: Dict com % de cada tecido
            wound_area_px: Área da ferida em pixels
            exudate_level: Nível de exsudato (input manual)
            pixel_to_cm2: Fator de conversão pixel²->cm²
        
        Returns:
            PushScore calculado
        """
        factor = pixel_to_cm2 or cls.PIXEL_TO_CM2_FACTOR
        area_cm2 = wound_area_px * factor
        
        # Determina tecido dominante para score de tecido
        necrosis = tissue_percentages.get("necrosis", 0)
        slough = tissue_percentages.get("slough", 0)
        granulation = tissue_percentages.get("granulation", 0)
        epithelialization = tissue_percentages.get("epithelialization", 0)
        
        # Prioridade: necrose > esfacelo > granulação > epitelização
        if necrosis >= 10:
            tissue_score = PushTissueScore.NECROTIC
        elif slough >= 15:
            tissue_score = PushTissueScore.SLOUGH
        elif granulation >= 50:
            tissue_score = PushTissueScore.GRANULATION
        elif epithelialization >= 50:
            tissue_score = PushTissueScore.EPITHELIAL
        elif wound_area_px == 0:
            tissue_score = PushTissueScore.CLOSED
        else:
            tissue_score = PushTissueScore.GRANULATION  # Default
        
        push = PushScore(
            area_cm2=area_cm2,
            exudate_level=exudate_level or PushExudateScore.NONE,
            dominant_tissue=tissue_score,
            date=datetime.now().isoformat(),
        )
        push.calculate()
        
        return push
    
    @classmethod
    def calculate_bwat_from_analysis(
        cls,
        tissue_percentages: Dict[str, float],
        wound_area_px: int,
        border_analysis: Optional[Dict] = None,
        pixel_to_cm2: Optional[float] = None,
    ) -> BWATScore:
        """
        Calcula BWAT Score a partir de análise de IA (itens auto-preenchíveis).
        
        Os itens que precisam input manual ficam com score 1 (melhor caso).
        
        Args:
            tissue_percentages: Dict com % de cada tecido
            wound_area_px: Área da ferida em pixels
            border_analysis: Análise das bordas da ferida
            pixel_to_cm2: Fator de conversão pixel²->cm²
        
        Returns:
            BWATScore parcialmente preenchido
        """
        bwat = BWATScore(date=datetime.now().isoformat())
        
        factor = pixel_to_cm2 or cls.PIXEL_TO_CM2_FACTOR
        area_cm2 = wound_area_px * factor
        
        necrosis = tissue_percentages.get("necrosis", 0)
        slough = tissue_percentages.get("slough", 0)
        granulation = tissue_percentages.get("granulation", 0)
        epithelialization = tissue_percentages.get("epithelialization", 0)
        
        # 1. Tamanho (auto)
        if area_cm2 <= 0:
            size_score = 1
        elif area_cm2 < 4:
            size_score = 2
        elif area_cm2 <= 16:
            size_score = 3
        elif area_cm2 <= 36:
            size_score = 4
        else:
            size_score = 5
        bwat.set_score(BWATItem.SIZE, size_score, is_auto=True)
        
        # 5. Tipo de tecido necrótico (auto)
        if necrosis >= 20:
            necrotic_type_score = 5  # Escara
        elif necrosis >= 5:
            necrotic_type_score = 4  # Esfacelo aderente
        elif slough >= 20:
            necrotic_type_score = 3  # Esfacelo solto
        elif slough >= 5:
            necrotic_type_score = 2  # Fibrina
        else:
            necrotic_type_score = 1  # Nenhum
        bwat.set_score(BWATItem.NECROTIC_TYPE, necrotic_type_score, is_auto=True)
        
        # 6. Quantidade de necrose (auto)
        total_necrotic = necrosis + slough
        if total_necrotic <= 0:
            necrotic_amount_score = 1
        elif total_necrotic < 25:
            necrotic_amount_score = 2
        elif total_necrotic < 50:
            necrotic_amount_score = 3
        elif total_necrotic < 75:
            necrotic_amount_score = 4
        else:
            necrotic_amount_score = 5
        bwat.set_score(BWATItem.NECROTIC_AMOUNT, necrotic_amount_score, is_auto=True)
        
        # 12. Granulação (auto) - Score invertido (mais granulação = melhor)
        if granulation >= 75:
            gran_score = 2
        elif granulation >= 50:
            gran_score = 3
        elif granulation >= 25:
            gran_score = 4
        elif granulation > 0:
            gran_score = 5
        else:
            gran_score = 1  # Sem granulação visível (pode ser cicatrizada)
        bwat.set_score(BWATItem.GRANULATION, gran_score, is_auto=True)
        
        # 13. Epitelização (auto)
        if epithelialization >= 75:
            epit_score = 2
        elif epithelialization >= 50:
            epit_score = 3
        elif epithelialization >= 25:
            epit_score = 4
        elif epithelialization > 0:
            epit_score = 5
        else:
            epit_score = 1
        bwat.set_score(BWATItem.EPITHELIALIZATION, epit_score, is_auto=True)
        
        # 3. Bordas (auto se análise disponível)
        if border_analysis:
            if border_analysis.get("regular_borders", True):
                edge_score = 2  # Distintas
            else:
                edge_score = 4  # Enroladas/irregulares
            if border_analysis.get("maceration", False):
                edge_score = max(edge_score, 3)  # Não aderidas
            bwat.set_score(BWATItem.EDGES, edge_score, is_auto=True)
        
        # 9. Cor da pele perilesional (auto se análise disponível)
        if border_analysis:
            if border_analysis.get("inflammation", False):
                skin_score = 3  # Vermelho-escuro
            else:
                skin_score = 1  # Normal
            bwat.set_score(BWATItem.SKIN_COLOR, skin_score, is_auto=True)
        
        bwat.calculate()
        return bwat
    
    @classmethod
    def generate_evolution_chart_data(
        cls,
        push_history: List[PushScore]
    ) -> Dict:
        """
        Gera dados para gráfico de evolução PUSH.
        
        Args:
            push_history: Lista de PushScores ao longo do tempo
        
        Returns:
            Dict com dados para gráfico (labels, datasets)
        """
        if not push_history:
            return {"labels": [], "datasets": []}
        
        labels = [p.date[:10] if p.date else f"#{i+1}" for i, p in enumerate(push_history)]
        
        return {
            "labels": labels,
            "datasets": [
                {
                    "label": "Score Total",
                    "data": [p.total_score for p in push_history],
                    "borderColor": "#3b82f6",
                    "fill": False,
                },
                {
                    "label": "Área",
                    "data": [p.area_score for p in push_history],
                    "borderColor": "#22c55e",
                    "fill": False,
                },
                {
                    "label": "Tecido",
                    "data": [p.tissue_score for p in push_history],
                    "borderColor": "#f59e0b",
                    "fill": False,
                },
            ]
        }


# ============================================================
# Exportação
# ============================================================

__all__ = [
    # PUSH
    "PushScore",
    "PushAreaScore",
    "PushExudateScore",
    "PushTissueScore",
    "PUSH_AREA_RANGES",
    
    # BWAT
    "BWATScore",
    "BWATItem",
    "BWAT_ITEMS",
    
    # Braden
    "BradenScore",
    "BradenCategory",
    "BRADEN_CATEGORIES",
    
    # Helper
    "ScaleCalculator",
]
