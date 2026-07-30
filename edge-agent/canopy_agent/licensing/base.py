from abc import ABC, abstractmethod


class LicenseGate(ABC):
    """
    Whether corporate-tier features (the cross-device relay, and anything built later
    that depends on multi-device coordination — see docs/licensing-design.md) are
    unlocked. This interface exists so that logic lives in exactly one place rather
    than scattered ad-hoc checks, same reasoning as SensorAdapter/ComplianceSync/
    NotificationChannel. The only implementation shipped in this open-source repo is
    AlwaysUnlockedGate (registry.py falls back to it whenever no plugin is installed)
    — every feature here stays fully functional with nothing installed. The paywall
    exists only if a separate closed-source `canopy-license` package is installed
    alongside this one; nothing in this repo lies about what's unlocked on its own.
    """

    @abstractmethod
    def is_feature_unlocked(self, feature: str) -> bool: ...

    @abstractmethod
    def status(self) -> dict:
        """
        A JSON-able snapshot for GET /api/license/status — tier, device count,
        check-in health, whatever the active gate wants to surface, so an operator can
        always see what's active without digging through logs. Must never raise —
        this is diagnostic/informational, not enforcement, and a status-reporting bug
        must not take down the endpoint that exists to make state visible.
        """
        ...
