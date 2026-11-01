"""Binary sensor: is the screen back on Protect's default message?"""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DoorbellConfigEntry
from .coordinator import DoorbellCoordinator
from .entity import DoorbellEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: DoorbellConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(ShowingDefault(coordinator, cam) for cam in coordinator.data.doorbells)


class ShowingDefault(DoorbellEntity, BinarySensorEntity):
    """On while nothing is set, i.e. Protect shows its default animation."""

    _attr_translation_key = "showing_default"

    def __init__(self, coordinator: DoorbellCoordinator, camera_id: str) -> None:
        super().__init__(coordinator, camera_id, "showing_default")

    @property
    def is_on(self) -> bool | None:
        doorbell = self.doorbell
        return doorbell.message.is_default if doorbell else None
