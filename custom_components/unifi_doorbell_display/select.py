"""Select entity: show/choose the doorbell display + the set/reset services."""

from __future__ import annotations

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DoorbellConfigEntry
from .const import OPTION_DEFAULT, OPTION_DO_NOT_DISTURB, OPTION_LEAVE_PACKAGE
from .coordinator import DoorbellCoordinator
from .entity import DoorbellEntity
from .util import (
    KIND_DO_NOT_DISTURB,
    KIND_IMAGE,
    KIND_LEAVE_PACKAGE,
    KIND_TEXT,
)

PARALLEL_UPDATES = 1

_DURATION = vol.All(cv.time_period, vol.Range(min=timedelta(seconds=1)))
SET_IMAGE_SCHEMA = {
    vol.Required("image"): cv.string,
    vol.Optional("duration"): _DURATION,
    vol.Optional("then"): cv.string,
}
SET_TEXT_SCHEMA = {
    vol.Required("text"): vol.All(cv.string, vol.Length(min=1, max=30)),
    vol.Optional("duration"): _DURATION,
    vol.Optional("then"): cv.string,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: DoorbellConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        DisplaySelect(coordinator, cam_id) for cam_id in coordinator.data.doorbells
    )
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service("set_image", SET_IMAGE_SCHEMA, "async_set_image")
    platform.async_register_entity_service("set_text", SET_TEXT_SCHEMA, "async_set_text")
    platform.async_register_entity_service("reset_display", None, "async_reset_display")


class DisplaySelect(DoorbellEntity, SelectEntity):
    """What the doorbell screen shows."""

    _attr_translation_key = "display"

    def __init__(self, coordinator: DoorbellCoordinator, camera_id: str) -> None:
        super().__init__(coordinator, camera_id, "display")

    @property
    def options(self) -> list[str]:
        return [
            OPTION_DEFAULT,
            OPTION_LEAVE_PACKAGE,
            OPTION_DO_NOT_DISTURB,
            *(i.name for i in self.coordinator.data.images),
        ]

    @property
    def current_option(self) -> str | None:
        doorbell = self.doorbell
        if doorbell is None:
            return None
        msg = doorbell.message
        if msg.is_default:
            return OPTION_DEFAULT
        if msg.kind == KIND_LEAVE_PACKAGE:
            return OPTION_LEAVE_PACKAGE
        if msg.kind == KIND_DO_NOT_DISTURB:
            return OPTION_DO_NOT_DISTURB
        if msg.kind == KIND_IMAGE:
            image = self.coordinator.data.image_by_id(msg.text)
            return image.name if image else None
        return None  # custom text: see the "Current display" sensor

    async def async_select_option(self, option: str) -> None:
        if option == OPTION_DEFAULT:
            await self.coordinator.async_reset(self.camera_id)
        elif option == OPTION_LEAVE_PACKAGE:
            await self.coordinator.async_set(self.camera_id, KIND_LEAVE_PACKAGE)
        elif option == OPTION_DO_NOT_DISTURB:
            await self.coordinator.async_set(self.camera_id, KIND_DO_NOT_DISTURB)
        else:
            image = self.coordinator.data.resolve_image(option)
            await self.coordinator.async_set(self.camera_id, KIND_IMAGE, image.id)

    # -- entity services -----------------------------------------------------

    async def async_set_image(self, image: str, duration=None, then: str | None = None) -> None:
        resolved = self.coordinator.data.resolve_image(image)
        await self.coordinator.async_set(
            self.camera_id,
            KIND_IMAGE,
            resolved.id,
            duration.total_seconds() if duration else None,
            then,
        )

    async def async_set_text(self, text: str, duration=None, then: str | None = None) -> None:
        await self.coordinator.async_set(
            self.camera_id, KIND_TEXT, text, duration.total_seconds() if duration else None, then
        )

    async def async_reset_display(self) -> None:
        await self.coordinator.async_reset(self.camera_id)
