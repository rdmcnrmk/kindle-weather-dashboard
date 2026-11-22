# Direct Dreamehome controls — experimental

The Kindle itself logs in and sends requests to Dreamehome's cloud. There is no
server to deploy and no background MQTT connection, polling or robot discovery.
An internet connection is necessary when connecting or sending commands. The
implementation uses an unofficial community protocol and may need updates if
Dreame changes its service. No real account or physical robot has been tested.

## Setup

1. In Dreamehome, create a cleaning shortcut named **Kitchen** containing only
   the kitchen and one named **Dining** containing only the dining area. Select
   suction, repeats and mop settings there. Names are matched without regard to
   letter case. Keep each name unique. They must be robot cleaning shortcuts,
   not a schedule or an external voice-assistant routine.
2. Quit KOReader, connect USB, run `python3 install.py --update --dry-run`, inspect
   the result, then run `python3 install.py --update`. Eject and unplug.
3. Open KOReader's **Weather Dashboard → Connect Dreamehome** menu. Enter the
   email in the large **Email address — Step 1 of 2** box. Use **Region: EU** to
   select the cloud region (`eu`, `us`, `cn`, `sg`, or `ru`), then **Next**.
   Enter the password in **Password — Step 2 of 2**. Use **Show password** to
   check it, **Back** to correct the email, or **Connect** to sign in.
   The region must match the existing app account; it is not inferred from GPS.
   Apple/Google-only sign-in, captcha and additional verification are not implemented.
4. Select the robot from your account. The L50 Pro Ultra identifiers
   `dreame.vacuum.r9445a`, `dreame.vacuum.r9445d` and `dreame.vacuum.r9445g` are
   allowed based on the upstream community model list. If your device has a
   different identifier, leave it disabled until its protocol mapping is checked.
   Discovery errors show the model identifiers, without account/device IDs. An
   empty list means no visible robot on that account/region: accept the share
   invitation in the second account and confirm the robot appears in Dreamehome.
   Use **Weather Dashboard → Find Dreamehome robot** to retry discovery with the
   saved session; you do not need to enter the password again.
5. Open the **Vacuum** tab at the top of the awake dashboard. Three large buttons
   appear in a vertical stack. They also remain accessible via
   **Weather Dashboard → Robot controls** after waking. Without an account, the
   Vacuum tab shows a **Connect Dreamehome** button and disabled cleaning buttons.
6. Tap **Check connection** first. It reads the robot task status, then the
   shortcut list without starting cleaning, and reports whether **Kitchen** and
   **Dining** are present. A failed shortcut lookup is reported separately when
   the basic robot read succeeded. The latest
   result stays below the button.
7. Test **Kitchen** first and confirm the intended room and mode in Dreamehome.
   Then test **Dining**, then **Clean all**. These tests start real cleaning.

**Clean all** starts a full clean on the current map with the robot's current
cleaning settings. It does not clean every floor of a multi-floor home.
Kitchen/Dining launch the corresponding saved shortcut with its existing settings.
The client checks that the robot has completed its previous task before sending
a command. It refuses busy or unknown states; stop/finish a task in Dreamehome.
Pause, return-to-dock and live progress are outside this first version.

## Sleep and reliability

The sleep screen shows weather with a sleep label and wake instructions instead
of tabs. Touch input is inactive during deep sleep.
With panel mode enabled, the power button reopens the interactive dashboard on
the last selected tab after KOReader removes its sleep screen. Cached weather
appears without waiting for Wi-Fi. Scheduled RTC wakes keep their unattended
weather refresh behavior. With panel mode disabled, KOReader resumes normally.
Switching tabs does not fetch forecasts, log in or send robot commands. The awake
dashboard preserves its selected tab across forecast refreshes. Tap the Weather
page outside the tab bar to return to the reader. Adding a tab to the shared
`dashboard_tabs.lua` registry automatically resizes the navigation; new page
content and actions can then be implemented separately.
The hourly weather wake never logs in or starts the robot. The existing weather
power path is unchanged; scheduled RTC wake remains unverified on hardware.

Requests use TLS with peer and hostname checks, a bundled public CA set and
bounded socket/response handling (15-second blocking operations and a 45-second
request deadline, apart from platform DNS resolution). Credential-free
`DreameTransport` lines in `koreader/crash.log` record request category, transport
phase, elapsed seconds and Wi-Fi on/off before and after the request. LuaSec builds without `certificate:checkhost()`
use the certificate's DNS subjectAltName extension instead, accepting exact names
or a wildcard covering exactly one complete DNS label. There is no Common Name
fallback. A missing/mismatched SAN, unavailable certificate API, failed native
check or failed TLS handshake blocks the connection before credentials are sent. A native
Kindle connection test is essential; desktop adapters do not prove compatibility.
The UI may block briefly during requests; DNS delays can exceed socket timeouts.

There is one cleaning action per press and no automatic retry. After a timeout,
check Dreamehome before tapping again: a robot may receive a command even when
its acknowledgement is lost. A success message means acknowledgement, not
physical verification that the robot started moving or cleaned the right area.
Expired sessions refresh on the next request. A rejected session may require
**Connect Dreamehome** again; passwords are not retained for fallback login.

While entering credentials, the panel's Wi-Fi cutoff and automatic-sleep watchdog
are paused by an in-memory five-minute lease, renewed by edits and step changes.
Cloud requests use a two-minute lease, released on completion/failure. An abandoned
form expires automatically; no permanent power setting is changed. Manual power
button sleep remains available. Sign-in errors distinguish no HTTP reply/TCP,
TLS failure, HTTP rejection, rate limits and an unexpected protocol response.
An HTTP rejection alone does not prove an incorrect password: account verification
or region can also matter. Raw server responses and transport errors are not shown.

## Account data

Enter credentials directly on the Kindle. Do not send them in chat or add them to
source code. The password is used in memory for login and is not saved. Refresh
and access tokens, account email, region and selected robot are saved in
KOReader's settings directory as `dreamehome-session.json`, outside the payload.
Tokens grant account access. Kindle USB storage is not encrypted and FAT may not
enforce private permissions. Keep this file out of device backups you share.
Client code does not log credentials, tokens or raw server replies.

**Disconnect Dreamehome** deletes local session files and disables cleaning on
the next repaint. It does not revoke tokens on Dreame's servers. Removing the
plugin alone does not remove its session; disconnect before uninstalling.

## Upstream references

- Protocol, login, signing and cloud envelope:
  https://github.com/Tasshack/dreame-vacuum/blob/master/custom_components/dreame_vacuum/dreame/protocol.py
- Shortcut parsing and start-custom command:
  https://github.com/Tasshack/dreame-vacuum/blob/master/custom_components/dreame_vacuum/dreame/device.py
- Property/action mapping:
  https://github.com/Tasshack/dreame-vacuum/blob/master/custom_components/dreame_vacuum/dreame/types.py
- L50 Pro Ultra variant identifiers:
  https://dv.tasshack.com/guide/more/supported-devices

The adapted protocol carries Tasshack's MIT notice in `DREAME-LICENSE.txt`.
The public Mozilla CA set comes from certifi, retrieved 2026-11-22:
https://github.com/certifi/python-certifi/blob/master/certifi/cacert.pem
Its notice is in `CERTIFI-LICENSE.txt`; update the CA set from that upstream when
necessary, keeping the notice and testing TLS behavior. No user secrets are bundled.
