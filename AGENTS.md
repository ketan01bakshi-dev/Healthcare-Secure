# Aarogya One Connect — agent notes

This repo is a dual-root clinic app: Python FastAPI in `backend/`, Next.js + Capacitor in `frontend/`. Production is a Hostinger Mumbai VPS (`docs/CLOUD_DEPLOY.md`). Do not treat LAN Wi‑Fi as the primary path.

## Build from Android (Chrome PWA)

There is no native Cursor Android app. Use the same Cloud Agents backend in Chrome:

1. Open [cursor.com/agents](https://cursor.com/agents) and sign in with the **same Cursor account** as this desktop.
2. Chrome menu → **Install app** / **Add to Home screen**.
3. Privacy Mode must be **Privacy Mode**, not Legacy. A paid plan is required to start runs.
4. Connect GitHub at [cursor.com/dashboard/integrations](https://cursor.com/dashboard/integrations) with access to `ketan01bakshi-dev/Healthcare-Secure`.
5. Create / refresh the cloud environment once at [cursor.com/dashboard/cloud-agents#environments](https://cursor.com/dashboard/cloud-agents#environments) (agent-driven setup). Dashboard secrets must be **demo only** — copy names from `backend/.env.example`, never from `backend/.env`.

| Goal | On the phone |
|------|----------------|
| New feature (PC can be off) | PWA → repo `Healthcare-Secure` → **Cloud** machine → describe the change → review the PR |
| Live debug of this PC / VPS | PWA → environment **healthcare-pc** (My Machines worker) |
| Continue a desk session | PWA inbox after `/remote-control` on desktop |
| Alternate trigger | GitHub issue → comment `@cursor` |

## Cursor Cloud specific instructions

Cloud Agents clone **GitHub**, not the dirty working tree on this Windows PC.

- Tests: `cd backend && WHISPER_PRELOAD=false python -m pytest -q`
- Frontend UI changes: `cd frontend && npm run lint`
- Do **not** SSH to Hostinger, rotate production PINs, or mutate the live VPS from a Cloud VM.
- Skip live STT/LLM unless dashboard secrets include `LLM_API_KEY` / Groq. Default install does **not** include `faster-whisper` or Ollama.
- Production-debug tasks (Lab Desk 403, CORS, QR pay, nginx) belong on **My Machines** (`healthcare-pc`), not Cloud.
- Never commit `.env`, APKs, keystores, or `.cursor/tmp_*` deploy scripts.

### Dashboard secrets (non-production)

Set these in the Cloud Agents Secrets tab if the agent must boot the API: `SECRET_KEY`, `SECRET_SALT`, demo `CLINIC_USERS`. Optional: Groq `LLM_API_KEY` / `WHISPER_API_KEY` for parser tests. Do not add Hostinger root passwords, live Razorpay keys, or clinic PINs.

## My Machines (live debug from Android)

On the Windows PC, keep a worker running while the machine is plugged in and awake:

```powershell
irm 'https://cursor.com/install?win32=true' | iex
agent login
agent worker start --name "healthcare-pc" --worker-dir "D:\Agents\Healthcare"
```

From the Android PWA, pick **healthcare-pc** in the environment dropdown. Tool calls run on this PC (local `.env`, Docker, Hostinger MCP). No inbound ports.

## Remote Control (desk → phone)

Use this when a local agent is already running and you leave the desk:

1. Cursor **3.9.8+**. Open the **Agents Window** (not the editor chat).
2. **Settings → Agents → Remote Control** on. Optionally enable **Keep this computer awake**.
3. In that agent input, run `/remote-control`, then send the next message.
4. The session appears in the Android PWA inbox. This PC must stay online — tool calls still run here.
