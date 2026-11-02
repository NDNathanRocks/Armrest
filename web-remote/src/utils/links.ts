/** Links shared to the TV: from Android's share menu (manifest share_target) or pasted. */

const MAX_URL = 2000; // contracts.MAX_URL_LEN

/**
 * The web address in what was shared. Apps put it in different fields: YouTube sends it as
 * "text", a browser as "url", some apps as "Watch this! https://...". Null when there is none.
 */
export function findLink(...parts: (string | null | undefined)[]): string | null {
  for (const part of parts) {
    const match = part?.match(/https?:\/\/[^\s<>"']+/i);
    if (!match) continue;
    const url = match[0].replace(/[),.;!?]+$/, ""); // a sentence's own punctuation
    try {
      const parsed = new URL(url);
      if ((parsed.protocol === "https:" || parsed.protocol === "http:") && !parsed.username && url.length <= MAX_URL) {
        return parsed.href;
      }
    } catch {
      /* not a real address: keep looking */
    }
  }
  return null;
}

/** The link handed over by Android's share menu (/share?title=&text=&url=), else null. */
export function readSharedLink(loc: Pick<Location, "pathname" | "search">): string | null {
  if (loc.pathname !== "/share") return null;
  const q = new URLSearchParams(loc.search);
  return findLink(q.get("url"), q.get("text"), q.get("title"));
}

/** Back to the app's own address once the shared link is taken (a reload must not resend it). */
export function clearSharedLink(win: Pick<Window, "location" | "history"> = window): void {
  if (win.location.pathname === "/share") win.history.replaceState(null, "", "/");
}

export function linkHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
