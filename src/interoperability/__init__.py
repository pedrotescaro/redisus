"""
REDISUS interoperability package.

Legacy entry points remain available through src.interoperability.fhir_client,
while the new HL7 FHIR R4 implementation lives in src.interoperability.fhir_r4.
"""

from src.interoperability.datasus_integration import DATASUSIntegration
from src.interoperability.esus_integration import ESUSIntegration, FichaAtendimentoIndividual
from src.interoperability.fhir_client import FHIRClient, FHIRResourceBuilder
from src.interoperability.fhir_r4 import (
    FHIRPublicationError,
    FHIRPublicationResult,
    FHIRPublicationService,
    FHIRValidationError,
    GoogleCloudHealthcareFHIRAdapter,
    RedisusFHIRMapper,
    build_example_artifacts,
    validate_bundle,
    validate_resource,
)

__all__ = [
    "DATASUSIntegration",
    "ESUSIntegration",
    "FHIRClient",
    "FHIRPublicationError",
    "FHIRPublicationResult",
    "FHIRPublicationService",
    "FHIRResourceBuilder",
    "FHIRValidationError",
    "FichaAtendimentoIndividual",
    "GoogleCloudHealthcareFHIRAdapter",
    "RedisusFHIRMapper",
    "build_example_artifacts",
    "validate_bundle",
    "validate_resource",
]
