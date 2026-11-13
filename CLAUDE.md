# Project Specification: "AegisRemote / CouchJarvis" — Hybrid AWS Cloud-to-Edge Multi-Device Voice & Vision PC Agent

## 1. System Overview & Core Objectives
Build a production-grade, fault-tolerant, hybrid cloud-to-edge voice and GUI automation system that allows multiple smartphones to control a Windows PC (connected to a TV) from anywhere without requiring local Wi-Fi IP configuration or user accounts.

### Key Architectural Pillars:
1. **Zero-Account QR Code Pairing & Multi-Phone Persistence:**
   - The PC daemon generates a persistent `room_id` and cryptographic `room_secret`, rendering a pairable QR code on the TV (via a lightweight PySide6 HUD overlay and terminal/tray output).
   - Anyone (me or my friends) can scan the QR code to open the deployed Mobile Web App (PWA).
   - Scanning issues a long-lived `device_token` stored in the phone's `localStorage` / `IndexedDB`. Closing the phone browser or locking the phone never loses the pairing; reopening the app auto-reconnects to the room and syncs live TV state across all connected phones simultaneously.
2. **AWS Serverless Control Plane (100% Always-Free Tier + IaC):**
   - Uses **AWS API Gateway (WebSocket API)**, **AWS Lambda (Python 3.12)**, and **Amazon DynamoDB** (with TTL) to relay commands, audio metadata, and real-time room state between multiple phones and the PC daemon.
   - Provisioned cleanly using **AWS SAM (`template.yaml`) or Terraform** so the entire cloud infrastructure deploys in one CLI command (`sam deploy` or `terraform apply`).
   - Also support a **Local LAN Direct WebSocket Mode** as an automatic fallback if internet is down.
3. **Production-Grade AI Agent (LangGraph Plan-Act-Verify Loop):**
   - Speech-to-Text via local GPU **`faster-whisper`** (with Groq Free Tier Whisper API fallback).
   - Stateful **LangGraph** workflow (`IntentRouter -> DOMExecutor -> VisionFallback -> PostActionVerifier -> RecoveryNode`).
   - Uses deterministic **Playwright over Chrome DevTools Protocol (CDP)** for Microsoft Edge tab/media control, seamlessly falling back to **Vision-Language Model (VLM) UI Grounding** (`Ollama qwen2.5vl:7b` or `Gemini 2.5 Flash Free Tier`) + DPI-aware **`PyAutoGUI`** when ad overlays or cross-origin iframes block DOM actions.
4. **Hardened Durability ("Never Breaks on the Sofa"):**
   - Self-healing Watchdog that monitors the Microsoft Edge CDP port (`9222`) and auto-relaunches Edge with a persistent TV profile (`--user-data-dir`) if closed or crashed.
   - `asyncio.PriorityQueue` command serialization with idempotency keys so multiple friends pressing buttons simultaneously never cause race conditions.
   - Structured JSONL / OpenTelemetry-compatible execution telemetry logging latency, token usage, and DOM vs. Vision fallback rates.

---

## 2. Repository layout (as built; `docs/DEVELOPING.md` has the full map)
```text
couch-jarvis/                       # GitHub repo name kept for the update check's redirects (plan 14.2 #4b)
├-- infra/                          # AWS SAM: template.yaml + lambdas/ (connect, disconnect, relay_router, spend_guard, common/)
├-- pc-daemon/                      # The Windows app (Python 3.12): main.py, service.py, contracts.py (wire contracts, single
│                                   #   source of truth), agent/, executors/, control/ (Control Center), hud/, llm/, voice/,
│                                   #   licensing.py, room.py, lan_auth.py, pair_codes.py, media_sessions.py, watchdog.py
├-- web-remote/                     # The phone app (Vite + React 19 + Tailwind 4), hosted on Cloudflare Pages (armrest-app)
│   ├-- src/App.tsx                 # Remote / Saved / Keys tabs; CommandBar dock; Settings sheet
│   ├-- src/components/             # TouchPad, TypeBox, KeyPad, Favorites, PairPanel (in-app QR scanner + typed code) ...
│   ├-- src/hooks/                  # useRoomSocket, useSpeech (keyboard dictation / desktop recording), useLockScreen
│   └-- public/                     # manifest.json, _headers (CSP), legal pages rendered by scripts/legal_pages.py
├-- shared/contracts/               # JSON Schema exported from contracts.py (web-remote/src/contracts.gen.ts is generated)
├-- installer/                      # PyInstaller spec, Inno Setup (Armrest.iss), build.ps1, build_msix.ps1 + msix/AppxManifest.xml
├-- scripts/                        # export_contracts, legal_pages, license_keys, licenses (gate), test_installer_upgrade.ps1 ...
├-- tests/                          # daemon/ and infra/ (pytest, quick), integration/ (real Edge), e2e/ (real browser + daemon)
└-- docs/                           # INSTALL, COMMANDS, DEVELOPING, STORE_LISTING, legal drafts, RELEASE_NOTES_<version>
```
Section 1 above is the original brief; where it and the code differ (Vercel, `.env` names, module names), the code and
`docs/DEVELOPING.md` are right.

## Release and update rules (binding; full text in `plan.md` section 12)
- **One version:** bump `pc-daemon/version.py` (semver); `installer/build.ps1` and `web-remote/package.json` follow it.
- **Installers update in place:** never change the Inno `AppId`; a user must never need to uninstall first. An update never
  touches `%APPDATA%\Armrest\` (or `%APPDATA%\CouchJarvis\` before the 0.5.0 move: `config.env`, `room.json`, tokens)
  or the Edge TV profile.
- **Upgrade test before every tag:** install the previous published version, install the candidate over it, check settings and
  `room.json` are untouched.
- **The phone app and the PC app ship separately:** keep changes backward compatible within a protocol version and hide new
  controls on an older PC (`daemon_version`). Redeploy the phone app to Cloudflare Pages after UI commits (Vercel is gone).
- **Secrets are per install:** room id/secret/PC key are generated on the user's PC and never shipped; builds fail if one is bundled.
- **Ask the user first** before any push, tag, production deploy or other outward-facing action.

## Where to resume
Read `plan.md` section 16 first (the 0.7.0 ship-ready pass: what changed, what was verified, what is left for the
user), then section 14 (current state, the ordered to-do list, the rename plan and the pricing plan). Keep them up to
date when work lands.

## Working notes that cost real time before
- Installer tests only through `scripts/test_installer_upgrade.ps1` (it sandboxes APPDATA); check for and kill any
  leftover `unins*` process afterwards. Back up `room.json` first.
- Edit files with the Edit/Write tools or a small Python script. Bash heredocs here break on apostrophes and backslashes.
- A probe that launches Edge with a throwaway `--user-data-dir` must `taskkill /T` it: Edge leaves dozens of processes.
