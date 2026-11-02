/**
 * Where this page runs. An iPhone home-screen app keeps its own storage, apart from Safari, so a
 * pairing made in Safari never reaches it: the app must pair itself (scan or code) once.
 */
interface NavigatorLike {
  userAgent: string;
  maxTouchPoints?: number;
  standalone?: boolean;
}

export function isIos(nav: NavigatorLike = navigator): boolean {
  // iPadOS reports a Mac; a Mac has no touch screen
  return /iPhone|iPad|iPod/.test(nav.userAgent) || (/Macintosh/.test(nav.userAgent) && (nav.maxTouchPoints ?? 0) > 1);
}

/** Opened from the home screen (any phone), not in a browser tab. */
export function isStandalone(nav: NavigatorLike = navigator, win: Pick<Window, "matchMedia"> | null = typeof window === "undefined" ? null : window): boolean {
  if (nav.standalone === true) return true;
  try {
    return win?.matchMedia("(display-mode: standalone)").matches === true;
  } catch {
    return false;
  }
}

/** A browser tab on an iPhone: the place to explain Add to Home Screen. */
export function wantsHomeScreenGuide(nav: NavigatorLike = navigator): boolean {
  return isIos(nav) && !isStandalone(nav);
}

const GUIDE_KEY = "cj.homeGuide.dismissed";

export function guideDismissed(): boolean {
  try {
    return localStorage.getItem(GUIDE_KEY) === "1";
  } catch {
    return false;
  }
}

export function dismissGuide(): void {
  try {
    localStorage.setItem(GUIDE_KEY, "1");
  } catch {
    /* private mode: it shows again next visit */
  }
}
