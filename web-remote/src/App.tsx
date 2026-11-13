import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { ConnectionBadge } from "./components/ConnectionBadge";
import { FriendsBar } from "./components/FriendsBar";
import { CommandBar } from "./components/CommandBar";
import { Favorites } from "./components/Favorites";
import { Icon } from "./components/Icon";
import { KeyPad } from "./components/KeyPad";
import { LogPanel } from "./components/LogPanel";
import { NowPlayingCard } from "./components/NowPlayingCard";
import { QRScanner, readPairParams, stripPairParams } from "./components/QRScanner";
import type { PairParams } from "./connection/roomConnection";
import { SettingsSheet } from "./components/SettingsSheet";
import { APP_NAME } from "./brand";
import { AppsRow } from "./components/AppsRow";
import { BookmarkList } from "./components/BookmarkList";
import { QuestionCard } from "./components/QuestionCard";
import { Suggestions } from "./components/Suggestions";
import { TimerList } from "./components/TimerList";
import { Toasts } from "./components/Toasts";
import { TouchPad } from "./components/TouchPad";
import { TypeBox } from "./components/TypeBox";
import { Transport } from "./components/Transport";
import { VolumeSlider } from "./components/VolumeSlider";
import { HomeScreenGuide } from "./components/HomeScreenGuide";
import { OpenLink } from "./components/OpenLink";
import { useRoomSocket } from "./hooks/useRoomSocket";
import { useLockScreen } from "./hooks/useLockScreen";
import { useSpeech } from "./hooks/useSpeech";
import { loadMicMode, saveMicMode, type MicMode } from "./hooks/useVoice";
import { selectDevices } from "./state/roomReducer";
import { resolveEndpoint } from "./utils/config";
import { loadFavorites, saveFavorites, type Fav, type Grid } from "./utils/favorites";
import { tap } from "./utils/haptics";
import { dismissGuide, guideDismissed, wantsHomeScreenGuide } from "./utils/install";
import { clearSharedLink, linkHost, readSharedLink } from "./utils/links";
import { loadRecents, rememberCommand } from "./utils/recents";
import { browserPairingStorage, type Pairing } from "./utils/storage";
import { forgetTv, loadTvs, rememberTv, renameTv, type Tv } from "./utils/tvs";
import { APPS_SINCE, POWER_SINCE, SHARE_SINCE, SLIDERS_SINCE, versionAtLeast } from "./utils/version";

type Tab = "remote" | "saved" | "keys";
const TABS: readonly { id: Tab; label: string; aria?: string }[] = [
  { id: "remote", label: "Remote" },
  { id: "saved", label: "Saved" },
  { id: "keys", label: "Keys", aria: "Touchpad & keys" },
];

const RELEASES_URL = "https://github.com/NDNathanRocks/couch-jarvis/releases/latest";

/** How long the mic stays open for the answer to a spoken question. */
const ASK_LISTEN_MS = 8000;

