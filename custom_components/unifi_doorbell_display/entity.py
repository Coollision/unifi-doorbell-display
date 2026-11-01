"""Shared entity base."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Doorbell, DoorbellCoordinator


class DoorbellEntity(CoordinatorEntity[DoorbellCoordinator]):
    """An entity belonging to one doorbell."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DoorbellCoordinator, camera_id: str, key: str) -> None:
        super().__init__(coordinator)
        self.camera_id = camera_id
        self._attr_unique_id = f"{camera_id}_{key}"
        doorbell = coordinator.data.doorbells[camera_id]
        # Home Assistant 2026.10 lets a device belong to a single config entry, so these
        # entities cannot sit on the native UniFi Protect device; they get their own.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera_id)},
            name=f"{doorbell.name} display",
            model=doorbell.model,
            manufacturer="Ubiquiti",
        )

    @property
    def doorbell(self) -> Doorbell | None:
        return self.coordinator.data.doorbells.get(self.camera_id)

    @property
    def available(self) -> bool:
        return super().available and self.doorbell is not None
