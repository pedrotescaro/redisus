"""
HEAL/REDISUS - Plataforma Nacional de Saúde Digital Integrada
Launcher unificado que integra todos os módulos do HEAL.

Este arquivo é o ponto de entrada unificado da plataforma, integrando:
- Eixo 1: Diagnóstico e Monitoramento (IA para feridas)
- Eixo 2: Gestão Personalizada do Cuidado (planos, mHealth)
- Eixo 3: Interoperabilidade SUS (FHIR, e-SUS, DATASUS)
- Eixo 4: Experiência do Paciente (educação, aderência, comunicação)
- Eixo 5: Validação e Escalabilidade (TRL, pilotos, métricas)

Subprojetos integrados:
- Heal+ (diagnóstico por IA)
- Twin@Home (gêmeo digital do paciente)
- mHealth Takere (app personalizado)
- Esporotricose (triagem e diagnóstico)
- Plataforma Unificada (dashboard, telemedicina, vigilância)

Uso:
    python heal_platform.py --mode realtime       # Detecção em tempo real
    python heal_platform.py --mode image FILE     # Análise de imagem
    python heal_platform.py --mode dashboard      # Dashboard web clínico
    python heal_platform.py --mode status         # Status da plataforma
    python heal_platform.py --mode demo           # Demonstração completa
"""
import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

# Path setup
sys.path.insert(0, str(Path(__file__).parent))


def _safe_import(module_path: str, class_name: str):
    """Import com fallback para quando módulo não está disponível."""
    try:
        mod = __import__(module_path, fromlist=[class_name])
        return getattr(mod, class_name)
    except (ImportError, AttributeError) as e:
        logger.warning(f"Módulo {module_path}.{class_name} não disponível: {e}")
        return None


