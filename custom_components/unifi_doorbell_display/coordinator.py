"""Polling coordinator and the "then show X afterwards" scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ApiAuthError, ApiError, ProtectApi
from .const import (
    CONF_CAMERAS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    RESET_DELAY_SECONDS,
    RESET_TEXT,
    STORAGE_VERSION,
)
from .util import (
    KIND_IMAGE,
    KIND_TEXT,
    Message,
    build_message,
    friendly_name,
    is_sprite,
    parse_message,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class UploadedImage:
    id: str
    name: str
    original: str
    size: int | None
    created: str | None


@dataclass
class Doorbell:
    camera_id: str
    name: str
    model: str | None
    mac: str | None
    message: Message


@dataclass
class CoordinatorData:
    doorbells: dict[str, Doorbell] = field(default_factory=dict)
    images: list[UploadedImage] = field(default_factory=list)

    def image_by_id(self, image_id: str | None) -> UploadedImage | None:
        return next((i for i in self.images if i.id == image_id), None)

    def resolve_image(self, ref: str) -> UploadedImage:
        """Find an uploaded image by id or by (case-insensitive) friendly name."""
        low = ref.strip().lower()
        for image in self.images:
            if image.id.lower() == low or image.name.lower() == low:
                return image
        raise HomeAssistantError(
            f"Unknown image '{ref}'. Available: {', '.join(i.name for i in self.images) or 'none'}"
        )


class DoorbellCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Reads doorbells + uploaded images and applies display changes."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: ProtectApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.api = api
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.pending")
        self._pending: dict[str, dict] = {}
        self._timers: dict[str, CALLBACK_TYPE] = {}

    async def _async_update_data(self) -> CoordinatorData:
        wanted = set(self.config_entry.data[CONF_CAMERAS])
        try:
            cameras = await self.api.cameras()
            files = await self.api.files()
        except ApiAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise UpdateFailed(f"API key rejected: {err}") from err
        except ApiError as err:
            raise UpdateFailed(str(err)) from err

        images: list[UploadedImage] = []
        seen: dict[str, int] = {}
        for file in sorted((f for f in files if is_sprite(f)), key=lambda f: f.get("createdAt", "")):
            name = friendly_name(file.get("originalName"), str(file["id"])[:8])
            seen[name] = seen.get(name, 0) + 1
            if seen[name] > 1:
                name = f"{name} ({seen[name]})"
            images.append(
                UploadedImage(
                    id=str(file["id"]),
                    name=name,
                    original=str(file.get("originalName") or ""),
                    size=file.get("size"),
                    created=file.get("createdAt"),
                )
            )

        doorbells = {
            cam["id"]: Doorbell(
                camera_id=cam["id"],
                name=cam.get("name") or cam["id"],
                model=cam.get("type"),
                mac=cam.get("mac"),
                message=parse_message(cam.get("lcdMessage")),
            )
            for cam in cameras
            if cam["id"] in wanted
        }
        return CoordinatorData(doorbells=doorbells, images=images)

    # -- setting the display -------------------------------------------------

    async def async_set(
        self,
        camera_id: str,
        kind: str,
        text: str | None = None,
        duration_s: float | None = None,
        then_image: str | None = None,
    ) -> None:
        """Set the screen; optionally for `duration_s`, then show `then_image`."""
        then = None
        if then_image:
            if not duration_s:
                raise HomeAssistantError("'then' only makes sense together with a duration")
            then = self.data.resolve_image(then_image)
        now_ms = int(time.time() * 1000)
        message = build_message(kind, text, duration_s, now_ms)
        try:
            await self.api.set_message(camera_id, message)
        except ApiError as err:
            raise HomeAssistantError(f"Could not set the display: {err}") from err

        self._cancel(camera_id)
        if then is not None and message["resetAt"]:
            self._pending[camera_id] = {"at_ms": message["resetAt"], "image_id": then.id}
            await self._store.async_save(self._pending)
            self._schedule(camera_id)
        elif camera_id in self._pending:
            self._pending.pop(camera_id)
            await self._store.async_save(self._pending)
        await self.async_request_refresh()

    async def async_reset(self, camera_id: str) -> None:
        """Back to Protect's default: a message that expires immediately."""
        message = build_message(
            KIND_TEXT, RESET_TEXT, RESET_DELAY_SECONDS, int(time.time() * 1000)
        )
        try:
            await self.api.set_message(camera_id, message)
        except ApiError as err:
            raise HomeAssistantError(f"Could not reset the display: {err}") from err
        self._cancel(camera_id)
        if self._pending.pop(camera_id, None) is not None:
            await self._store.async_save(self._pending)
        await self.async_request_refresh()

    # -- "then" scheduler ----------------------------------------------------

    async def async_load_pending(self) -> None:
        self._pending = await self._store.async_load() or {}
        for camera_id in list(self._pending):
            self._schedule(camera_id)

    @callback
    def async_shutdown_timers(self) -> None:
        for camera_id in list(self._timers):
            self._cancel(camera_id)

    def _cancel(self, camera_id: str) -> None:
        if (unsub := self._timers.pop(camera_id, None)) is not None:
            unsub()

    def _schedule(self, camera_id: str) -> None:
        at = datetime.fromtimestamp(self._pending[camera_id]["at_ms"] / 1000 + 2, tz=dt_util.UTC)
        async def _due(_now: datetime, cid: str = camera_id) -> None:
            await self._fire(cid)

        self._timers[camera_id] = async_track_point_in_utc_time(self.hass, _due, at)

    async def _fire(self, camera_id: str) -> None:
        self._timers.pop(camera_id, None)
        pending = self._pending.pop(camera_id, None)
        await self._store.async_save(self._pending)
        if pending is None:
            return
        await self.async_refresh()
        doorbell = self.data.doorbells.get(camera_id) if self.data else None
        if doorbell is None:
            return
        # Only take over if Protect already fell back to the default; if someone
        # set something else in the meantime, leave it alone.
        if not doorbell.message.is_default:
            _LOGGER.debug("Display of %s changed meanwhile, not applying 'then'", camera_id)
            return
        image = self.data.image_by_id(pending["image_id"])
        if image is None:
            _LOGGER.warning("Image %s for 'then' no longer exists", pending["image_id"])
            return
        try:
            await self.api.set_message(camera_id, build_message(KIND_IMAGE, image.id))
        except ApiError as err:
            _LOGGER.warning("Could not apply 'then' image: %s", err)
            return
        await self.async_request_refresh()
