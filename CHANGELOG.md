# Changelog

All notable changes to Healthcare Secure are documented here.
Versions follow [SemVer](https://semver.org/) (`MAJOR.MINOR.PATCH`).
Git tags and GitHub Releases use a `v` prefix (e.g. `v0.1.0`).

## [Unreleased]

## [0.1.0] - 2026-07-20

### Added

- Dual-root clinic app: FastAPI backend + Next.js / Capacitor frontend
- Patient lock by name + 10-digit phone (HMAC-blinded history)
- Doctor / staff roles, vitals entry, voice dictation, sign & seal PDF
- Document upload, timeline, and free native share (no Twilio)
- Simplified clinic UI copy for non-technical staff
