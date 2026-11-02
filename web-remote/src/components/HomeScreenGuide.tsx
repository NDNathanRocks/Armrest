import { APP_NAME } from "../brand";
import { Icon } from "./Icon";

/**
 * iPhone Safari only: how to get the remote onto the home screen. Safari and the home-screen app
 * keep separate storage, so the app pairs once more by itself (scan or code) after it is added.
 */
export function HomeScreenGuide({ paired, onDismiss }: { paired: boolean; onDismiss?: () => void }) {
  const steps = [
    <>
      Tap <b>Share</b> <span className="inline-block align-middle"><Icon name="share" size={16} /></span> at the bottom of
      Safari.
    </>,
    <>
      Choose <b>Add to Home Screen</b>, then <b>Add</b>.
    </>,
    <>
      Open <b>{APP_NAME}</b> from your home screen and tap <b>Scan the code on the TV</b> once.
    </>,
  ];
  return (
    <aside className="glass rise rounded-3xl p-5" aria-labelledby="home-guide-title">
      <div className="flex items-start justify-between gap-3">
        <h2 id="home-guide-title" className="text-base font-semibold">
          Put {APP_NAME} on your home screen
        </h2>
        {onDismiss && (
          <button type="button" onClick={onDismiss} aria-label="Hide these steps" className="press -m-2 min-h-11 min-w-11 text-zinc-400">
            ✕
          </button>
        )}
      </div>
      <p className="mt-1 text-sm text-zinc-400">
        {paired
          ? "It opens full screen like an app. The home-screen app has its own storage, so it pairs once more by itself."
          : "It opens full screen like an app, and you won't need the TV's QR again."}
      </p>
      <ol className="mt-4 space-y-3 text-sm">
        {steps.map((step, i) => (
          <li key={i} className="flex gap-3">
            <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-full bg-white/10 text-xs font-semibold">
              {i + 1}
            </span>
            <span className="pt-0.5">{step}</span>
          </li>
        ))}
      </ol>
    </aside>
  );
}
