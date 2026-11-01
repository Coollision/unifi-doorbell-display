"""Constants for UniFi Doorbell Display."""

DOMAIN = "unifi_doorbell_display"

CONF_HOST = "host"
CONF_API_KEY = "api_key"
CONF_VERIFY_SSL = "verify_ssl"
CONF_CAMERAS = "cameras"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_PREVIEW_FOLDER = "preview_folder"
CONF_DEFAULT_IMAGE = "default_image"

DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 600

# Protect clears a message by itself once `resetAt` has passed; there is no way
# to delete it through the API, so a reset is a message that expires right away.
RESET_DELAY_SECONDS = 2
RESET_TEXT = "WELCOME"

OPTION_DEFAULT = "Default message"
OPTION_LEAVE_PACKAGE = "Leave package at door"
OPTION_DO_NOT_DISTURB = "Do not disturb"

STORAGE_VERSION = 1

# Folder (inside the config folder) that is created on setup and searched for preview pictures
# when no other folder is configured.
PREVIEW_DIR_NAME = "unifi_doorbell_display"
PREVIEW_README = """UniFi Doorbell Display - preview pictures

The UniFi Protect API shows which image is on the doorbell screen but does not hand out the
uploaded GIFs themselves, so the "Current display image" entity looks here for pictures:

  * one file per image you uploaded to Protect, named like the upload,
    for example cat_halloween_small.gif  (any of gif, png, webp, avif, jpg)
  * default.<ext>  - shown for Protect's default message (for example default.avif)

Anything that has no file here is drawn as a card with the name of what is showing.
You can use another folder under Settings > Devices & services > UniFi Doorbell Display > Configure.
"""