export default function App() {
  const endpoint = useMemo(
    () => resolveEndpoint(import.meta.env.VITE_RELAY_WS_URL as string | undefined, window.location),
    [],
  );
  const pairParams = useMemo(() => readPairParams(window.location.search), []);
  const [self, setSelf] = useState<Pairing | null>(null);
  const [tab, setTab] = useState<Tab>("remote");
  const [logOpen, setLogOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [recents, setRecents] = useState<string[]>(loadRecents);
  const [micMode, setMicMode] = useState<MicMode>(loadMicMode);
  const [favorites, setFavorites] = useState<(string | null)[]>(() => loadFavorites("remote"));
  const [keyFavorites, setKeyFavorites] = useState<(string | null)[]>(() => loadFavorites("keys"));
  const [dismissedUpdate, setDismissedUpdate] = useState<string | null>(null);
  const [tvs, setTvs] = useState<Tv[]>(loadTvs);
  // Pairing from inside the app (scanned QR or typed code) is under way.
  const [pairingInApp, setPairingInApp] = useState(false);
  // A link from Android's share menu (/share?url=...), opened on the TV once connected.
  const [shared, setShared] = useState<string | null>(() => readSharedLink(window.location));
  const [showGuide, setShowGuide] = useState(() => wantsHomeScreenGuide() && !guideDismissed());

  const { view, actions } = useRoomSocket({
    endpoint,
    pairParams,
    onPaired: (pairing) => {
      setSelf(pairing);
      setPairingInApp(false);
      setTvs(rememberTv(pairing)); // another TV's QR adds it; the others are kept
      stripPairParams(); // the room secret has been exchanged for a token: remove it from the URL
    },
    onRestored: (pairing) => {
      setSelf(pairing);
      setPairingInApp(false); // e.g. a typed code failed and the TV we had reconnects
      setTvs(rememberTv(pairing));
    },
    onUnpaired: () => {
      setSelf(null);
      setPairingInApp(false);
    },
  });

  const connected = view.connection === "online";
  const pairingNow = pairingInApp && view.connection !== "idle"; // a refused code ends as "idle"
  // Paired = we hold a token, i.e. either this session paired or a saved pairing is reconnecting.
  const paired = self !== null || (pairParams === null && !pairingNow && view.connection !== "idle");
  const progress = Object.values(view.pending).at(-1) ?? null;
  const lastIsError = view.log.at(-1)?.level === "error";
  // A guest phone (set on the PC) gets media, volume and voice: no touchpad, keys or PC settings.
  const guest = view.room.devices.find((d) => d.device_id === self?.deviceId)?.role === "guest";
  const inputAllowed = view.room.remote_input && !guest;
  // The phone app and the PC app update separately: only show sliders a PC this old can answer.
  const canSlide = versionAtLeast(view.room.daemon_version, SLIDERS_SINCE);
  const hasApps = versionAtLeast(view.room.daemon_version, APPS_SINCE);
  const canShare = versionAtLeast(view.room.daemon_version, SHARE_SINCE);
  const canPower = versionAtLeast(view.room.daemon_version, POWER_SINCE) && !guest;
  const voice = useSpeech({
    mode: micMode,
    disabled: !connected,
    onRecording: (recording) => actions.sendAudio(recording),
    onProblem: actions.notify,
  });
  const lockScreen = useLockScreen({
    playing: view.room.now_playing,
    connected,
    send: (action) => actions.sendButton(action),
  });
  const pairWith = (params: PairParams) => {
    setPairingInApp(true);
    actions.pairWith(params);
  };
  const pairWithCode = (code: string) => {
    setPairingInApp(true);
    actions.pairWithCode(code);
  };
  const openLink = (url: string) => {
    tap();
    if (actions.sendButton("open_url", { url })) actions.notify(`Opening ${linkHost(url)} on the TV`);
  };

  // A shared link waits for the connection, then opens once (a reload must not open it again).
  const shareSent = useRef(false);
  useEffect(() => {
    clearSharedLink();
  }, []);
  useEffect(() => {
    if (!shared || shareSent.current || !connected || !view.room.daemon_version) return;
    shareSent.current = true;
    if (canShare) openLink(shared);
    else actions.notify(`Update ${APP_NAME} on the PC to 0.6.0 or later to open shared links.`);
    setTimeout(() => setShared(null), 0);
  });
  const chooseMic = (next: MicMode) => {
    setMicMode(next);
    saveMicMode(next);
  };
  const sendCommand = (text: string) => {
    tap();
    return actions.sendText(text);
  };
  const sendTyped = (text: string) => {
    const sent = sendCommand(text);
    if (sent) setRecents(rememberCommand(text));
    return sent;
  };
  const sendFavorite = (fav: Fav) => {
    const { send } = fav;
    if (send.kind === "action") actions.sendButton(send.action);
    else if (send.kind === "key") actions.sendKey(send.key, send.mods);
    else actions.sendText(send.text);
  };
  const changeGrid = (grid: Grid) => (next: (string | null)[]) => {
    (grid === "keys" ? setKeyFavorites : setFavorites)(next);
    saveFavorites(next, grid);
  };
  // Another TV: make it the active pairing and start again (the connection only knows one).
  const switchTv = async (roomId: string) => {
    const target = tvs.find((t) => t.pairing.roomId === roomId);
    if (!target || roomId === self?.roomId) return;
    await browserPairingStorage.save(target.pairing);
    window.location.reload();
  };
  // Forget only this TV; with others left, switch to one of them instead of unpairing.
  const forgetThisTv = async () => {
    const rest = self ? forgetTv(self.roomId) : tvs;
    setTvs(rest);
    const next = rest[0];
    if (next) {
      await browserPairingStorage.save(next.pairing);
      window.location.reload();
    } else {
      await actions.unpair();
    }
  };
  // Slide the new tab in from the side it sits on.
  const tabIndex = TABS.findIndex((t) => t.id === tab);
  const [lastIndex, setLastIndex] = useState(tabIndex);
  const from = tabIndex >= lastIndex ? "18px" : "-18px";
  const chooseTab = (next: Tab) => {
    setLastIndex(tabIndex);
    setTab(next);
  };

  // A spoken command that ended in a question: let the answer be spoken too. Wait for the TV to
  // finish asking, or the mic would hear the question, and stop listening if nothing is said.
  const askId = view.ask?.listen ? view.ask.id : null;
  const askLength = view.ask?.question.length ?? 0;
  const voiceRef = useRef(voice);
  useEffect(() => {
    voiceRef.current = voice; // always the latest, without reading a ref while rendering
  });
  useEffect(() => {
    if (askId === null) return;
    const open = setTimeout(() => {
      // the keyboard's dictation can only be opened by a tap, so it waits for one
      const v = voiceRef.current;
      if (v.supported && v.engine === "record" && !v.active) v.toggle();
    }, 1500 + askLength * 70);
    const close = setTimeout(() => {
      if (voiceRef.current.active) voiceRef.current.toggle(); // sends what was said
    }, 1500 + askLength * 70 + ASK_LISTEN_MS);
    return () => {
      clearTimeout(open);
      clearTimeout(close);
    };
  }, [askId, askLength]);

  const update = view.room.update_available;
  const licence = view.room.license; // absent: paid, or a PC older than 1.0.0
  const inputOff = (
    <p className="glass rounded-2xl p-4 text-sm text-zinc-400">
      {guest
        ? "This phone is a guest: the touchpad and keyboard are for the TV owner's phones."
        : "Touchpad and keyboard are turned off on the PC (CJ_REMOTE_INPUT=false)."}
    </p>
  );

  return (
    <main className="mx-auto flex min-h-full w-full max-w-md flex-col gap-4 px-4 pb-[calc(env(safe-area-inset-bottom)+6rem)] pt-[calc(env(safe-area-inset-top)+1rem)]">
      <header className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <h1 className="whitespace-nowrap bg-gradient-to-r from-white to-accent bg-clip-text text-xl font-bold tracking-tight text-transparent">{APP_NAME}</h1>
        <div className="flex items-center gap-2">
          {paired && tvs.length > 1 && (
            <label className="glass-btn flex min-h-11 items-center rounded-full px-3 text-xs">
              <span className="sr-only">TV</span>
              <select
                value={self?.roomId ?? ""}
                onChange={(e) => void switchTv(e.target.value)}
                className="max-w-28 bg-transparent font-semibold outline-none"
              >
                {tvs.map((t) => (
                  <option key={t.pairing.roomId} value={t.pairing.roomId}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          {paired && (
            <button type="button" onClick={() => setSettingsOpen(true)} aria-label="Settings" className="press glass-btn min-h-11 min-w-11">
              <Icon name="gear" size={18} />
            </button>
          )}
          <button
            type="button"
            onClick={() => setLogOpen(true)}
            aria-label={lastIsError ? "Log (there was a problem)" : "Log"}
            className="press glass-btn relative min-h-11 min-w-11 px-3 text-xs"
          >
            Log
            {lastIsError && <span aria-hidden className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-rose-500" />}
          </button>
          <ConnectionBadge view={view} transport={endpoint.transport} />
        </div>
      </header>

      <QRScanner
        connection={view.connection}
        hasPairParams={pairParams !== null}
        paired={paired}
        pairing={pairingNow}
        onScan={pairWith}
        onCode={pairWithCode}
      />

      {showGuide && (
        <HomeScreenGuide
          paired={paired}
          onDismiss={() => {
            dismissGuide();
            setShowGuide(false);
          }}
        />
      )}

      {shared && (
        <aside className="glass rise flex items-center gap-3 rounded-2xl p-3 text-sm" role="status" aria-label="Shared link">
          <Icon name="link" size={18} />
          <span className="min-w-0 flex-1 truncate">
            {paired ? "Opening on the TV: " : "Pair this phone to open "}
            <b>{linkHost(shared)}</b>
          </span>
        </aside>
      )}

      {paired && view.connection !== "rejected" && (
        <>
          {update && update !== dismissedUpdate && (
            <aside className="glass rise flex items-center gap-3 rounded-2xl p-3 text-sm" aria-label="Update available">
              <Icon name="download" size={18} />
              <span className="flex-1">
                {APP_NAME} <b>{update}</b> is out.{" "}
                <a href={RELEASES_URL} target="_blank" rel="noopener noreferrer" className="font-semibold text-accent underline underline-offset-2">
                  Get it
                </a>
              </span>
              <button type="button" aria-label="Dismiss update notice" onClick={() => setDismissedUpdate(update)} className="press min-h-11 min-w-11 text-zinc-400">
                ✕
              </button>
            </aside>
          )}

          {licence && (
            // only a 1.0.0+ PC sends `license`, so Buy never reaches a PC that cannot handle it
            <aside
              className={`glass rise flex items-center gap-3 rounded-2xl p-3 text-sm ${licence.status === "expired" ? "ring-1 ring-rose-400/60" : ""}`}
              aria-label="Licence"
              role={licence.status === "expired" ? "alert" : undefined}
            >
              <span className="flex-1">
                {licence.status === "expired" ? (
                  <>Your free {APP_NAME} trial has ended.</>
                ) : (
                  <>
                    Free trial: <b>{licence.days_left ?? "a few"}</b> {licence.days_left === 1 ? "day" : "days"} left.
                  </>
                )}
              </span>
              <button
                type="button"
                disabled={!connected}
                onClick={() => actions.sendButton("buy")}
                className="press min-h-11 rounded-full bg-accent px-4 font-semibold text-zinc-950"
              >
                Buy
              </button>
            </aside>
          )}

          <nav role="tablist" aria-label="Views" className="glass relative grid grid-cols-3 rounded-full p-1">
            <span
              aria-hidden
              className="tab-pill absolute inset-y-1 left-1 w-[calc((100%-0.5rem)/3)] rounded-full bg-white/15 shadow-inner"
              style={{ transform: `translateX(${tabIndex * 100}%)` }}
            />
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-label={t.aria}
                aria-selected={tab === t.id}
                onClick={() => chooseTab(t.id)}
                className={`relative min-h-11 rounded-full text-sm font-semibold transition-colors ${tab === t.id ? "text-white" : "text-muted"}`}
              >
                {t.label}
              </button>
            ))}
          </nav>

          <div key={tab} className="view flex flex-col gap-4" style={{ "--from": from } as CSSProperties}>
            {tab === "remote" && (
              <>
                {view.ask && (
                  <QuestionCard
                    ask={view.ask}
                    disabled={!connected}
                    listening={voice.active}
                    onAnswer={(choice) => {
                      actions.dismissAsk();
                      sendCommand(choice);
                    }}
                    onDismiss={actions.dismissAsk}
                  />
                )}
                <NowPlayingCard
                  playing={view.room.now_playing}
                  pending={progress}
                  onSeek={canSlide && connected ? (s) => actions.sendSlider("seek_to", s) : undefined}
                />
                {!view.room.now_playing && <Suggestions disabled={!connected} recents={recents} onSend={sendCommand} />}
                <Transport
                  playing={view.room.now_playing?.is_playing === true}
                  disabled={!connected}
                  onPress={(action) => {
                    tap();
                    actions.sendButton(action);
                  }}
                />
                {canSlide ? (
                  <VolumeSlider
                    level={view.room.volume}
                    muted={view.room.muted}
                    disabled={!connected}
                    onLevel={(level) => actions.sendSlider("volume_set", level)}
                    onToggleMute={() => actions.sendButton("mute")}
                  />
                ) : (
                  <div className="glass rise grid grid-cols-3 gap-2 rounded-[28px] p-2" role="group" aria-label="Volume">
                    {(
                      [
                        ["vol_down", "Volume down", "speakerLow"],
                        ["mute", "Mute", "speakerMute"],
                        ["vol_up", "Volume up", "speakerHigh"],
                      ] as const
                    ).map(([action, label, icon]) => (
                      <button key={action} type="button" disabled={!connected} aria-label={label} onClick={() => actions.sendButton(action)} className="press glass-btn min-h-12">
                        <Icon name={icon} />
                      </button>
                    ))}
                  </div>
                )}
                {hasApps && <AppsRow disabled={!connected} onOpen={sendCommand} />}
                <Favorites slots={favorites} connected={connected} keysAllowed={inputAllowed} daemonVersion={view.room.daemon_version} onSend={sendFavorite} onChange={changeGrid("remote")} />
                {inputAllowed ? (
                  <>
                    <TouchPad disabled={!connected} onPointer={(e) => actions.sendPointer(e)} />
                    <TypeBox title="Keyboard" disabled={!connected} onKey={actions.sendKey} onText={actions.sendTyped} />
                  </>
                ) : (
                  inputOff
                )}
                <TimerList timers={view.room.timers} />
                <FriendsBar devices={selectDevices(view)} selfId={self?.deviceId ?? null} />
              </>
            )}

            {tab === "saved" && (
              <>
                {canShare && <OpenLink disabled={!connected} onOpen={openLink} />}
                <BookmarkList items={view.room.bookmarks} disabled={!connected} onCommand={sendCommand} />
              </>
            )}

            {tab === "keys" && (
              <>
                {/* more buttons of your own: the same choices as Favourites, kept separately */}
                <Favorites
                  title="My buttons"
                  growable
                  slots={keyFavorites}
                  connected={connected}
                  keysAllowed={inputAllowed}
                  daemonVersion={view.room.daemon_version}
                  onSend={sendFavorite}
                  onChange={changeGrid("keys")}
                />
                {inputAllowed ? <KeyPad disabled={!connected} onKey={actions.sendKey} /> : inputOff}
              </>
            )}
          </div>
        </>
      )}
      <Toasts toasts={view.toasts} onDismiss={actions.dismiss} onSuggest={sendCommand} />
      {paired && view.connection !== "rejected" && tab === "remote" && (
        <CommandBar disabled={!connected} voice={voice} micMode={micMode} onSend={sendTyped} />
      )}
      {settingsOpen && (
        <SettingsSheet
          voice={view.room.voice}
          adblock={view.room.browser.adblock}
          micMode={micMode}
          micModeApplies={voice.engine === "record"}
          version={view.room.daemon_version}
          disabled={!connected}
          onCommand={sendCommand}
          onMicMode={chooseMic}
          onUnpair={() => {
            setSettingsOpen(false);
            void forgetThisTv();
          }}
          tvs={tvs}
          currentRoom={self?.roomId ?? null}
          guest={guest}
          onRenameTv={(roomId, label) => setTvs(renameTv(roomId, label))}
          onPower={canPower ? (action) => actions.sendButton(action) : undefined}
          onScan={(params) => {
            setSettingsOpen(false);
            pairWith(params);
          }}
          onCode={(code) => {
            setSettingsOpen(false);
            pairWithCode(code);
          }}
          lockScreen={lockScreen.supported ? { enabled: lockScreen.enabled, choose: lockScreen.choose } : undefined}
          onClose={() => setSettingsOpen(false)}
        />
      )}
      {logOpen && <LogPanel entries={view.log} onClear={actions.clearLog} onClose={() => setLogOpen(false)} />}
    </main>
  );
}
