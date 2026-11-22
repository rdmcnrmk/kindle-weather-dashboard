# Device validation

Target: Kindle Paperwhite 3 (2015), firmware 5.16.2.1.1, KOReader v2026.07.1.
The installed model/runtime were read from the device during development.

## Current evidence

On 2026-11-22 the user reported that robot control was working after the 1.2.12
protocol changes. This is a user-reported end-to-end result, not an independently
observed test of every button. The inspected robot identifier was
`dreame.vacuum.r9445d`.

Earlier USB inspection confirmed the installed payload matched the project,
`wifi_disable_action` was `leave_on`, and both session and robot requests returned
HTTP 200 with Wi-Fi on before and after. The user subsequently reported cloud
code 80001. Version 1.2.12 aligned request IDs and property correlation keys with
the reference client. The successful report followed that update; it does not
isolate which difference caused the earlier failure. Detailed changes are in
[CHANGELOG.md](../CHANGELOG.md).

| Check | Evidence/status |
| --- | --- |
| English dates, Amsterdam DST, midnight and stale/missing forecasts | Automated Lua 5.1 tests |
| Layout geometry and Weather/Vacuum touch mapping | Local widget adapters and illustrative previews |
| Install, update, migration and rollback | Temporary fake-volume integration tests |
| Scoped native-screen handoff and failure cleanup | Shell tests with simulated LIPC |
| No automatic sleep without a wake manager | Power, startup and lifecycle regression tests |
| Five-minute idle deadline and login/network protection | Automated regression tests; exact physical timing pending |
| Manual wake reopens the last tab after screen-saver cleanup | Normal/delayed cleanup, cancellation and RTC-isolation tests; physical wake validation pending |
| Dreamehome login and robot control | User reported working after 1.2.12; no recorded per-button acceptance test |
| TLS peer/hostname verification, legacy DNS SAN matching | Automated acceptance/rejection tests; device HTTP exchanges observed |
| Request signatures, correlation keys, IDs and cloud/robot result codes | Synthetic protocol contract tests against the reference wire shape |
| No duplicate command after timeout or late callback | Automated regression tests |
| Keyboard visibility, exact password submission and region selection | Automated dialog-flow tests; no separate physical acceptance record |
| Full current-floor clean, Kitchen and Dining individually | Pending explicit per-target confirmation |
| Actual scheduled RTC wake and hourly unattended refresh on the current version | Pending controlled hardware validation |
| Multi-day battery runtime | Pending; do not advertise an estimate |

The 1.2.13 cleanup preserves the working protocol and UI behavior. Its automated
checks do not replace a new hardware acceptance test. No live robot commands are
sent by the test suite.

## Hardware acceptance

1. Quit KOReader and connect USB; run the update preflight, then update.
2. Safely eject and unplug; enable Wi-Fi and open Weather-Dashboard.
3. Confirm the screen renders, both tabs respond, and Check connection reads the
   robot status and shortcut availability without starting cleaning.
4. When cleaning is intended, test Kitchen, Dining and Clean all individually;
   confirm the selected rooms and cleaning mode in Dreamehome.
5. Verify that manual power-button sleep/wake returns to the last interactive tab
   and that inactivity permits sleep after the configured five-minute deadline.
6. For RTC validation, inspect the diagnostics for
   `first scheduled RTC wake observed; switching to hourly`. Then test a complete
   hour on battery before a longer unattended session.

Relevant device files are `koreader/crash.log`, `koreader/fridge-diagnostics.txt`,
`koreader/battery-log.txt`, and `hava-panosu-launch.log`. `DreameTransport` records
only request category, phase, elapsed time and Wi-Fi on/off. Do not commit raw
logs, account/session files or reader settings; record only observed results here.

Protocol references: Tasshack/dreame-vacuum `device.py` `_request_properties`,
`types.py` `TASK_STATUS`/`SHORTCUTS`, and `protocol.py` `send`, inspected 2026-11-22.
