import { useEffect, useRef, useState } from "react";
import { APP_NAME } from "../brand";
import { normalizeCode, type PairParams } from "../connection/roomConnection";
import { readPairParams } from "./QRScanner";
import { Icon } from "./Icon";

interface Props {
  onScan: (params: PairParams) => void;
  onCode: (code: string) => void;
  /** A pairing is under way: the buttons wait. */
  busy?: boolean;
}

/**
 * Pair from inside the app: scan the TV's QR with the camera, or type the code under it. A
 * phone's camera app opens the QR in the browser, which an iPhone home-screen app never sees.
 */
export function PairPanel({ onScan, onCode, busy = false }: Props) {
  const [mode, setMode] = useState<"buttons" | "scan" | "code">("buttons");
  if (mode === "scan") {
    return (
      <Scanner
        onFound={(params) => {
          setMode("buttons");
          onScan(params);
        }}
        onCancel={() => setMode("buttons")}
        onTypeInstead={() => setMode("code")}
      />
    );
  }
  if (mode === "code") {
    return <CodeForm busy={busy} onCode={onCode} onCancel={() => setMode("buttons")} />;
  }
  return (
    <div className="mt-5 grid gap-2">
      <button
        type="button"
        disabled={busy}
        onClick={() => setMode("scan")}
        className="press flex min-h-12 items-center justify-center gap-2 rounded-full bg-accent font-semibold text-zinc-950 disabled:opacity-50"
      >
        <Icon name="camera" size={20} />
        Scan the code on the TV
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => setMode("code")}
        className="press glass-btn min-h-12 rounded-full font-semibold disabled:opacity-50"
      >
        Type the code instead
      </button>
    </div>
  );
}

/** "K7QM4X" -> "K7QM-4X": the dash appears as you type, like on the TV. */
export function formatCodeInput(typed: string): string {
  const raw = typed.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 8);
  return raw.length > 4 ? `${raw.slice(0, 4)}-${raw.slice(4)}` : raw;
}

function CodeForm({ busy, onCode, onCancel }: { busy: boolean; onCode: (code: string) => void; onCancel: () => void }) {
  const [text, setText] = useState("");
  const code = normalizeCode(text);
  return (
    <form
      className="mt-5 grid gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (code) onCode(code);
      }}
    >
      <label className="grid gap-1 text-sm">
        <span className="text-zinc-300">The code under the QR on the TV</span>
        <input
          value={text}
          onChange={(e) => setText(formatCodeInput(e.target.value))}
          placeholder="K7QM-4XPA"
          aria-label="Pairing code"
          autoFocus
          autoCapitalize="characters"
          autoComplete="one-time-code"
          spellCheck={false}
          inputMode="text"
          className="h-14 rounded-2xl bg-surface px-4 text-center font-mono text-2xl tracking-[0.2em] text-zinc-100 ring-1 ring-line placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-accent"
        />
      </label>
      <p className="text-xs text-zinc-400">
        No code on the TV? Say <b>"pair a friend"</b> on a paired phone, or open <b>{APP_NAME}</b> on the PC and
        choose Phones. A code works once, for 10 minutes.
      </p>
      <div className="flex gap-2">
        <button type="button" onClick={onCancel} className="press glass-btn min-h-12 flex-1 rounded-full">
          Back
        </button>
        <button
          type="submit"
          disabled={!code || busy}
          className="press min-h-12 flex-[2] rounded-full bg-accent font-semibold text-zinc-950 disabled:opacity-40"
        >
          {busy ? "Pairing…" : "Pair"}
        </button>
      </div>
    </form>
  );
}

/** Frames are decoded at this width: enough for the TV's QR from the sofa, quick on an old phone. */
const SCAN_WIDTH = 960;
const SCAN_EVERY_MS = 150;

/** The pairing link inside a scanned QR, or null for anything else. */
export function pairParamsFromScan(text: string): PairParams | null {
  try {
    return readPairParams(new URL(text.trim()).search);
  } catch {
    return null;
  }
}

function Scanner({
  onFound,
  onCancel,
  onTypeInstead,
}: {
  onFound: (params: PairParams) => void;
  onCancel: () => void;
  onTypeInstead: () => void;
}) {
  const video = useRef<HTMLVideoElement | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [wrongQr, setWrongQr] = useState(false);
  const found = useRef(onFound);
  useEffect(() => {
    found.current = onFound;
  });

  useEffect(() => {
    let stream: MediaStream | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;
    const canvas = document.createElement("canvas");

    const start = async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        setProblem("This browser can't use the camera here. Type the code instead.");
        return;
      }
      // The decoder loads while the camera permission prompt is up, so neither waits for the other.
      const decoder = import("jsqr").then((m) => m.default);
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        });
      } catch {
        setProblem("The camera is blocked. Allow it in your browser settings, or type the code instead.");
        return;
      }
      if (stopped || !video.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      video.current.srcObject = stream;
      await video.current.play().catch(() => undefined);
      // jsQR runs everywhere, so it is the only decoder. The browser's BarcodeDetector was tried
      // first in 0.6.0, but on many Android phones it exists and silently never finds anything (it
      // needs a Google download that may be missing), which left people stuck on this screen.
      const jsQR = await decoder;
      const tick = () => {
        if (stopped) return;
        const v = video.current;
        let text: string | null = null;
        if (v && v.readyState >= 2 && v.videoWidth > 0) {
          const scale = Math.min(1, SCAN_WIDTH / v.videoWidth); // decodes in a few ms at this size
          canvas.width = Math.round(v.videoWidth * scale);
          canvas.height = Math.round(v.videoHeight * scale);
          const ctx = canvas.getContext("2d", { willReadFrequently: true });
          if (ctx) {
            ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
            const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
            text = jsQR(img.data, img.width, img.height, { inversionAttempts: "attemptBoth" })?.data ?? null;
          }
        }
        if (text) {
          const params = pairParamsFromScan(text);
          if (params) {
            navigator.vibrate?.(30);
            found.current(params);
            return;
          }
          setWrongQr(true);
        }
        timer = setTimeout(tick, SCAN_EVERY_MS);
      };
      tick();
    };
    void start();
    return () => {
      stopped = true;
      if (timer !== null) clearTimeout(timer);
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return (
    <div className="mt-5 grid gap-3">
      {problem ? (
        <p className="rounded-2xl bg-amber-500/10 p-4 text-sm text-amber-200 ring-1 ring-amber-500/30" role="alert">
          {problem}
        </p>
      ) : (
        <div className="relative overflow-hidden rounded-3xl bg-black ring-1 ring-line">
          <video ref={video} muted playsInline aria-label="Camera" className="aspect-square w-full object-cover" />
          <div aria-hidden className="pointer-events-none absolute inset-[18%] rounded-2xl border-2 border-white/80" />
          <p className="absolute inset-x-0 bottom-0 bg-black/60 p-2 text-center text-xs text-zinc-200" role="status">
            {wrongQr ? "That isn't the TV's pairing code" : "Point the camera at the QR on the TV"}
          </p>
        </div>
      )}
      <div className="flex gap-2">
        <button type="button" onClick={onCancel} className="press glass-btn min-h-12 flex-1 rounded-full">
          Cancel
        </button>
        <button type="button" onClick={onTypeInstead} className="press glass-btn min-h-12 flex-[2] rounded-full font-semibold">
          Type the code instead
        </button>
      </div>
    </div>
  );
}
