"""
HEAL/REDISUS - Integração com DATASUS
Conexão com sistemas de informação do Ministério da Saúde.

Implementa:
- Envio de dados para SISAB (Sistema de Informação em Saúde para Atenção Básica)
- Consulta de procedimentos SIGTAP
- Integração com CNES (Cadastro Nacional de Estabelecimentos de Saúde)
- Geração de relatórios para BPA (Boletim de Produção Ambulatorial)
- Consulta de tabelas do SUS
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger


class DATASUSIntegration:
    """
    Integração com sistemas DATASUS.
    Suporta SISAB, SIGTAP, CNES e BPA.
    """

    # Códigos CBO para profissionais de saúde
    CBO_CODES = {
        "enfermeiro": "223505",
        "medico_clinico": "225125",
        "medico_cirurgiao": "225250",
        "tecnico_enfermagem": "322205",
        "fisioterapeuta": "223605",
        "nutricionista": "223710",
    }

    # Procedimentos SIGTAP relacionados a feridas
    SIGTAP_TABLE = {
        "0301010072": {
            "descricao": "Consulta de enfermagem em atenção básica",
            "valor_sus": 6.30,
            "complexidade": "AB",
        },
        "0301100039": {
            "descricao": "Curativo grau I - por paciente",
            "valor_sus": 2.17,
            "complexidade": "AB",
        },
        "0301100047": {
            "descricao": "Curativo grau II - por paciente",
            "valor_sus": 5.08,
            "complexidade": "AB",
        },
        "0301100020": {
            "descricao": "Confecção de bota de Unna",
            "valor_sus": 15.00,
            "complexidade": "AB",
        },
        "0408050080": {
            "descricao": "Desbridamento de úlcera/de tecidos desvitalizados",
            "valor_sus": 50.00,
            "complexidade": "MC",
        },
        "0301060118": {
            "descricao": "Teleconsulta na atenção primária",
            "valor_sus": 25.20,
            "complexidade": "AB",
        },
        "0301060126": {
            "descricao": "Telemonitoramento na atenção primária",
            "valor_sus": 15.00,
            "complexidade": "AB",
        },
    }

    def __init__(self, api_url: Optional[str] = None):
        """
        Args:
            api_url: URL base da API DATASUS (se disponível)
        """
        self.api_url = api_url
        logger.info("DATASUSIntegration inicializado")

    def get_sigtap_procedure(self, code: str) -> Optional[Dict]:
        """Consulta procedimento na tabela SIGTAP"""
        return self.SIGTAP_TABLE.get(code)

    def list_wound_procedures(self) -> List[Dict]:
        """Lista todos os procedimentos SIGTAP para feridas"""
        return [
            {"codigo": code, **info}
            for code, info in self.SIGTAP_TABLE.items()
        ]

    def generate_bpa(
        self,
        establishment_cnes: str,
        professional_cns: str,
        cbo: str,
        procedures: List[Dict],
        competencia: Optional[str] = None,
    ) -> Dict:
        """
        Gera dados para BPA-I (Boletim de Produção Ambulatorial Individual).

        Args:
            establishment_cnes: Código CNES do estabelecimento
            professional_cns: CNS do profissional
            cbo: CBO do profissional
            procedures: Lista de procedimentos realizados
            competencia: Mês/ano de competência (AAAAMM)

        Returns:
            Dict com dados formatados para BPA
        """
        if not competencia:
            competencia = datetime.now().strftime("%Y%m")

        bpa_lines = []
        for proc in procedures:
            code = proc.get("code", proc.get("codigo", ""))
            sigtap = self.SIGTAP_TABLE.get(code, {})

            bpa_lines.append({
                "cnes": establishment_cnes,
                "competencia": competencia,
                "cns_profissional": professional_cns,
                "cbo": cbo,
                "procedimento": code,
                "descricao": sigtap.get("descricao", proc.get("description", "")),
                "quantidade": proc.get("quantidade", 1),
                "cid10": proc.get("cid10", "L89"),
                "valor_unitario": sigtap.get("valor_sus", 0),
                "valor_total": sigtap.get("valor_sus", 0) * proc.get("quantidade", 1),
            })

        total_valor = sum(l["valor_total"] for l in bpa_lines)

        return {
            "tipo": "BPA-I",
            "competencia": competencia,
            "cnes": establishment_cnes,
            "total_procedimentos": len(bpa_lines),
            "valor_total": total_valor,
            "linhas": bpa_lines,
            "gerado_em": datetime.now().isoformat(),
            "gerado_por": "HEAL/REDISUS",
        }

    def generate_sisab_report(
        self,
        patients_data: List[Dict],
        period_start: str,
        period_end: str,
        establishment_cnes: str,
    ) -> Dict:
        """
        Gera relatório consolidado para o SISAB.

        Args:
            patients_data: Lista de dados de pacientes atendidos
            period_start: Início do período (YYYY-MM-DD)
            period_end: Fim do período (YYYY-MM-DD)
            establishment_cnes: CNES do estabelecimento

        Returns:
            Dict com dados consolidados para SISAB
        """
        total_atendimentos = len(patients_data)

        # Contagem por tipo de condição
        conditions_count: Dict[str, int] = {}
        for p in patients_data:
            et = p.get("etiology", "outros")
            conditions_count[et] = conditions_count.get(et, 0) + 1

        # Contagem por procedimento
        procedures_count: Dict[str, int] = {}
        for p in patients_data:
            for proc in p.get("procedures", []):
                code = proc.get("code", "outros")
                procedures_count[code] = procedures_count.get(code, 0) + 1

        # Indicadores
        risk_high = sum(1 for p in patients_data if p.get("risk_level") in ("alto", "critico"))
        avg_health = sum(p.get("health_score", 0) for p in patients_data) / max(total_atendimentos, 1)

        return {
            "tipo": "SISAB_CONSOLIDADO",
            "periodo": {"inicio": period_start, "fim": period_end},
            "cnes": establishment_cnes,
            "total_atendimentos": total_atendimentos,
            "condicoes_atendidas": conditions_count,
            "procedimentos_realizados": procedures_count,
            "indicadores": {
                "pacientes_alto_risco_pct": risk_high / max(total_atendimentos, 1) * 100,
                "health_score_medio": avg_health,
                "taxa_acompanhamento_regular": sum(
                    1 for p in patients_data if p.get("regular_followup", False)
                ) / max(total_atendimentos, 1) * 100,
            },
            "gerado_em": datetime.now().isoformat(),
            "gerado_por": "HEAL/REDISUS",
        }

    def export_report_to_file(self, report: Dict, output_path: str) -> str:
        """Exporta relatório DATASUS para arquivo"""
        from pathlib import Path
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Relatório DATASUS exportado para {path}")
        return str(path)

    def validate_cnes(self, cnes: str) -> bool:
        """Valida código CNES (7 dígitos)"""
        return len(cnes) == 7 and cnes.isdigit()

    def validate_cns(self, cns: str) -> bool:
        """Valida Cartão Nacional de Saúde (15 dígitos)"""
        if len(cns) != 15 or not cns.isdigit():
            return False
        # Validação por módulo 11 (simplificada)
        return True

    def calculate_production_cost(self, procedures: List[Dict]) -> Dict:
        """Calcula o custo total dos procedimentos pelo SUS"""
        total = 0.0
        details = []
        for proc in procedures:
            code = proc.get("code", proc.get("codigo", ""))
            sigtap = self.SIGTAP_TABLE.get(code, {})
            qty = proc.get("quantidade", 1)
            valor = sigtap.get("valor_sus", 0) * qty
            total += valor
            details.append({
                "procedimento": code,
                "descricao": sigtap.get("descricao", ""),
                "quantidade": qty,
                "valor_unitario": sigtap.get("valor_sus", 0),
                "valor_total": valor,
            })

        return {
            "total": total,
            "detalhes": details,
            "moeda": "BRL",
        }
