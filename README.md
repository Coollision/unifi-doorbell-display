# UniFi Doorbell Display

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Validate](https://github.com/Coollision/unifi-doorbell-display/actions/workflows/validate.yml/badge.svg)](https://github.com/Coollision/unifi-doorbell-display/actions/workflows/validate.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

See and control **the screen of your UniFi Protect doorbell** (G4 Doorbell Pro and friends) from Home Assistant: which message or custom image is showing right now, when it resets, which images you have uploaded, and services to switch between them, optionally for a limited time and with a follow-up image instead of the default animation.

> **Unofficial.** Not affiliated with or endorsed by Ubiquiti, Home Assistant, Nabu Casa or the Open Home Foundation. See [NOTICE](NOTICE).

**It extends the built-in UniFi Protect integration, it does not replace it.** Streams, ring events, motion and everything else stay with the native integration; this one only adds the display. It does not upload images: add those in the Protect app or web UI as usual.

> **Device note.** Since Home Assistant 2026.10 a device belongs to a single integration, so these entities live on their own device ("<doorbell name> display") next to the native UniFi Protect device, not on it. The `Current display` and `Display message` entities are what you use in automations and dashboards.

## Features

- **Select** (*Display message*): shows the current display and lets you pick the default message, *Leave package at door*, *Do not disturb* or any uploaded image by name.
- **Sensors**: *Current display* (e.g. `Image: cat halloween small`, with type, image id and reset time as attributes), *Display resets at* (timestamp) and *Available images* (count, with the name, id, file and size of every uploaded image in the `images` attribute).
- **Binary sensor** *Showing default*: on while nothing is set and Protect shows its default animation. Handy to trigger an automation that puts your own image back when a timed message expires.
- **Image** *Current display image*: a picture of what is showing, never empty (see [Previews](#previews)).
- **Services** `set_image`, `set_text`, `reset_display` with an optional **duration** and a **then** image: Protect clears a timed message by itself and falls back to its default animation; with `then` the integration shows your image instead.

## Requirements

| | |
|---|---|
| Home Assistant | 2026.10 or newer |
| UniFi Protect | Version with the local integration API (7.x); a doorbell with a screen |
| API key | Created in UniFi OS: **Control Plane → Integrations**. A Protect-only key is enough |
| Network | HA must reach the console's address on your LAN (HTTPS, self-signed certificate is fine) |

## Installation

1. [![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Coollision&repository=unifi-doorbell-display&category=integration)
   adds this repository to HACS as an **Integration** and opens it. Click **Download**, then restart Home Assistant.
   (Manually: HACS → ⋮ → **Custom repositories** → `https://github.com/Coollision/unifi-doorbell-display`, type **Integration**.)
2. [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=unifi_doorbell_display)
   starts the setup. Enter the console address and the API key, and pick your doorbells.

## Services

```yaml
action: unifi_doorbell_display.set_image
target:
  entity_id: select.front_door_display_message
data:
  image: cat halloween small        # name or id, see the "Available images" sensor
  duration: "01:00:00"              # optional: show it for an hour...
  then: cat hello small             # ...optional: then this image instead of the default animation
```

`set_text` takes `text` (max 30 characters) with the same `duration` / `then`. `reset_display` goes back to the default message right away. Pending `then` images survive a Home Assistant restart. If someone changes the screen before a timer ends, the `then` image is not applied.

## Previews

The Protect API does not hand out the uploaded GIFs, so the image entity uses pictures you provide: under **Configure** set a **Preview folder** with one file per uploaded image, named like the upload (an upload called `cat_halloween_small.gif` is matched by `cat_halloween_small.gif`), and optionally a **Default picture** for when nothing matches or the screen shows the default or a text. Without these, a built-in placeholder is shown. Anything inside your config folder works; paths elsewhere must be listed in `allowlist_external_dirs`. Animated GIFs (and AVIF) are served as they are.

## Notes

- The API cannot delete a message. `reset_display` therefore sends a message that expires after two seconds; Protect then shows its default animation.
- Updates are polled (default every 30 s, configurable).
- Uploading images and everything outside the screen are deliberately out of scope.
