# Changelog

## 1.2.13 — 2026-11-22

- Rename the project and release archives to Kindle Home Dashboard
  (`kindle-home-dashboard`). Installed Kindle paths and session files remain
  compatible with existing installations.

- Refactor repeated control status, settings and client creation code into shared
  helpers; share shortcut-name decoding between checks and cleaning commands.
- Remove an unused local and a redundant sign-in status check. Expand the login
  and control flow for readability and use descriptive module-local names.
- Preserve request envelopes, IDs, signatures, UI text/layout, timing and error
  handling. No device migration or reauthentication is required.
- Record the user's successful robot-control report after 1.2.12 and consolidate
  the validation notes; individual cleaning targets and power behavior are not
  independently verified by that report.

## 1.2.12 — 2026-11-22

- Align robot property requests with Tasshack's reference wire format: small
  initial request IDs and separate property correlation keys (11 for task status,
  52 for shortcuts), retaining the robot ID in the outer RPC envelope.
- Read and validate task status before shortcut discovery in Check connection.
  Report a shortcut lookup failure separately from a successful basic robot read.
- Preserve the idle check before cleaning, validate echoed property addresses and
  never retry actions. Identify cloud code 80001 as an unacknowledged robot RPC.
- Physical success is still pending; these protocol differences have not been
  established as the cause of the user's 80001 replies.

## 1.2.11 — 2026-11-22

- Accept cloud envelope success codes 0 and 200, keeping robot property/action
  result checks separate. Explicit failure flags still reject the response.
- Replace generic Wi-Fi/region advice with HTTP status or numeric service code;
  never echo server messages or response bodies. Diagnose missing response data.
- Actual device reply code and successful cleaning remain unverified.

## 1.2.10 — 2026-11-22

- Give Dreame operations 15 seconds per blocking operation with a 45-second
  request deadline enforced before each socket read/write and TLS handshake.
- Preserve the timed-out phase and log only operation type, phase, elapsed time
  and Wi-Fi on/off state; never log URLs, headers, response bodies or credentials.
- Skip post-request Wi-Fi teardown for interactive weather and robot controls.
  Existing sleep/idle handling remains responsible for panel power saving.

## 1.2.9 — 2026-11-22

- Distinguish HTTP send failures, closure before any reply, interrupted replies
  and timeouts. Identify session refresh versus robot reads versus cleaning actions.
- Preserve no automatic retries: an interrupted reply cannot establish whether
  the server accepted a cleaning action. The reported device failure remains under diagnosis.

## 1.2.8 — 2026-11-22

- Reopen the interactive dashboard after manual wake in panel mode, using cached
  weather immediately and preserving the selected tab. Wait for delayed sleep-screen
  cleanup; cancel pending opens on suspend/exit. Keep RTC refresh separate.
- Add Check connection to the Vacuum page: a read-only shortcut availability
  check. Retain the last command/check result on the page after popups disappear.

## 1.2.7 — 2026-11-22

- Replace the fixed 20-second boot sleep and unconditional battery watchdog
  sleep with a five-minute inactivity deadline. Dashboard taps, manual wake,
  login edits and dialog opening reset the deadline.
- Keep the inactivity deadline independent of short network leases so finishing
  a login/request does not immediately re-enable sleep. Recheck before suspend.
- Set the reader's scoped auto-suspend timeout to the same configurable idle
  period. Preserve manual sleep and the requirement for a real RTC wake manager.

## 1.2.6 — 2026-11-22

- Fix a robot-selection callback crash: resolve the session store in the device
  picker's scope. Keep selection open if saving fails, and repaint after success.
- Keep login, region, robot selection and feedback windows modal above the
  dashboard. Add regression coverage for selecting and saving an actual list item.

## 1.2.5 — 2026-11-22

- Include L50 Pro Ultra model identifiers r9445d/r9445g alongside r9445a using
  the upstream integration's supported-device list; hardware validation is pending.
- Separate empty/shared-account discovery, unsupported identifiers and missing
  routing information. Show only non-sensitive model identifiers in diagnostics.
- Add Find Dreamehome robot to reuse the saved session without retyping a password.

## 1.2.4 — 2026-11-22

- Add a DNS subjectAltName verifier for older LuaSec builds without checkhost().
  Keep peer-chain verification enabled and check names before sending credentials.
- Reject missing/mismatched SANs, partial or multi-label wildcards, invalid DNS
  names and native verification failures. Never fall back to a certificate CN.

## 1.2.3 — 2026-11-22

- Protect login entry and on-demand cloud requests from the panel's Wi-Fi
  cutoff and automatic-sleep watchdog using an expiring in-memory interaction lease.
- Distinguish TCP/network, TLS handshake/verification, HTTP sign-in rejection,
  rate limit and unexpected protocol responses without exposing server secrets.

## 1.2.2 — 2026-11-22

- Replace the crowded three-field login form with separate fullscreen Email and
  Password steps that reserve space for the keyboard. Password includes
  KOReader's Show password checkbox; Back returns to email without retaining it.
- Select account region from a labeled list and repaint the complete form when
  opening each step. Keep passwords unchanged, including spaces.

## 1.2.1 — 2026-11-22

- Fix tab switching: mark dashboard windows for repaint before the e-ink refresh.
  Previously the selected page changed in memory while the old pixels stayed up.
- Show tabs only on the interactive dashboard. The sleep screen now explicitly
  identifies itself and explains how to reach controls after waking.
- Add regression coverage for visible repaint and rejection of sleep-screen taps.

## 1.2.0 — 2026-11-22 (experimental robot controls)

- Add direct, on-demand Dreamehome login and token refresh with no bridge server.
- Add Weather/Vacuum tabs with large Clean all, Kitchen and Dining buttons on a
  dedicated Vacuum page, plus menu controls. Keep navigation extensible.
- Use named Dreamehome shortcuts for room cleaning and their saved settings.
- Keep account tokens outside the payload; never save the login password.
- Verify TLS peer/hostname, reject unknown models and busy robots, and never
  automatically retry cleaning commands. Physical-device validation is pending.

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
