"""
HEAL/REDISUS - Integração com e-SUS PEC (Prontuário Eletrônico do Cidadão)
Conexão com o sistema de atenção primária do SUS.

Implementa:
- Exportação de dados para o e-SUS/PEC (SOAP, fichas de atendimento)
- Importação de dados cadastrais do e-SUS
- Sincronização bidirecional de fichas de atendimento individual
- Geração de fichas CDS (Coleta de Dados Simplificada)
"""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger


class FichaAtendimentoIndividual:
    """
    Gera fichas de Atendimento Individual do e-SUS AB/PEC.
    Modelo baseado na ficha CDS do e-SUS APS.
    """

    # Códigos CIAP2 para feridas
    CIAP2_WOUNDS = {
        "VENOUS_ULCER": {"code": "S97", "description": "Úlcera crônica da pele"},
        "ARTERIAL_ULCER": {"code": "S97", "description": "Úlcera crônica da pele"},
        "DIABETIC_FOOT": {"code": "S97", "description": "Úlcera crônica da pele"},
        "PRESSURE_INJURY": {"code": "S97", "description": "Úlcera crônica da pele"},
        "SURGICAL_WOUND": {"code": "S18", "description": "Laceração/corte"},
    }

    # Procedimentos SIGTAP para curativos
    SIGTAP_PROCEDURES = {
        "curativo_simples": {"code": "0301100039", "description": "Curativo grau I - por paciente"},
        "curativo_especial": {"code": "0301100047", "description": "Curativo grau II - por paciente"},
        "desbridamento": {"code": "0408050080", "description": "Desbridamento de úlcera/de tecidos desvitalizados"},
        "bota_unna": {"code": "0301100020", "description": "Confecção de bota de Unna"},
        "consulta_enfermagem": {"code": "0301010072", "description": "Consulta de enfermagem em atenção básica"},
    }

    def __init__(self):
        logger.info("FichaAtendimentoIndividual e-SUS inicializada")

    def generate_ficha(
        self,
        patient_data: Dict,
        wound_data: Dict,
        professional_data: Dict,
        establishment_data: Dict,
    ) -> Dict:
        """
        Gera ficha de Atendimento Individual para o e-SUS PEC.

        Args:
            patient_data: Dados do paciente (nome, CNS, CPF, etc.)
            wound_data: Dados da ferida (etiology, tissue_percentages, etc.)
            professional_data: Dados do profissional (CBO, CNS, nome)
            establishment_data: Dados do estabelecimento (CNES, INE)

        Returns:
            Dict representando a ficha de atendimento
        """
        etiology = wound_data.get("etiology", "VENOUS_ULCER")
        ciap2 = self.CIAP2_WOUNDS.get(etiology, self.CIAP2_WOUNDS["VENOUS_ULCER"])

        ficha = {
            "tipoFicha": "fichaAtendimentoIndividual",
            "versao": "3.2",
            "geradoPor": "HEAL/REDISUS",
            "dataAtendimento": datetime.now().strftime("%Y-%m-%d"),
            "horaAtendimento": datetime.now().strftime("%H:%M"),
            "uuid": str(uuid.uuid4()),

            # Cabeçalho
            "headerTransport": {
                "cnes": establishment_data.get("cnes", ""),
                "ine": establishment_data.get("ine", ""),
                "profissionalCNS": professional_data.get("cns", ""),
                "cboCodigo": professional_data.get("cbo", "223505"),  # Enfermeiro
                "dataAtendimento": datetime.now().strftime("%Y-%m-%d"),
            },

            # Paciente
            "paciente": {
                "cns": patient_data.get("cns", ""),
                "cpf": patient_data.get("cpf", ""),
                "nome": patient_data.get("name", ""),
                "dataNascimento": patient_data.get("birth_date", ""),
                "sexo": patient_data.get("gender", ""),
            },

            # Tipo de atendimento
            "tipoAtendimento": "CONSULTA_AGENDADA_PROGRAMADA_CUIDADO_CONTINUADO",

            # Problema/Condição Avaliada
            "problemasCondições": {
                "ciap2": ciap2["code"],
                "descricao": ciap2["description"],
                "cid10": wound_data.get("icd10_code", "L89"),
            },

            # SOAP
            "soap": self._generate_soap(patient_data, wound_data),

            # Procedimentos realizados
            "procedimentos": self._get_procedures(wound_data),

            # Conduta
            "conduta": {
                "retornoConsultaAgendada": True,
                "diasRetorno": wound_data.get("days_until_next", 7),
                "encaminhamento": wound_data.get("referral", None),
            },

            # Dados HEAL
            "extensao_heal": {
                "risk_score": wound_data.get("risk_score", 0),
                "risk_level": wound_data.get("risk_level", "moderado"),
                "tissue_percentages": wound_data.get("tissue_percentages", {}),
                "area_cm2": wound_data.get("area_cm2", 0),
                "health_score": wound_data.get("health_score", 0),
                "ai_confidence": wound_data.get("confidence", 0),
                "image_ref": wound_data.get("image_path", ""),
            },
        }

        logger.info(f"Ficha e-SUS gerada — paciente: {patient_data.get('name', 'N/A')}")
        return ficha

    def _generate_soap(self, patient_data: Dict, wound_data: Dict) -> Dict:
        """Gera registro SOAP para a ficha"""
        etiology = wound_data.get("etiology", "desconhecida")
        tissue_pcts = wound_data.get("tissue_percentages", {})
        area = wound_data.get("area_cm2", 0)
        risk = wound_data.get("risk_level", "moderado")

        subjetivo = (
            f"Paciente em acompanhamento por ferida crônica. "
            f"Relata {'melhora' if wound_data.get('improving', False) else 'manutenção do quadro'}. "
            f"{'Refere dor local. ' if wound_data.get('pain', False) else ''}"
            f"Adesão ao tratamento: {wound_data.get('adherence_pct', 'não avaliada')}."
        )

        # Objetivo: dados da análise HEAL
        tissue_desc = ", ".join(
            f"{name}: {pct:.1f}%" for name, pct in tissue_pcts.items() if pct > 0
        )
        objetivo = (
            f"Ferida avaliada por sistema HEAL/REDISUS. "
            f"Etiologia classificada: {etiology} (confiança: {wound_data.get('confidence', 0)*100:.0f}%). "
            f"Área: {area:.1f} cm². "
            f"Composição tecidual: {tissue_desc}. "
            f"Score de saúde: {wound_data.get('health_score', 0):.1f}. "
            f"Nível de risco: {risk}."
        )

        avaliacao = (
            f"Ferida crônica em {'evolução favorável' if wound_data.get('improving') else 'acompanhamento'}. "
            f"Risco classificado como {risk}."
        )

        plano = " | ".join(wound_data.get("recommendations", [
            "Manter protocolo terapêutico atual",
            "Reavaliar conforme agendamento",
        ]))

        return {
            "subjetivo": subjetivo,
            "objetivo": objetivo,
            "avaliacao": avaliacao,
            "plano": plano,
        }

    def _get_procedures(self, wound_data: Dict) -> List[Dict]:
        """Identifica procedimentos SIGTAP realizados"""
        procedures = []

        # Consulta de enfermagem (sempre)
        procedures.append(self.SIGTAP_PROCEDURES["consulta_enfermagem"])

        # Tipo de curativo baseado na complexidade
        tissue_pcts = wound_data.get("tissue_percentages", {})
        necrosis = tissue_pcts.get("Necrose", tissue_pcts.get("NECROSIS", 0))

        if necrosis > 30:
            procedures.append(self.SIGTAP_PROCEDURES["desbridamento"])
            procedures.append(self.SIGTAP_PROCEDURES["curativo_especial"])
        elif wound_data.get("area_cm2", 0) > 20:
            procedures.append(self.SIGTAP_PROCEDURES["curativo_especial"])
        else:
            procedures.append(self.SIGTAP_PROCEDURES["curativo_simples"])

        # Bota de Unna para úlcera venosa
        if wound_data.get("etiology") == "VENOUS_ULCER":
            procedures.append(self.SIGTAP_PROCEDURES["bota_unna"])

        return procedures


