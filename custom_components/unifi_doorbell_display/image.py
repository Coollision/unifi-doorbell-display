"""Image entity: a picture of what the screen shows.

The Protect API does not hand out the uploaded GIFs, so previews come from a
folder you point the integration at (files named like the uploaded images). When
there is no preview, or the screen shows the default/text, the default picture
(your own file, or a bundled placeholder) is shown, so the entity is never empty.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import DoorbellConfigEntry
from .const import CONF_DEFAULT_IMAGE, CONF_PREVIEW_FOLDER
from .coordinator import DoorbellCoordinator
from .entity import DoorbellEntity
from .util import KIND_IMAGE, content_type, find_preview

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0
PLACEHOLDER = Path(__file__).parent / "placeholder.png"


async def async_setup_entry(
    hass: HomeAssistant, entry: DoorbellConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        CurrentDisplayImage(hass, entry, coordinator, cam) for cam in coordinator.data.doorbells
    )


class CurrentDisplayImage(DoorbellEntity, ImageEntity):
    """Preview of the current display, falling back to the default picture."""

    _attr_translation_key = "current_display_image"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: DoorbellConfigEntry,
        coordinator: DoorbellCoordinator,
        camera_id: str,
    ) -> None:
        DoorbellEntity.__init__(self, coordinator, camera_id, "current_display_image")
        ImageEntity.__init__(self, hass)
        self._entry = entry
        self._shown: tuple | None = None
        self._attr_image_last_updated = dt_util.utcnow()

    def _handle_coordinator_update(self) -> None:
        shown = self._signature()
        if shown != self._shown:
            self._shown = shown
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    def _signature(self) -> tuple | None:
        doorbell = self.doorbell
        if doorbell is None:
            return None
        return (doorbell.message.kind, doorbell.message.text)

    def _path_allowed(self, path: str) -> bool:
        """The config folder is always fine; anything else must be in allowlist_external_dirs."""
        resolved = Path(path).resolve()
        if resolved.is_relative_to(Path(self.hass.config.config_dir).resolve()):
            return True
        if self.hass.config.is_allowed_path(path):
            return True
        _LOGGER.warning("Path %s is not allowed; add it to allowlist_external_dirs", path)
        return False

    def _pick_file(self) -> Path:
        """Runs in the executor: the preview for the current image, else the default."""
        doorbell = self.doorbell
        folder = self._entry.options.get(CONF_PREVIEW_FOLDER)
        if doorbell and doorbell.message.kind == KIND_IMAGE and folder and self._path_allowed(folder):
            image = self.coordinator.data.image_by_id(doorbell.message.text)
            directory = Path(folder)
            if image and directory.is_dir():
                match = find_preview([p.name for p in directory.iterdir()], image.original)
                if match:
                    return directory / match
        default = self._entry.options.get(CONF_DEFAULT_IMAGE)
        if default and self._path_allowed(default) and Path(default).is_file():
            return Path(default)
        return PLACEHOLDER

    async def async_image(self) -> bytes | None:
        def _read() -> tuple[bytes, str]:
            path = self._pick_file()
            return path.read_bytes(), content_type(path.name)

        data, ctype = await self.hass.async_add_executor_job(_read)
        self._attr_content_type = ctype
        return data
