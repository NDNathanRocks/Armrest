"""The product name people see. Change it here (and in web-remote/src/brand.ts).

The app was called CouchJarvis until 0.5.0. What still carries that name does so to keep existing
installs working: the installer AppId (never changes), the data move (app_dirs), the ``CJ_``
settings still read (config.py), the device-token issuer (lan_auth.py) and the relay stack.
"""

from __future__ import annotations

APP_NAME = "Armrest"
TAGLINE = "Your PC, within arm's reach"
# Where "Buy" goes. The Store build opens the Store page instead, once STORE_PRODUCT_ID is set
# (Partner Center > the app > Product identity > Store ID, e.g. 9NBLGGH4R315).
SITE_URL = "https://armrest-app.pages.dev"  # the phone app's site also serves these pages
BUY_URL = f"{SITE_URL}/get.html"
PRIVACY_URL = f"{SITE_URL}/privacy.html"
TERMS_URL = f"{SITE_URL}/terms.html"
SUPPORT_URL = f"{SITE_URL}/support.html"
GEMINI_KEY_URL = "https://aistudio.google.com/apikey"
STORE_PRODUCT_ID = ""

# Addresses the phone app used to live at (Vercel, retired 2026-10-26). A config.env written by an
# older installer still names one: the QR uses the current site instead, without rewriting the file.
RETIRED_PWA_URLS = frozenset(
    {"https://couch-jarvis-remote.vercel.app", "https://couch-jarvis.vercel.app"}
)


def qr_base_url(configured: str) -> str:
    """The address to put in the pairing QR for a configured CJ_PWA_BASE_URL."""
    return SITE_URL if configured.rstrip("/") in RETIRED_PWA_URLS else configured
