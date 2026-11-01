"""Sensors: what is shown now, when it resets, and which images exist."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import DoorbellConfigEntry
from .coordinator import DoorbellCoordinator
from .entity import DoorbellEntity
from .util import KIND_DEFAULT, KIND_DO_NOT_DISTURB, KIND_IMAGE, KIND_LEAVE_PACKAGE, KIND_TEXT

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: DoorbellConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[DoorbellEntity] = []
    for cam_id in coordinator.data.doorbells:
        entities += [
            CurrentDisplay(coordinator, cam_id),
            ResetsAt(coordinator, cam_id),
            AvailableImages(coordinator, cam_id),
        ]
    async_add_entities(entities)


class CurrentDisplay(DoorbellEntity, SensorEntity):
    """Human-readable description of what the screen shows."""

    _attr_translation_key = "current_display"

    def __init__(self, coordinator: DoorbellCoordinator, camera_id: str) -> None:
        super().__init__(coordinator, camera_id, "current_display")

    @property
    def native_value(self) -> str | None:
        doorbell = self.doorbell
        if doorbell is None:
            return None
        msg = doorbell.message
        if msg.kind == KIND_DEFAULT:
            return "Default message"
        if msg.kind == KIND_LEAVE_PACKAGE:
            return "Leave package at door"
        if msg.kind == KIND_DO_NOT_DISTURB:
            return "Do not disturb"
        if msg.kind == KIND_TEXT:
            return f"Text: {msg.text}"
        image = self.coordinator.data.image_by_id(msg.text)
        return f"Image: {image.name}" if image else f"Image: {msg.text}"

    @property
    def extra_state_attributes(self) -> dict | None:
        doorbell = self.doorbell
        if doorbell is None:
            return None
        msg = doorbell.message
        image = self.coordinator.data.image_by_id(msg.text) if msg.kind == KIND_IMAGE else None
        return {
            "kind": msg.kind,
            "text": msg.text if msg.kind == KIND_TEXT else None,
            "image_id": msg.text if msg.kind == KIND_IMAGE else None,
            "image_name": image.name if image else None,
            "resets_at": _as_datetime(msg.reset_at_ms),
        }


class ResetsAt(DoorbellEntity, SensorEntity):
    """When Protect will clear the current message (empty when it stays)."""

    _attr_translation_key = "resets_at"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: DoorbellCoordinator, camera_id: str) -> None:
        super().__init__(coordinator, camera_id, "resets_at")

    @property
    def native_value(self) -> datetime | None:
        doorbell = self.doorbell
        return _as_datetime(doorbell.message.reset_at_ms) if doorbell else None


class AvailableImages(DoorbellEntity, SensorEntity):
    """Count of uploaded images, with the full list as an attribute."""

    _attr_translation_key = "available_images"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DoorbellCoordinator, camera_id: str) -> None:
        super().__init__(coordinator, camera_id, "available_images")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.images)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "images": [
                {"name": i.name, "id": i.id, "file": i.original, "size": i.size, "created": i.created}
                for i in self.coordinator.data.images
            ]
        }


def _as_datetime(ms: int | None) -> datetime | None:
    return dt_util.utc_from_timestamp(ms / 1000) if ms else None