class ESUSIntegration:
    """
    Integração completa com o e-SUS APS / PEC.
    Gerencia importação e exportação de dados com o sistema do SUS.
    """

    def __init__(self, esus_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Args:
            esus_url: URL da API do e-SUS PEC local
            api_key: Chave de API para autenticação
        """
        self.esus_url = esus_url
        self.api_key = api_key
        self.ficha_generator = FichaAtendimentoIndividual()
        logger.info(f"ESUSIntegration inicializado — URL: {esus_url or 'não configurada'}")

    def export_attendance(
        self,
        patient_data: Dict,
        wound_data: Dict,
        professional_data: Dict,
        establishment_data: Dict,
    ) -> Dict:
        """
        Exporta atendimento para o e-SUS PEC.
        Gera ficha de atendimento individual e tenta enviar via API.
        """
        ficha = self.ficha_generator.generate_ficha(
            patient_data, wound_data, professional_data, establishment_data
        )

        if self.esus_url:
            return self._send_to_esus(ficha)
        else:
            return {
                "status": "local",
                "message": "e-SUS não configurado — ficha gerada localmente",
                "ficha": ficha,
            }

    def _send_to_esus(self, ficha: Dict) -> Dict:
        """Envia ficha para a API do e-SUS PEC"""
        try:
            import requests
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = requests.post(
                f"{self.esus_url}/api/v1/fichas/atendimento-individual",
                json=ficha,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            logger.info("Ficha enviada ao e-SUS PEC com sucesso")
            return {"status": "success", "response": response.json()}
        except ImportError:
            return {"status": "local", "message": "requests não disponível", "ficha": ficha}
        except Exception as e:
            logger.error(f"Erro ao enviar ficha ao e-SUS: {e}")
            return {"status": "error", "message": str(e), "ficha": ficha}

    def export_ficha_to_file(self, ficha: Dict, output_path: str) -> str:
        """Exporta ficha e-SUS para arquivo JSON"""
        from pathlib import Path
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ficha, f, indent=2, ensure_ascii=False)
        logger.info(f"Ficha e-SUS exportada para {path}")
        return str(path)

    def import_patient_from_esus(self, cns: str) -> Optional[Dict]:
        """
        Importa dados do paciente do e-SUS PEC pelo CNS.
        """
        if not self.esus_url:
            logger.warning("e-SUS não configurado para importação")
            return None

        try:
            import requests
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            r = requests.get(
                f"{self.esus_url}/api/v1/cidadaos",
                params={"cns": cns},
                headers=headers,
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("results"):
                    cidadao = data["results"][0]
                    return {
                        "id": cidadao.get("id", ""),
                        "name": cidadao.get("nome", ""),
                        "birth_date": cidadao.get("dataNascimento", ""),
                        "cns": cns,
                        "cpf": cidadao.get("cpf", ""),
                        "gender": cidadao.get("sexo", ""),
                    }
            return None
        except Exception as e:
            logger.error(f"Erro ao importar paciente do e-SUS: {e}")
            return None
