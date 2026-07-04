# Running CardPilot on an Android phone

CardPilot is a PWA over a local FastAPI server, so there are two good ways to
get it on your phone — and one of them keeps it running **entirely on the
phone**, no computer needed.

## Option A — Fully on-device with Termux (recommended)

The whole app (backend + UI + your data) lives and runs on the phone. This is
the truest form of local-first: your financial data never touches another
machine, and `http://localhost` is a secure context so the PWA installs with
full offline support.

1. **Install Termux from F-Droid** (https://f-droid.org/packages/com.termux/ —
   the Play Store build is outdated and unmaintained).
2. In Termux:
   ```bash
   pkg update && pkg install python git nodejs
   git clone https://github.com/madhurmishra9/CardPilot
   cd CardPilot
   pip install -r backend/requirements.txt
   (cd frontend && npm install && npm run build)   # one-time UI build
   cd backend && uvicorn app.main:app --port 8000
   ```
3. Open **Chrome → http://localhost:8000** → menu → **Add to Home screen /
   Install app**. CardPilot now opens full-screen like a native app.

### Keeping it running

- **While using it:** run `termux-wake-lock` once in Termux (and
  `pkg install termux-api`); this stops Android from killing the server while
  the screen is off. Also exclude Termux from battery optimization
  (Settings → Apps → Termux → Battery → Unrestricted).
- **Start on boot:** install **Termux:Boot** (also from F-Droid), open it once,
  then create `~/.termux/boot/cardpilot.sh`:
  ```bash
  #!/data/data/com.termux/files/usr/bin/sh
  termux-wake-lock
  cd ~/CardPilot/backend
  CARDPILOT_ENABLE_SCHEDULER=1 uvicorn app.main:app --port 8000 &
  ```
  `chmod +x ~/.termux/boot/cardpilot.sh` — the server (and the daily
  nudge/fare scheduler) now starts whenever the phone boots.
- **Updating:** `cd ~/CardPilot && git pull && (cd frontend && npm run build)`.
  Your SQLite DB is untouched by updates.

Tip: with the scheduler running on the phone plus `TELEGRAM_BOT_TOKEN` /
`TELEGRAM_CHAT_ID` set, expiry, milestone and fare-drop nudges arrive as
Telegram notifications — even if you never open the app.

## Option B — Server on your computer, app on the phone (same Wi-Fi)

Good when the phone is just a screen and the data lives on your laptop.

1. On the computer:
   ```bash
   (cd frontend && npm run build)
   cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. Find the computer's LAN IP (`ip addr` / `ipconfig`), then open
   `http://<laptop-ip>:8000` in Android Chrome and **Add to Home screen**.

**Honest limitation:** browsers treat plain-HTTP LAN IPs as insecure origins,
so the *service worker* (offline cache) won't register — the home-screen icon
and the full app work fine, but only while the server is reachable. If you
want full PWA behaviour over LAN, either use Option A, or enable
`chrome://flags/#unsafely-treat-insecure-origin-as-secure` for
`http://<laptop-ip>:8000` on the phone (developer-grade workaround), or put a
TLS reverse proxy (e.g. Caddy with a local CA, or Tailscale Serve) in front.

Also note: `--host 0.0.0.0` exposes the (unauthenticated, single-user) API to
your LAN. Do this only on a network you trust.

## Option C — Native wrapper (future)

The PWA can be wrapped into an installable APK with Capacitor or a Trusted Web
Activity when a Play-Store-style distribution is wanted. Not built yet — the
Termux path covers personal use without any packaging.
