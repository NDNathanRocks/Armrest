import { useEffect, useRef, useState } from "react";
import type { NowPlaying } from "../protocol";
import { browserLockScreenPlayer, loadLockScreen, lockScreenSupported, saveLockScreen, type LockAction, type LockScreenPlayer } from "../utils/lockScreen";

interface Options {
  playing: NowPlaying | null;
  connected: boolean;
  send: (action: LockAction) => void;
}

/** The lock-screen player setting, and the player itself while it is on and connected. */
export function useLockScreen({ playing, connected, send }: Options) {
  const [enabled, setEnabled] = useState(loadLockScreen);
  const supported = lockScreenSupported();
  const player = useRef<LockScreenPlayer | null>(null);
  const latestSend = useRef(send);
  useEffect(() => {
    latestSend.current = send;
  });

  useEffect(() => {
    if (!enabled || !connected || !supported) {
      player.current?.stop();
      player.current = null;
      return;
    }
    const p = browserLockScreenPlayer((a) => latestSend.current(a));
    if (!p) return;
    player.current = p;
    p.start();
    return () => {
      p.stop();
      player.current = null;
    };
  }, [enabled, connected, supported]);

  useEffect(() => {
    player.current?.update(playing);
  }, [playing]);

  const choose = (on: boolean) => {
    setEnabled(on);
    saveLockScreen(on);
  };
  return { enabled, supported, choose };
}
