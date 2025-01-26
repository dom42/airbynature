"""Sensor for AirByNature integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    REVOLUTIONS_PER_MINUTE,
    CONCENTRATION_PARTS_PER_MILLION,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AirByNatureCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSORS: dict[str, SensorEntityDescription] = {
    "wifisignal": SensorEntityDescription(
        key="wifirssi",
        translation_key="wifi_signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "outsidetemp": SensorEntityDescription(
        key="outsidetemp",
        translation_key="outside_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "inlet_temp": SensorEntityDescription(
        key="inlettemp",
        translation_key="inlet_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "inlet_hum": SensorEntityDescription(
        key="inlethum",
        translation_key="inlet_humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "inlet_fan": SensorEntityDescription(
        key="inletfan",
        translation_key="inlet_fan",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "inlet_fan_1_rpm": SensorEntityDescription(
        key="inletfan1rpm",
        translation_key="inlet_fan1_rpm",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "inlet_fan_2_rpm": SensorEntityDescription(
        key="inletfan2rpm",
        translation_key="inlet_fan2_rpm",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "outlet_temp": SensorEntityDescription(
        key="outlettemp",
        translation_key="outlet_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "outlet_hum": SensorEntityDescription(
        key="outlethum",
        translation_key="outlet_humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "outlet_fan": SensorEntityDescription(
        key="outletfan",
        translation_key="outlet_fan",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "outlet_fan_1_rpm": SensorEntityDescription(
        key="outletfan1rpm",
        translation_key="outlet_fan1_rpm",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "outlet_fan_2_rpm": SensorEntityDescription(
        key="outletfan2rpm",
        translation_key="outlet_fan2_rpm",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "outlet_co2": SensorEntityDescription(
        key="outletco2",
        translation_key="outlet_co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the AirByNature sensors from config entries."""
    _LOGGER.warning("Asyc setup_entry")
    coordinator = config_entry.runtime_data

    entities = []

    entities.append(AirByNatureSensor(coordinator, SENSORS["outsidetemp"]))
    entities.append(AirByNatureSensor(coordinator, SENSORS["inlet_temp"]))
    entities.append(AirByNatureSensor(coordinator, SENSORS["inlet_hum"]))
    entities.append(AirByNatureSensor(coordinator, SENSORS["inlet_fan_1_rpm"]))
    entities.append(AirByNatureSensor(coordinator, SENSORS["outlet_fan_1_rpm"]))

    #    coordinator: AirByNatureCoordinator = hass.data[DOMAIN][
    #        config_entry.entry_id
    #    ].coordinator

    async_add_entities(entities)
    _LOGGER.warning("Asyc setup_entry")


class AirByNatureSensor(CoordinatorEntity[AirByNatureCoordinator], SensorEntity):
    """Representation of a sensor entity for AirByNature status values."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirByNatureCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, context=description.key.upper())

        self.entity_description = description
        self._attr_device_info = coordinator.device_info

        _LOGGER.warning(description)
        _LOGGER.warning(coordinator.device_info)

        # Initial update of attributes.
        self._update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.error("_handle_coordinator_update")
        _LOGGER.info(self.entity_id)
        _LOGGER.warning(self.coordinator.data)

        # TODO
        if self.entity_id == "sensor.external_temperature":
            self._attr_native_value = self.coordinator.data["data"]["devices"][0][
                "latest_history"
            ]["external_temp"]
        elif self.entity_id == "sensor.inlet_temperature":
            self._attr_native_value = self.coordinator.data["data"]["devices"][0][
                "latest_history"
            ]["inlet_temp"]
        elif self.entity_id == "sensor.inlet_humidity":
            self._attr_native_value = self.coordinator.data["data"]["devices"][0][
                "latest_history"
            ]["inlet_humid"]
        elif self.entity_id == "sensor.inlet_fan_1_speed":
            self._attr_native_value = self.coordinator.data["data"]["devices"][0][
                "latest_history"
            ]["inlet_fan1_rpm"]
        elif self.entity_id == "sensor.outlet_fan_1_speed":
            self._attr_native_value = self.coordinator.data["data"]["devices"][0][
                "latest_history"
            ]["outlet_fan1_rpm"]

        self.async_write_ha_state()

    def _update_attrs(self) -> None:
        """Update sensor attributes based on coordinator data."""
        # TODO
        _LOGGER.error("_update_attrs")
        _LOGGER.error(self)
