# Healthcare Secure Application

Production-oriented dual-root layout for a secure healthcare web app.

```
Healthcare/
├── backend/          # Python FastAPI API
└── frontend/         # Next.js App Router + Tailwind + TypeScript
```

## Backend

```cmd
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Default transcription is **local CPU Whisper** (`faster-whisper`, `tiny.en`) — no API key. Keep clips short (5–15 s).

Clinical parsing defaults to **Ollama** (fully free, local):

```cmd
winget install Ollama.Ollama
ollama pull llama3.2
ollama serve
```

```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
LLM_API_KEY=ollama
```

Optional cloud: `LLM_PROVIDER=openai` or `groq` with `LLM_API_KEY`. Optional cloud Whisper via `WHISPER_PROVIDER=openai`.

## Frontend

```cmd
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

CORS allows `http://localhost:3000` and `http://127.0.0.1:3000` by default.

### Clinical workflow (dashboard)

1. **Lock patient** — enter patient name → HMAC-encoded blind ID (name never stored in DB).
2. **Record** one or more voice segments → session transcript list.
3. **Write prescription** — consolidates transcripts → LLM parse → PDF → saves history → share sheet / copy link.
4. **Upload** scanned prescriptions or diagnostic reports against the same patient.
5. **Timeline** auto-loads for the locked patient (visits + documents).

Requires Ollama (`LLM_PROVIDER=ollama`) for structured parse when writing a prescription.

Prescription PDFs use a clinic letterhead template (clinic name + doctor seal) and auto-stamp local date/time (`PRESCRIPTION_TIMEZONE`, default `Asia/Kolkata`). Optional images: `backend/app/assets/doctor_seal.png`, `letterhead.png`.


### Phone setup (same Wi‑Fi as this PC)

Your laptop LAN IP is used so the phone can reach the API. Example: `192.168.1.19`.

**1. Backend — bind to all interfaces + restart**

```cmd
cd backend
.\.venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In `backend/.env` (already set for `192.168.1.19` on this machine):

- `ALLOWED_HOSTS` includes your LAN IP
- `CORS_ORIGINS` includes `http://YOUR_LAN_IP:3000` and Capacitor origins
- `PUBLIC_API_BASE_URL=http://YOUR_LAN_IP:8000`

Allow Windows Firewall inbound TCP **8000** (and **3000** if using the phone browser).

**2a. Quick test — phone browser**

```cmd
cd frontend
REM .env.local → NEXT_PUBLIC_API_BASE_URL=http://YOUR_LAN_IP:8000
npm run dev -- -H 0.0.0.0 -p 3000
```

On the phone open `http://YOUR_LAN_IP:3000`.

**2b. Capacitor Android app**

```cmd
cd frontend
npm run mobile:build
npm run cap:open:android
```

In Android Studio: Run on a USB device or emulator. Allow microphone when prompted.

`NEXT_PUBLIC_API_BASE_URL` is baked in at **build** time — change `.env.local`, then `npm run mobile:build` again after IP changes.

| Script | What it does |
|--------|----------------|
| `mobile:build` | `next build` → `out/` then `cap sync` |
| `cap:open:android` | Open the Android project (prefers registry Studio path) |
| `mobile:android` | Build + sync + open IDE |

Prescription delivery uses the **Web Share API** (native share sheet / SMS) — no Twilio. Desktop falls back to copy-to-clipboard.

### Native mic

- **Android:** `RECORD_AUDIO` + cleartext HTTP for the LAN API (dev)
- **iOS:** needs a Mac; set `NSMicrophoneUsageDescription` in `Info.plist`

## Releases (GitHub-style)

Versions are maintained on GitHub:
[ketan01bakshi-dev/Healthcare-Secure](https://github.com/ketan01bakshi-dev/Healthcare-Secure)
([Releases](https://github.com/ketan01bakshi-dev/Healthcare-Secure/releases)).

Tag a commit → publish a Release with notes. Keep the same SemVer in two places:

| File | Field |
|------|--------|
| `frontend/package.json` | `"version"` |
| `backend/app/__init__.py` | `__version__` |

Check the running API: `GET http://127.0.0.1:8000/api/v1/health` → `{ "status": "healthy", "version": "0.1.0" }`.

### SemVer

| Change | Bump |
|--------|------|
| Bug fix / copy | patch (`0.1.0` → `0.1.1`) |
| New feature | minor (`0.1.1` → `0.2.0`) |
| Breaking clinic change | major (`0.2.0` → `1.0.0`) |

Tag format: `v` + SemVer (`v0.2.0`).

### Publish a release

1. Finish work on `main` (or merge your PR).
2. Move notes from `[Unreleased]` in `CHANGELOG.md` into a new `## [X.Y.Z] - YYYY-MM-DD` section.
3. Set `X.Y.Z` in `frontend/package.json` and `backend/app/__init__.py`.
4. Commit: `chore: release X.Y.Z`
5. Tag and push (from repo root, PowerShell or cmd):

```cmd
git tag v0.2.0
git push origin main --tags
```

6. Create the GitHub Release (pick one):

**GitHub UI (recommended if `gh` is not installed)**

Open [New release](https://github.com/ketan01bakshi-dev/Healthcare-Secure/releases/new), choose tag `v0.2.0`, paste the changelog section, and publish.

**CLI** (requires [GitHub CLI](https://cli.github.com/))

```cmd
gh release create v0.2.0 --repo ketan01bakshi-dev/Healthcare-Secure --title "v0.2.0" --notes "See CHANGELOG.md section [0.2.0]."
```

7. Deploy that build to the clinic: restart the API, then `cd frontend` → `npm run mobile:build` and install the APK. Optionally set Android Studio `versionName` to the same SemVer by hand.

### First release (`v0.1.0`)

Publish the baseline on [Healthcare-Secure](https://github.com/ketan01bakshi-dev/Healthcare-Secure):

```cmd
git tag v0.1.0
git push origin main --tags
```

Then open [New release](https://github.com/ketan01bakshi-dev/Healthcare-Secure/releases/new), select tag `v0.1.0`, title `v0.1.0`, and paste the `[0.1.0]` section from `CHANGELOG.md`.

Or with GitHub CLI:

```cmd
gh release create v0.1.0 --repo ketan01bakshi-dev/Healthcare-Secure --title "v0.1.0" --notes "Initial clinic release. See CHANGELOG.md."
```

No CI is required.
