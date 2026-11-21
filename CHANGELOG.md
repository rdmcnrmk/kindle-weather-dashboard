# Changelog

## 1.1.0 — 2026-11-21

- Translate dashboard labels, dates, conditions, summaries, menus, warnings,
  launcher messages and installation tools to English.
- Add Weather-Dashboard and Stop-Weather-Dashboard launchers, with migration and
  rollback for the previous Turkish names.
- Extract a self-contained Git project with declared development dependencies,
  build commands, CI, architecture notes and Codex handoff context.
- Add deterministic device/source ZIP builds and manifest verification.
- Keep the existing scoped native-screen handoff and fail-safe RTC checks.

## 1.0.2 — local prototype

- Scope native ad_screensaver handoff to the running application and restore it
  on exit. Never alter the USB blanket component.
- Skip automatic sleep when a wake manager is unavailable; report diagnostics.
- Show the first dashboard before sleeping; test the first scheduled RTC wake
  after two minutes and then return to hourly scheduling.
- Add update/rollback chaining and lifecycle/launcher regression tests.

## 1.0.0 — local prototype

- Add the portrait weather layout, Open-Meteo data/cache, Amsterdam date handling,
  rain probabilities, gusts, sunset, three-day outlook and a local installer.
