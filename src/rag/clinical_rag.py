"""
HEAL/REDISUS - RAG (Retrieval-Augmented Generation) para Suporte Clínico
Base de conhecimento médico com recuperação contextual para apoio à decisão.

Implementa:
- Base de conhecimento em feridas e cicatrização
- Protocolos clínicos SUS (CONITEC, Ministério da Saúde)
- Recuperação contextual baseada no caso clínico
- Geração de respostas assistidas por evidência
- Referências bibliográficas e nível de evidência
"""
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class EvidenceLevel(Enum):
    """Níveis de evidência (Oxford CEBM)"""
    LEVEL_1A = "1a"  # Revisão sistemática de ECR
    LEVEL_1B = "1b"  # ECR individual
    LEVEL_2A = "2a"  # Revisão sistemática de estudos de coorte
    LEVEL_2B = "2b"  # Estudo de coorte individual
    LEVEL_3  = "3"   # Estudo caso-controle
    LEVEL_4  = "4"   # Série de casos
    LEVEL_5  = "5"   # Opinião de especialista
    EXPERT_CONSENSUS = "consensus"
    CLINICAL_GUIDELINE = "guideline"


class KnowledgeCategory(Enum):
    """Categorias de conhecimento clínico"""
    WOUND_ASSESSMENT = "avaliacao_feridas"
    WOUND_TREATMENT = "tratamento_feridas"
    TISSUE_MANAGEMENT = "manejo_tecidual"
    INFECTION_CONTROL = "controle_infeccao"
    DRESSING_SELECTION = "selecao_coberturas"
    NUTRITION = "nutricao"
    PAIN_MANAGEMENT = "manejo_dor"
    PREVENTION = "prevencao"
    SPOROTRICHOSIS = "esporotricose"
    DIABETIC_FOOT = "pe_diabetico"
    VENOUS_ULCER = "ulcera_venosa"
    PRESSURE_INJURY = "lesao_pressao"
    PATIENT_EDUCATION = "educacao_paciente"
    SUS_PROTOCOLS = "protocolos_sus"


