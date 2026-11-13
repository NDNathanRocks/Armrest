import type { FormEvent, KeyboardEvent } from "react";
import type { Modifier } from "../protocol";

interface Props {
  onKey: (key: string, mods?: Modifier[]) => void;
  onText: (text: string) => void;
  disabled: boolean;
  /** Shown under the box: the heading of the section it sits in, when it is not the keypad. */
  title?: string;
}

const SENTINEL = "​"; // so Backspace always has something to delete on a phone keyboard
const NAMED_FROM_KEYBOARD: Record<string, string> = {
  Enter: "enter",
  Backspace: "backspace",
  Delete: "delete",
  Escape: "esc",
  Tab: "tab",
  ArrowLeft: "left",
  ArrowRight: "right",
  ArrowUp: "up",
  ArrowDown: "down",
};

/**
 * Type on the TV from the phone keyboard. Every character goes straight to the PC as you type;
 * Enter, Backspace and (from a hardware keyboard) Esc, Tab and the arrows go as keys. The box
 * itself is kept empty, so predictive keyboards never see a stale word.
 */
export function TypeBox({ onKey, onText, disabled, title }: Props) {
  const reset = (el: HTMLTextAreaElement) => {
    el.value = SENTINEL;
    el.setSelectionRange?.(SENTINEL.length, SENTINEL.length);
  };

  const onInput = (e: FormEvent<HTMLTextAreaElement>) => {
    const ev = e.nativeEvent as InputEvent;
    const el = e.currentTarget;
    if (ev.isComposing) return; // predictive keyboards: wait for the finished word
    switch (ev.inputType) {
      case "insertText":
      case "insertFromPaste":
        if (ev.data) onText(ev.data);
        else if (el.value.replace(SENTINEL, "")) onText(el.value.replace(SENTINEL, ""));
        break;
      case "insertLineBreak":
      case "insertParagraph":
        onKey("enter", []);
        break;
      case "deleteContentBackward":
        onKey("backspace", []);
        break;
      case "deleteContentForward":
        onKey("delete", []);
        break;
    }
    reset(el);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.nativeEvent.isComposing) return;
    const named = NAMED_FROM_KEYBOARD[e.key];
    // Backspace/Enter arrive as input events (handled in onInput); the rest never edit the box,
    // so a hardware keyboard's Esc/Tab/arrows are forwarded here and kept out of the field.
    if (named && e.key !== "Backspace" && e.key !== "Enter") {
      e.preventDefault();
      onKey(named, []);
    }
  };

  const box = (
    <textarea
      aria-label="Type on the TV"
      placeholder="Tap here to type on the TV"
      disabled={disabled}
      defaultValue={SENTINEL}
      rows={1}
      autoCapitalize="off"
      autoCorrect="off"
      spellCheck={false}
      onInput={onInput}
      onKeyDown={onKeyDown}
      onCompositionEnd={(e) => {
        if (e.data) onText(e.data);
        reset(e.currentTarget);
      }}
      className="glass min-h-12 w-full resize-none rounded-2xl px-4 py-3 text-base text-zinc-100 outline-none placeholder:text-zinc-500 focus:ring-2 focus:ring-accent disabled:opacity-40"
    />
  );
  if (!title) return box;
  return (
    <section aria-label={title} className="space-y-2.5">
      <h2 className="px-1 text-xs font-semibold uppercase tracking-widest text-muted">{title}</h2>
      {box}
    </section>
  );
}
