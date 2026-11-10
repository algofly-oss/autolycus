# Storage relocation and persistent sign-in

The active repository, distribution archive and application data are on the SSD:
`/mnt/WD512/autolycus`, with `/data` bound to its `volumes/single` directory.
Downloaded media stays on the 8 TB HDD at
`/mnt/WD8TB/autolycus/volumes/downloads`, mounted as `/downloads`.
The HDD ext4 filesystem UUID is `cee81b24-57da-417f-9be0-fd50d8ff8a0f`.
Docker's shared image/build cache remains in its existing system-managed location.

This supersedes the earlier all-HDD relocation at the user's request. The HDD
repository/state copy remains a rollback backup, with `ACTIVE_LOCATION.txt`
pointing to the SSD installation. Media was not copied back to the SSD. The
cutover used a stopped final sync and verified account, torrent and session
identities. The existing-data guard refuses to start an empty application state
when `AUTOLYCUS_REQUIRE_EXISTING_DATA=1` is configured.

## Drive capacity

Previously, three separate implementations scanned each user's files and
reported a per-user virtual capacity. They counted hard-linked copies more than
once, which could show values such as 607/753 GB on a physically smaller SSD.

All storage responses come from `shared.modules.storage_usage`. The navbar
ring and the hover percentage show **drive occupied / total drive capacity**.
The hover lists drive used, total, and free space, plus Autolycus usage as a
separate row. There is no adjusted application capacity or per-user quota.
Every account sees the same drive figures.

Drive statistics come from the downloads filesystem. Autolycus usage includes
repository, service data and downloads on that drive, deduplicated by allocated
device/inode blocks so hard links and overlapping mounts count once. That app
footprint is sampled every 60 seconds outside request and progress paths; the UI
refreshes every 30 seconds. No filesystem scan runs just to display a hover.

## HomeSense comparison and chosen policy

The running HomeSense installation was inspected without changing it. Its
configuration uses `session_days=30`. Its auth routes issue HttpOnly,
SameSite=Lax persistent cookies, backed by durable server-side sessions; session
validation renews the server lifetime while in use.

The user explicitly chose the same **30-day rolling duration** for Autolycus.
Every authenticated HTTP access renews the cookie and Redis TTL. MongoDB expiry
is checkpointed hourly, with a matching recovery allowance, to avoid a database
write on every polling request. Redis cache loss can recover an active session
from MongoDB; revoked or expired records cannot recover. No password or session
token is stored in frontend localStorage.

The old session-only cookies had no Max-Age or Expires. Sign-in also raced an
unawaited sign-out, and network errors could incorrectly send the UI to login.
Those paths are corrected. Auth responses are marked no-store and all API
requests bypass service-worker caching. An installed app can close and reopen
with its persistent cookie, while a temporary network failure leaves its login
intact. Explicit logout, device revocation, browser-data deletion or more than
30 days without access requires another sign-in.

If an old Safari home-screen installation has already discarded its former
session-only cookie, sign in once inside that installed app after deployment.
The new cookie can then persist normally. Automated browser tests cover browser
process close/reopen and simulated auth-network failure; they do not constitute
a test on a physical iPhone.

## Verification

Eleven unit tests cover shared application usage, hard-link deduplication,
concurrent snapshot refresh, persistent cookie attributes,
cache recovery, expiry/revocation, hourly checkpoints, rolling renewal and
returning just before the inactivity limit. The isolated full-stack test covers
fresh-account storage over HTTP and Socket.IO, durable-session recovery, cookie
renewal, credential verification, logout, browser close/reopen and transient
network failures, alongside the existing application workflows. The installation
also refuses to initialize a blank database if its required existing data mount
is absent.

The completed relocation's exact mount paths and identity checks are recorded in
`relocation-validation.json` (local-only, excluded from Git) beside this document.
