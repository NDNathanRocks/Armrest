import type { Modifier, QuickAction } from "../protocol";
import type { IconName } from "../components/Icon";
import { EXTRAS_SINCE, versionAtLeast } from "./version";

export type FavGroup = "Custom" | "Playback" | "Volume" | "Display" | "Browser" | "Keys" | "Say";

/** What pressing a favourite does: a PC button, a keyboard key, or a spoken-style command. */
export type FavSend =
  | { kind: "action"; action: QuickAction }
  | { kind: "key"; key: string; mods: Modifier[] }
  | { kind: "text"; text: string };

export interface Fav {
  id: string;
  label: string;
  group: FavGroup;
  /** Drawn above the label; keys without an icon show their own name large instead. */
  icon?: IconName;
  send: FavSend;
  /** First PC app version that understands it (older PCs show it disabled). */
  since?: string;
}

const action = (id: string, label: string, group: FavGroup, icon: IconName, a: QuickAction, since?: string): Fav => ({
  id,
  label,
  group,
  icon,
  send: { kind: "action", action: a },
  since,
});
const say = (id: string, label: string, icon: IconName, text: string, since?: string): Fav => ({
  id,
  label,
  group: "Say",
  icon,
  send: { kind: "text", text },
  since,
});
const key = (id: string, label: string, k: string, icon?: IconName): Fav => ({
  id,
  label,
  group: "Keys",
  icon,
  send: { kind: "key", key: k, mods: [] },
});

/** Every button a favourite slot can hold. Ids are stored on the phone: never rename one. */
export const LIBRARY: readonly Fav[] = [
  action("play_pause", "Play / Pause", "Playback", "play", "play_pause"),
  action("prev", "Previous", "Playback", "prev", "prev"),
  action("next", "Next", "Playback", "next", "next"),
  action("seek_back_10", "Back 10s", "Playback", "back10", "seek_back_10"),
  action("seek_fwd_10", "Forward 10s", "Playback", "fwd10", "seek_fwd_10"),
  action("panic", "Stop", "Playback", "stop", "panic"),
  action("vol_down", "Volume down", "Volume", "speakerLow", "vol_down"),
  action("vol_up", "Volume up", "Volume", "speakerHigh", "vol_up"),
  action("mute", "Mute", "Volume", "speakerMute", "mute"),
  action("fullscreen", "Fullscreen", "Display", "fullscreen", "fullscreen"),
  action("exit_fullscreen", "Exit fullscreen", "Display", "exitFullscreen", "exit_fullscreen", EXTRAS_SINCE),
  action("subtitles", "Subtitles", "Display", "cc", "subtitles"),
  action("skip_ad", "Skip ad", "Display", "skipAd", "skip_ad"),
  action("sleep_display", "Screen off", "Display", "moon", "sleep_display"),
  action("show_qr", "Pair (QR)", "Display", "plus", "show_qr"),
  action("back", "Back page", "Browser", "back", "back"),
  action("forward", "Forward page", "Browser", "forward", "forward"),
  action("reload", "Reload", "Browser", "reload", "reload"),
  action("new_tab", "New tab", "Browser", "plus", "new_tab"),
  action("duplicate_tab", "Duplicate tab", "Browser", "copy", "duplicate_tab", EXTRAS_SINCE),
  action("close_tab", "Close tab", "Browser", "close", "close_tab"),
  action("prev_tab", "Tab left", "Browser", "tabLeft", "prev_tab"),
  action("next_tab", "Tab right", "Browser", "tabRight", "next_tab"),
  action("scroll_up", "Scroll up", "Browser", "up", "scroll_up"),
  action("scroll_down", "Scroll down", "Browser", "down", "scroll_down"),
  key("key_f11", "Full screen (F11)", "f11", "fullscreen"),
  key("key_esc", "Escape", "esc"),
  key("key_space", "Space", "space"),
  key("key_enter", "Enter", "enter"),
  ...Array.from({ length: 12 }, (_, i) => key(`key_f${i + 1}`, `F${i + 1}`, `f${i + 1}`)).filter((f) => f.id !== "key_f11"),
  say("say_subs_on", "Subtitles on", "cc", "subtitles on"),
  say("say_subs_off", "Subtitles off", "cc", "subtitles off"),
  say("say_fullscreen", "Go fullscreen", "fullscreen", "fullscreen"),
  say("say_speed_up", "Faster", "speed", "speed up", EXTRAS_SINCE),
  say("say_speed_down", "Slower", "speed", "slow down", EXTRAS_SINCE),
  say("say_speed_125", "Speed 1.25×", "speed", "play at 1.25x", EXTRAS_SINCE),
  say("say_speed_normal", "Normal speed", "speed", "normal speed", EXTRAS_SINCE),
];

