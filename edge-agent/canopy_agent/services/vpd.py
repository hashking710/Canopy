import math


def vpd_kpa(temp_f: float, rh_pct: float) -> float:
    """Vapor pressure deficit (leaf-temp-agnostic, air VPD) via the Tetens equation."""
    temp_c = (temp_f - 32) * 5 / 9
    saturation_vapor_pressure = 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    return saturation_vapor_pressure * (1 - rh_pct / 100)
