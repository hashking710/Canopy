from canopy_agent.licensing.base import LicenseGate


class AlwaysUnlockedGate(LicenseGate):
    """The default when no canopy-license package is installed — every feature stays
    unlocked. This is what makes 'open source but paywalled' not a contradiction: the
    paywall is an opt-in add-on this repo doesn't require, not something baked into
    this repo's own behavior."""

    def is_feature_unlocked(self, feature: str) -> bool:
        return True

    def status(self) -> dict:
        return {
            "tier": "unlicensed",
            "gate": "Open source — no license required, everything unlocked",
            "features_unlocked": "all",
        }
