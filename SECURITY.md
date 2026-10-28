# Security and credentials

The service binds to loopback and uses a per-process control token. Keep it on
the workstation; do not expose the port directly to a LAN or the Internet.
Anyone with access to the local account can read its saved routes and stream
keys. Network destination URLs are redacted in engine logs/command previews,
but runtime/route.json contains real settings.

Keep runtime/, settings.json, diagnostics, captured media and credentials out
of GitHub. Use fake keys in test cases. If a real key was shared, rotate it with
the streaming provider. Do not paste tokens into public issues.

Report security concerns through the repository's private vulnerability reporting
feature if enabled; otherwise contact the owner privately through their listed
GitHub contact route. Public issues are appropriate for sanitized functional
bugs, not credentials or exploit details affecting live systems.
