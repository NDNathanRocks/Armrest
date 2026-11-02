# Armrest 0.6.0

A faster mic, a home-screen app for iPhone that can pair, more buttons, and Armrest now reaches beyond the TV
browser: Spotify and other media apps, links shared from your phone, and the PC's own power.

**Free preview:** 0.x versions stay free with no trial and no licence key.

## New
- **A much faster mic.** The phone's own speech engine (the one behind keyboard dictation) now does the listening.
  Your words appear in the command bar as you speak and go to the TV the moment you stop. No Send tap, no upload, no
  wait for the PC. Where a phone can't do that (some home-screen apps, Firefox), the mic opens the keyboard: tap its
  mic, speak, and the command is sent 1.5 seconds after your words stop. Hold-to-talk still works.
- **iPhone home screen.** An iPhone keeps a home-screen app's storage apart from Safari, so a pairing made in Safari
  never reached it. Now the app pairs itself:
  - **Scan the code on the TV**: a camera opens inside the app.
  - **Or type the code** shown under the QR on the TV (like `K7QM-4XPA`). A code lasts 10 minutes and works once.
  - Safari on an iPhone shows the three steps to put Armrest on your home screen.
  - Settings now has **Add another TV**, which works the same way.
- **Share to TV (Android).** In YouTube, Netflix, a browser or any app: Share → Armrest, and the link opens on the
  TV. On any phone you can also paste a link into the new box at the top of the **Saved** tab.
- **Other media apps.** When the TV browser isn't playing, Now Playing shows what Spotify, VLC, Media Player and
  other apps are playing (title, artist and app name). Play / pause / next / previous go to that app, and the
  timeline seeks it where the app allows.
- **PC power.** Settings → PC power: **Lock**, **Sleep** and **Shut down**. Shut down waits a minute, and **Cancel a
  shutdown** stops it. You can also say "lock the PC", "put the PC to sleep", "shut down the PC" and "cancel the
  shutdown". Sleep and Shut down ask first, because a sleeping PC can't be woken from the phone. Guest phones don't
  get these.
- **8 more buttons.** The Keys tab has its own **My buttons** grid above the keyboard. You fill it like
  Favourites, and it is saved separately.
- **Buttons that run a command.** Besides keyboard shortcuts, a button of your own can now hold a command, like
  "volume 30 and fullscreen" or "open my bookmark netflix". It works in both grids.
- **A backup AI brain.** With a free Groq key (Settings → Groq key, the same key speech already used), commands go
  to Groq when Gemini is busy or rate-limited, before falling back to this PC's own model. "Understand commands
  with → Groq first" makes it the first choice.

## Good to know
- **The phone and the PC update separately.** The new buttons appear once the PC runs 0.6.0. Before that, the phone
  hides them.
- **Typed codes need the updated cloud relay.** Until it is deployed, the TV shows only the QR. Scanning inside the
  app works without it.
- **Voice privacy:** the phone's speech engine is Apple's or Google's. Your words go to them (as they do with keyboard
  dictation), then to the TV as text. The PC no longer receives recordings from phones that have the engine.
- **Share to TV is Android only:** iPhone has no share-to-web-app menu. Copy the link and use the Saved tab's box.
- **Media apps vary:** some don't report their position or allow seeking, and then the timeline only shows progress.
- The installer isn't code-signed, so Windows SmartScreen may warn on first run ("More info" → "Run anyway").

## Files
| File | SHA-256 |
|---|---|
| `Armrest-Setup.exe` (recommended) | *(filled in when the release is built)* |
| `Armrest-portable-0.6.0.zip` | *(filled in when the release is built)* |

## Checked before release
See plan.md section 15 *Status* for the test results.
