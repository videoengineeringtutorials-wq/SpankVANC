# 30-day online activation (0.10.0)

SpankVANC 0.10.0 requires a license key to run routes and source monitoring.
The local browser and activation form remain available while locked. Diagnostics
remain available to help troubleshoot installation. This gate is part of the
app; it does not change the FFmpeg executable or Blackmagic drivers.

## Activate or renew

1. Obtain an issued **SV1-…** key from the operator. A key is not included in
   the download. Do not post it to GitHub or attach it to a support issue.
2. Launch SpankVANC and open **http://127.0.0.1:8877** on that PC.
3. Under **Application license**, paste the key and click **Activate key**.
4. The server starts exactly **30 × 24 hours** on the first successful
   activation, binds it to this installation identifier, and returns the expiry.
   Re-entering the same key, restarting or reinstalling the app does not extend
   the server's existing expiry. The browser displays the expiry in local time.
5. Before expiry, obtain a new key. Entering a newly issued key starts its own
   30-day window immediately; unused time on an old key is not carried over.

Internet access is required on startup and before media starts. During use,
checks run every **60 seconds**, or sooner at the known expiry. There is no
long offline grace period. Expiry, revocation, or a failed online check stops
routes, caption recognition and standalone source monitoring. A check timeout
and process shutdown can add several seconds. After restoring connectivity,
click **Check license** and restart the route manually. Restoration never
restarts a stopped route automatically.

Keep this interruption behavior in mind when planning operational use. The
license is checked against server time; changing the PC's wall clock cannot
extend the validated window.

## Storage and privacy

- The key and random installation identifier stay in per-user `license.json`:
  Windows `%LOCALAPPDATA%\SpankVANC\license.json`; Linux
  `${XDG_DATA_HOME:-~/.local/share}/SpankVANC/license.json`.
- Keep that file private. It is separate from saved media routes and survives
  extraction of a new app ZIP. Do not delete it when upgrading. If it is lost,
  contact the operator to recover the existing installation binding without
  resetting activation/expiry. Do not copy it to other users or machines.
- HTTPS requests send only the key, random installation identifier and the
  action (`activate` or `check`). No stream key, saved route, audio, machine
  name, or broadcast recording is sent. The hosting provider can see normal
  connection metadata such as source IP addresses.
- The database stores SHA-256 hashes of the high-entropy key and installation
  identifier, an operator label, issuance/activation/expiry/last-check timestamps
  and revocation state. Raw license keys are not stored in SQL.
- The temporary endpoint uses the existing TV-Watermark hosting domain at
  `https://tvrewards.gear.host/spankvanc-license.ashx`. It has its own SQL table;
  it does not share TV-Watermark viewer/business credentials or account records.

## Operator setup and key issuance

See [server deployment and administration](https://github.com/videoengineeringtutorials-wq/SpankVANC/blob/main/licensing/README.md). Issuance and
revocation use private SQL access; there is no unauthenticated web key generator.
Never package issued keys, database settings, credentials or SQL backups. The
server endpoint URL itself is public and contains no credentials.

The existing MIT source license remains unchanged. Anyone with the public source
can modify it to remove these checks, and old ungated versions remain available.
The distributed app enforces this gate; it is not tamper-proof DRM or a change
to the permissions already granted by the source license. Editing the public
client or redirecting a modified build to a different server can bypass it.
