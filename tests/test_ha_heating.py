import sys
from unittest.mock import MagicMock

# Mock homeassistant modules so tests run in environments without HA core installed
if "homeassistant" not in sys.modules:
    ha_mock = MagicMock()
    sys.modules["homeassistant"] = ha_mock
    sys.modules["homeassistant.config_entries"] = MagicMock()
    sys.modules["homeassistant.const"] = MagicMock()
    sys.modules["homeassistant.core"] = MagicMock()
    sys.modules["homeassistant.components"] = MagicMock()
    sys.modules["homeassistant.components.http"] = MagicMock()
    sys.modules["homeassistant.components.climate"] = MagicMock()
    sys.modules["homeassistant.helpers"] = MagicMock()
    sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()
    sys.modules["homeassistant.helpers.event"] = MagicMock()

from datetime import datetime, date
import unittest

from custom_components.ha_heating.energy_arbitrage import EnergyArbitrage
from custom_components.ha_heating.scheduler import HeatingScheduler
from custom_components.ha_heating.const import (
    CYCLE_ANCHOR_DATE,
    CYCLE_EXTERNAL_ENTITY,
    CYCLE_ISO_EVEN_ODD,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOLIDAY,
    PRESET_SLEEP,
)


class TestEnergyArbitrage(unittest.TestCase):
    """Test COP estimation and arbitrage math."""

    def setUp(self):
        self.arbitrage = EnergyArbitrage(gas_kwh_per_m3=9.0)

    def test_estimate_cop(self):
        # Mild weather
        self.assertAlmostEqual(self.arbitrage.estimate_cop(12.0), 4.6, places=1)
        self.assertAlmostEqual(self.arbitrage.estimate_cop(7.0), 4.0, places=1)
        self.assertAlmostEqual(self.arbitrage.estimate_cop(2.0), 3.2, places=1)
        # Freezing
        self.assertAlmostEqual(self.arbitrage.estimate_cop(-2.0), 2.6, places=1)
        self.assertAlmostEqual(self.arbitrage.estimate_cop(-7.0), 2.1, places=1)
        # None fallback
        self.assertEqual(self.arbitrage.estimate_cop(None), 3.5)

    def test_thermal_cost_gas(self):
        # Gas price €1.35/m3 -> 1.35 / 9.0 = 0.15 €/kWh
        self.assertAlmostEqual(self.arbitrage.calculate_thermal_cost_gas(1.35), 0.15, places=3)
        self.assertIsNone(self.arbitrage.calculate_thermal_cost_gas(None))
        self.assertIsNone(self.arbitrage.calculate_thermal_cost_gas(0))

    def test_thermal_cost_electric(self):
        # Stroom €0.30/kWh at 7°C (COP 4.0) -> 0.30 / 4.0 = 0.075 €/kWh
        cost = self.arbitrage.calculate_thermal_cost_electric(0.30, outdoor_temp=7.0)
        self.assertAlmostEqual(cost, 0.075, places=3)

        # Solar surplus (>200W export) -> 0.0 €/kWh
        cost_solar = self.arbitrage.calculate_thermal_cost_electric(0.30, outdoor_temp=7.0, solar_export_watts=500)
        self.assertEqual(cost_solar, 0.0)

    def test_should_use_ac_decisions(self):
        # Case 1: Electricity is much cheaper
        use_ac, reason = self.arbitrage.should_use_ac_for_heating(
            gas_price_per_m3=1.45,
            electric_price_per_kwh=0.25,
            outdoor_temp=10.0,
        )
        self.assertTrue(use_ac)
        self.assertIn("Airco is cheaper", reason)

        # Case 2: Extreme gas price drop or peak electricity
        use_ac_gas, reason_gas = self.arbitrage.should_use_ac_for_heating(
            gas_price_per_m3=0.80,
            electric_price_per_kwh=0.50,
            outdoor_temp=-2.0,
        )
        self.assertFalse(use_ac_gas)
        self.assertIn("Gas is cheaper", reason_gas)

        # Case 3: Solar excess forces AC
        use_ac_solar, _ = self.arbitrage.should_use_ac_for_heating(
            gas_price_per_m3=0.50,
            electric_price_per_kwh=0.50,
            outdoor_temp=0.0,
            solar_export_watts=1200,
        )
        self.assertTrue(use_ac_solar)

        # Case 4: Quiet hours overrides decision
        use_ac_quiet, reason_quiet = self.arbitrage.should_use_ac_for_heating(
            gas_price_per_m3=2.00,
            electric_price_per_kwh=0.05,
            outdoor_temp=10.0,
            is_quiet_hours=True,
        )
        self.assertFalse(use_ac_quiet)
        self.assertIn("Quiet hours active", reason_quiet)

    def test_quiet_hours(self):
        dt_night = datetime(2026, 1, 15, 23, 30)
        dt_day = datetime(2026, 1, 15, 14, 0)
        dt_morning = datetime(2026, 1, 15, 6, 30)

        self.assertTrue(EnergyArbitrage.is_in_quiet_hours(dt_night, "22:00", "07:00"))
        self.assertTrue(EnergyArbitrage.is_in_quiet_hours(dt_morning, "22:00", "07:00"))
        self.assertFalse(EnergyArbitrage.is_in_quiet_hours(dt_day, "22:00", "07:00"))