export const FAV_GROUPS: readonly FavGroup[] = ["Custom", "Playback", "Volume", "Display", "Browser", "Keys", "Say"];

/** False when the PC app is too old to understand this favourite (it is then hidden or greyed). */
export const favSupported = (fav: Fav, daemonVersion: string): boolean => !fav.since || versionAtLeast(daemonVersion, fav.since);
export const SLOTS = 8;
export const DEFAULT_FAVORITES: readonly (string | null)[] = [
  "fullscreen",
  "subtitles",
  "mute",
  "skip_ad",
  "back",
  "new_tab",
  "panic",
  "sleep_display",
];

const byId = new Map(LIBRARY.map((f) => [f.id, f]));
/** A library button, or one of the user's own shortcuts. */
export const findFav = (id: string | null, custom: readonly CustomButton[] = []): Fav | null => {
  if (!id) return null;
  const mine = custom.find((c) => c.id === id);
  return mine ? customFav(mine) : (byId.get(id) ?? null);
};

// ---- the user's own buttons: keyboard shortcuts ("Ctrl+Shift+T", "Alt+Left", "F5") and saved
// commands ("open my bookmark netflix"), sent as if typed in the command bar

export interface CustomKey {
  id: string;
  label: string;
  key: string;
  mods: Modifier[];
  /** Absent on buttons saved before 0.6.0 (they are all shortcuts). */
  kind?: "key";
}

export interface CustomSay {
  id: string;
  label: string;
  kind: "say";
  text: string;
}

export type CustomButton = CustomKey | CustomSay;
const MAX_SAY = 200;

const CUSTOM_KEY = "cj.favorites.custom.v1";
export const MAX_CUSTOM = 24;
const MODS: readonly Modifier[] = ["ctrl", "alt", "shift"];
export const MOD_LABEL: Record<Modifier, string> = { ctrl: "Ctrl", alt: "Alt", shift: "Shift" };

/** Named keys a shortcut can use, as the PC names them, with what the phone shows. */
export const NAMED_KEYS: readonly (readonly [string, string])[] = [
  ["enter", "Enter"],
  ["esc", "Esc"],
  ["space", "Space"],
  ["tab", "Tab"],
  ["backspace", "Backspace"],
  ["delete", "Delete"],
  ["left", "←"],
  ["right", "→"],
  ["up", "↑"],
  ["down", "↓"],
  ["home", "Home"],
  ["end", "End"],
  ["pageup", "Page Up"],
  ["pagedown", "Page Down"],
  ...Array.from({ length: 12 }, (_, i) => [`f${i + 1}`, `F${i + 1}`] as const),
  ["-", "-"],
  ["=", "="],
];
const NAMED = new Map(NAMED_KEYS);

/** A key the PC accepts from a phone (contracts REMOTE_KEY_PATTERN). */
export const validKey = (key: string): boolean => /^[a-z0-9]$/.test(key) || NAMED.has(key);

/** "Ctrl+Shift+T". */
export function comboLabel(key: string, mods: readonly Modifier[]): string {
  const name = NAMED.get(key) ?? key.toUpperCase();
  return [...MODS.filter((m) => mods.includes(m)).map((m) => MOD_LABEL[m]), name].join("+");
}

/** Why the PC would refuse this shortcut (pc-daemon/remote_input.py), or null when it is fine. */
export function blockedReason(key: string, mods: readonly Modifier[]): string | null {
  const has = (m: Modifier) => mods.includes(m);
  const only = (...want: Modifier[]) => mods.length === want.length && want.every(has);
  if (has("ctrl") && has("alt")) return "Ctrl+Alt shortcuts are blocked for safety.";
  if (key === "f4" && only("alt")) return "Alt+F4 would close the TV browser, so it is blocked.";
  if (key === "esc" && (only("ctrl") || only("alt") || only("ctrl", "shift"))) return "That shortcut is blocked for safety.";
  if ((key === "delete" || key === "backspace") && only("ctrl", "shift")) return "That shortcut is blocked for safety.";
  return null;
}

