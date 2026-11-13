import { describe, expect, it, vi } from "vitest";
import { ACTIONS, LockScreenPlayer, loadLockScreen, lockScreenSupported, saveLockScreen, silentWav } from "../utils/lockScreen";

class FakeSession {
  metadata: unknown = null;
  playbackState = "none";
  handlers = new Map<string, (() => void) | null>();
  positions: unknown[] = [];
  setActionHandler(action: string, handler: (() => void) | null) {
    if (action === "seekto") throw new TypeError("not supported here");
    this.handlers.set(action, handler);
  }
  setPositionState(state: unknown) {
    this.positions.push(state);
  }
}

const setup = () => {
  const session = new FakeSession();
  const audio = { play: vi.fn(() => Promise.resolve()), pause: vi.fn(), loop: false, src: "" };
  const send = vi.fn();
  const player = new LockScreenPlayer({ session, audio, metadata: (init) => ({ ...init }), send });
  return { session, audio, send, player };
};

describe("lock-screen controls", () => {
  it("is off until chosen, and remembers the choice", () => {
    expect(loadLockScreen()).toBe(false);
    saveLockScreen(true);
    expect(loadLockScreen()).toBe(true);
    expect(lockScreenSupported({ mediaSession: {} })).toBe(true);
    expect(lockScreenSupported({})).toBe(false);
  });

  it("the silent loop is a valid one-second 8-bit WAV", () => {
    const uri = silentWav();
    expect(uri.startsWith("data:audio/wav;base64,")).toBe(true);
    const bytes = Uint8Array.from(atob(uri.split(",")[1]!), (c) => c.charCodeAt(0));
    expect(String.fromCharCode(...bytes.subarray(0, 4))).toBe("RIFF");
    expect(String.fromCharCode(...bytes.subarray(36, 40))).toBe("data");
    expect(bytes.length).toBe(44 + 8000);
    expect(bytes[44]).toBe(128); // silence, not a click
  });

  it("starts the silent loop, mirrors the TV and sends lock-screen taps as commands", () => {
    const { session, audio, send, player } = setup();
    player.start();
    expect(audio.loop).toBe(true);
    expect(audio.src.startsWith("data:audio/wav")).toBe(true);
    expect(audio.play).toHaveBeenCalledTimes(1);
    expect([...session.handlers.keys()].sort()).toEqual(ACTIONS.map((a) => a.media).sort());

    player.update({ title: "Lofi Girl", source: "youtube", is_playing: true, position_s: 30, duration_s: 300, thumbnail_url: "https://i.ytimg.com/x.jpg" });
    expect(session.metadata).toEqual({ title: "Lofi Girl", artist: "YouTube", artwork: [{ src: "https://i.ytimg.com/x.jpg" }] });
    expect(session.playbackState).toBe("playing");
    expect(session.positions.at(-1)).toEqual({ duration: 300, playbackRate: 1, position: 30 });

    session.handlers.get("pause")!();
    session.handlers.get("nexttrack")!();
    session.handlers.get("previoustrack")!();
    expect(send.mock.calls.map((c) => c[0])).toEqual(["play_pause", "next", "prev"]);

    player.update({ title: "Blinding Lights", app: "Spotify", is_playing: false });
    expect(session.metadata).toMatchObject({ artist: "Spotify" });
    expect(session.playbackState).toBe("paused");
    player.update(null);
    expect(session.metadata).toMatchObject({ title: "Nothing playing", artist: "TV" });
  });

  it("stop gives the phone its audio back and clears the lock screen", () => {
    const { session, audio, player } = setup();
    player.start();
    player.stop();
    expect(audio.pause).toHaveBeenCalled();
    expect(audio.src).toBe("");
    expect([...session.handlers.values()].every((h) => h === null)).toBe(true);
    expect(session.metadata).toBeNull();
    expect(session.playbackState).toBe("none");
    player.update({ title: "x" }); // after stop: nothing happens
    expect(session.metadata).toBeNull();
  });
});
