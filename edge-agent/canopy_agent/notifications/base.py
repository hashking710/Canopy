from abc import ABC, abstractmethod
from typing import ClassVar


class NotificationChannel(ABC):
    """
    Interface for delivering an alert somewhere a person will actually see it.
    Same plugin shape as SensorAdapter/ComplianceSync — "webhook" and "email" are the
    two channels this package ships itself (broadly useful defaults, unlike sensor/
    compliance integrations which are inherently vendor-specific), discovered via
    notifications/registry.py alongside anything a plugin package adds under the
    canopy.notification_channels entry-point group.
    """

    plugin_name: ClassVar[str] = "unnamed channel"
    plugin_description: ClassVar[str] = ""
    config_schema: ClassVar[dict[str, str]] = {}

    @abstractmethod
    async def send(self, alert: dict) -> None: ...
