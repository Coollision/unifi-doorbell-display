"""Config flow: connect to the console, pick the doorbells, tune the options."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import ApiAuthError, ApiError, ProtectApi
from .const import (
    CONF_API_KEY,
    CONF_CAMERAS,
    CONF_DEFAULT_IMAGE,
    CONF_HOST,
    CONF_PREVIEW_FOLDER,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


class UnifiDoorbellDisplayFlow(ConfigFlow, domain=DOMAIN):
    """Set up the integration."""

    VERSION = 1

    def __init__(self) -> None:
        self._user: dict[str, Any] = {}
        self._cameras: list[dict] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip().removeprefix("https://").rstrip("/")
            api = ProtectApi(
                async_create_clientsession(self.hass, verify_ssl=user_input[CONF_VERIFY_SSL]),
                host,
                user_input[CONF_API_KEY],
            )
            try:
                await api.meta()
                self._cameras = await api.cameras()
            except ApiAuthError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                self._user = {**user_input, CONF_HOST: host}
                return await self.async_step_cameras()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_API_KEY): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                    vol.Required(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            api = ProtectApi(
                async_create_clientsession(self.hass, verify_ssl=reauth_entry.data[CONF_VERIFY_SSL]),
                reauth_entry.data[CONF_HOST],
                user_input[CONF_API_KEY],
            )
            try:
                await api.meta()
            except ApiAuthError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                }
            ),
            description_placeholders={"host": reauth_entry.data[CONF_HOST]},
            errors=errors,
        )

    async def async_step_cameras(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=self._user[CONF_HOST], data={**self._user, CONF_CAMERAS: user_input[CONF_CAMERAS]}
            )
        options = [
            selector.SelectOptionDict(value=c["id"], label=f"{c.get('name')} ({c.get('type')})")
            for c in self._cameras
        ]
        # Doorbells are the cameras with a screen; preselect them.
        default = [c["id"] for c in self._cameras if "doorbell" in str(c.get("type", "")).lower()]
        return self.async_show_form(
            step_id="cameras",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CAMERAS, default=default): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, multiple=True)
                    )
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> UnifiDoorbellDisplayOptions:
        return UnifiDoorbellDisplayOptions()


class UnifiDoorbellDisplayOptions(OptionsFlowWithReload):
    """Polling interval and the pictures used by the image entity."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        o = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=o.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                    ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
                    vol.Optional(
                        CONF_PREVIEW_FOLDER, description={"suggested_value": o.get(CONF_PREVIEW_FOLDER)}
                    ): str,
                    vol.Optional(
                        CONF_DEFAULT_IMAGE, description={"suggested_value": o.get(CONF_DEFAULT_IMAGE)}
                    ): str,
                }
            ),
        )
