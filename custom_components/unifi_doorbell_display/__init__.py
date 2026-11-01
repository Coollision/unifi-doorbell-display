"""UniFi Doorbell Display: see and control the doorbell screen of UniFi Protect."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import ProtectApi
from .const import CONF_API_KEY, CONF_HOST, CONF_VERIFY_SSL
from .coordinator import DoorbellCoordinator

PLATFORMS = [Platform.SELECT, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.IMAGE]

type DoorbellConfigEntry = ConfigEntry[DoorbellCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DoorbellConfigEntry) -> bool:
    session = async_create_clientsession(hass, verify_ssl=entry.data[CONF_VERIFY_SSL])
    api = ProtectApi(session, entry.data[CONF_HOST], entry.data[CONF_API_KEY])
    coordinator = DoorbellCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_load_pending()
    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_shutdown_timers)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DoorbellConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

