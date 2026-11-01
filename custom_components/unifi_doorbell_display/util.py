"""Pure helpers (no Home Assistant imports, unit-testable on their own)."""

from __future__ import annotations

from dataclasses import dataclass
import re

KIND_DEFAULT = "default"
KIND_LEAVE_PACKAGE = "leave_package"
KIND_DO_NOT_DISTURB = "do_not_disturb"
KIND_TEXT = "custom_text"
KIND_IMAGE = "image"

_API_TYPE = {
    KIND_LEAVE_PACKAGE: "LEAVE_PACKAGE_AT_DOOR",
    KIND_DO_NOT_DISTURB: "DO_NOT_DISTURB",
    KIND_TEXT: "CUSTOM_MESSAGE",
    KIND_IMAGE: "IMAGE",
}
_KIND_BY_API_TYPE = {v: k for k, v in _API_TYPE.items()}
_BUILTIN_TEXT = {
    KIND_LEAVE_PACKAGE: "LEAVE PACKAGE AT DOOR",
    KIND_DO_NOT_DISTURB: "DO NOT DISTURB",
}
_EXTENSIONS = (".png", ".gif", ".webp", ".avif", ".jpg", ".jpeg")


@dataclass(frozen=True)
class Message:
    """What a doorbell screen is currently set to."""

    kind: str = KIND_DEFAULT
    text: str | None = None  # custom text, or the image id for KIND_IMAGE
    reset_at_ms: int | None = None

    @property
    def is_default(self) -> bool:
        return self.kind == KIND_DEFAULT


def parse_message(lcd: dict | None) -> Message:
    """Turn the `lcdMessage` of a camera into a Message (absent = default)."""
    if not lcd:
        return Message()
    kind = _KIND_BY_API_TYPE.get(lcd.get("type"))
    if kind is None:
        return Message()
    reset_at = lcd.get("resetAt")
    return Message(
        kind=kind,
        text=lcd.get("text"),
        reset_at_ms=int(reset_at) if reset_at else None,
    )


def build_message(
    kind: str, text: str | None = None, duration_s: float | None = None, now_ms: int = 0
) -> dict:
    """Build the `lcdMessage` payload for the Protect API."""
    if kind not in _API_TYPE:
        raise ValueError(f"cannot send message kind {kind!r}")
    reset_at = int(now_ms + duration_s * 1000) if duration_s else None
    return {
        "type": _API_TYPE[kind],
        "text": _BUILTIN_TEXT.get(kind, text or ""),
        "resetAt": reset_at,
    }


def friendly_name(original: str | None, fallback: str) -> str:
    """`cat_halloween_small.gif.png` -> `cat halloween small`."""
    name = (original or "").strip() or fallback
    changed = True
    while changed:
        changed = False
        for ext in _EXTENSIONS:
            if name.lower().endswith(ext):
                name = name[: -len(ext)]
                changed = True
    name = re.sub(r"[_\-\s]+", " ", name).strip()
    return name or fallback


def is_sprite(file: dict) -> bool:
    """Uploaded images come as `<id>.png` (sprite) + `<id>.png.gif` (preview)."""
    file_id = str(file.get("id", ""))
    return file_id.lower().endswith(".png")


def find_preview(filenames: list[str], original: str | None) -> str | None:
    """Pick the local preview file for an uploaded image.

    Matches the uploaded file's name with and without its extensions, so
    `cat_halloween_small.gif.png` finds `cat_halloween_small.gif`.
    """
    if not original:
        return None
    base = original
    if base.lower().endswith(".png"):
        base = base[:-4]
    stem = base
    for ext in _EXTENSIONS:
        if stem.lower().endswith(ext):
            stem = stem[: -len(ext)]
    by_lower = {f.lower(): f for f in filenames}
    if base.lower() in by_lower:
        return by_lower[base.lower()]
    for f in filenames:
        for ext in _EXTENSIONS:
            if f.lower() == (stem + ext).lower():
                return f
    return None


def content_type(path: str) -> str:
    low = path.lower()
    for ext, ctype in (
        (".gif", "image/gif"),
        (".png", "image/png"),
        (".webp", "image/webp"),
        (".avif", "image/avif"),
        (".jpg", "image/jpeg"),
        (".jpeg", "image/jpeg"),
    ):
        if low.endswith(ext):
            return ctype
    return "application/octet-stream"
