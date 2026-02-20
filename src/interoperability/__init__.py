"""
HEAL/REDISUS - Módulo de Interoperabilidade
Integração com padrões HL7 FHIR R4, e-SUS/PEC e DATASUS.

Camada 3 da Plataforma Nacional de Saúde Digital Integrada:
- HL7 FHIR R4: Recursos Patient, Observation, Condition, CarePlan, DiagnosticReport
- e-SUS/PEC: Fichas de Atendimento Individual, SOAP, importação de cadastro
- DATASUS: SIGTAP, BPA, SISAB, CNES
"""
from src.interoperability.fhir_client import FHIRClient, FHIRResourceBuilder
from src.interoperability.esus_integration import ESUSIntegration, FichaAtendimentoIndividual
from src.interoperability.datasus_integration import DATASUSIntegration

__all__ = [
    "FHIRClient",
    "FHIRResourceBuilder",
    "ESUSIntegration",
    "FichaAtendimentoIndividual",
    "DATASUSIntegration",
]
