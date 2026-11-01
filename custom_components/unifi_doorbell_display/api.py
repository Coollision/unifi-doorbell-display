"""Client for the local UniFi Protect integration API."""

from __future__ import annotations

from typing import Any

import aiohttp


class ApiError(Exception):
    """Talking to the console failed."""


class ApiAuthError(ApiError):
    """The API key was rejected."""


class ProtectApi:
    """Minimal client: cameras, uploaded animation files and the display message."""

    def __init__(self, session: aiohttp.ClientSession, host: str, api_key: str) -> None:
        self._session = session
        self._base = f"https://{host}/proxy/protect/integration/v1"
        self._headers = {"X-API-KEY": api_key}

    async def _request(self, method: str, path: str, json: Any = None) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self._base}/{path}",
                headers=self._headers,
                json=json,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status in (401, 403):
                    raise ApiAuthError(f"{method} {path}: HTTP {resp.status}")
                if resp.status >= 400:
                    body = (await resp.text())[:200]
                    raise ApiError(f"{method} {path}: HTTP {resp.status} {body}")
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise ApiError(f"{method} {path}: {err}") from err
        except TimeoutError as err:
            raise ApiError(f"{method} {path}: timeout") from err

    async def meta(self) -> dict:
        return await self._request("GET", "meta/info")

    async def cameras(self) -> list[dict]:
        return await self._request("GET", "cameras")

    async def files(self) -> list[dict]:
        return await self._request("GET", "files/animations")

    async def set_message(self, camera_id: str, message: dict) -> dict:
        return await self._request("PATCH", f"cameras/{camera_id}", {"lcdMessage": message})
