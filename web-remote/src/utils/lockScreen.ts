import type { NowPlaying } from "../protocol";

/**
 * Lock-screen controls through the Media Session API. A web page only gets the phone's lock-screen
 * player while it is itself playing audio, so this plays a silent loop and tells the phone what
 * the TV is playing; the lock screen's play / pause / next / previous then send TV commands.
 *
 * Off by default: the silent track takes the phone's audio focus (it pauses music playing on the
 * phone) and keeps the page awake, which costs battery. iPhone Live Activities need a native app,
 * so this is the closest a web app gets.
 */
const KEY = "cj.lockScreen";
export type LockAction = "play_pause" | "next" | "prev";

export function loadLockScreen(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function saveLockScreen(on: boolean): void {
  try {
    localStorage.setItem(KEY, on ? "1" : "0");
  } catch {
    /* private mode: lasts until the page closes */
  }
}

export const lockScreenSupported = (nav: unknown = typeof navigator === "undefined" ? undefined : navigator): boolean =>
  typeof (nav as { mediaSession?: unknown } | undefined)?.mediaSession === "object" && typeof Audio !== "undefined";

/** One second of silence (8 kHz, 8-bit, mono) as a WAV data URI: 8 kB, loops forever. */
export function silentWav(): string {
  const rate = 8000;
  const samples = rate; // 1 s
  const bytes = new Uint8Array(44 + samples);
  const view = new DataView(bytes.buffer);
  const ascii = (at: number, text: string) => {
    for (let i = 0; i < text.length; i++) bytes[at + i] = text.charCodeAt(i);
  };
  ascii(0, "RIFF");
  view.setUint32(4, 36 + samples, true);
  ascii(8, "WAVE");
  ascii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, rate, true);
  view.setUint32(28, rate, true); // byte rate
  view.setUint16(32, 1, true); // block align
  view.setUint16(34, 8, true); // bits per sample
  ascii(36, "data");
  view.setUint32(40, samples, true);
  bytes.fill(128, 44); // 8-bit PCM silence is 128, not 0
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return `data:audio/wav;base64,${btoa(binary)}`;
}

interface MediaSessionLike {
  metadata: unknown;
  playbackState?: string;
  setActionHandler(action: string, handler: (() => void) | null): void;
  setPositionState?(state: { duration: number; playbackRate: number; position: number }): void;
}

interface Deps {
  session: MediaSessionLike;
  audio: Pick<HTMLAudioElement, "play" | "pause" | "loop" | "src">;
  metadata: (init: { title: string; artist: string; artwork: { src: string }[] }) => unknown;
  send: (action: LockAction) => void;
}

export const ACTIONS: readonly { media: string; send: LockAction }[] = [
  { media: "play", send: "play_pause" },
  { media: "pause", send: "play_pause" },
  { media: "nexttrack", send: "next" },
  { media: "previoustrack", send: "prev" },
];

/** Holds the lock-screen player while on. `update` mirrors the TV's state; `stop` gives it back. */
export class LockScreenPlayer {
  private running = false;

  constructor(private readonly deps: Deps) {}

  start(): void {
    if (this.running) return;
    this.running = true;
    const { audio, session } = this.deps;
    audio.loop = true;
    audio.src = silentWav();
    void audio.play()?.catch?.(() => undefined); // needs a user gesture first: the Settings tap
    for (const a of ACTIONS) {
      try {
        session.setActionHandler(a.media, () => this.deps.send(a.send));
      } catch {
        /* an action this phone does not offer */
      }
    }
  }

  update(playing: NowPlaying | null, tvName = "TV"): void {
    if (!this.running) return;
    const { session, metadata } = this.deps;
    session.metadata = metadata({
      title: playing?.title ?? "Nothing playing",
      artist: playing?.app ?? (playing?.source === "ytmusic" ? "YouTube Music" : playing?.source === "youtube" ? "YouTube" : tvName),
      artwork: playing?.thumbnail_url ? [{ src: playing.thumbnail_url }] : [],
    });
    if ("playbackState" in session) session.playbackState = playing?.is_playing ? "playing" : "paused";
    const duration = playing?.duration_s ?? 0;
    if (session.setPositionState && duration > 0) {
      try {
        session.setPositionState({
          duration,
          playbackRate: 1,
          position: Math.min(duration, Math.max(0, playing?.position_s ?? 0)),
        });
      } catch {
        /* a position past the end during a seek: skip this update */
      }
    }
  }

  stop(): void {
    if (!this.running) return;
    this.running = false;
    const { audio, session } = this.deps;
    audio.pause();
    audio.src = "";
    for (const a of ACTIONS) {
      try {
        session.setActionHandler(a.media, null);
      } catch {
        /* ignore */
      }
    }
    session.metadata = null;
    if ("playbackState" in session) session.playbackState = "none";
  }
}

/** The real thing in a browser, or null where the API is missing. */
export function browserLockScreenPlayer(send: (action: LockAction) => void): LockScreenPlayer | null {
  if (!lockScreenSupported()) return null;
  const Meta = (window as unknown as { MediaMetadata?: new (init: unknown) => unknown }).MediaMetadata;
  if (!Meta) return null;
  return new LockScreenPlayer({
    session: navigator.mediaSession as unknown as MediaSessionLike,
    audio: new Audio(),
    metadata: (init) => new Meta(init),
    send,
  });
}
