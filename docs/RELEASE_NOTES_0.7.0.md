# Armrest 0.7.0

The ship-ready pass: the remote is simpler to use from the first tab, YouTube Music shows up in Now Playing, the
in-app QR scanner works on phones where it got stuck, and the phone can show the TV on its lock screen.

**Free preview:** 0.x versions stay free with no trial and no licence key.

## New and changed on the phone
- **Everything you need is on the Remote tab.** The *Type on the TV* box now sits under the touchpad, so you can
  type without changing tabs. The Keys tab keeps the special keys, F1-F12 and the browser shortcuts.
- **The mic is your keyboard's dictation.** Tap the mic, the keyboard opens, tap its own mic and speak; the command
  is sent 1.5 seconds after your words stop. The 0.6.0 in-browser speech engine is gone (dictation proved better on
  the sofa). A desktop browser, which has no dictation key, still records for the PC.
- **As many buttons as you like.** The Keys tab's *My buttons* grid grows: tap **Add** for a new slot (up to 64),
  and removing a button takes its slot away. Favourites on the Remote tab stay at eight. You can now keep up to 100
  buttons of your own.
- **Touchpad.** The Left click and Double click buttons are gone: tap the pad to click. **Hold Scroll up / down**
  to keep scrolling slowly. The pad is taller.
- **Lock-screen controls (Settings, off by default).** Your phone's lock screen shows what the TV is playing, with
  play / pause, next and previous. It works by playing silence, so it pauses music on the phone and uses more
  battery; that is why it is a switch. Appears only on browsers that support it.
- **Scanning the TV's QR inside the app works on more phones.** Some Android phones offer a built-in barcode reader
  that never finds anything; the scanner now uses its own decoder everywhere, at a higher resolution.

## Fixed on the PC
- **YouTube Music is detected.** Now Playing, the seek bar and play / pause follow a YouTube Music tab: its hidden
  player reports no size and often no length, so the state now comes from the player bar.
- **Faster state updates on pages with ads.** Child frames are checked together with one short deadline instead of
  one after another; a page with several ad frames no longer slows every update by seconds.

## Good to know
- The phone app and the PC app update separately. Everything above except the YouTube Music fix is on the phone
  and reaches you with the next page load; the PC fixes need this installer.
- The installer isn't code-signed, so Windows SmartScreen may warn on first run ("More info" → "Run anyway").

## Files
| File | SHA-256 |
|---|---|
| `Armrest-Setup.exe` (recommended) | *(filled in when the release is built)* |
| `Armrest-portable-0.7.0.zip` | *(filled in when the release is built)* |

## Checked before release
See plan.md section 16 *Status* for the test results.
