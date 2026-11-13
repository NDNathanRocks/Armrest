import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { pickEngine, useSpeech } from "../hooks/useSpeech";

const setup = (over: Partial<Parameters<typeof useSpeech>[0]> = {}) =>
  renderHook(() =>
    useSpeech({
      mode: "tap",
      disabled: false,
      onRecording: vi.fn(),
      onProblem: vi.fn(),
      touch: true,
      ...over,
    }),
  );

describe("useSpeech", () => {
  it("a phone uses its keyboard's dictation; a desktop browser records for the PC", () => {
    expect(pickEngine(true)).toBe("keyboard");
    expect(pickEngine(false)).toBe("record");
    expect(setup().result.current.engine).toBe("keyboard");
    expect(setup({ touch: false }).result.current.engine).toBe("record");
  });

  it("the mic arms keyboard dictation and a second tap or cancel disarms it", () => {
    const { result } = setup();
    expect(result.current.supported).toBe(true);
    act(() => result.current.toggle());
    expect(result.current.armed).toBe(true);
    act(() => result.current.toggle());
    expect(result.current.armed).toBe(false);
    act(() => result.current.arm());
    act(() => result.current.cancel());
    expect(result.current.armed).toBe(false);
    act(() => result.current.holdStart()); // hold mode has no meaning here: it arms like a tap
    expect(result.current.armed).toBe(true);
  });

  it("the keyboard engine never records anything", () => {
    const { result } = setup();
    expect(result.current.active).toBe(false);
    expect(result.current.elapsedMs).toBe(0);
  });
});
