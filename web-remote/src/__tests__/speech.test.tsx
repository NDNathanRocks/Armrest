import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { pickEngine, speechRecognition, useSpeech } from "../hooks/useSpeech";

/** A stand-in for the browser's SpeechRecognition that the test drives by hand. */
class FakeRecognition {
  static last: FakeRecognition | null = null;
  lang = "";
  interimResults = false;
  continuous = false;
  maxAlternatives = 1;
  onresult: ((e: unknown) => void) | null = null;
  onerror: ((e: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  started = false;
  constructor() {
    FakeRecognition.last = this;
  }
  start() {
    this.started = true;
  }
  stop() {
    this.onend?.();
  }
  abort() {
    this.onend?.();
  }
  hear(...parts: [string, boolean][]) {
    const results = parts.map(([transcript, isFinal]) => Object.assign([{ transcript }], { isFinal }));
    this.onresult?.({ resultIndex: 0, results });
  }
}

const setup = (over: Partial<Parameters<typeof useSpeech>[0]> = {}) => {
  const onText = vi.fn();
  const onProblem = vi.fn();
  const hook = renderHook(() =>
    useSpeech({
      mode: "tap",
      disabled: false,
      onText,
      onRecording: vi.fn(),
      onProblem,
      recognition: FakeRecognition as never,
      touch: true,
      lang: "en-GB",
      ...over,
    }),
  );
  return { ...hook, onText, onProblem };
};

describe("useSpeech", () => {
  it("picks the best way to hear you", () => {
    expect(pickEngine(true, true)).toBe("speech");
    expect(pickEngine(false, true)).toBe("keyboard");
    expect(pickEngine(false, false)).toBe("record");
    expect(speechRecognition({ webkitSpeechRecognition: FakeRecognition })).toBe(FakeRecognition);
    expect(speechRecognition({})).toBeNull();
  });

  it("shows the words live and sends them as text when you stop talking", () => {
    const { result, onText } = setup();
    expect(result.current.engine).toBe("speech");
    act(() => result.current.toggle());
    const rec = FakeRecognition.last!;
    expect(rec.started && rec.lang === "en-GB" && rec.interimResults && !rec.continuous).toBe(true);
    expect(result.current.active).toBe(true);
    act(() => rec.hear(["play lofi", false]));
    expect(result.current.interim).toBe("play lofi");
    act(() => rec.hear(["play lofi on youtube", true]));
    act(() => rec.onend?.()); // the engine heard the end of the phrase
    expect(onText).toHaveBeenCalledWith("play lofi on youtube");
    expect(result.current.active).toBe(false);
  });

  it("a tap while listening sends what was heard so far", () => {
    const { result, onText } = setup();
    act(() => result.current.toggle());
    act(() => FakeRecognition.last!.hear(["pause", false]));
    act(() => result.current.toggle());
    expect(onText).toHaveBeenCalledWith("pause");
  });

  it("cancel throws the words away", () => {
    const { result, onText } = setup();
    act(() => result.current.toggle());
    act(() => FakeRecognition.last!.hear(["shut down the pc", false]));
    act(() => result.current.cancel());
    expect(onText).not.toHaveBeenCalled();
  });

  it("hold mode listens until the finger lifts", () => {
    const { result, onText } = setup({ mode: "hold" });
    act(() => result.current.holdStart());
    expect(FakeRecognition.last!.continuous).toBe(true);
    act(() => FakeRecognition.last!.hear(["next", true], [" episode", true]));
    act(() => result.current.holdEnd());
    expect(onText).toHaveBeenCalledWith("next episode");
  });

  it("an engine that refuses (some home-screen apps) hands over to the keyboard", () => {
    const { result, onProblem, onText } = setup();
    act(() => result.current.toggle());
    act(() => FakeRecognition.last!.onerror?.({ error: "service-not-allowed" }));
    act(() => FakeRecognition.last!.onend?.());
    expect(onProblem).toHaveBeenCalledWith(expect.stringMatching(/keyboard/));
    expect(result.current.engine).toBe("keyboard");
    expect(onText).not.toHaveBeenCalled();
  });

  it("nothing heard sends nothing, and a denied mic says so", () => {
    const { result, onProblem, onText } = setup();
    act(() => result.current.toggle());
    act(() => FakeRecognition.last!.onerror?.({ error: "not-allowed" }));
    act(() => FakeRecognition.last!.onend?.());
    expect(onProblem).toHaveBeenCalledWith(expect.stringMatching(/permission/i));
    expect(onText).not.toHaveBeenCalled();
    expect(result.current.engine).toBe("speech"); // a permission problem is not the engine's fault
  });

  it("a phone without the engine arms keyboard dictation instead", () => {
    const { result } = setup({ recognition: null });
    expect(result.current.engine).toBe("keyboard");
    act(() => result.current.arm());
    expect(result.current.armed).toBe(true);
    act(() => result.current.disarm());
    expect(result.current.armed).toBe(false);
  });

  it("a desktop browser with neither keeps the old recording path", () => {
    const { result } = setup({ recognition: null, touch: false });
    expect(result.current.engine).toBe("record");
  });

  it("does nothing while disconnected", () => {
    FakeRecognition.last = null;
    const { result } = setup({ disabled: true });
    act(() => result.current.toggle());
    expect(FakeRecognition.last).toBeNull();
    expect(result.current.active).toBe(false);
  });
});
