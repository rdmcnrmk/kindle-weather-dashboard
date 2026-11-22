# Working on Kindle Home Dashboard

Read README.md and docs/DEVICE-VALIDATION.md before changing device behavior.
The repository root is the self-contained project; the surrounding chat workspace
and its temporary files are not dependencies.

## Source and compatibility

- Device source lives under payload/. Keep code compatible with Lua 5.1 and
  BusyBox /bin/sh. No Python runtime is available on the Kindle.
- The supported device is Paperwhite 3 / firmware 5.16.2.1.1 / KOReader v2026.07.1.
  Do not claim support for other models without evidence.
- English UI is the default. Preserve the simple portrait layout and absence of
  a ticking clock. Fixed sunrise/sunset times and relative forecast hours are fine.
- Internal `hava-panosu-*` paths and the `weatherlockscreen` plugin identifier
  are intentional compatibility interfaces. Do not rename them without migration
  and rollback tests.
- Amsterdam date/DST handling is intentionally scoped; arbitrary timezone strings
  are not supported yet.

## Validation

```bash
source .venv/bin/activate
make test
make preview
make build
make check
```

If .venv does not exist, follow README.md to create it. Dependencies are declared
in requirements-dev.txt. Never add machine-specific /tmp or /Users paths.
Commit manifest.json with payload changes. Build outputs are ignored.

Power changes need regression coverage in tests/test_power.py,
tests/test_lifecycle.py and tests/test_launcher.py. Never automatically suspend
without a real wake manager. Never unload the native USB blanket component.
Native screensaver handoff must be scoped to the app session and restored on exit.

Automated tests and local preview adapters do not prove physical RTC wake,
real font metrics, or battery life. Record actual device results in
docs/DEVICE-VALIDATION.md, keeping unknown results explicitly pending.

## Data and releases

Do not add device backups, reader settings, books, diagnostic logs, credentials,
virtual environments, or KOReader runtime archives to Git or release packages.
Preserve upstream notices, AGPL source and font licenses. Use scripts/build.py
for release/source archives. A physical-device install begins with --dry-run.
