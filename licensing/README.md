# Online licensing server

The temporary backend targets the existing ASP.NET Framework 4.6 / SQL Server
host. It is a standalone handler; do not replace TV-Watermark's DLL, Web.config,
Square settings, routes or account tables. All new rows live in
`dbo.spankvanc_licenses` and `dbo.spankvanc_license_activations`.

## Deployment

1. Back up the existing protected site configuration privately.
2. Execute `gearhost/schema.sql` against the existing SQL database. It is an
   additive migration and can be rerun. Review an existing table of the same
   name before applying it to a different environment.
3. Upload only `gearhost/spankvanc-license.ashx` to the site's web root over
   encrypted publishing. It uses the existing `TvRewards` SQL connection-string
   entry. Never upload a connection string or database credential from this repo.
4. Require valid HTTPS. POST JSON to the handler with `action`, `key`, and a
   64-character lowercase hexadecimal random `installation`. Keys use `SV1-`
   followed by 43 URL-safe characters. GET and plain HTTP do not activate keys.
5. Verify an isolated test key: first activation, repeated activation with the
   same expiry, wrong installation, expired key, revoked key, and simultaneous
   first activation from two identifiers. Confirm existing site health afterward.
6. Point a future host at the same data or migrate the rows with their original
   timestamps. `SPANKVANC_LICENSE_SERVER` selects an alternate HTTPS endpoint
   for a managed deployment. Restart clients after changing it.

First activation takes a serializable transaction and locks the key row. It
sets `activated_at` once and `expires_at=activated_at+2592000`. SQL Server UTC
is authoritative. `check` never activates an unused key. Expired/revoked keys
cannot restart their window. Keys are random 256-bit secrets; only their hashes
are stored. The endpoint has no issuance/admin API. Add hosting request limits
and monitoring appropriate to wider public use; this is a temporary low-volume
shared-host deployment, not a dedicated high-availability licensing service.

Implementation references: [ASP.NET IHttpHandler](https://learn.microsoft.com/en-us/dotnet/api/system.web.ihttphandler?view=netframework-4.8.1)
and [SQL Server transaction locking hints](https://learn.microsoft.com/en-us/sql/t-sql/queries/hints-transact-sql-table).

## Issue a key privately

From the source checkout, using a private output folder outside this project:

```bash
python3 tools/license_operator.py --label "Customer reference" --output-prefix /private/operator/customer-license-private
```

This creates owner-readable `.json` (the key) and `.sql` (an INSERT containing
only its hash). Existing output files are not overwritten. Import the SQL using
your protected SQL connection. Deliver the key to its intended recipient through
a private channel. Issuance does not start the 30-day period. Keep the JSON out
of source control, app packages, screenshots, and logs. Back up the SQL database
and operator records privately.

To revoke a key, take `key_hash` from the private JSON and run a parameterized
SQL update setting `revoked=1` for that exact hash. Do not send the raw key in a
URL. Clients stop on their next check, normally within a minute. To renew, issue
a new key instead of changing an old activation/expiry timestamp.

For a lost installation file, the operator can inspect the private SQL row and
recover the known installation file from backup. A binding transfer requires an
explicit support decision; preserve activation and expiry and revoke the old
installation before transferring. No automatic reset endpoint is provided.

## Shared public tester keys (compatible with the 0.10.0 app)

Use `--shared` when running `tools/license_operator.py` to issue a key intended
for public testers. Import its SQL after applying the current additive schema.
Do not convert an existing private/owner key to public use.

The parent key's `shared` flag is false by default, preserving private key
behavior. For shared keys, activation dates live in a separate table keyed by
key hash and installation hash. Each installation receives 30 days from its
own first activation; re-entry and concurrent retries preserve that expiry.
One tester's expiry does not affect others. Setting the parent's `revoked=1`
blocks both new activations and checks by every existing installation.

There is no global enrollment deadline by default: the key accepts new testers
until revoked. This is a temporary, openly shared trial. Installation identity
is random per-user saved state, not a hardware fingerprint; deleting that state
can create a new identity. Do not present this as tamper-proof trial enforcement.
The existing 0.10.0 app works without an update; no key is embedded in it.
