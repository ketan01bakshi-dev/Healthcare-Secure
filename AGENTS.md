# Agent instructions — Aarogya One Connect

## Documentation model (required)

**All documentation** in this project must be produced using **Google Gemini** in Cursor.

Switch to Gemini before:

- Editing files under `docs/` or `deploy/www/`
- Writing marketing copy, DPA/privacy text, Play Store listings, release reports, demo scripts, or README prose
- Creating one-pagers, pricing pages, or handbooks

If you are not on Gemini, start a new Agent chat with **Google Gemini** selected.

Detailed rule: `.cursor/rules/documentation-gemini.mdc`

## Product context

- **Product:** Aarogya One Connect — clinic staff OPD software (Android + browser)
- **Market:** B2B clinics in India (gynae, GP, polyclinic)
- **Not:** consumer patient app, full hospital HIS

## Code vs docs

- Implementation (Python/TS/Android): any model unless user prefers otherwise
- Documentation and user-facing copy: **Gemini only**
