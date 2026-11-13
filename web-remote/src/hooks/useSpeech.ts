import { useCallback, useState } from "react";
import type { Recording } from "../utils/audioRecorder";
import { useVoice, type MicMode } from "./useVoice";

/**
 * The mic button. Two ways to hear you:
 *
 * - "keyboard" (phones): the mic opens the phone keyboard and arms it; you tap the keyboard's own
 *   mic (Siri / Google dictation) and the command is sent 1.5 s after the words stop changing.
 *   Nothing is recorded by the app and no speech model runs on the PC.
 * - "record" (a desktop browser, which has no dictation key): the app records audio for the
 *   PC's speech model, the original path.
 *
 * The phone's Web Speech engine (0.6.0) is gone: keyboard dictation proved better on the sofa.
 */
export type Engine = "keyboard" | "record";

/** How long the words must stay still before keyboard dictation is sent. */
export const AUTO_SEND_MS = 1500;

const isTouch = () => typeof navigator !== "undefined" && (navigator.maxTouchPoints ?? 0) > 0;

export function pickEngine(touch: boolean): Engine {
  return touch ? "keyboard" : "record";
}

export interface Speech {
  engine: Engine;
  supported: boolean;
  active: boolean;
  elapsedMs: number;
  /** "keyboard" engine: the mic was tapped; the next dictated words are sent automatically. */
  armed: boolean;
  toggle(): void;
  cancel(): void;
  holdStart(): void;
  holdEnd(): void;
  arm(): void;
  disarm(): void;
}

interface Options {
  mode: MicMode;
  disabled: boolean;
  /** The old path: a recording for the PC's speech model. */
  onRecording: (recording: Recording) => void;
  onProblem: (message: string) => void;
  /** Tests inject this. */
  touch?: boolean;
}

export function useSpeech({ mode, disabled, onRecording, onProblem, touch }: Options): Speech {
  const engine = pickEngine(touch ?? isTouch());
  const recorder = useVoice({ mode, disabled: disabled || engine !== "record", onRecording, onProblem });
  const [armed, setArmed] = useState(false);
  const arm = useCallback(() => setArmed(true), []);
  const disarm = useCallback(() => setArmed(false), []);

  if (engine === "record") {
    return { ...recorder, engine, armed: false, arm: () => undefined, disarm: () => undefined };
  }
  return {
    engine,
    supported: true,
    active: false,
    elapsedMs: 0,
    armed,
    toggle: () => setArmed((a) => !a),
    cancel: disarm,
    holdStart: arm,
    holdEnd: () => undefined,
    arm,
    disarm,
  };
}
