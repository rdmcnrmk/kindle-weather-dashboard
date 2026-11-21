# Installation and recovery

Python 3.11+ is used on the computer. KOReader is already required on the Kindle.
This repository does not include firmware or a KOReader runtime archive.

From the project folder:

```bash
python3 scripts/build.py
python3 install.py --update --dry-run
python3 install.py --update
```

For a new dashboard installation, omit --update. On Linux, use --target with the
actual mounted Kindle directory. Always quit KOReader before mounting USB, then
safely eject and unplug before starting the dashboard.

Open **Weather-Dashboard** in the Kindle library. The menu is **Tools → Weather
Dashboard**. You can show/hide the dashboard, refresh, enter the sleep screen, or
stop the dashboard and restore reading preferences. After a full device reboot,
open the launcher again; no boot job is installed by this project.

Before an update, the installer checks the prior installed-file hashes. It will
stop if you manually edited an installed file. Keep those edits and reconcile
them deliberately rather than bypassing the guard.

## Rollback

First select **Stop dashboard and return to reading**, then quit KOReader and
connect USB. Keep the computer-side device-backups/ directory.

```bash
python3 install.py --rollback
```

This restores the immediately previous version and its installation record.
User edits made after installation are preserved by stopping rather than deleting
them. Books and annotations are never part of the payload.

## Recovery

If the device appears unresponsive, try its power button once. A fully unresponsive
Kindle can be restarted by holding the power button for 40 seconds and releasing.
After restart, leave the dashboard closed and connect USB to retrieve diagnostics.
This is a restart, not a factory reset.

The app never automatically sleeps without a real wake manager. If the displayed
warning says wake is unavailable, collect the power diagnostic before assuming
that the device lacks hardware support. It may be a native-screen or LIPC setup issue.

With USB connected, the device does not exercise the battery sleep path. Scheduled
wake and battery validation require an unplugged test.
