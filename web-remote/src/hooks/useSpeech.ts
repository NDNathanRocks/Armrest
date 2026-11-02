import { useCallback, useEffect, useRef, useState } from "react";
import type { Recording } from "../utils/audioRecorder";
import { useVoice, type MicMode } from "./useVoice";

/**
 * The mic button, fast. Three ways to hear you, best first:
 *
 * - "speech": the phone's own speech engine (Web Speech API: Siri dictation on iPhone, Google on
 *   Android). Words show live in the command bar and are sent as text the moment you stop
 *   talking: no audio upload, no speech model on the PC.
 * - "keyboard": where that engine is missing or refused (some home-screen apps, Firefox on a
 *   phone) the mic opens the keyboard; you tap its own mic, and the command goes 1.5 s after
 *   the words stop changing.
 * - "record": a desktop browser with neither records audio for the PC's speech model (the old
 *   path, kept as a fallback for one release).
 */
export type Engine = "speech" | "keyboard" | "record";

/** How long the words must stay still before keyboard dictation is sent. */
export const AUTO_SEND_MS = 1500;
/** The engine stops by itself at the end of a phrase; this is only a safety net. */
const MAX_LISTEN_MS = 15_000;

interface Alternative {
  transcript: string;
}
interface Result {
  readonly isFinal: boolean;
  readonly length: number;
  [index: number]: Alternative;
}
interface ResultEvent {
  readonly resultIndex: number;
  readonly results: { readonly length: number; [index: number]: Result };
}
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((e: ResultEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type RecognitionCtor = new () => Recognition;

export function speechRecognition(win: unknown = typeof window === "undefined" ? undefined : window): RecognitionCtor | null {
  const w = win as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor } | undefined;
  return w?.SpeechRecognition ?? w?.webkitSpeechRecognition ?? null;
}

const isTouch = () => typeof navigator !== "undefined" && (navigator.maxTouchPoints ?? 0) > 0;

export function pickEngine(hasSpeech: boolean, touch: boolean): Engine {
  if (hasSpeech) return "speech";
  return touch ? "keyboard" : "record";
}

/** Errors that mean "this engine will not work here": switch to the keyboard for this visit. */
const ENGINE_REFUSED = new Set(["service-not-allowed", "language-not-supported", "network"]);

const PROBLEMS: Record<string, string> = {
  "not-allowed": "Microphone permission was denied. Allow it in the browser settings.",
  "audio-capture": "No microphone was found.",
  "no-speech": "I didn't hear anything. Tap the mic and speak.",
};

export interface Speech {
  engine: Engine;
  supported: boolean;
  active: boolean;
  /** The words heard so far ("speech" engine), shown live in the command bar. */
  interim: string;
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
  /** Spoken words, ready to send as a typed command. */
  onText: (text: string) => void;
  /** The old path: a recording for the PC's speech model. */
  onRecording: (recording: Recording) => void;
  onProblem: (message: string) => void;
  /** Tests inject these. */
  recognition?: RecognitionCtor | null;
  touch?: boolean;
  lang?: string;
}

/** The microphone is only offered to secure pages (https, localhost); a LAN http page has none. */
const micAllowed = (): boolean =>
  typeof window !== "undefined" && window.isSecureContext && typeof navigator.mediaDevices?.getUserMedia === "function";

export function useSpeech({ mode, disabled, onText, onRecording, onProblem, recognition, touch, lang }: Options): Speech {
  const [refused, setRefused] = useState(false); // the speech engine said no: keyboard instead
  const [ctor] = useState<RecognitionCtor | null>(() =>
    recognition !== undefined ? recognition : micAllowed() ? speechRecognition() : null,
  );
  const engine = pickEngine(ctor !== null && !refused, touch ?? isTouch());
  const recorder = useVoice({ mode, disabled: disabled || engine !== "record", onRecording, onProblem });

  const [active, setActive] = useState(false);
  const [interim, setInterim] = useState("");
  const [armed, setArmed] = useState(false);
  const [startedAt, setStartedAt] = useState(0);
  const [now, setNow] = useState(0);
  const rec = useRef<Recognition | null>(null);
  const heard = useRef("");
  const cancelled = useRef(false);
  const latest = useRef({ onText, onProblem });
  useEffect(() => {
    latest.current = { onText, onProblem };
  });

  useEffect(() => {
    if (!active) return;
    const tick = setInterval(() => setNow(Date.now()), 200);
    const limit = setTimeout(() => rec.current?.stop(), MAX_LISTEN_MS);
    return () => {
      clearInterval(tick);
      clearTimeout(limit);
    };
  }, [active]);
  useEffect(() => () => rec.current?.abort(), []);

  const start = useCallback(
    (continuous: boolean) => {
      if (disabled || !ctor || rec.current) return;
      const r = new ctor();
      r.lang = lang ?? (typeof navigator !== "undefined" ? navigator.language : "") ?? "en-US";
      r.interimResults = true;
      r.continuous = continuous; // hold: keep listening until the finger lifts
      r.maxAlternatives = 1;
      heard.current = "";
      cancelled.current = false;
      r.onresult = (e) => {
        let text = "";
        for (let i = 0; i < e.results.length; i++) text += e.results[i]?.[0]?.transcript ?? "";
        heard.current = text.trim();
        setInterim(heard.current);
      };
      r.onerror = (e) => {
        if (ENGINE_REFUSED.has(e.error)) {
          setRefused(true);
          latest.current.onProblem("Voice recognition isn't available here. Tap the mic again to use the keyboard's dictation.");
        } else if (e.error !== "aborted") {
          const problem = PROBLEMS[e.error];
          if (problem) latest.current.onProblem(problem);
        }
      };
      r.onend = () => {
        rec.current = null;
        setActive(false);
        setInterim("");
        const text = heard.current;
        heard.current = "";
        if (!cancelled.current && text) latest.current.onText(text);
      };
      rec.current = r;
      try {
        r.start();
      } catch {
        rec.current = null;
        latest.current.onProblem("Could not start the microphone.");
        return;
      }
      navigator.vibrate?.(15);
      setStartedAt(Date.now());
      setNow(Date.now());
      setActive(true);
    },
    [ctor, disabled, lang],
  );

  const stop = useCallback(() => {
    if (!rec.current) return;
    navigator.vibrate?.(10);
    rec.current.stop(); // onend sends what was heard
  }, []);

  const cancel = useCallback(() => {
    cancelled.current = true;
    rec.current?.abort();
    setArmed(false);
  }, []);

  if (engine === "record") {
    return {
      ...recorder,
      engine,
      interim: "",
      armed: false,
      arm: () => undefined,
      disarm: () => undefined,
    };
  }
  if (engine === "keyboard") {
    return {
      engine,
      supported: true,
      active: false,
      interim: "",
      elapsedMs: 0,
      armed,
      toggle: () => setArmed((a) => !a),
      cancel,
      holdStart: () => setArmed(true),
      holdEnd: () => undefined,
      arm: () => setArmed(true),
      disarm: () => setArmed(false),
    };
  }
  return {
    engine,
    supported: true,
    active,
    interim,
    elapsedMs: active ? now - startedAt : 0,
    armed: false,
    toggle: () => (rec.current ? stop() : start(false)),
    cancel,
    holdStart: () => start(true),
    holdEnd: stop,
    arm: () => undefined,
    disarm: () => undefined,
  };
}