@dataclass
class KnowledgeEntry:
    """Entrada na base de conhecimento"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    content: str = ""
    category: KnowledgeCategory = KnowledgeCategory.WOUND_TREATMENT
    evidence_level: EvidenceLevel = EvidenceLevel.LEVEL_5
    source: str = ""
    year: int = 2024
    keywords: List[str] = field(default_factory=list)
    icd10_codes: List[str] = field(default_factory=list)

    def relevance_score(self, query_keywords: List[str]) -> float:
        """Calcula relevância para uma consulta"""
        if not query_keywords or not self.keywords:
            return 0.0

        query_set = set(w.lower() for w in query_keywords)
        entry_set = set(w.lower() for w in self.keywords)
        content_words = set(self.content.lower().split())

        # Match direto em keywords
        keyword_match = len(query_set & entry_set) / max(len(query_set), 1)

        # Match no conteúdo
        content_match = len(query_set & content_words) / max(len(query_set), 1)

        # Bonus por nível de evidência
        evidence_bonus = {
            EvidenceLevel.LEVEL_1A: 0.15,
            EvidenceLevel.LEVEL_1B: 0.12,
            EvidenceLevel.LEVEL_2A: 0.10,
            EvidenceLevel.CLINICAL_GUIDELINE: 0.10,
        }.get(self.evidence_level, 0.0)

        # Bonus por recência
        recency = max(0, (self.year - 2018)) * 0.01

        return keyword_match * 0.5 + content_match * 0.3 + evidence_bonus + recency


class ClinicalKnowledgeBase:
    """
    Base de conhecimento clínico para feridas.
    Inclui protocolos SUS, diretrizes internacionais e evidências.
    """

    def __init__(self):
        self.entries: List[KnowledgeEntry] = []
        self._load_default_knowledge()

    def _load_default_knowledge(self):
        """Carrega base de conhecimento padrão"""
        self.entries = [
            # === AVALIAÇÃO DE FERIDAS ===
            KnowledgeEntry(
                title="Avaliação TIME de Feridas",
                content=(
                    "A abordagem TIME guia a preparação do leito da ferida: "
                    "T (Tissue/Tecido) — remover tecido não viável por debridamento; "
                    "I (Infection/Inflamação) — controlar carga bacteriana e inflamação; "
                    "M (Moisture/Umidade) — manter equilíbrio de umidade adequado; "
                    "E (Edge/Borda) — promover avanço das bordas epiteliais. "
                    "Reavaliar em cada troca de curativo. "
                    "Documentar área (cm²), profundidade, tipo de tecido, exsudato e odor."
                ),
                category=KnowledgeCategory.WOUND_ASSESSMENT,
                evidence_level=EvidenceLevel.EXPERT_CONSENSUS,
                source="Schultz GS et al. Wound bed preparation: a systematic approach. Wound Repair Regen. 2003",
                year=2003,
                keywords=["TIME", "avaliacao", "preparo", "leito", "debridamento", "umidade", "borda", "tecido"],
            ),
            KnowledgeEntry(
                title="Escala de Braden para Risco de Lesão por Pressão",
                content=(
                    "A escala de Braden avalia 6 subescalas: percepção sensorial, umidade, "
                    "atividade, mobilidade, nutrição e fricção/cisalhamento. "
                    "Score total 6-23. Risco: ≤9 muito alto, 10-12 alto, 13-14 moderado, "
                    "15-18 baixo, >18 sem risco. Aplicar na admissão e reavaliar a cada 48h "
                    "em pacientes hospitalizados ou semanalmente na atenção domiciliar."
                ),
                category=KnowledgeCategory.PRESSURE_INJURY,
                evidence_level=EvidenceLevel.LEVEL_1B,
                source="Bergstrom N et al. Braden Scale for Predicting Pressure Sore Risk. Nursing Research. 1987",
                year=1987,
                keywords=["braden", "pressao", "risco", "avaliacao", "escala", "prevenção", "lesao"],
            ),

            # === COBERTURAS ===
            KnowledgeEntry(
                title="Seleção de Coberturas para Feridas",
                content=(
                    "Princípios de seleção de coberturas: "
                    "1. Ferida com necrose seca → hidrogel para autólise ou debridamento instrumental; "
                    "2. Ferida com esfacelo → alginato de cálcio ou hidrofibra; "
                    "3. Ferida com granulação saudável → espuma/hidrocoloide para proteção; "
                    "4. Ferida com exsudato abundante → alginato, hidrofibra ou espuma absorvente; "
                    "5. Ferida infectada → prata iônica (Ag+), PHMB ou mel medicinal; "
                    "6. Ferida cavitária → alginato em fita ou espuma cavitária; "
                    "7. Pele periferida frágil → barreira protetora cutânea (óxido de zinco, dimeticona)."
                ),
                category=KnowledgeCategory.DRESSING_SELECTION,
                evidence_level=EvidenceLevel.CLINICAL_GUIDELINE,
                source="Ministério da Saúde. Protocolo de Prevenção e Tratamento de Feridas. 2023",
                year=2023,
                keywords=[
                    "cobertura", "curativo", "alginato", "hidrogel", "espuma",
                    "hidrocoloide", "prata", "debridamento", "exsudato", "necrose",
                ],
                icd10_codes=["L89", "L97", "I83.0"],
            ),

            # === ÚLCERA VENOSA ===
            KnowledgeEntry(
                title="Tratamento de Úlcera Venosa Crônica",
                content=(
                    "A terapia compressiva é o pilar do tratamento da úlcera venosa. "
                    "1. Confirmar ITB (índice tornozelo-braquial) ≥0.8 antes de comprimir; "
                    "2. Compressão multicomponente (40mmHg no tornozelo) é superior à de um componente; "
                    "3. Bota de Unna ou bandagem multicamada; "
                    "4. Curativo primário conforme características do leito (TIME); "
                    "5. Elevação de MMII 30min 3-4x/dia; "
                    "6. Exercícios de bombeamento de panturrilha; "
                    "7. Avaliar ITB a cada 3 meses; "
                    "8. Taxa de cicatrização esperada: 40-50% redução de área em 4 semanas; "
                    "Se <40% em 4 semanas, reavaliar diagnóstico e tratamento."
                ),
                category=KnowledgeCategory.VENOUS_ULCER,
                evidence_level=EvidenceLevel.LEVEL_1A,
                source="O'Meara S et al. Compression for venous leg ulcers. Cochrane Database Syst Rev. 2012",
                year=2012,
                keywords=[
                    "venosa", "ulcera", "compressao", "bota", "unna", "ITB",
                    "tornozelo", "bandagem", "insuficiencia", "varizes",
                ],
                icd10_codes=["I83.0", "I83.2", "L97"],
            ),

            # === PÉ DIABÉTICO ===
            KnowledgeEntry(
                title="Classificação e Manejo do Pé Diabético",
                content=(
                    "Classificação de Wagner: "
                    "0 — pé intacto, risco; 1 — úlcera superficial; "
                    "2 — úlcera profunda até tendão; 3 — abscesso, osteomielite; "
                    "4 — gangrena parcial; 5 — gangrena extensa. "
                    "Manejo: 1. Controle glicêmico rigoroso (HbA1c <7%); "
                    "2. Offloading total (gesso de contato total ou bota removível); "
                    "3. Debridamento de tecido desvitalizado; "
                    "4. Antibioticoterapia se infecção (não tratar colonização); "
                    "5. Avaliação vascular (ITB, Doppler); "
                    "6. Inspeção diária dos pés pelo paciente; "
                    "7. Calçados terapêuticos e palmilhas; "
                    "8. Exame dos pés por profissional a cada consulta."
                ),
                category=KnowledgeCategory.DIABETIC_FOOT,
                evidence_level=EvidenceLevel.CLINICAL_GUIDELINE,
                source="IWGDF Guidelines on the Prevention and Management of Diabetes-related Foot Disease. 2023",
                year=2023,
                keywords=[
                    "diabetico", "pe", "wagner", "neuropatia", "offloading",
                    "osteomielite", "glicemia", "HbA1c", "diabetes", "amputacao",
                ],
                icd10_codes=["E11.5", "E11.6", "L97"],
            ),

            # === ESPOROTRICOSE ===
            KnowledgeEntry(
                title="Diagnóstico e Tratamento da Esporotricose",
                content=(
                    "Esporotricose — micose subcutânea causada por Sporothrix spp. "
                    "Epidemiologia: zoonose emergente no Brasil, transmissão por gatos. "
                    "Formas clínicas: cutânea fixa, linfocutânea, disseminada, extracutânea. "
                    "Diagnóstico: cultura fúngica (padrão-ouro), histopatologia, teste rápido. "
                    "Tratamento: "
                    "1. Forma cutânea/linfocutânea: Itraconazol 100-200mg/dia 3-6 meses; "
                    "2. Forma disseminada: Itraconazol 200-400mg/dia ou Anfotericina B; "
                    "3. Forma extracutânea: Anfotericina B lipossômica + Itraconazol; "
                    "4. Gestantes: Termoterapia local (aquecimento 42-43°C); "
                    "5. Imunocomprometidos: tratar agressivamente, manter supressão. "
                    "Notificação: doença de notificação compulsória em alguns estados."
                ),
                category=KnowledgeCategory.SPOROTRICHOSIS,
                evidence_level=EvidenceLevel.CLINICAL_GUIDELINE,
                source="Ministério da Saúde. Protocolo Clínico e Diretrizes Terapêuticas — Esporotricose. 2022",
                year=2022,
                keywords=[
                    "esporotricose", "sporothrix", "itraconazol", "anfotericina",
                    "fungica", "gato", "linfocutanea", "disseminada", "micose",
                ],
                icd10_codes=["B42", "B42.0", "B42.1", "B42.7"],
            ),

            # === LESÃO POR PRESSÃO ===
            KnowledgeEntry(
                title="Prevenção e Tratamento de Lesão por Pressão",
                content=(
                    "Classificação NPUAP/EPUAP 2019: "
                    "Estágio 1 — eritema não branqueável; "
                    "Estágio 2 — perda parcial da espessura da pele; "
                    "Estágio 3 — perda total da espessura da pele; "
                    "Estágio 4 — perda total com exposição de osso/músculo; "
                    "Não classificável — base coberta por necrose/esfacelo; "
                    "Tissular profunda — descoloração roxa/marrom persistente. "
                    "Prevenção: 1. Reposicionamento a cada 2h; 2. Superfície de redistribuição; "
                    "3. Inspeção diária da pele; 4. Nutrição adequada (proteínas >1.25g/kg/dia); "
                    "5. Manter pele limpa e hidratada; 6. Minimizar forças de fricção/cisalhamento."
                ),
                category=KnowledgeCategory.PRESSURE_INJURY,
                evidence_level=EvidenceLevel.CLINICAL_GUIDELINE,
                source="EPUAP/NPIAP/PPPIA. Prevention and Treatment of Pressure Ulcers/Injuries: Clinical Practice Guideline. 2019",
                year=2019,
                keywords=[
                    "pressao", "lesao", "estagio", "NPUAP", "prevencao",
                    "reposicionamento", "superficie", "braden", "decubito",
                ],
                icd10_codes=["L89", "L89.0", "L89.1", "L89.2", "L89.3", "L89.9"],
            ),

            # === CONTROLE DE INFECÇÃO ===
            KnowledgeEntry(
                title="Identificação e Manejo de Infecção em Feridas",
                content=(
                    "Continuum da infecção: contaminação → colonização → colonização crítica → infecção. "
                    "Sinais clássicos de infecção: dor, calor, rubor, edema, exsudato purulento. "
                    "Sinais sutis (feridas crônicas): aumento de exsudato, tecido friável, "
                    "mau odor, ponte de epitélio, descoloração do leito, retardo na cicatrização. "
                    "Manejo: 1. Limpeza com SF 0.9% sob pressão adequada; "
                    "2. Debridamento do tecido desvitalizado; "
                    "3. Antimicrobiano tópico (prata, PHMB, iodo cadexômero) por 2 semanas; "
                    "4. Antibiótico sistêmico SOMENTE se celulite, linfangite ou sepse; "
                    "5. Cultura quantitativa se não resposta em 2 semanas; "
                    "6. NÃO usar antibiótico tópico (neomicina, etc) — risco de resistência."
                ),
                category=KnowledgeCategory.INFECTION_CONTROL,
                evidence_level=EvidenceLevel.LEVEL_2A,
                source="International Wound Infection Institute (IWII). Wound Infection in Clinical Practice. 2022",
                year=2022,
                keywords=[
                    "infeccao", "antimicrobiano", "prata", "antibiotico",
                    "celulite", "exsudato", "biofilme", "cultura", "debridamento",
                ],
                icd10_codes=["L08", "L08.9", "T79.3"],
            ),

            # === NUTRIÇÃO ===
            KnowledgeEntry(
                title="Suporte Nutricional na Cicatrização de Feridas",
                content=(
                    "A desnutrição é fator independente de retardo na cicatrização. "
                    "Recomendações: "
                    "1. Proteínas: 1.25-1.5 g/kg/dia (aumentar para 1.5-2.0 em feridas graves); "
                    "2. Calorias: 30-35 kcal/kg/dia; "
                    "3. Vitamina C: 250mg 2x/dia (cofator na síntese de colágeno); "
                    "4. Zinco: 40mg/dia por 10 dias (se deficiência); "
                    "5. Vitamina A: 10.000 UI/dia se em uso de corticosteroides; "
                    "6. Ferro: tratar anemia (Hb <10 g/dL prejudica oxigenação tecidual); "
                    "7. Hidratação: ≥30 mL/kg/dia; "
                    "8. Suplementos orais hiperproteicos (se ingestão oral <75%); "
                    "9. Avaliar risco nutricional com MNA ou MUST."
                ),
                category=KnowledgeCategory.NUTRITION,
                evidence_level=EvidenceLevel.LEVEL_2B,
                source="Munoz N et al. Nutrition and Wound Healing. NPUAP White Paper. 2020",
                year=2020,
                keywords=[
                    "nutricao", "proteina", "vitamina", "zinco", "desnutricao",
                    "colageno", "cicatrizacao", "suplemento", "caloria",
                ],
            ),

            # === PROTOCOLOS SUS ===
            KnowledgeEntry(
                title="Procedimentos SIGTAP para Tratamento de Feridas no SUS",
                content=(
                    "Procedimentos registráveis na produção ambulatorial SUS: "
                    "03.01.10.003-4 — Curativo grau I (nível primário); "
                    "03.01.10.004-2 — Curativo grau II (nível especializado); "
                    "03.01.10.006-9 — Debridamento de ferida; "
                    "04.01.01.029-0 — Tratamento cirúrgico de úlcera de pressão; "
                    "02.01.01.063-1 — Cultura de secreção de ferida; "
                    "03.01.08.002-5 — Terapia compressiva (bota de Unna); "
                    "03.01.08.003-3 — Terapia por pressão negativa. "
                    "Registro obrigatório via BPA-I (Boletim de Produção Ambulatorial). "
                    "Profissionais: enfermeiro (CBO 2235), médico (CBO 2251), "
                    "técnico de enfermagem (CBO 3222) sob supervisão."
                ),
                category=KnowledgeCategory.SUS_PROTOCOLS,
                evidence_level=EvidenceLevel.CLINICAL_GUIDELINE,
                source="SIGTAP/DATASUS. Tabela Unificada de Procedimentos. 2024",
                year=2024,
                keywords=[
                    "SIGTAP", "BPA", "SUS", "procedimento", "curativo",
                    "producao", "ambulatorial", "DATASUS",
                ],
            ),

            # === MANEJO DA DOR ===
            KnowledgeEntry(
                title="Manejo da Dor em Feridas",
                content=(
                    "A dor em feridas é multifatorial: nociceptiva, neuropática, operatória. "
                    "Avaliação: escala EVA (0-10) em cada troca de curativo. "
                    "Manejo escalonado (OMS): "
                    "1. Dor leve (EVA 1-3): paracetamol 1g 6/6h ou dipirona 1g 6/6h; "
                    "2. Dor moderada (EVA 4-6): tramadol 50-100mg 6/6h ou codeína + paracetamol; "
                    "3. Dor intensa (EVA 7-10): morfina 10mg VO 4/4h (titular dose); "
                    "Dor na troca: anestésico tópico (lidocaína 2% gel) 15min antes; "
                    "Dor neuropática: gabapentina 300-1200mg/dia ou pregabalina; "
                    "Dor de fundo: coberturas atraumáticas (silicone, espuma); "
                    "NÃO minimizar dor do paciente — é indicador de complicações."
                ),
                category=KnowledgeCategory.PAIN_MANAGEMENT,
                evidence_level=EvidenceLevel.CLINICAL_GUIDELINE,
                source="World Union of Wound Healing Societies. Consensus Document: Wound Pain. 2004",
                year=2004,
                keywords=[
                    "dor", "analgesia", "EVA", "morfina", "tramadol",
                    "neuropatica", "lidocaina", "atraumatica", "troca",
                ],
            ),
        ]

    def search(
        self,
        query: str,
        category: Optional[KnowledgeCategory] = None,
        min_evidence: Optional[EvidenceLevel] = None,
        top_k: int = 5,
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """
        Busca conhecimento relevante para uma consulta.

        Args:
            query: Texto da consulta
            category: Filtrar por categoria
            top_k: Número máximo de resultados

        Returns:
            Lista de (entrada, score) ordenada por relevância
        """
        # Tokenizar query
        query_words = [
            w.lower().strip(".,;:!?()[]")
            for w in query.split()
            if len(w) > 2
        ]

        candidates = self.entries
        if category:
            candidates = [e for e in candidates if e.category == category]

        # Calcular relevância
        scored = []
        for entry in candidates:
            score = entry.relevance_score(query_words)

            # Bonus se título contém palavras-chave
            title_words = set(entry.title.lower().split())
            title_match = len(set(query_words) & title_words)
            score += title_match * 0.1

            if score > 0:
                scored.append((entry, score))

        # Ordenar por relevância
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[:top_k]

    def get_by_icd10(self, code: str) -> List[KnowledgeEntry]:
        """Busca por código CID-10"""
        return [
            e for e in self.entries
            if code in e.icd10_codes or any(code.startswith(c) for c in e.icd10_codes)
        ]

    def add_entry(self, entry: KnowledgeEntry):
        """Adiciona nova entrada à base"""
        self.entries.append(entry)


class ClinicalDecisionSupport:
    """
    Sistema de apoio à decisão clínica baseado em RAG.
    Recupera conhecimento relevante e gera recomendações contextuais.
    """

    def __init__(self):
        self.knowledge_base = ClinicalKnowledgeBase()

    def get_wound_guidance(
        self,
        wound_etiology: str,
        wound_data: Dict,
        patient_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Obtém orientação clínica contextualizada para o caso.

        Args:
            wound_etiology: Tipo/etiologia da ferida
            wound_data: Dados da ferida (área, tecido, exsudato, etc.)
            patient_data: Dados do paciente (comorbidades, etc.)

        Returns:
            Orientação com evidências e referências
        """
        # Construir query
        query_parts = [wound_etiology]
        if wound_data.get("infection"):
            query_parts.append("infeccao")
        if wound_data.get("necrosis_pct", 0) > 20:
            query_parts.append("necrose debridamento")
        if wound_data.get("exudate_level") == "heavy":
            query_parts.append("exsudato cobertura")
        if patient_data:
            if patient_data.get("diabetes"):
                query_parts.append("diabetico glicemia")
            if patient_data.get("malnourished"):
                query_parts.append("nutricao proteina")

        query = " ".join(query_parts)

        # Buscar conhecimento
        results = self.knowledge_base.search(query, top_k=5)

        # Montar resposta
        guidance_sections = []
        references = []

        for entry, score in results:
            guidance_sections.append({
                "title": entry.title,
                "content": entry.content,
                "evidence_level": entry.evidence_level.value,
                "relevance": round(score, 2),
            })
            references.append({
                "source": entry.source,
                "year": entry.year,
                "evidence_level": entry.evidence_level.value,
            })

        # Recomendações contextuais específicas
        specific_recs = self._generate_specific_recommendations(
            wound_etiology, wound_data, patient_data
        )

        return {
            "query_context": query,
            "guidance": guidance_sections,
            "specific_recommendations": specific_recs,
            "references": references,
            "disclaimer": (
                "Esta orientação é baseada em evidências e protocolos clínicos, "
                "porém NÃO substitui o julgamento clínico do profissional de saúde. "
                "Decisões terapêuticas devem considerar o contexto individual do paciente."
            ),
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_specific_recommendations(
        self,
        etiology: str,
        wound_data: Dict,
        patient_data: Optional[Dict],
    ) -> List[Dict]:
        """Recomendações específicas baseadas no contexto"""
        recs = []

        # Recomendações por etiologia
        etiology_recs = {
            "venosa": [
                "Realizar ITB antes de iniciar compressão",
                "Aplicar terapia compressiva (30-40 mmHg) se ITB ≥ 0.8",
                "Avaliar redução de área em 4 semanas (meta: >40%)",
            ],
            "arterial": [
                "Encaminhamento URGENTE para angiologista",
                "NÃO aplicar compressão sem avaliação vascular",
                "Avaliar ITB e considerar revascularização",
            ],
            "diabetica": [
                "Solicitar HbA1c e otimizar controle glicêmico",
                "Implementar offloading adequado",
                "Avaliar neuropatia (monofilamento 10g, diapasão 128Hz)",
            ],
            "pressao": [
                "Aplicar escala de Braden e implementar prevenção",
                "Reposicionamento a cada 2 horas",
                "Avaliar e otimizar nutrição (proteínas ≥ 1.25 g/kg/dia)",
            ],
            "esporotricose": [
                "Solicitar cultura fúngica para confirmação",
                "Iniciar itraconazol 100mg/dia se suspeita clínica alta",
                "Avaliar forma clínica e status imunológico",
            ],
        }

        for rec in etiology_recs.get(etiology, []):
            recs.append({
                "type": "etiology_specific",
                "recommendation": rec,
            })

        # Recomendações por achados da ferida
        if wound_data.get("infection"):
            recs.append({
                "type": "infection",
                "recommendation": (
                    "Sinais de infecção: limpeza com SF 0.9%, "
                    "cobertura com prata iônica por 14 dias. "
                    "Se celulite ou sinais sistêmicos, iniciar ATB."
                ),
            })

        if wound_data.get("necrosis_pct", 0) > 20:
            recs.append({
                "type": "tissue",
                "recommendation": "Necrose > 20% — indicar debridamento (autolítico/instrumental).",
            })

        if wound_data.get("pain_level", 0) > 6:
            recs.append({
                "type": "pain",
                "recommendation": (
                    "Dor intensa (EVA > 6) — analgesia escalonada, "
                    "curativo atraumático, lidocaína tópica na troca."
                ),
            })

        if patient_data and patient_data.get("malnourished"):
            recs.append({
                "type": "nutrition",
                "recommendation": (
                    "Paciente desnutrido — suplementação: proteínas 1.5g/kg/dia, "
                    "vitamina C 250mg 2x/dia, zinco 40mg/dia."
                ),
            })

        return recs

    def answer_clinical_question(self, question: str) -> Dict:
        """
        Responde pergunta clínica usando a base de conhecimento.
        Simula comportamento RAG (sem LLM externo, usa base local).
        """
        results = self.knowledge_base.search(question, top_k=3)

        if not results:
            return {
                "answer": "Não foi possível encontrar informação relevante na base de conhecimento.",
                "confidence": 0.0,
                "sources": [],
            }

        # Construir resposta a partir das entradas mais relevantes
        top_entry, top_score = results[0]

        return {
            "question": question,
            "answer": top_entry.content,
            "confidence": min(top_score, 1.0),
            "source": top_entry.source,
            "evidence_level": top_entry.evidence_level.value,
            "related_topics": [
                {"title": e.title, "relevance": round(s, 2)}
                for e, s in results[1:]
            ],
        }