class TestHeatingScheduler(unittest.TestCase):
    """Test 2-week cycle and vacation calendar overrides."""

    def test_iso_even_odd_cycle(self):
        scheduler = HeatingScheduler(cycle_type=CYCLE_ISO_EVEN_ODD)
        dt_even = datetime(2026, 10, 4)  # Week 40
        self.assertEqual(scheduler.determine_week_cycle(dt_even), "week_a")

        dt_odd = datetime(2026, 10, 8)  # Week 41
        self.assertEqual(scheduler.determine_week_cycle(dt_odd), "week_b")

    def test_anchor_date_cycle(self):
        scheduler = HeatingScheduler(
            cycle_type=CYCLE_ANCHOR_DATE,
            cycle_anchor_date_str="2026-10-01",
        )
        dt1 = datetime(2026, 10, 4)
        self.assertEqual(scheduler.determine_week_cycle(dt1), "week_a")

        dt2 = datetime(2026, 10, 11)
        self.assertEqual(scheduler.determine_week_cycle(dt2), "week_b")

    def test_vacation_calendar_filter(self):
        scheduler = HeatingScheduler(calendar_filter="Vakantie")
        self.assertFalse(scheduler.is_vacation_active("off"))

        attrs_match = {"message": "Herfst Vakantie Ardennen"}
        self.assertTrue(scheduler.is_vacation_active("on", attrs_match))

        attrs_no_match = {"message": "Tandarts controle"}
        self.assertFalse(scheduler.is_vacation_active("on", attrs_no_match))

    def test_resolve_target_temperature(self):
        scheduler = HeatingScheduler()
        preset_temps = {
            PRESET_COMFORT: 20.5,
            PRESET_ECO: 18.0,
            PRESET_SLEEP: 16.0,
            PRESET_AWAY: 15.0,
            PRESET_BOOST: 22.0,
            PRESET_HOLIDAY: 14.5,
        }

        now = datetime(2026, 10, 4, 12, 0)

        temp, reason = scheduler.resolve_target_temperature(
            current_dt=now,
            preset_mode=None,
            is_vacation=True,
            active_week="week_a",
            schedule_a_state="on",
            schedule_b_state="off",
            preset_temps=preset_temps,
        )
        self.assertEqual(temp, 14.5)
        self.assertIn("Vacation", reason)

        temp_sched_on, reason_sched = scheduler.resolve_target_temperature(
            current_dt=now,
            preset_mode=None,
            is_vacation=False,
            active_week="week_a",
            schedule_a_state="on",
            schedule_b_state="off",
            preset_temps=preset_temps,
        )
        self.assertEqual(temp_sched_on, 20.5)
        self.assertIn("Comfort", reason_sched)

        temp_sched_off, _ = scheduler.resolve_target_temperature(
            current_dt=now,
            preset_mode=None,
            is_vacation=False,
            active_week="week_a",
            schedule_a_state="off",
            schedule_b_state="on",
            preset_temps=preset_temps,
        )
        self.assertEqual(temp_sched_off, 18.0)


