// The product name people see; keep in step with pc-daemon/brand.py. Storage keys ("cj.*") and the
// IndexedDB name keep the pre-0.5.0 "couch-jarvis" names on purpose: nobody sees them, and one deploy
// reaches every phone at once, so a migration bug would un-pair them all.
export const APP_NAME = "Armrest";
export const TAGLINE = "Your PC, within arm's reach";

// The website (the same Cloudflare Pages project as this app): legal pages and where to get it.
export const SITE_URL = "https://armrest-app.pages.dev";
export const GET_URL = "/get.html";
export const PRIVACY_URL = "/privacy.html";
export const TERMS_URL = "/terms.html";
export const LICENCES_URL = "/licenses.html";
export const SUPPORT_URL = "/support.html";
