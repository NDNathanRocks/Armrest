import { describe, expect, it } from "vitest";
import { pairParamsFromScan } from "../components/PairPanel";
import { formatCodeInput } from "../components/PairPanel";
import { isIos, isStandalone, wantsHomeScreenGuide } from "../utils/install";
import { findLink, linkHost, readSharedLink } from "../utils/links";

describe("shared links", () => {
  it("finds the address wherever the app put it", () => {
    expect(findLink(null, "Watch this! https://youtu.be/dQw4w9WgXcQ?si=x.", "Rick")).toBe("https://youtu.be/dQw4w9WgXcQ?si=x");
    expect(findLink("https://www.netflix.com/title/80057281")).toBe("https://www.netflix.com/title/80057281");
    expect(findLink("", "no link here")).toBeNull();
    expect(findLink("javascript:alert(1)")).toBeNull();
    expect(findLink("https://user:pw@example.com/")).toBeNull();
  });

  it("reads Android's share menu only on /share", () => {
    expect(readSharedLink({ pathname: "/share", search: "?title=Song&text=https%3A%2F%2Fyoutu.be%2Fabc" })).toBe("https://youtu.be/abc");
    expect(readSharedLink({ pathname: "/share", search: "?url=https%3A%2F%2Fexample.com%2Fa" })).toBe("https://example.com/a");
    expect(readSharedLink({ pathname: "/", search: "?url=https%3A%2F%2Fexample.com" })).toBeNull();
    expect(linkHost("https://www.youtube.com/watch?v=1")).toBe("youtube.com");
  });
});

describe("in-app pairing", () => {
  it("takes only the TV's pairing link from a scanned QR", () => {
    expect(pairParamsFromScan("https://armrest-app.pages.dev/?room=room-abcdef12&secret=qr-secret-value-123456")).toEqual({
      roomId: "room-abcdef12",
      secret: "qr-secret-value-123456",
    });
    expect(pairParamsFromScan("https://example.com/menu")).toBeNull();
    expect(pairParamsFromScan("WIFI:S:home;P:pw;;")).toBeNull();
  });

  it("formats the code box like the TV shows it", () => {
    expect(formatCodeInput("k7")).toBe("K7");
    expect(formatCodeInput("k7qm4x")).toBe("K7QM-4X");
    expect(formatCodeInput("K7QM-4XPA-EXTRA")).toBe("K7QM-4XPA");
  });
});

describe("home screen guide", () => {
  const iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 Version/26.0 Mobile/15E148 Safari/604.1";
  const ipad = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/26.0 Safari/605.1.15";
  const noMedia = { matchMedia: () => ({ matches: false }) as unknown as MediaQueryList };

  it("is for iPhone and iPad Safari tabs, not the home-screen app or other phones", () => {
    expect(isIos({ userAgent: iphone })).toBe(true);
    expect(isIos({ userAgent: ipad, maxTouchPoints: 5 })).toBe(true); // iPadOS says it is a Mac
    expect(isIos({ userAgent: ipad, maxTouchPoints: 0 })).toBe(false); // a real Mac
    expect(isIos({ userAgent: "Mozilla/5.0 (Linux; Android 15; Pixel 9)" })).toBe(false);
    expect(isStandalone({ userAgent: iphone, standalone: true }, noMedia)).toBe(true);
    expect(isStandalone({ userAgent: iphone }, noMedia)).toBe(false);
    expect(wantsHomeScreenGuide({ userAgent: iphone, standalone: true })).toBe(false);
  });
});