class HEALPlatform:
    """
    Plataforma Nacional de Saúde Digital Integrada — HEAL/REDISUS
    Integra os 5 eixos estruturantes e todos os subprojetos.

    Cluster REDISUS — RNP/RUTE
    """

    VERSION = "3.0.0"
    CODENAME = "HEAL"

    # 5 Eixos Estruturantes
    AXES = {
        1: {
            "name": "Diagnóstico e Monitoramento",
            "description": "IA para detecção, classificação e monitoramento de feridas crônicas",
            "modules": [
                "Detecção em tempo real (YOLO)",
                "Segmentação de tecidos (U-Net + HSV/LAB multi-espaço)",
                "Classificação etiológica (ResNet50 Two-Stage + EfficientNet)",
                "Triagem Normal/Ferida (ResNet50 Estágio 1)",
                "Classificação de tipo (Diabética/Pressão/Venosa — Estágio 2)",
                "Explicabilidade com Grad-CAM (layer4 ResNet50)",
                "Monitoramento de sinais vitais",
                "Estratificação de risco",
            ],
        },
        2: {
            "name": "Gestão Personalizada do Cuidado",
            "description": "Planos de cuidado individualizados e apps mHealth",
            "modules": [
                "Planos de cuidado baseados em evidências",
                "mHealth Takere (app personalizado)",
                "Recomendação de tratamento",
                "Rastreamento de evolução",
                "Digital Twin (Twin@Home)",
            ],
        },
        3: {
            "name": "Interoperabilidade SUS",
            "description": "Integração com sistemas de saúde brasileiros",
            "modules": [
                "HL7 FHIR R4 (perfis brasileiros)",
                "e-SUS PEC (Prontuário Eletrônico)",
                "DATASUS (SIGTAP, BPA, SISAB)",
                "RNDS (Rede Nacional de Dados em Saúde)",
                "Vigilância epidemiológica",
            ],
        },
        4: {
            "name": "Experiência do Paciente",
            "description": "Educação em saúde, aderência e comunicação",
            "modules": [
                "Biblioteca de educação em saúde",
                "Monitoramento de aderência",
                "Comunicação bidirecional",
                "Teleconsulta estruturada",
                "Triagem de esporotricose",
            ],
        },
        5: {
            "name": "Validação e Escalabilidade",
            "description": "Validação clínica, TRL e framework de pilotos",
            "modules": [
                "Rastreamento TRL (atualmente TRL 4-5)",
                "Protocolo de validação clínica",
                "Framework multicêntrico",
                "Conformidade regulatória (ANVISA, LGPD)",
                "Apoio à decisão clínica (RAG)",
            ],
        },
    }

    def __init__(self):
        self.initialized = False
        self._modules: Dict[str, Any] = {}
        logger.info(f"HEAL Platform v{self.VERSION} — Inicializando...")

    def initialize(self, modules: str = "all"):
        """
        Inicializa módulos da plataforma.

        Args:
            modules: "all", "core", "dashboard", "analysis"
        """
        logger.info(f"Inicializando módulos: {modules}")

        # Módulos core (sempre carregados)
        self._init_core()

        if modules in ("all", "analysis"):
            self._init_analysis()

        if modules in ("all", "dashboard"):
            self._init_dashboard()

        if modules == "all":
            self._init_extended()

        self.initialized = True
        active = [k for k, v in self._modules.items() if v is not None]
        logger.info(f"Plataforma inicializada. Módulos ativos: {len(active)}")

    def _init_core(self):
        """Inicializa módulos core"""
        # Risco
        RiskScoring = _safe_import("src.risk.stratification", "WoundRiskScoring")
        if RiskScoring:
            self._modules["risk_scoring"] = RiskScoring()

        PopAnalyzer = _safe_import("src.risk.stratification", "PopulationRiskAnalyzer")
        if PopAnalyzer:
            self._modules["population_risk"] = PopAnalyzer()

        # Interoperabilidade
        FHIRBuilder = _safe_import("src.interoperability.fhir_client", "FHIRResourceBuilder")
        if FHIRBuilder:
            self._modules["fhir_builder"] = FHIRBuilder()

        FHIRClient = _safe_import("src.interoperability.fhir_client", "FHIRClient")
        if FHIRClient:
            self._modules["fhir_client"] = FHIRClient()

        ESUSInteg = _safe_import("src.interoperability.esus_integration", "ESUSIntegration")
        if ESUSInteg:
            self._modules["esus"] = ESUSInteg()

        DATASUSInteg = _safe_import("src.interoperability.datasus_integration", "DATASUSIntegration")
        if DATASUSInteg:
            self._modules["datasus"] = DATASUSInteg()

        # RAG
        CDS = _safe_import("src.rag.clinical_rag", "ClinicalDecisionSupport")
        if CDS:
            self._modules["clinical_support"] = CDS()

        # Validação
        VF = _safe_import("src.validation.validation_framework", "ValidationFramework")
        if VF:
            self._modules["validation"] = VF()

    def _init_analysis(self):
        """Inicializa módulos de análise/diagnóstico"""
        # Monitoramento vital
        VSM = _safe_import("src.monitoring.vital_signs", "VitalSignsMonitor")
        if VSM:
            self._modules["vital_monitor"] = VSM()

        WI = _safe_import("src.monitoring.vital_signs", "WearableIntegration")
        if WI and self._modules.get("vital_monitor"):
            self._modules["wearable"] = WI(self._modules["vital_monitor"])

        # Digital Twin
        PatientDT = _safe_import("src.digital_twin.twin_model", "PatientDigitalTwin")
        self._modules["_digital_twin_class"] = PatientDT

        WHS = _safe_import("src.digital_twin.twin_model", "WoundHealingSimulator")
        if WHS:
            self._modules["healing_simulator"] = WHS()

        # Care Plans
        CPM = _safe_import("src.care_plans.care_plan_manager", "CarePlanManager")
        if CPM:
            self._modules["care_plans"] = CPM()

        # Patient Experience
        HEL = _safe_import("src.patient.experience", "HealthEducationLibrary")
        if HEL:
            self._modules["education"] = HEL()

        AT = _safe_import("src.patient.experience", "AdherenceTracker")
        if AT:
            self._modules["adherence"] = AT()

        PC = _safe_import("src.patient.experience", "PatientCommunication")
        if PC:
            self._modules["communication"] = PC()

    def _init_dashboard(self):
        """Inicializa dashboard e visualização"""
        CD = _safe_import("src.dashboard.clinical_dashboard", "ClinicalDashboard")
        if CD:
            self._modules["dashboard"] = CD()

    def _init_extended(self):
        """Inicializa módulos estendidos"""
        # Vigilância
        GS = _safe_import("src.surveillance.epidemiological", "GeoSurveillance")
        if GS:
            self._modules["surveillance"] = GS()

        # Telemedicina
        TM = _safe_import("src.telemedicine.teleconsult", "TeleconsultManager")
        if TM:
            self._modules["teleconsult"] = TM()

        SS = _safe_import("src.telemedicine.teleconsult", "SporotrichosisScreening")
        if SS:
            self._modules["sporotrichosis"] = SS()

    def get_module(self, name: str):
        """Obtém módulo por nome"""
        return self._modules.get(name)

    def get_platform_status(self) -> Dict:
        """Status completo da plataforma"""
        modules_status = {}
        for name, mod in self._modules.items():
            if name.startswith("_"):
                continue
            modules_status[name] = {
                "loaded": mod is not None,
                "type": type(mod).__name__ if mod else "N/A",
            }

        # TRL
        trl_info = {}
        validation = self._modules.get("validation")
        if validation:
            trl_info = validation.trl_tracker.get_current_status()

        return {
            "platform": "HEAL/REDISUS",
            "version": self.VERSION,
            "codename": self.CODENAME,
            "organization": "Cluster REDISUS — RNP/RUTE",
            "description": "Plataforma Nacional de Saúde Digital Integrada",
            "axes": self.AXES,
            "modules": modules_status,
            "modules_loaded": sum(1 for v in modules_status.values() if v["loaded"]),
            "modules_total": len(modules_status),
            "trl": trl_info,
            "timestamp": datetime.now().isoformat(),
        }

    def run_dashboard(self, host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
        """Inicia dashboard web clínico"""
        dashboard = self._modules.get("dashboard")
        if not dashboard:
            logger.error("Dashboard não inicializado. Execute initialize('dashboard') primeiro.")
            return

        logger.info(f"Iniciando HEAL Dashboard em http://{host}:{port}")
        dashboard.run(host=host, port=port, debug=debug)

    def run_realtime(self):
        """Executa detecção em tempo real (app desktop)"""
        try:
            from realtime_app import RedisusRealtimeApp
            app = RedisusRealtimeApp()
            app.initialize()
            app.run_webcam()
        except ImportError:
            logger.error("realtime_app.py não encontrado")
        except Exception as e:
            logger.error(f"Erro na detecção em tempo real: {e}")

    def run_image_analysis(self, image_path: str):
        """Executa análise de imagem via pipeline principal"""
        try:
            from main import RedisusApp
            app = RedisusApp()
            app.initialize()
            app.run_image(image_path)
        except ImportError:
            logger.error("main.py não encontrado")
        except Exception as e:
            logger.error(f"Erro na análise de imagem: {e}")

    def print_status(self):
        """Imprime status da plataforma no console"""
        status = self.get_platform_status()

        print("=" * 70)
        print(f"  {status['platform']} v{status['version']}")
        print(f"  {status['description']}")
        print(f"  {status['organization']}")
        print("=" * 70)
        print()

        # Eixos
        print("  5 EIXOS ESTRUTURANTES:")
        print("-" * 70)
        for num, axis in status["axes"].items():
            print(f"  [{num}] {axis['name']}")
            print(f"      {axis['description']}")
            for m in axis["modules"]:
                print(f"        • {m}")
            print()

        # Módulos
        print(f"  MÓDULOS CARREGADOS: {status['modules_loaded']}/{status['modules_total']}")
        print("-" * 70)
        for name, info in status["modules"].items():
            marker = "+" if info["loaded"] else "-"
            print(f"  [{marker}] {name}: {info['type']}")
        print()

        # TRL
        if status.get("trl"):
            trl = status["trl"]
            print(f"  MATURIDADE TECNOLÓGICA: TRL {trl.get('current_trl', '?')}")
            print(f"  {trl.get('trl_description', '')}")
            nxt = trl.get("next_milestone")
            if nxt:
                print(f"  Próximo: TRL {nxt['trl']} — {nxt['description']}")
        print()
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="HEAL/REDISUS — Plataforma Nacional de Saúde Digital Integrada",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modos disponíveis:
  realtime    Detecção de feridas em tempo real (webcam)
  image       Análise de imagem estática
  dashboard   Dashboard web clínico (Flask)
  status      Exibe status da plataforma
  demo        Demonstração completa
  query       Consulta à base de conhecimento (RAG)
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["realtime", "image", "dashboard", "status", "demo", "query"],
        default="status",
        help="Modo de operação",
    )
    parser.add_argument("--input", "-i", help="Caminho da imagem para análise")
    parser.add_argument("--port", "-p", type=int, default=5000, help="Porta do dashboard")
    parser.add_argument("--host", default="0.0.0.0", help="Host do dashboard")
    parser.add_argument("--debug", action="store_true", help="Modo debug")
    parser.add_argument("--query", "-q", help="Pergunta clínica (modo query)")

    args = parser.parse_args()

    platform = HEALPlatform()

    if args.mode == "status":
        platform.initialize(modules="all")
        platform.print_status()

    elif args.mode == "dashboard":
        platform.initialize(modules="all")
        platform.run_dashboard(host=args.host, port=args.port, debug=args.debug)

    elif args.mode == "realtime":
        platform.initialize(modules="core")
        platform.run_realtime()

    elif args.mode == "image":
        if not args.input:
            print("ERRO: --input é obrigatório no modo image")
            sys.exit(1)
        platform.initialize(modules="core")
        platform.run_image_analysis(args.input)

    elif args.mode == "query":
        platform.initialize(modules="core")
        cds = platform.get_module("clinical_support")
        if cds:
            query = args.query or input("Pergunta clínica: ")
            result = cds.answer_clinical_question(query)
            print(f"\nPergunta: {result.get('question', query)}")
            print(f"Confiança: {result.get('confidence', 0):.0%}")
            print(f"Nível de evidência: {result.get('evidence_level', 'N/A')}")
            print(f"\nResposta:\n{result.get('answer', 'Sem resposta')}")
            print(f"\nFonte: {result.get('source', 'N/A')}")
        else:
            print("Módulo de suporte clínico não disponível")

    elif args.mode == "demo":
        platform.initialize(modules="all")
        platform.print_status()
        print("\n--- DEMONSTRAÇÃO: Consulta RAG ---")
        cds = platform.get_module("clinical_support")
        if cds:
            questions = [
                "Como tratar ulcera venosa cronica?",
                "Quais coberturas usar em ferida infectada?",
                "Como diagnosticar esporotricose?",
            ]
            for q in questions:
                result = cds.answer_clinical_question(q)
                print(f"\nQ: {q}")
                print(f"A: {result.get('answer', '')[:200]}...")
                print(f"   Evidência: {result.get('evidence_level', 'N/A')}")

        print("\n--- DEMONSTRAÇÃO: Simulação de Cicatrização ---")
        from src.digital_twin.twin_model import (
            PatientProfile, WoundState, PatientDigitalTwin, HealingPhase
        )
        patient = PatientProfile(
            id="demo-001", age=65, sex="F",
            weight_kg=80, height_cm=160,
            diabetes=True, vascular_disease=True,
            comorbidities=["DM2", "HAS", "IVC"],
        )
        wound = WoundState(
            area_cm2=12.0, depth_cm=0.5,
            granulation_pct=40, necrosis_pct=15,
            slough_pct=20, epithelialization_pct=5,
            healing_phase=HealingPhase.INFLAMMATORY,
        )
        twin = PatientDigitalTwin(patient)
        twin.update_wound_state(wound)
        pred = twin.predict_outcomes(weeks=12)
        sim = pred["simulation"]
        print(f"  Taxa de cicatrização: {sim['healing_rate_per_week']}%/semana")
        print(f"  Semanas estimadas para fechamento: {sim.get('estimated_weeks_to_closure', 'N/A')}")
        print(f"  Risco de complicações: {pred['complication_risk']['level']}")

        print("\nDemonstração concluída.")


if __name__ == "__main__":
    main()
