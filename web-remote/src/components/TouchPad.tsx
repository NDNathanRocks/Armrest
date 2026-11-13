import { useEffect, useRef, useState } from "react";
import type { PointerAction } from "../protocol";
import { TouchpadGesture, type PointerEmit } from "../utils/gestures";
import { tap } from "../utils/haptics";

interface Props {
  onPointer: (e: PointerEmit) => void;
  disabled: boolean;
}

/** Cursor speed choices; acceleration is on for all of them (slow finger = precise). */
export const PAD_SPEEDS = { slow: 1.1, normal: 1.6, fast: 2.4 } as const;
export type PadSpeed = keyof typeof PAD_SPEEDS;
const SPEED_KEY = "cj.touchpad.speed";

/** Scroll buttons: one notch on the tap, then while held, one notch every REPEAT_MS after a pause. */
export const SCROLL_HOLD_DELAY_MS = 350;
export const SCROLL_REPEAT_MS = 140;

export function loadPadSpeed(): PadSpeed {
  try {
    const saved = localStorage.getItem(SPEED_KEY);
    if (saved && saved in PAD_SPEEDS) return saved as PadSpeed;
  } catch {
    /* blocked storage */
  }
  return "normal";
}

function savePadSpeed(speed: PadSpeed): void {
  try {
    localStorage.setItem(SPEED_KEY, speed);
  } catch {
    /* private mode: lasts until the page closes */
  }
}

/** A relative-motion touchpad for the PC cursor. The page itself must never scroll under it. */
export function TouchPad({ onPointer, disabled }: Props) {
  const gesture = useRef<TouchpadGesture | null>(null);
  const emit = useRef(onPointer);
  const [speed, setSpeed] = useState<PadSpeed>(loadPadSpeed);
  useEffect(() => {
    emit.current = onPointer;
  });
  useEffect(() => {
    gesture.current = new TouchpadGesture({
      speed: PAD_SPEEDS[speed],
      accel: 1,
      emit: (e) => {
        if (e.action === "click" || e.action === "right_click" || e.action === "drag_start") tap(8);
        emit.current(e);
      },
    });
    return () => gesture.current?.cancel();
  }, [speed]);

  const click = (action: PointerAction) => () => {
    tap(8);
    onPointer({ action });
  };
  const button = "press glass-btn min-h-12 flex-1 !rounded-2xl text-sm font-medium";

  return (
    <section aria-label="Touchpad" className="space-y-2.5">
      <div className="flex items-center justify-between px-1">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-muted">Touchpad</h2>
        <div role="radiogroup" aria-label="Cursor speed" className="glass flex rounded-full p-0.5 text-xs">
          {(Object.keys(PAD_SPEEDS) as PadSpeed[]).map((s) => (
            <button
              key={s}
              type="button"
              role="radio"
              aria-checked={speed === s}
              onClick={() => {
                setSpeed(s);
                savePadSpeed(s);
              }}
              className={`min-h-11 min-w-11 rounded-full px-3 font-semibold capitalize ${speed === s ? "bg-white/15 text-white" : "text-muted"}`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>
      <div
        role="application"
        aria-label="Touchpad area: drag to move the cursor, tap to click, two fingers to scroll"
        data-testid="touchpad"
        className={`glass relative h-[min(22rem,48vh)] min-h-56 touch-none select-none rounded-[28px] ${disabled ? "opacity-40" : ""}`}
        onPointerDown={(e) => {
          if (disabled) return;
          e.currentTarget.setPointerCapture?.(e.pointerId);
          gesture.current?.down(e.pointerId, e.clientX, e.clientY);
        }}
        onPointerMove={(e) => gesture.current?.move(e.pointerId, e.clientX, e.clientY)}
        onPointerUp={(e) => gesture.current?.up(e.pointerId)}
        onPointerCancel={() => gesture.current?.cancel()}
        onContextMenu={(e) => e.preventDefault()}
      >
        <p className="pointer-events-none absolute inset-0 flex items-center justify-center px-6 text-center text-xs text-zinc-600">
          Drag to move · tap to click · two fingers to scroll or right-click · hold then drag to select
        </p>
      </div>
      <div className="flex gap-3">
        <ScrollButton direction={-1} disabled={disabled} onPointer={onPointer} className={button} />
        <ScrollButton direction={1} disabled={disabled} onPointer={onPointer} className={button} />
        <button type="button" disabled={disabled} onClick={click("right_click")} className={button}>
          Right click
        </button>
      </div>
    </section>
  );
}

/**
 * Scroll up / down. A tap scrolls one notch; holding the button keeps scrolling slowly, so a long
 * page can be read without tapping a hundred times. Timers stop on release, leave or cancel.
 */
function ScrollButton({
  direction,
  disabled,
  onPointer,
  className,
}: {
  direction: -1 | 1;
  disabled: boolean;
  onPointer: (e: PointerEmit) => void;
  className: string;
}) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef(onPointer);
  useEffect(() => {
    latest.current = onPointer;
  });
  const stop = () => {
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
  };
  useEffect(() => stop, []);
  const start = () => {
    if (disabled) return;
    stop();
    latest.current({ scroll: direction });
    const repeat = () => {
      latest.current({ scroll: direction });
      timer.current = setTimeout(repeat, SCROLL_REPEAT_MS);
    };
    timer.current = setTimeout(repeat, SCROLL_HOLD_DELAY_MS);
  };
  const label = direction < 0 ? "Scroll up" : "Scroll down";
  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={label}
      title="Hold to keep scrolling"
      onPointerDown={start}
      onPointerUp={stop}
      onPointerLeave={stop}
      onPointerCancel={stop}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !e.repeat) start();
      }}
      onKeyUp={stop}
      onContextMenu={(e) => e.preventDefault()}
      style={{ touchAction: "none", WebkitUserSelect: "none", userSelect: "none" }}
      className={className}
    >
      {direction < 0 ? "▲ Scroll up" : "▼ Scroll down"}
    </button>
  );
}
