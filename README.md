# Healthcare-Secure

A security-focused patient records demo. It pairs a hardened Express + SQLite
API with a React (Vite) frontend so clinicians can register, sign in, and manage
patient records.

## Stack

| Layer    | Technology                                                        |
| -------- | ----------------------------------------------------------------- |
| Backend  | Node.js, Express, better-sqlite3, JWT auth, bcrypt, Helmet, rate limiting |
| Frontend | React 18, Vite, TypeScript                                        |
| Tooling  | npm workspaces, Node's built-in test runner                       |

## Security features

- Password hashing with bcrypt (configurable cost factor).
- Stateless JWT authentication with route-level role checks (`admin` / `clinician`).
- Input validation with `zod` on every write endpoint.
- `helmet` security headers, JSON body-size limits, and per-route rate limiting.
- Refuses to boot in production without a `JWT_SECRET`.
- Lightweight audit log of auth and record events.

## Prerequisites

- Node.js >= 20 (repo is developed on Node 22)
- npm >= 10

## Getting started

```bash
npm install          # installs server + client workspaces
npm run seed         # creates the default admin account
npm run dev:server   # API on http://localhost:3001
npm run dev:client   # web app on http://localhost:5173
```

The Vite dev server proxies `/api/*` to the backend on port 3001.

### Default seeded account

| Email                    | Password       | Role  |
| ------------------------ | -------------- | ----- |
| `admin@healthcare.local` | `ChangeMe123!` | admin |

Override with `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` before running the seed.

## API overview

| Method | Path                 | Auth        | Description                    |
| ------ | -------------------- | ----------- | ------------------------------ |
| GET    | `/api/health`        | none        | Liveness probe                 |
| POST   | `/api/auth/register` | none        | Create an account, returns JWT |
| POST   | `/api/auth/login`    | none        | Authenticate, returns JWT      |
| GET    | `/api/patients`      | Bearer      | List patient records          |
| GET    | `/api/patients/:id`  | Bearer      | Fetch one patient record       |
| POST   | `/api/patients`      | Bearer      | Create a patient record        |
| DELETE | `/api/patients/:id`  | Bearer admin| Delete a patient record        |

## Testing

```bash
npm test             # runs the server API test suite (node:test)
```

## Configuration

See `server/.env.example`. Notable variables:

- `JWT_SECRET` — required in production.
- `PORT` / `HOST` — API bind address (defaults to `3001` / `0.0.0.0`).
- `DATABASE_PATH` — SQLite file location (defaults to `server/data/healthcare.db`).
- `BCRYPT_ROUNDS` — bcrypt cost factor (default `12`).
