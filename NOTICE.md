# Sources and changes

This package contains a modified copy of Kindle Weather Station v1.1.0:
https://github.com/muffism/kindle-weather-station/releases/tag/v1.1.0
Upstream release SHA-256: d8beed4e52301c8176299faa73520b950156489dee96dd67ae50f90a6b6bed04
That project extends WeatherLockscreen v1.1.0 by Andreas Lösel:
https://github.com/loeffner/WeatherLockscreen
License: GNU Affero General Public License v3.0, preserved in LICENSE and in the plugin.

Modifications, 2026-11-21:
- Replaced the Week layout with the user's approved Turkish portrait layout.
- Added an Open-Meteo-only provider, validated/atomic cache, no-data/stale states.
- Removed the bundled default WeatherAPI credential and disabled provider fallback.
- Added a pure date/forecast model, Amsterdam DST arithmetic, midnight/date selection,
  hourly rain probabilities, wind gusts, three future days, and a weather summary.
- Aligned refresh scheduling to hourly boundaries; retained upstream RTC/power integration.
- Scoped the startup patch to an explicit user-selected mode, preserved/restored
  KOReader preferences, disabled Wi-Fi before suspend, added Turkish menu/launchers.
- Added a local installer with integrity checks, backup, rollback and tests.

All corresponding modified application source code is included under payload/,
with tests under tests/. Our additions use AGPL-3.0-or-later.
Inter fonts retain their SIL Open Font License: payload/koreader/fonts/inter/OFL.txt.
Open-Meteo weather data: https://open-meteo.com/ — CC BY 4.0.
KOReader is not part of the small distribution archive. It is a separately
installed dependency, verified on the device as v2026.07.1:
https://github.com/koreader/koreader/releases/tag/v2026.07.1
No new Kindle firmware, root filesystem modification or boot job is installed.

English project 1.1.0, 2026-11-21:
- Translated the active dashboard, weather/date labels, menus and diagnostics to English.
- Added English launchers with migration and rollback for the Turkish entries.
- Added a self-contained development project, pinned dependencies, GitHub CI,
  deterministic build/source packaging and Codex working context.
- Retained internal state-file names for upgrades and kept device backups private.

Hotfix 1.0.2, 2026-11-21:
- Added a temporary, reversible blanket ad_screensaver handoff in the launcher.
  Reference: https://github.com/sgoeds/Kindle-Screensaver-Settings
- Never automatically suspend without a successfully initialized wakeup manager.
- Show the initial dashboard before sleeping; write explicit power diagnostics.
- Run a one-time 120-second RTC smoke test, then use hourly scheduling.
- Added update/rollback chaining and lifecycle/launcher regression tests.
