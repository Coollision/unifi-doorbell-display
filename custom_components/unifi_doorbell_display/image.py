"""Image entity: a picture of what the screen shows.

The Protect API does not hand out the uploaded GIFs, so previews come from a
folder you point the integration at (files named like the uploaded images). When
there is no preview, or the screen shows the default/text, the default picture
(your own file, or a bundled placeholder) is shown, so the entity is never empty.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
import textwrap

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import DoorbellConfigEntry
from .const import CONF_DEFAULT_IMAGE, CONF_PREVIEW_FOLDER, OPTION_DEFAULT, PREVIEW_DIR_NAME
from .coordinator import DoorbellCoordinator
from .entity import DoorbellEntity
from .util import KIND_DEFAULT, KIND_DO_NOT_DISTURB, KIND_IMAGE, KIND_LEAVE_PACKAGE, KIND_TEXT, content_type, find_preview

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

    def _label(self) -> str:
        """Name of what is showing, for the generated card."""
        doorbell = self.doorbell
        if doorbell is None:
            return OPTION_DEFAULT
        msg = doorbell.message
        if msg.kind == KIND_IMAGE:
            image = self.coordinator.data.image_by_id(msg.text)
            return image.name if image else "Custom image"
        if msg.kind == KIND_TEXT:
            return msg.text or ""
        if msg.kind == KIND_LEAVE_PACKAGE:
            return "Leave package at door"
        if msg.kind == KIND_DO_NOT_DISTURB:
            return "Do not disturb"
        return OPTION_DEFAULT

    def _pick_file(self) -> Path | None:
        """Runs in the executor: the picture for the current display, or None to draw a card."""
        doorbell = self.doorbell
        configured = self._entry.options.get(CONF_PREVIEW_FOLDER)
        folder = configured or self.hass.config.path(PREVIEW_DIR_NAME)
        directory = Path(folder)
        if not (self._path_allowed(folder) and directory.is_dir()):
            directory = None
        names = [p.name for p in directory.iterdir()] if directory else []
        if doorbell and doorbell.message.kind == KIND_IMAGE and directory:
            image = self.coordinator.data.image_by_id(doorbell.message.text)
            if image and (match := find_preview(names, image.original)):
                return directory / match
        elif doorbell and doorbell.message.kind == KIND_DEFAULT:
            default = self._entry.options.get(CONF_DEFAULT_IMAGE)
            if default and self._path_allowed(default) and Path(default).is_file():
                return Path(default)
            if directory and (match := find_preview(names, "default")):
                return directory / match
        return None

    async def async_image(self) -> bytes | None:
        def _read() -> tuple[bytes, str]:
            path = self._pick_file()
            if path is not None:
                return path.read_bytes(), content_type(path.name)
            return _label_card(self._label()), "image/png"

        data, ctype = await self.hass.async_add_executor_job(_read)
        self._attr_content_type = ctype
        return data


def _label_card(label: str) -> bytes:
    """A 240x240 card with the name of what is showing (falls back to a static picture)."""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps  # Pillow ships with Home Assistant

        card = ImageOps.colorize(
            ImageOps.invert(Image.radial_gradient("L").resize((240, 240))),
            black="#05256f",
            white="#3cc3f2",
        )
        font = ImageFont.load_default(size=26)
        draw = ImageDraw.Draw(card)
        lines = textwrap.wrap(label, 14)[:5] or [""]
        line_h = 34
        y = 120 - len(lines) * line_h // 2
        for line in lines:
            draw.text((120, y), line, font=font, fill="white", anchor="mt")
            y += line_h
        out = io.BytesIO()
        card.save(out, format="PNG")
        return out.getvalue()
    except Exception:  # noqa: BLE001 - never let a cosmetic card break the entity
        _LOGGER.debug("Could not draw the label card", exc_info=True)
        return PLACEHOLDER.read_bytes()
