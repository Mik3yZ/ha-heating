"""Energy Arbitrage calculation engine for ha_heating.

Evaluates cost per thermal kWh for gas vs. electricity (heat pump / AC),
taking into account outdoor temperature (COP curve), dynamic tariffs,
solar PV export, and quiet-hours restrictions.
"""

from __future__ import annotations

from datetime import datetime, time
import logging

from .const import DEFAULT_GAS_KWH_PER_M3

_LOGGER = logging.getLogger(__name__)


class EnergyArbitrage:
    """Calculates thermodynamic efficiency and financial arbitrage."""

    def __init__(
        self,
        gas_kwh_per_m3: float = DEFAULT_GAS_KWH_PER_M3,
    ) -> None:
        """Initialize energy arbitrage calculator."""
        self.gas_kwh_per_m3 = gas_kwh_per_m3

    @staticmethod
    def estimate_cop(outdoor_temp: float | None) -> float:
        """Estimate the Coefficient of Performance (COP) based on outdoor temperature.

        Typical residential air-to-air heat pump curve:
        > 12°C: 4.5
        7°C: 4.0
        2°C: 3.2
        -2°C (defrost penalties): 2.6
        -7°C: 2.1
        < -10°C: 1.8
        """
        if outdoor_temp is None:
            return 3.5  # reasonable fallback default

        if outdoor_temp >= 12.0:
            return 4.6
        if outdoor_temp >= 7.0:
            # Linear interpolation between 7°C (4.0) and 12°C (4.6)
            return 4.0 + (outdoor_temp - 7.0) * (0.6 / 5.0)
        if outdoor_temp >= 2.0:
            # Linear interpolation between 2°C (3.2) and 7°C (4.0)
            return 3.2 + (outdoor_temp - 2.0) * (0.8 / 5.0)
        if outdoor_temp >= -2.0:
            # Linear interpolation between -2°C (2.6) and 2°C (3.2)
            return 2.6 + (outdoor_temp - (-2.0)) * (0.6 / 4.0)
        if outdoor_temp >= -7.0:
            # Linear interpolation between -7°C (2.1) and -2°C (2.6)
            return 2.1 + (outdoor_temp - (-7.0)) * (0.5 / 5.0)
        if outdoor_temp >= -15.0:
            # Linear interpolation between -15°C (1.6) and -7°C (2.1)
            return 1.6 + (outdoor_temp - (-15.0)) * (0.5 / 8.0)
        return 1.5

    def calculate_thermal_cost_gas(self, gas_price_per_m3: float | None) -> float | None:
        """Calculate thermal cost per kWh heat from natural gas (€/kWh)."""
        if gas_price_per_m3 is None or gas_price_per_m3 <= 0:
            return None
        return gas_price_per_m3 / self.gas_kwh_per_m3

    def calculate_thermal_cost_electric(
        self,
        electric_price_per_kwh: float | None,
        outdoor_temp: float | None,
        solar_export_watts: float | None = None,
    ) -> float | None:
        """Calculate thermal cost per kWh heat from electricity via heat pump (€/kWh)."""
        if electric_price_per_kwh is None:
            return None

        cop = self.estimate_cop(outdoor_temp)

        # If significant solar power is exported (> 200W), consider marginal electric cost 0.0 or feed-in rate
        if solar_export_watts is not None and solar_export_watts > 200:
            return 0.0

        # If electricity price is negative, thermal cost is negative (you get paid to heat!)
        if electric_price_per_kwh <= 0:
            return electric_price_per_kwh / cop

        return electric_price_per_kwh / cop

    def should_use_ac_for_heating(
        self,
        gas_price_per_m3: float | None,
        electric_price_per_kwh: float | None,
        outdoor_temp: float | None,
        solar_export_watts: float | None = None,
        is_quiet_hours: bool = False,
    ) -> tuple[bool, str]:
        """Determine if AC (heat pump) should be prioritized over Gas heating.

        Returns (use_ac: bool, reason: str).
        """
        if is_quiet_hours:
            return False, "Quiet hours active (airco restricted to avoid noise/draft)"

        # If solar export is available, AC is free
        if solar_export_watts is not None and solar_export_watts > 300:
            return True, "Solar surplus available (Airco prioritized)"

        # Severe frost bivalency safety check: below -7°C radiators give superior comfort and less cycling
        if outdoor_temp is not None and outdoor_temp < -7.0:
            return False, f"Outdoor temperature too low ({outdoor_temp:.1f}°C, below -7°C bivalency threshold)"

        cost_gas = self.calculate_thermal_cost_gas(gas_price_per_m3)
        cost_elec = self.calculate_thermal_cost_electric(
            electric_price_per_kwh, outdoor_temp, solar_export_watts
        )

        if cost_elec is None or cost_gas is None:
            # Fallback if pricing sensors are not configured: use AC if outdoor temp > 2°C
            if outdoor_temp is not None and outdoor_temp >= 2.0:
                return True, "No price data, but outdoor temp favorable (>= 2°C)"
            return False, "Missing price sensors, fallback to gas central heating"

        cop = self.estimate_cop(outdoor_temp)
        if cost_elec < cost_gas:
            savings_pct = ((cost_gas - cost_elec) / cost_gas) * 100.0
            return (
                True,
                f"Airco is cheaper: €{cost_elec:.3f}/kWh (COP {cop:.1f}) vs Gas €{cost_gas:.3f}/kWh ({savings_pct:.0f}% cheaper)",
            )

        savings_pct = ((cost_elec - cost_gas) / cost_elec) * 100.0
        return (
            False,
            f"Gas is cheaper: €{cost_gas:.3f}/kWh vs Airco €{cost_elec:.3f}/kWh (COP {cop:.1f}, {savings_pct:.0f}% cheaper)",
        )

    @staticmethod
    def is_in_quiet_hours(
        current_dt: datetime,
        quiet_start_str: str | None,
        quiet_end_str: str | None,
    ) -> bool:
        """Check if the given time falls within configured quiet hours (e.g. 22:00 to 07:00)."""
        if not quiet_start_str or not quiet_end_str:
            return False

        try:
            start_parts = [int(p) for p in quiet_start_str.split(":")]
            end_parts = [int(p) for p in quiet_end_str.split(":")]
            t_start = time(start_parts[0], start_parts[1])
            t_end = time(end_parts[0], end_parts[1])
        except (ValueError, IndexError):
            _LOGGER.warning(
                "Invalid quiet hours format: %s - %s", quiet_start_str, quiet_end_str
            )
            return False

        current_t = current_dt.time()

        if t_start <= t_end:
            # Same day window, e.g. 13:00 - 15:00
            return t_start <= current_t <= t_end
        # Overnight window, e.g. 22:00 - 07:00
        return current_t >= t_start or current_t <= t_end

