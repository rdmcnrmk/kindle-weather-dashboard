# Device validation

Target: Kindle Paperwhite 3 (2015), firmware 5.16.2.1.1, KOReader v2026.07.1.
The installed model/runtime were read from the device during development.

| Check | Evidence/status |
| --- | --- |
| English dates, DST, midnight transitions | Automated Lua 5.1 tests |
| Missing/outdated forecast and cache | Automated model/source tests |
| Layout geometry | Local KOReader-widget adapters with Pillow/Resvg |
| Install, update, migration and rollback | Temporary fake-volume integration tests |
| Scoped native-screen handoff and failure cleanup | Shell integration tests with simulated LIPC |
| No automatic sleep without a wake manager | Startup/lifecycle regression test |
| Actual English screen on Paperwhite 3 | Pending after 1.1.0 installation |
| Actual scheduled RTC wake after the handoff fix | Pending; no post-fix result has been collected |
| Hourly unattended refresh | Pending |
| Multi-day battery runtime | Pending; do not advertise an estimate |

The original prototype's log showed that a wake manager was unavailable while the
startup patch still sent the device to sleep. That automatic-sleep bug was fixed.
A scoped native-screen handoff was then added because KOReader's Kindle wake setup
depends on sleep-screen ownership. This remains a hypothesis requiring the new
native module and power diagnostics on the physical device.

## Next hardware session

1. Quit KOReader and connect USB; run the update preflight, then update.
2. Safely eject and unplug; enable Wi-Fi and open Weather-Dashboard.
3. Confirm the English screen renders and the power button responds.
4. Leave it untouched for at least three minutes to observe the short RTC test.
5. Reconnect USB and inspect the diagnostic files locally. Look for
   `first scheduled RTC wake observed; switching to hourly` in crash.log.
6. If successful, test a full hour on battery, then a longer battery session.

Relevant files are koreader/crash.log, koreader/fridge-diagnostics.txt,
koreader/battery-log.txt, and hava-panosu-launch.log. Do not commit raw device logs
or reader settings. Record only the relevant observed result in this document.
