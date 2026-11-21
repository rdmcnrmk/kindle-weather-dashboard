# Architecture

The Kindle fetches and renders weather locally. There is no server to deploy.
KOReader provides the display, fonts, Wi-Fi and Kindle power integration.

| Module | Responsibility |
| --- | --- |
| `fridge-run.sh` | Temporarily hand off the native sleep screen, run KOReader, restore on exit |
| `2-fridge-weather.lua` | Activate the dashboard mode, scope reader settings, coordinate initial display and sleep |
| `fridge_control.lua` | Preserve and restore reader preferences and the mode flag |
| `main.lua` | Register the menu and integrate the weather screen with KOReader lifecycle |
| `fridge_source.lua` | Query Open-Meteo, validate responses, write the cache atomically |
| `fridge_model.lua` | Pure dates, Amsterdam DST, hourly/daily selection and summary logic |
| `display_week.lua` | Render the English portrait layout using KOReader widgets |
| `fridge_power.lua` | Probe wake support, diagnose missing prerequisites, choose the first/hourly alarm |

## Lifecycle

The launcher checks the native blanket module list. If ad_screensaver is active,
it temporarily unloads that module before KOReader initializes. KOReader can then
own its sleep screen and initialize its power wake manager. An exit trap restores
the original native module, including when the child process fails.

The startup patch activates only when the dashboard flag exists. It saves reader
preferences once, applies dashboard settings, turns off the frontlight, and shows
the initial weather view. On battery, it then transitions into the weather sleep
screen. Automatic sleep is skipped if the wake manager is absent.

The first scheduled wake uses a short two-minute test. A real RTC resume marks
that test as observed, after which future alarms use hourly boundaries. During a
wake, the cached image can appear immediately while Wi-Fi reconnects. A fresh
forecast then replaces it before the device goes back to sleep. Retries are bounded.

This depends on physical Kindle behavior; local tests cannot validate the whole
power path. See DEVICE-VALIDATION.md.

## Data correctness

The API uses Unix timestamps, metric units and Europe/Amsterdam. The pure model
chooses dates and daily rows independently of the host process timezone. DST is
calculated for Amsterdam; the current configuration is not a global timezone API.

Cache identity includes coordinates/timezone. Missing rain probability is unknown,
not zero. A failed request preserves the last valid forecast, with an outdated
indicator after 90 minutes; data older than 48 hours is not shown as current.
The outlook is a deterministic summary of the forecast, not live radar.

## Packaging and installation

payload/ mirrors the device's paths. manifest.json records source hashes and the
version. scripts/build.py rebuilds that manifest and produces deterministic ZIPs.
install.py verifies the selected drive, jailbreak marker, payload hashes and free
space before writes. It backs up replaced files, verifies transfers, migrates
legacy launcher names and chains update records so rollback restores the prior
version. Existing KOReader, books and annotations remain outside the payload.