const customFav = (c: CustomButton): Fav =>
  c.kind === "say"
    ? { id: c.id, label: c.label || c.text, group: "Custom", icon: "chat", send: { kind: "text", text: c.text } }
    : {
        id: c.id,
        label: c.label || comboLabel(c.key, c.mods),
        group: "Custom",
        icon: "keyboard",
        send: { kind: "key", key: c.key, mods: [...c.mods] },
      };

const isCustom = (v: unknown): v is CustomButton => {
  if (typeof v !== "object" || v === null) return false;
  const c = v as Record<string, unknown>;
  const named = typeof c.id === "string" && c.id.startsWith("custom_") && typeof c.label === "string" && c.label.length <= 40;
  if (!named) return false;
  if (c.kind === "say") return typeof c.text === "string" && c.text.trim() !== "" && c.text.length <= MAX_SAY;
  return (
    (c.kind === undefined || c.kind === "key") &&
    typeof c.key === "string" &&
    validKey(c.key) &&
    Array.isArray(c.mods) &&
    c.mods.every((m) => MODS.includes(m as Modifier))
  );
};

export function loadCustomKeys(): CustomButton[] {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(CUSTOM_KEY) ?? "[]");
    if (Array.isArray(raw)) return raw.filter(isCustom).slice(0, MAX_CUSTOM);
  } catch {
    /* blocked or corrupt storage */
  }
  return [];
}

export function saveCustomKeys(list: readonly CustomButton[]): void {
  try {
    localStorage.setItem(CUSTOM_KEY, JSON.stringify(list.slice(0, MAX_CUSTOM)));
  } catch {
    /* private mode: the shortcuts last until the page closes */
  }
}

const newId = () => `custom_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;

/** A new shortcut button; an empty label shows the shortcut itself. */
export function makeCustomKey(label: string, key: string, mods: readonly Modifier[]): CustomKey {
  return { id: newId(), label: label.trim().slice(0, 40), key, mods: MODS.filter((m) => mods.includes(m)) };
}

/** A new saved-command button: tapping it sends ``text`` like the command bar. */
export function makeCustomSay(label: string, text: string): CustomSay {
  return { id: newId(), label: label.trim().slice(0, 40), kind: "say", text: text.trim().slice(0, MAX_SAY) };
}

/** Where each grid keeps its slots on the phone: Favourites (Remote tab) and the Keys tab. */
export type Grid = "remote" | "keys";
const STORAGE_KEYS: Record<Grid, string> = { remote: "cj.favorites.v1", keys: "cj.favorites.keys.v1" };
export const DEFAULT_KEY_FAVORITES: readonly (string | null)[] = [
  "key_esc",
  "key_space",
  "key_enter",
  "key_f11",
  "back",
  "forward",
  "reload",
  "close_tab",
];
const DEFAULTS: Record<Grid, readonly (string | null)[]> = { remote: DEFAULT_FAVORITES, keys: DEFAULT_KEY_FAVORITES };

/** The saved slots, always exactly SLOTS long. Anything unreadable falls back to the defaults. */
export function loadFavorites(grid: Grid = "remote"): (string | null)[] {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEYS[grid]) ?? "null");
    if (Array.isArray(raw)) {
      const mine = new Set(loadCustomKeys().map((c) => c.id));
      const slots = raw.slice(0, SLOTS).map((v) => (typeof v === "string" && (byId.has(v) || mine.has(v)) ? v : null));
      while (slots.length < SLOTS) slots.push(null);
      return slots;
    }
  } catch {
    /* blocked or corrupt storage: use the defaults */
  }
  return [...DEFAULTS[grid]];
}

export function saveFavorites(slots: readonly (string | null)[], grid: Grid = "remote"): void {
  try {
    localStorage.setItem(STORAGE_KEYS[grid], JSON.stringify(slots.slice(0, SLOTS)));
  } catch {
    /* private mode: the choice lasts until the page closes */
  }
}

/** Slot list with `id` put in slot `index` (an id never sits in two slots). */
export function assign(slots: readonly (string | null)[], index: number, id: string | null): (string | null)[] {
  const next = slots.map((s) => (id !== null && s === id ? null : s));
  next[index] = id;
  return next;
}
