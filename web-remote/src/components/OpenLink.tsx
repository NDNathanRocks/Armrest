import { useState } from "react";
import { findLink } from "../utils/links";
import { Icon } from "./Icon";

interface Props {
  disabled: boolean;
  onOpen: (url: string) => void;
}

/**
 * Open a link on the TV: paste it (iPhone: copy it in YouTube, Netflix... then paste here). On
 * Android, Share > Armrest from any app does the same without opening this box.
 */
export function OpenLink({ disabled, onOpen }: Props) {
  const [text, setText] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const link = findLink(text);
  const canPaste = typeof navigator !== "undefined" && typeof navigator.clipboard?.readText === "function";

  const open = (url: string | null) => {
    if (!url) {
      setProblem("That doesn't look like a web link.");
      return;
    }
    onOpen(url);
    setText("");
    setProblem(null);
  };

  return (
    <form
      aria-label="Open a link on the TV"
      className="glass rounded-2xl p-3"
      onSubmit={(e) => {
        e.preventDefault();
        open(link);
      }}
    >
      <div className="flex items-center gap-2">
        <span className="text-muted" aria-hidden>
          <Icon name="link" size={18} />
        </span>
        <input
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setProblem(null);
          }}
          placeholder="Paste a link to open on the TV"
          aria-label="Link to open on the TV"
          inputMode="url"
          autoCapitalize="none"
          autoCorrect="off"
          enterKeyHint="go"
          className="min-h-11 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted"
        />
        {link ? (
          <button type="submit" disabled={disabled} className="press min-h-11 rounded-full bg-accent px-4 text-sm font-semibold text-ink disabled:opacity-40">
            Open
          </button>
        ) : (
          canPaste && (
            <button
              type="button"
              disabled={disabled}
              onClick={async () => {
                try {
                  open(findLink(await navigator.clipboard.readText()));
                } catch {
                  setProblem("Paste it into the box instead (long-press, then Paste).");
                }
              }}
              className="press glass-btn min-h-11 rounded-full px-4 text-sm disabled:opacity-40"
            >
              Paste
            </button>
          )
        )}
      </div>
      {problem && (
        <p className="mt-1 px-1 text-xs text-amber-300" role="alert">
          {problem}
        </p>
      )}
    </form>
  );
}
