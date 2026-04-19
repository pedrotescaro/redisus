from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from ..validators import validate_bundle, validate_resource


class AbstractFHIRClient(ABC):
    def __init__(self, *, strict_validation: bool = False):
        self.strict_validation = strict_validation

    def validate_resource_before_send(self, resource: Mapping[str, Any]) -> None:
        validate_resource(resource, strict=self.strict_validation)

    def validate_bundle_before_send(self, bundle: Mapping[str, Any]) -> None:
        validate_bundle(bundle, strict=self.strict_validation)

    @abstractmethod
    def send_resource(self, resource: Mapping[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def send_bundle(self, bundle: Mapping[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def read(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def search(self, resource_type: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError
