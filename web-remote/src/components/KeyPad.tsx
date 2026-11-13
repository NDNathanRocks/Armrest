import { useState } from "react";
import type { Modifier } from "../protocol";

interface Props {
  onKey: (key: string, mods?: Modifier[]) => void;
  disabled: boolean;
}

interface Key {
  key: string;
  label: string;
}

const MODS: readonly { mod: Modifier; label: string }[] = [
  { mod: "ctrl", label: "Ctrl" },
  { mod: "alt", label: "Alt" },
  { mod: "shift", label: "Shift" },
];

const KEYS: readonly Key[] = [
  { key: "esc", label: "Esc" },
  { key: "tab", label: "Tab" },
  { key: "enter", label: "Enter" },
  { key: "backspace", label: "⌫" },
  { key: "delete", label: "Del" },
  { key: "space", label: "Space" },
  { key: "home", label: "Home" },
  { key: "end", label: "End" },
  { key: "pageup", label: "PgUp" },
  { key: "pagedown", label: "PgDn" },
];

/** F1-F12. F11 is the browser's own full screen: it hides the tab strip that fullscreen can leave. */
const FUNCTION_KEYS: readonly Key[] = Array.from({ length: 12 }, (_, i) => ({
  key: `f${i + 1}`,
  label: `F${i + 1}`,
}));

const ARROWS: readonly Key[] = [
  { key: "left", label: "←" },
  { key: "up", label: "↑" },
  { key: "down", label: "↓" },
  { key: "right", label: "→" },
];

interface Shortcut {
  label: string;
  key: string;
  mods: Modifier[];
}

/** One-tap chords for the browser on the TV. alt+left is "Back". */
export const SHORTCUTS: readonly Shortcut[] = [
  { label: "Back", key: "left", mods: ["alt"] },
  { label: "Forward", key: "right", mods: ["alt"] },
  { label: "Reload", key: "r", mods: ["ctrl"] },
  { label: "New tab", key: "t", mods: ["ctrl"] },
  { label: "Close tab", key: "w", mods: ["ctrl"] },
  { label: "Next tab", key: "tab", mods: ["ctrl"] },
  { label: "Prev tab", key: "tab", mods: ["ctrl", "shift"] },
  { label: "Address bar", key: "l", mods: ["ctrl"] },
  { label: "Zoom in", key: "=", mods: ["ctrl"] },
  { label: "Zoom out", key: "-", mods: ["ctrl"] },
  { label: "Reset zoom", key: "0", mods: ["ctrl"] },
  { label: "Switch window", key: "tab", mods: ["alt"] },
  { label: "Full screen (F11)", key: "f11", mods: [] },
];

/** The special keys, F-keys and browser shortcuts. Typing lives in TypeBox, on the Remote tab. */
export function KeyPad({ onKey, disabled }: Props) {
  const [mods, setMods] = useState<Modifier[]>([]);

  const toggle = (mod: Modifier) =>
    setMods((m) => (m.includes(mod) ? m.filter((x) => x !== mod) : [...m, mod]));

  /** Latched modifiers apply to the next key only, like a sticky key. */
  const press = (key: string, extra: Modifier[] = []) => {
    onKey(key, [...new Set([...mods, ...extra])]);
    setMods([]);
  };

  const keyButton =
    "press glass-btn min-h-11 !rounded-xl px-1 text-sm";

  return (
    <section aria-label="Keyboard" className="space-y-3">
      <div role="group" aria-label="Modifiers" className="flex gap-2">
        {MODS.map(({ mod, label }) => (
          <button
            key={mod}
            type="button"
            disabled={disabled}
            aria-pressed={mods.includes(mod)}
            onClick={() => toggle(mod)}
            className={`press glass-btn min-h-11 flex-1 !rounded-xl text-sm ${
              mods.includes(mod) ? "!bg-accent !text-ink font-semibold" : ""
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div role="group" aria-label="Keys" className="grid grid-cols-4 gap-2">
        {ARROWS.map((k) => (
          <button key={k.key} type="button" disabled={disabled} aria-label={`Key ${k.key}`} onClick={() => press(k.key)} className={keyButton}>
            {k.label}
          </button>
        ))}
        {KEYS.map((k) => (
          <button key={k.key} type="button" disabled={disabled} aria-label={`Key ${k.key}`} onClick={() => press(k.key)} className={keyButton}>
            {k.label}
          </button>
        ))}
      </div>

      <div role="group" aria-label="Function keys" className="grid grid-cols-6 gap-2">
        {FUNCTION_KEYS.map((k) => (
          <button key={k.key} type="button" disabled={disabled} aria-label={`Key ${k.key}`} onClick={() => press(k.key)} className={keyButton}>
            {k.label}
          </button>
        ))}
      </div>

      <div role="group" aria-label="Browser shortcuts" className="grid grid-cols-3 gap-2">
        {SHORTCUTS.map((s) => (
          <button
            key={s.label}
            type="button"
            disabled={disabled}
            onClick={() => press(s.key, s.mods)}
            className="press glass-btn min-h-11 !rounded-xl px-1 text-xs"
          >
            {s.label}
          </button>
        ))}
      </div>
    </section>
  );
}