class TestWindowManager(unittest.IsolatedAsyncioTestCase):
    """Test window open debounce logic."""

    async def test_window_debounce(self):
        import asyncio
        from custom_components.ha_heating.window_manager import WindowManager

        wm = WindowManager(open_delay_sec=0.1, close_delay_sec=0.1)
        loop = asyncio.get_running_loop()
        events = []

        def callback(room_id, is_open):
            events.append((room_id, is_open))

        wm.handle_sensor_update("room_1", any_window_open=True, loop=loop, on_state_change=callback)
        self.assertFalse(wm.get_is_room_paused("room_1"))

        await asyncio.sleep(0.15)
        self.assertTrue(wm.get_is_room_paused("room_1"))
        self.assertEqual(events, [("room_1", True)])

        wm.handle_sensor_update("room_1", any_window_open=False, loop=loop, on_state_change=callback)
        self.assertTrue(wm.get_is_room_paused("room_1"))

        await asyncio.sleep(0.15)
        self.assertFalse(wm.get_is_room_paused("room_1"))
        self.assertEqual(events, [("room_1", True), ("room_1", False)])

    async def test_fast_open_close_cancelled(self):
        import asyncio
        from custom_components.ha_heating.window_manager import WindowManager

        wm = WindowManager(open_delay_sec=0.2, close_delay_sec=0.2)
        loop = asyncio.get_running_loop()
        events = []

        def callback(room_id, is_open):
            events.append((room_id, is_open))

        wm.handle_sensor_update("room_1", any_window_open=True, loop=loop, on_state_change=callback)
        await asyncio.sleep(0.05)
        wm.handle_sensor_update("room_1", any_window_open=False, loop=loop, on_state_change=callback)

        await asyncio.sleep(0.25)
        self.assertFalse(wm.get_is_room_paused("room_1"))
        self.assertEqual(events, [])


class TestMasterThermostatController(unittest.IsolatedAsyncioTestCase):
    """Test master thermostat demand aggregation and anti-cycling."""

    async def test_demand_aggregation_and_anti_cycling(self):
        from unittest.mock import AsyncMock
        from custom_components.ha_heating.heat_demand import MasterThermostatController
        from custom_components.ha_heating.const import MASTER_MODE_SETPOINT_BOOST

        hass_mock = MagicMock()
        hass_mock.services.async_call = AsyncMock()

        controller = MasterThermostatController(
            hass=hass_mock,
            master_entity_id="climate.thermostaat_boven",
            control_mode=MASTER_MODE_SETPOINT_BOOST,
            boost_temp=25.0,
            idle_temp=15.0,
            min_cycle_duration_sec=300,
            min_off_duration_sec=180,
        )

        controller.register_room("slaapkamer_1")
        controller.register_room("slaapkamer_2")

        t0 = datetime(2026, 10, 4, 10, 0, 0)
        await controller.update_room_demand("slaapkamer_1", True, t0)
        self.assertTrue(controller.is_heating_active)

        # Anti-cycling minimum run duration
        t1 = datetime(2026, 10, 4, 10, 1, 0)
        await controller.update_room_demand("slaapkamer_1", False, t1)
        self.assertTrue(controller.is_heating_active)

        # Exceeding min cycle duration
        t2 = datetime(2026, 10, 4, 10, 5, 20)
        await controller.update_room_demand("slaapkamer_1", False, t2)
        self.assertFalse(controller.is_heating_active)


if __name__ == "__main__":
    unittest.main()
